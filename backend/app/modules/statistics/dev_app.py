"""Run with: uv run uvicorn app.modules.statistics.dev_app:app --reload --port 8001."""

from .api import create_descriptive_app

app = create_descriptive_app()
