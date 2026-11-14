"""Bounded Google Gemini API adapter (via OpenAI-compatible endpoint).

Uses standard library urllib for zero external dependencies and maximum reliability.
"""

import asyncio
import json
import re
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from pydantic import Field

from app.core.config import Settings
from app.shared.ai_errors import AIError


class GeminiSettings(Settings):
    gemini_timeout_seconds: float = Field(default=45, ge=1, le=120)
    gemini_max_input_tokens: int = Field(default=128000, ge=4000, le=1000000)
    gemini_max_output_tokens: int = Field(default=4096, ge=256, le=8192)


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class GeminiLanguageModel:
    is_external: bool = True
    is_local: bool = False

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.api_key = getattr(settings, "gemini_api_key", "")
        self.model = getattr(settings, "gemini_model", "gemini-3.5-flash") or "gemini-3.5-flash"
        self.limits = GeminiSettings(_env_file=None, **settings.model_dump())

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def generate(
        self, system: str, content: str, schema: dict, *, max_tokens: int | None = None
    ) -> str:
        if not self.configured:
            raise AIError("not_configured")
        output_limit = self.limits.gemini_max_output_tokens if max_tokens is None else max_tokens
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": content},
        ]
        return self.chat(messages, max_tokens=output_limit, response_schema=schema)

    def chat(
        self, messages: list[dict[str, str]], *, max_tokens: int = 4096, response_schema=None
    ) -> str:
        if not self.configured:
            raise AIError("not_configured")
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.3,
        }
        if response_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "response",
                    "schema": response_schema,
                },
            }
        url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        request = Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode(),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            deadline = monotonic() + self.limits.gemini_timeout_seconds
            with build_opener(NoRedirects()).open(
                request, timeout=self.limits.gemini_timeout_seconds
            ) as response:
                body = bytearray()
                while True:
                    if monotonic() > deadline:
                        raise AIError("timeout")
                    chunk = response.read1(min(8192, 131073 - len(body)))
                    if monotonic() > deadline:
                        raise AIError("timeout")
                    if not chunk:
                        break
                    body.extend(chunk)
                    if len(body) > 131072:
                        raise AIError("invalid_response")
            result = json.loads(body)
            choices = result.get("choices", [])
            if not choices:
                raise AIError("invalid_response")
            value = choices[0]["message"]["content"]
            if not isinstance(value, str):
                raise AIError("invalid_response")
            value = value.strip()
            if value.startswith("```json"):
                value = value[7:].strip()
            elif value.startswith("```"):
                value = value[3:].strip()
            if value.endswith("```"):
                value = value[:-3].strip()
            # Normalize response_version if tutor wire answer
            if '"response_version": "1.0"' in value or '"response_version":"1.0"' in value:
                value = re.sub(
                    r'"response_version"\s*:\s*"1\.0"',
                    '"response_version": "tutor-wire-1.0"',
                    value,
                )
            return value
        except HTTPError as exc:
            code = "quota" if exc.code == 429 else "provider_error"
            if exc.code in (401, 403):
                code = "credentials"
            elif exc.code == 503:
                code = "quota"
            raise AIError(code) from None
        except TimeoutError:
            raise AIError("timeout") from None
        except URLError as exc:
            code = "timeout" if isinstance(exc.reason, TimeoutError) else "provider_error"
            raise AIError(code) from None
        except OSError:
            raise AIError("provider_error") from None
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            raise AIError("invalid_response") from None

    async def complete(self, prompt: str, *, max_tokens: int) -> str:
        return await asyncio.to_thread(
            self.generate, "Return JSON only.", prompt, {"type": "object"}, max_tokens=max_tokens
        )
