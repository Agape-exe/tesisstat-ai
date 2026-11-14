"""Package boundaries use only fictitious research and dataset values."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.modules.research.dev_app import create_app
from app.shared.contracts import ResearchPackage
from tests.research.test_methodology import setup
from tests.research.test_methodology_review import manual


def prepared(tmp_path):
    client, document_root, settings, _ = setup(tmp_path)
    project_root = document_root.split("/documents/")[0]
    package_root = project_root + "/package"
    review = client.post(document_root + "/methodology/review").json()
    content = review["content"]
    content["title"] = manual("Investigación ficticia de hábitos")
    content["general_objective"] = manual("Relacionar hábitos y rendimiento")
    content["general_hypothesis"] = manual("Existe relación entre hábitos y rendimiento")
    content["research_design"] = manual("Diseño transversal")
    variable_id = str(uuid4())
    content["variables"] = [
        {
            "id": variable_id,
            "name": manual("Hábitos"),
            "role": manual("independent"),
            "measurement_scale": manual("ordinal"),
            "dimensions": [],
            "indicators": [],
            "instrument_items": [],
        }
    ]
    assert (
        client.put(
            document_root + "/methodology/review",
            json={
                "version": 0,
                "content": content,
            },
        ).status_code
        == 200
    )
    assert (
        client.post(
            document_root + "/methodology/review/confirm",
            json={
                "version": 1,
            },
        ).status_code
        == 200
    )
    dataset = client.post(
        project_root + "/datasets",
        content=b"habitos,nota,extra\n3,15,x\n",
        headers={"X-File-Name": "ficticio.csv"},
    ).json()
    dataset_root = project_root + "/datasets/" + dataset["id"]
    assert client.post(dataset_root + "/activate").status_code == 200
    config = client.get(package_root + "/configuration").json()
    config["document_id"] = document_root.split("/documents/")[1]
    config["dataset_id"] = dataset["id"]
    config["variables"] = [
        {
            "variable_id": variable_id,
            "columns": ["habitos", "extra"],
            "role": "independent",
            "measurement_scale": "ordinal",
        }
    ]
    config["hypotheses"] = [
        {
            "id": str(uuid4()),
            "source": "general",
            "objective": "Relacionar hábitos y rendimiento",
            "variable_ids": [variable_id],
            "kind": "association",
            "alternative": "unspecified",
            "null_statement": None,
        }
    ]
    return client, settings, document_root, dataset_root, package_root, config


def test_build_contract_restart_and_stale_sources(tmp_path):
    client, settings, document_root, dataset_root, root, config = prepared(tmp_path)
    assert client.post(root + "/build").status_code == 422
    saved = client.put(root + "/configuration", json=config)
    assert saved.status_code == 200, saved.text
    assert client.post(root + "/build").status_code == 422  # origin unknown
    assert client.put(dataset_root + "/origin", json={"synthetic": True}).status_code == 200
    config = client.get(root + "/configuration").json()
    assert client.put(root + "/configuration", json=config).status_code == 200
    built = client.post(root + "/build")
    assert built.status_code == 200, built.text
    package = ResearchPackage.model_validate(built.json())
    assert package.dataset.synthetic is True
    assert package.dataset.location == "research-dataset:" + package.dataset.id
    assert package.variables[0].columns == ["habitos", "extra"]
    assert package.hypotheses[0].variable_ids == [package.variables[0].id]
    restarted = TestClient(create_app(settings=settings))
    assert restarted.get(root).json() == built.json()
    review = restarted.get(document_root + "/methodology/review").json()
    review["content"]["general_hypothesis"] = manual("Hipótesis ficticia revisada")
    assert (
        restarted.put(
            document_root + "/methodology/review",
            json={
                "version": review["version"],
                "content": review["content"],
            },
        ).status_code
        == 200
    )
    assert restarted.get(root + "/status").json()["state"] == "stale"
    assert restarted.get(root).status_code == 409


def test_invalid_links_conflict_and_missing_resources(tmp_path):
    client, _, _, dataset_root, root, config = prepared(tmp_path)
    assert (
        client.get("/api/research/projects/" + str(uuid4()) + "/package/status").status_code == 404
    )
    assert client.put(dataset_root + "/origin", json={"synthetic": False}).status_code == 200
    config["variables"][0]["columns"] = ["deleted_column"]
    assert client.put(root + "/configuration", json=config).status_code == 200
    status = client.post(root + "/validate").json()
    assert any("inexistentes" in item for item in status["errors"])
    assert client.post(root + "/build").status_code == 422
    assert client.put(root + "/configuration", json=config).status_code == 409
    current = client.get(root + "/configuration").json()
    current["variables"][0]["columns"] = ["habitos"]
    current["hypotheses"][0]["objective"] = "Objetivo inventado"
    assert client.put(root + "/configuration", json=current).status_code == 200
    assert any("objetivo" in item.lower() for item in client.get(root + "/status").json()["errors"])
    current = client.get(root + "/configuration").json()
    current["dataset_id"] = str(uuid4())
    assert client.put(root + "/configuration", json=current).status_code == 404


def test_unreviewed_document_and_dataset_switch_invalidate_package(tmp_path):
    client, _, document_root, dataset_root, root, config = prepared(tmp_path)
    project_root = document_root.split("/documents/")[0]
    assert client.put(dataset_root + "/origin", json={"synthetic": False}).status_code == 200
    assert client.put(root + "/configuration", json=config).status_code == 200
    assert client.post(root + "/build").status_code == 200
    second = client.post(
        project_root + "/datasets", content=b"other\n1\n", headers={"X-File-Name": "segundo.csv"}
    ).json()
    assert client.post(project_root + "/datasets/" + second["id"] + "/activate").status_code == 200
    assert client.get(root + "/status").json()["state"] == "stale"
    assert client.get(root).status_code == 409
    assert client.delete(dataset_root).status_code == 204
    assert client.get(root + "/status").json()["state"] == "stale"
    unreviewed = client.post(document_root + "/methodology/review")
    assert unreviewed.status_code == 409
    review = client.get(document_root + "/methodology/review").json()
    review["content"]["title"] = manual("Título nuevo")
    assert (
        client.put(
            document_root + "/methodology/review",
            json={
                "version": review["version"],
                "content": review["content"],
            },
        ).status_code
        == 200
    )
    current = client.get(root + "/configuration").json()
    current["dataset_id"] = None
    assert client.put(root + "/configuration", json=current).status_code == 422


def test_invalid_enums_and_duplicate_references_rejected(tmp_path):
    client, _, _, dataset_root, root, config = prepared(tmp_path)
    assert client.put(dataset_root + "/origin", json={"synthetic": True}).status_code == 200
    wrong = config | {"design": "cross_sectional"}
    assert client.put(root + "/configuration", json=wrong).status_code == 422
    config["hypotheses"][0]["variable_ids"] *= 2
    config["variables"][0]["columns"] *= 2
    assert client.put(root + "/configuration", json=config).status_code == 200
    errors = client.get(root + "/status").json()["errors"]
    assert any("únicas" in item for item in errors)
    assert client.post(root + "/build").status_code == 422
