"""Bounded Workers AI REST adapter. No retries, redirects, logging or fallback."""

import asyncio
import json
import re
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener

from pydantic import Field

from app.core.config import Settings
from app.shared.ai_errors import AIError


class CloudflareSettings(Settings):
    cloudflare_timeout_seconds: float = Field(default=45, ge=1, le=120)
    cloudflare_max_input_tokens: int = Field(default=12000, ge=4000, le=24000)
    cloudflare_max_output_tokens: int = Field(default=4096, ge=256, le=8192)
    cloudflare_max_calls_per_request: int = Field(default=1, ge=1, le=1)


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class CloudflareLanguageModel:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.model = settings.cloudflare_model
        self.limits = CloudflareSettings(_env_file=None, **settings.model_dump())

    @property
    def configured(self) -> bool:
        return bool(
            re.fullmatch(r"[a-fA-F0-9]{32}", self._settings.cloudflare_account_id)
            and self._settings.cloudflare_api_token.strip()
            and self.model.startswith("@cf/")
        )

    def generate(
        self, system: str, content: str, schema: dict, *, max_tokens: int | None = None
    ) -> str:
        if not self.configured:
            raise AIError("not_configured")
        output_limit = (
            self.limits.cloudflare_max_output_tokens if max_tokens is None else max_tokens
        )
        if not 1 <= output_limit <= self.limits.cloudflare_max_output_tokens:
            raise AIError("output_limit")
        payload = {
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            "response_format": {"type": "json_schema", "json_schema": schema},
            "max_tokens": output_limit,
            "temperature": 0,
            "stream": False,
        }
        # UTF-8 bytes conservatively bound tokens, including schema and framing.
        if len(json.dumps(payload, ensure_ascii=False).encode()) + 256 > (
            self.limits.cloudflare_max_input_tokens
        ):
            raise AIError("input_limit")
        url = (
            "https://api.cloudflare.com/client/v4/accounts/"
            f"{self._settings.cloudflare_account_id}/ai/run/{quote(self.model, safe='@/')}"
        )
        request = Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode(),
            headers={
                "Authorization": f"Bearer {self._settings.cloudflare_api_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            deadline = monotonic() + self.limits.cloudflare_timeout_seconds
            with build_opener(NoRedirects()).open(
                request, timeout=self.limits.cloudflare_timeout_seconds
            ) as response:
                body = bytearray()
                while True:
                    if monotonic() > deadline:
                        raise AIError("timeout")
                    # read1 avoids a single read waiting indefinitely for a trickling body.
                    chunk = response.read1(min(8192, 131073 - len(body)))
                    if monotonic() > deadline:
                        raise AIError("timeout")
                    if not chunk:
                        break
                    body.extend(chunk)
                    if len(body) > 131072:
                        raise AIError("invalid_response")
            result = json.loads(body)
            if result.get("success") is False:
                codes = {str(error.get("code")) for error in result.get("errors", [])}
                raise AIError("quota" if codes & {"3036", "3040"} else "provider_error")
            result = result.get("result", result)
            if "choices" in result:
                choice = result["choices"][0]
                if choice.get("finish_reason") not in (None, "stop"):
                    raise AIError("invalid_response")
                value = choice["message"]["content"]
            else:
                value = result["response"]
            if isinstance(value, dict):
                return json.dumps(value, ensure_ascii=False)
            if not isinstance(value, str):
                raise AIError("invalid_response")
            return value
        except HTTPError as exc:
            code = "quota" if exc.code == 429 else "provider_error"
            if exc.code in (401, 403):
                code = "credentials"
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
