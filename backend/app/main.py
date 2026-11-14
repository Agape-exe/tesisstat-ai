"""Main entry point for TesisStat AI production deployment."""

from app.core.config import Settings, get_settings
from app.production_app import create_production_app

app = create_production_app()


def create_app(settings: Settings | None = None):
    return create_production_app(settings)
