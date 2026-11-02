"""Development-only API for the descriptive statistics demonstration."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .datasets import fixture_catalog, list_profiles, read_csv_dataset
from .descriptive import describe_column


class DescriptiveRequest(BaseModel):
    columns: list[str] = Field(min_length=1, max_length=20)


def create_descriptive_app(root: Path | None = None) -> FastAPI:
    app = FastAPI(title="TesisStat AI — Descriptivos", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
        allow_credentials=False,
    )
    catalog = fixture_catalog(root)

    def definition_or_404(dataset_id: str):
        definition = catalog.get(dataset_id)
        if definition is None:
            raise HTTPException(status_code=404, detail="Dataset de demostración no encontrado.")
        return definition

    @app.get("/datasets")
    def datasets() -> list[dict[str, str]]:
        return [{"id": item.id, "label": item.label} for item in catalog.values()]

    @app.get("/datasets/{dataset_id}/columns")
    def columns(dataset_id: str) -> list[dict[str, object]]:
        try:
            return [asdict(profile) for profile in list_profiles(definition_or_404(dataset_id))]
        except (OSError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/datasets/{dataset_id}/descriptive")
    def descriptive(dataset_id: str, request: DescriptiveRequest) -> list[dict[str, object]]:
        try:
            data = read_csv_dataset(definition_or_404(dataset_id))
        except (OSError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        unknown = sorted(set(request.columns) - set(data))
        if unknown:
            raise HTTPException(
                status_code=422, detail=f"Columnas desconocidas: {', '.join(unknown)}"
            )
        return [asdict(describe_column(name, data[name])) for name in request.columns]

    return app
