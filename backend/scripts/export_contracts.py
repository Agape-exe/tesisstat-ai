"""Run from backend: uv run python -m scripts.export_contracts [--check]."""

import argparse
import json
from pathlib import Path

from app.shared.analysis_v2 import V2_CONTRACT_MODELS
from app.shared.contracts import CONTRACT_MODELS
from app.shared.data_sources_v2 import DATA_SOURCE_MODELS
from app.shared.data_workspace_v2 import WORKSPACE_MODELS

ROOT = Path(__file__).resolve().parents[2]


def schema_text(model: type, version: str = "v1") -> str:
    schema = model.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = f"https://tesisstat.local/contracts/{version}/{model.__name__}.schema.json"
    return json.dumps(schema, ensure_ascii=False, indent=2) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for version, models in (
        ("v1", CONTRACT_MODELS),
        ("v2", (*V2_CONTRACT_MODELS, *DATA_SOURCE_MODELS, *WORKSPACE_MODELS)),
    ):
        output = ROOT / "contracts" / version
        output.mkdir(parents=True, exist_ok=True)
        for model in models:
            path = output / f"{model.__name__}.schema.json"
            content = schema_text(model, version)
            if args.check:
                if not path.exists() or path.read_text(encoding="utf-8") != content:
                    raise SystemExit(f"Outdated schema: {path}")
            else:
                path.write_text(content, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
