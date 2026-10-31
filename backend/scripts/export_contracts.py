"""Run from backend: uv run python -m scripts.export_contracts [--check]."""

import argparse
import json
from pathlib import Path

from app.shared.contracts import CONTRACT_MODELS

ROOT = Path(__file__).resolve().parents[2]


def schema_text(model: type) -> str:
    schema = model.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = f"https://tesisstat.local/contracts/v1/{model.__name__}.schema.json"
    return json.dumps(schema, ensure_ascii=False, indent=2) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    output = ROOT / "contracts" / "v1"
    output.mkdir(parents=True, exist_ok=True)
    for model in CONTRACT_MODELS:
        path = output / f"{model.__name__}.schema.json"
        content = schema_text(model)
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                raise SystemExit(f"Outdated schema: {path}")
        else:
            path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
