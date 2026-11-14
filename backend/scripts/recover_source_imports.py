"""Inspect interrupted local C3 publications; apply only after reviewing the dry run."""

import argparse
import json
from pathlib import Path

from app.modules.research.sources.repository import SourceRepository


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--storage", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.db.is_file() or not args.storage.is_dir():
        parser.error("Indica la base y el directorio de fuentes existentes de la misma instancia.")
    print(
        json.dumps(
            SourceRepository(args.db, args.storage).recover(apply=args.apply),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
