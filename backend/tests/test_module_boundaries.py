from pathlib import Path

import pytest

from app.core.config import Settings
from app.shared.adapters.cloudflare import CloudflareLanguageModel
from app.shared.adapters.fixtures import (
    FixtureAnalysisPlanner,
    FixtureResearchReader,
    FixtureStatisticalEngine,
)
from app.shared.adapters.supabase import SupabaseAdapter

ROOT = Path(__file__).resolve().parents[2]


def test_independent_modules_can_exchange_fixture_contracts():
    research = FixtureResearchReader(ROOT / "fixtures/research/association.package.json")
    planner = FixtureAnalysisPlanner(ROOT / "fixtures/statistics/association.plan.json")
    engine = FixtureStatisticalEngine(ROOT / "fixtures/statistics/association.result.json")
    package = research.get_package("research-association")
    plan = planner.propose(package, "h1")
    result = engine.execute(plan)
    assert result.status == "not_executed"
    assert result.metrics == []
    package.title = "Changed locally"
    assert research.get_package(package.id).title != package.title
    with pytest.raises(KeyError):
        research.get_package("unknown")
    with pytest.raises(ValueError):
        planner.propose(package, "unknown")
    with pytest.raises(ValueError):
        engine.execute(plan.model_copy(update={"dataset_id": "other"}))


def test_external_adapters_fail_explicitly_without_network():
    import asyncio

    settings = Settings(_env_file=None)
    with pytest.raises(NotImplementedError):
        asyncio.run(CloudflareLanguageModel(settings).complete("fixture", max_tokens=10))
    with pytest.raises(NotImplementedError):
        asyncio.run(SupabaseAdapter(settings).read("fixture"))
