"""Real Research HTTP/storage → planner → approval → engine integration.

All source documents, reviews and datasets are synthetic. Only the explicitly
marked failure-injection tests replace an engine/planner method.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.modules.research.dev_app import create_app
from app.modules.statistics.engine import DeterministicStatisticalEngine
from app.orchestration.analysis_inputs import analysis_input
from app.shared.contracts import AnalysisPlan, AnalysisResult, ResearchPackage
from tests.research.test_datasets import xlsx
from tests.research.test_methodology import setup
from tests.research.test_methodology_review import manual

CSV = b"horas_estudio,rendimiento\n1,2\n2,4\n3,6\n4,8\n"


@dataclass
class Case:
    client: TestClient
    settings: object
    project: str
    document: str
    dataset: str
    package_root: str
    package: dict

    @property
    def root(self):
        return self.project + "/analysis"

    def propose(self, **changes):
        body = {
            "package_id": self.package["id"],
            "hypothesis_id": self.package["hypotheses"][0]["id"],
        } | changes
        return self.client.post(self.root + "/plan", json=body)

    def approve(self, record):
        return self.client.post(
            self.root + f"/plans/{record['plan']['id']}/approve",
            json={"confirm": True, "proposal_token": record["proposal_token"]},
        )

    def execute(self, record):
        return self.client.post(self.root + f"/plans/{record['plan']['id']}/execute")


def research_case(
    tmp_path,
    *,
    kind="descriptive",
    fmt="csv",
    data=CSV,
    scales=("ratio", "ratio"),
    **config_changes,
):
    client, document, settings, provider = setup(
        tmp_path, research_datasets_path=tmp_path / "datasets"
    )
    project = document.split("/documents/")[0]
    review = client.post(document + "/methodology/review").json()
    content = review["content"]
    content["title"] = manual("Estudio sintético de horas y rendimiento")
    content["general_objective"] = manual("Analizar horas y rendimiento ficticios")
    content["general_hypothesis"] = manual("Hipótesis sintética de horas y rendimiento")
    content["research_design"] = manual("Observacional con observaciones independientes")
    ids = [str(uuid4()), str(uuid4())]
    content["variables"] = [
        {
            "id": variable_id,
            "name": manual(name),
            "role": manual(role),
            "measurement_scale": manual(scale),
            "dimensions": [],
            "indicators": [],
            "instrument_items": [],
        }
        for variable_id, name, role, scale in zip(
            ids,
            ["Horas de estudio", "Rendimiento"],
            ["independent", "dependent"],
            scales,
            strict=True,
        )
    ]
    assert (
        client.put(
            document + "/methodology/review", json={"version": 0, "content": content}
        ).status_code
        == 200
    )
    assert (
        client.post(document + "/methodology/review/confirm", json={"version": 1}).status_code
        == 200
    )
    if fmt == "xlsx":
        rows = [["horas_estudio", "rendimiento"], [1, 2], [2, 4], [3, 6], [4, 8]]
        data = xlsx({"Sintetico": rows})
    upload = client.post(
        project + "/datasets", content=data, headers={"X-File-Name": "synthetic." + fmt}
    )
    assert upload.status_code == 201, upload.text
    dataset = project + "/datasets/" + upload.json()["id"]
    assert client.put(dataset + "/origin", json={"synthetic": True}).status_code == 200
    assert client.post(dataset + "/activate").status_code == 200
    package_root = project + "/package"
    config = client.get(package_root + "/configuration").json()
    config.update(
        document_id=document.split("/documents/")[1],
        dataset_id=upload.json()["id"],
        design="observational",
        observations="independent",
        variables=[
            {
                "variable_id": ids[0],
                "columns": ["horas_estudio"],
                "role": "independent",
                "measurement_scale": scales[0],
            },
            {
                "variable_id": ids[1],
                "columns": ["rendimiento"],
                "role": "dependent",
                "measurement_scale": scales[1],
            },
        ],
        hypotheses=[
            {
                "id": str(uuid4()),
                "source": "general",
                "kind": kind,
                "objective": content["general_objective"]["value"],
                "variable_ids": ids,
                "alternative": "two-sided",
                "null_statement": None,
            }
        ],
    )
    config.update(config_changes)
    saved = client.put(package_root + "/configuration", json=config)
    assert saved.status_code == 200, saved.text
    response = client.post(package_root + "/build")
    assert response.status_code == 200, response.text
    assert provider.calls == []
    package = ResearchPackage.model_validate(response.json()).model_dump(mode="json")
    return Case(client, settings, project, document, dataset, package_root, package)


def proposed(case):
    response = case.propose()
    assert response.status_code == 201, response.text
    record = response.json()
    assert "package" not in record  # private source snapshot, no dataset bytes
    assert record["approved_at"] is None
    assert record["result"] is None
    plan = AnalysisPlan.model_validate(record["plan"])
    assert plan.research_package_id == case.package["id"]
    assert plan.hypothesis_id == case.package["hypotheses"][0]["id"]
    assert plan.dataset_id == case.package["dataset"]["id"]
    return record


def executed(case):
    record = proposed(case)
    approval = case.approve(record)
    assert approval.status_code == 200, approval.text
    assert approval.json()["plan"]["status"] == "approved"
    assert approval.json()["approved_at"]
    response = case.execute(record)
    assert response.status_code == 200, response.text
    result = AnalysisResult.model_validate(response.json())
    assert result.status == "completed", result.warnings
    return record, result


@pytest.mark.parametrize("fmt", ["csv", "xlsx"])
def test_real_descriptive_metrics_and_reload(tmp_path, fmt):
    case = research_case(tmp_path, fmt=fmt)
    record, result = executed(case)
    assert record["plan"]["technique"] == "descriptive_summary"
    metrics = {item.name: item.value for item in result.metrics}
    assert metrics["horas_estudio.mean"] == 2.5
    assert metrics["horas_estudio.median"] == 2.5
    assert metrics["horas_estudio.sample_variance"] == pytest.approx(5 / 3)
    assert metrics["rendimiento.mean"] == 5
    assert metrics["rendimiento.sample_variance"] == pytest.approx(20 / 3)
    case.client = TestClient(create_app(settings=case.settings))
    plans = case.client.get(case.root + "/plans").json()
    assert plans[0]["approved_at"]
    assert plans[0]["result"] == result.model_dump(mode="json")
    assert case.client.get(case.root + "/results").json() == plans
    assert case.execute(record).json() == result.model_dump(mode="json")


def test_real_derived_dataset(tmp_path):
    case = research_case(tmp_path)
    plan = {"operations": [{"type": "drop_columns", "columns": ["rendimiento"]}]}
    preview = case.client.post(case.dataset + "/preparation/preview", json=plan).json()
    applied = case.client.post(
        case.dataset + "/preparation/apply",
        json={
            "plan": plan,
            "preview_id": preview["preview_id"],
            "plan_hash": preview["plan_hash"],
            "confirm": True,
        },
    )
    assert applied.status_code == 201, applied.text
    derived = applied.json()["result_id"]
    assert case.client.post(case.project + f"/datasets/{derived}/activate").status_code == 200
    config = case.client.get(case.package_root + "/configuration").json()
    config["dataset_id"] = derived
    config["variables"][1]["columns"] = ["horas_estudio"]
    assert case.client.put(case.package_root + "/configuration", json=config).status_code == 200
    case.package = case.client.post(case.package_root + "/build").json()
    _, result = executed(case)
    assert result.dataset_id == derived
    assert {item.name: item.value for item in result.metrics}["horas_estudio.mean"] == 2.5


@pytest.mark.parametrize("fmt", ["csv", "xlsx"])
def test_real_pearson_columns(tmp_path, fmt):
    case = research_case(tmp_path, kind="association", fmt=fmt)
    record, result = executed(case)
    assert record["plan"]["technique"] == "pearson"
    assert record["plan"]["assumptions_to_check"]
    assert {item.name: item.value for item in result.metrics} == {"n": 4, "r": 1}
    assert any("p-valor" in warning for warning in result.warnings)
    assert result.assumptions  # Report actual engine diagnostic, not implied significance.


def test_real_spearman_columns_with_ordinal_variable(tmp_path):
    case = research_case(
        tmp_path,
        kind="association",
        scales=("ordinal", "ratio"),
        data=b"horas_estudio,rendimiento\n1,10\n2,20\n3,30\n4,40\n",
    )
    record, result = executed(case)
    assert record["plan"]["technique"] == "spearman"
    metrics = {item.name: item.value for item in result.metrics}
    assert metrics["n"] == 4
    assert metrics["rho"] == pytest.approx(1)
    assert any("coeficiente de asociación" in warning for warning in result.warnings)


def test_pearson_nontrivial_values_and_pairwise_missing(tmp_path):
    case = research_case(
        tmp_path,
        kind="association",
        data=(b"horas_estudio,rendimiento\n1,1\n2,3\n,999\n999,\n3,2\n4,5\n"),
    )
    _, result = executed(case)
    metrics = {item.name: item.value for item in result.metrics}
    assert metrics["n"] == 4
    assert metrics["r"] == pytest.approx(0.8315218406202999)
    assert any("4 de 6" in warning for warning in result.warnings)


@pytest.mark.parametrize("bad_rows", ["1,texto\n2,4\n3,6\n", "1,2\n1,4\n1,6\n", "1,2\n2,4\n"])
def test_pearson_incompatible_constant_or_insufficient_data(tmp_path, bad_rows):
    case = research_case(
        tmp_path, kind="association", data=("horas_estudio,rendimiento\n" + bad_rows).encode()
    )
    record = proposed(case)
    assert case.approve(record).status_code == 200
    response = case.execute(record)
    assert response.status_code == 200
    result = AnalysisResult.model_validate(response.json())
    assert result.status == "failed"
    assert result.metrics == []
    assert result.warnings
    assert case.execute(record).json() == response.json()


def test_approval_required_exact_proposal_and_no_arbitrary_technique(tmp_path):
    case = research_case(tmp_path)
    record = proposed(case)
    assert case.execute(record).status_code == 409
    approve_url = case.root + f"/plans/{record['plan']['id']}/approve"
    assert case.client.post(approve_url).status_code == 422
    assert (
        case.client.post(
            approve_url,
            json={
                "confirm": False,
                "proposal_token": record["proposal_token"],
            },
        ).status_code
        == 422
    )
    assert (
        case.client.post(
            approve_url,
            json={
                "confirm": True,
                "proposal_token": "otra-propuesta",
            },
        ).status_code
        == 409
    )
    assert case.propose(technique="pearson").status_code == 422
    assert case.approve(record).status_code == 200
    other = proposed(case)
    assert other["plan"]["id"] != record["plan"]["id"]
    assert case.execute(other).status_code == 409


@pytest.mark.parametrize(
    "changes",
    [
        {"kind": "unknown"},
        {"kind": "association", "design": "unknown"},
        {"kind": "association", "observations": "unknown"},
    ],
)
def test_clarification_cannot_be_approved_or_executed(tmp_path, changes):
    case = research_case(tmp_path, **changes)
    record = proposed(case)
    assert record["plan"]["status"] == "needs_clarification"
    assert record["plan"]["pending_questions"]
    assert case.approve(record).status_code == 409
    assert case.execute(record).status_code == 409


def test_unsupported_adapter_preserves_technique_and_blocks_approval(tmp_path):
    case = research_case(tmp_path, kind="prediction")
    record = proposed(case)
    assert record["plan"]["technique"] == "linear_regression_simple"
    assert record["plan"]["status"] == "proposed"
    assert not record["executable"]
    assert "adaptador" in record["limitation"]
    assert case.approve(record).status_code == 409
    assert case.execute(record).status_code == 409


@pytest.mark.parametrize(
    "mutation", ["review", "dataset", "bytes", "config", "rebuild", "document", "document_bytes"]
)
@pytest.mark.parametrize("approved", [False, True])
def test_sources_invalidate_proposals_and_approvals(tmp_path, mutation, approved):
    case = research_case(tmp_path)
    record = proposed(case)
    if approved:
        assert case.approve(record).status_code == 200
    if mutation == "review":
        review = case.client.get(case.document + "/methodology/review").json()
        review["content"]["title"] = manual("Título metodológico modificado")
        assert (
            case.client.put(
                case.document + "/methodology/review",
                json={
                    "version": review["version"],
                    "content": review["content"],
                },
            ).status_code
            == 200
        )
    elif mutation == "dataset":
        new = case.client.post(
            case.project + "/datasets", content=CSV, headers={"X-File-Name": "otro.csv"}
        ).json()["id"]
        assert case.client.post(case.project + f"/datasets/{new}/activate").status_code == 200
    elif mutation == "bytes":
        dataset_id = UUID(case.package["dataset"]["id"])
        path = case.settings.research_datasets_path / dataset_id.hex
        path.write_bytes(CSV.replace(b"1,2", b"9,2"))
    elif mutation == "config":
        config = case.client.get(case.package_root + "/configuration").json()
        config["sampling_notes"] = "Muestreo modificado"
        assert case.client.put(case.package_root + "/configuration", json=config).status_code == 200
    elif mutation == "rebuild":
        assert case.client.post(case.package_root + "/build").status_code == 200
    elif mutation == "document_bytes":
        document_id = UUID(case.document.rsplit("/", 1)[1])
        path = case.settings.research_documents_path / document_id.hex
        path.write_bytes(path.read_bytes() + b"changed synthetic document")
    else:
        assert case.client.delete(case.document).status_code == 204
    response = case.execute(record) if approved else case.approve(record)
    assert response.status_code == 409, response.text
    persisted = case.client.get(case.root + "/plans").json()[0]
    assert persisted["invalidated_at"]
    assert persisted["approved_at"] is None
    assert case.execute(record).status_code == 409
    assert case.approve(record).status_code == 409


def test_missing_and_foreign_references(tmp_path):
    case = research_case(tmp_path)
    assert case.propose(hypothesis_id=str(uuid4())).status_code == 404
    assert case.propose(package_id=str(uuid4())).status_code == 409
    record = proposed(case)
    other = research_case(tmp_path / "other")
    # Same SQLite database, different project, so a guessed ID cannot authorize the record.
    foreign = case.client.post(
        "/api/research/projects",
        json={
            "title": "Otro proyecto sintético",
            "university": "Demo",
            "program": "Demo",
            "degree": "bachelor",
        },
    ).json()["id"]
    root = f"/api/research/projects/{foreign}/analysis"
    assert case.client.get(root + "/plans").json() == []
    assert case.client.get(root + "/results").json() == []
    assert case.client.post(root + f"/plans/{record['plan']['id']}/execute").status_code == 404
    assert (
        case.client.post(
            root + "/plan",
            json={
                "package_id": case.package["id"],
                "hypothesis_id": record["plan"]["hypothesis_id"],
            },
        ).status_code
        == 409
    )
    assert other.propose(package_id=case.package["id"]).status_code == 409
    assert case.client.get(f"/api/research/projects/{uuid4()}/analysis/plans").status_code == 404


def test_unknown_column_and_multi_column_pearson(tmp_path):
    case = research_case(tmp_path, kind="association")
    config = case.client.get(case.package_root + "/configuration").json()
    config["variables"][0]["columns"] = ["no_existe"]
    assert case.client.put(case.package_root + "/configuration", json=config).status_code == 200
    assert case.client.post(case.package_root + "/build").status_code == 422
    assert case.propose().status_code == 409
    config = case.client.get(case.package_root + "/configuration").json()
    config["variables"][0]["columns"] = ["horas_estudio", "rendimiento"]
    assert case.client.put(case.package_root + "/configuration", json=config).status_code == 200
    case.package = case.client.post(case.package_root + "/build").json()
    record = proposed(case)
    assert record["plan"]["technique"] == "pearson"
    assert record["plan"]["status"] == "needs_clarification"
    assert case.approve(record).status_code == 409


def test_loopback_and_synthetic_only(tmp_path):
    case = research_case(tmp_path)
    remote = TestClient(case.client.app, client=("203.0.113.8", 12345))
    assert remote.get(case.root + "/plans").status_code == 403
    assert (
        case.client.get(case.root + "/plans", headers={"Host": "public.example"}).status_code == 403
    )
    assert case.client.put(case.dataset + "/origin", json={"synthetic": False}).status_code == 200
    config = case.client.get(case.package_root + "/configuration").json()
    assert case.client.put(case.package_root + "/configuration", json=config).status_code == 200
    case.package = case.client.post(case.package_root + "/build").json()
    assert case.propose().status_code == 403


def test_concurrent_retry_calculates_once(tmp_path, monkeypatch):
    """Real engine, instrumented only to count calls during concurrent HTTP retries."""
    case = research_case(tmp_path)
    record = proposed(case)
    assert case.approve(record).status_code == 200
    original = DeterministicStatisticalEngine.execute
    calls = []

    def counted(engine, plan):
        calls.append(plan.id)
        return original(engine, plan)

    monkeypatch.setattr(DeterministicStatisticalEngine, "execute", counted)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: case.execute(record), range(2)))
    assert [response.status_code for response in responses] == [200, 200]
    assert responses[0].json() == responses[1].json()
    assert calls == [record["plan"]["id"]]


def test_controlled_unexpected_engine_error_mock(tmp_path, monkeypatch):
    """Failure injection, not evidence of real statistical calculation."""
    case = research_case(tmp_path)
    record = proposed(case)
    assert case.approve(record).status_code == 200

    def failure(*args):
        raise RuntimeError("private/internal/path")

    monkeypatch.setattr(DeterministicStatisticalEngine, "execute", failure)
    response = case.execute(record)
    assert response.status_code == 200
    result = AnalysisResult.model_validate(response.json())
    assert result.status == "failed"
    assert result.metrics == []
    assert "private/internal" not in response.text
    assert case.execute(record).json() == response.json()


def test_input_adapter_unit_rejects_absent_column(tmp_path):
    """Unit boundary check using a malformed table, not a full integration claim."""
    from fastapi import HTTPException

    from app.modules.statistics.datasets import DatasetTable

    case = research_case(tmp_path, kind="association")
    package = ResearchPackage.model_validate(case.package)
    plan = AnalysisPlan.model_validate(proposed(case)["plan"])
    with pytest.raises(HTTPException, match="columna"):
        analysis_input(
            package, plan, DatasetTable(columns=("other",), rows=(("1",),), format="csv")
        )
