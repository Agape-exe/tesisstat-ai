from uuid import UUID

from app.shared.contracts import AnalysisPlan, ResearchPackage
from tests.research.test_packages import prepared
from tests.research.test_statistics_bridge import built


def test_statistics_runtime_proposes_and_executes_approved_descriptive_plan(tmp_path):
    client, _, document_root, dataset_root, package_root, config = prepared(tmp_path)
    assert client.put(dataset_root + "/origin", json={"synthetic": True}).status_code == 200
    config["hypotheses"][0]["kind"] = "descriptive"
    assert client.put(package_root + "/configuration", json=config).status_code == 200
    package = ResearchPackage.model_validate(client.post(package_root + "/build").json())
    project_id = UUID(document_root.split("/documents/")[0].rsplit("/", 1)[1])
    endpoint = f"/api/research/projects/{project_id}/statistics"

    plan_response = client.post(
        f"{endpoint}/plan",
        json={"package_id": package.id, "hypothesis_id": package.hypotheses[0].id},
    )

    assert plan_response.status_code == 200, plan_response.text
    plan = AnalysisPlan.model_validate(plan_response.json())
    assert plan.status == "proposed"
    assert plan.technique == "descriptive_summary"

    blocked = client.post(
        f"{endpoint}/analysis",
        json={"package_id": package.id, "hypothesis_id": package.hypotheses[0].id},
    )
    assert blocked.status_code == 409

    executed = client.post(
        f"{endpoint}/analysis",
        json={
            "package_id": package.id,
            "hypothesis_id": package.hypotheses[0].id,
            "approve": True,
        },
    )
    assert executed.status_code == 200, executed.text
    result = executed.json()
    assert result["status"] == "completed"
    assert any(metric["name"] == "habitos.mean" for metric in result["metrics"])


def test_statistics_runtime_rejects_unknown_package_and_hypothesis(tmp_path):
    client, _, _, _, _, project_id, package = built(tmp_path)
    endpoint = f"/api/research/projects/{project_id}/statistics"
    assert (
        client.post(
            f"{endpoint}/plan",
            json={"package_id": "wrong", "hypothesis_id": package.hypotheses[0].id},
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"{endpoint}/plan",
            json={"package_id": package.id, "hypothesis_id": "wrong"},
        ).status_code
        == 422
    )
