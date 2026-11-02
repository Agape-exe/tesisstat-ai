"""Synthetic, internal consumer tests; Statistics is not present on develop."""

from uuid import UUID, uuid4

import pytest

from app.orchestration.research_statistics import ResearchInputError
from app.shared.contracts import DatasetReference, ResearchPackage
from tests.research.test_datasets import xlsx
from tests.research.test_methodology_review import manual
from tests.research.test_packages import prepared


def built(tmp_path):
    client, settings, document_root, dataset_root, root, config = prepared(tmp_path)
    assert client.put(dataset_root + "/origin", json={"synthetic": True}).status_code == 200
    assert client.put(root + "/configuration", json=config).status_code == 200
    response = client.post(root + "/build")
    assert response.status_code == 200, response.text
    package = ResearchPackage.model_validate(response.json())
    project_id = UUID(document_root.split("/documents/")[0].rsplit("/", 1)[1])
    return client, settings, document_root, dataset_root, root, project_id, package


def code(exc: pytest.ExceptionInfo[ResearchInputError]) -> str:
    return exc.value.code


def test_current_package_and_contract_consumer(tmp_path):
    client, _, _, _, _, project_id, package = built(tmp_path)
    bridge = client.app.state.research_statistics_bridge
    assert bridge.get_package(project_id, package.id) == package

    def synthetic_consumer(contract: ResearchPackage) -> bytes:
        assert contract.hypotheses[0].variable_ids[0] == contract.variables[0].id
        assert isinstance(contract.dataset, DatasetReference)
        return bridge.read_dataset(project_id, contract, contract.dataset)

    assert synthetic_consumer(package) == b"habitos,nota,extra\n3,15,x\n"
    assert not any(
        "/bytes" in getattr(route, "path", "") or "/download" in getattr(route, "path", "")
        for route in client.app.routes
    )


def test_missing_or_foreign_project_package(tmp_path):
    client, _, _, _, _, project_id, package = built(tmp_path)
    bridge = client.app.state.research_statistics_bridge
    with pytest.raises(ResearchInputError) as exc:
        bridge.get_package(project_id, str(uuid4()))
    assert code(exc) == "package_missing"
    with pytest.raises(ResearchInputError) as exc:
        bridge.get_package(uuid4(), package.id)
    assert code(exc) == "project_missing"
    other = client.post(
        "/api/research/projects",
        json={
            "title": "Otro proyecto ficticio",
            "university": "Demo",
            "program": "Demo",
            "degree": "bachelor",
        },
    ).json()["id"]
    with pytest.raises(ResearchInputError) as exc:
        bridge.get_package(UUID(other), package.id)
    assert code(exc) == "package_missing"


def test_stale_after_methodology_and_dataset_changes(tmp_path):
    client, _, document_root, dataset_root, root, project_id, package = built(tmp_path)
    bridge = client.app.state.research_statistics_bridge
    review = client.get(document_root + "/methodology/review").json()
    review["content"]["title"] = manual("Título ficticio modificado")
    assert (
        client.put(
            document_root + "/methodology/review",
            json={"version": review["version"], "content": review["content"]},
        ).status_code
        == 200
    )
    with pytest.raises(ResearchInputError) as exc:
        bridge.get_package(project_id, package.id)
    assert code(exc) == "package_stale"
    assert client.get(root + "/status").json()["state"] == "stale"
    # A separate fixture checks a deleted selected dataset.
    client2, _, _, dataset_root2, _, project_id2, package2 = built(tmp_path / "deleted")
    assert client2.delete(dataset_root2).status_code == 204
    with pytest.raises(ResearchInputError) as exc:
        client2.app.state.research_statistics_bridge.get_package(project_id2, package2.id)
    assert code(exc) == "dataset_inaccessible"
    assert dataset_root != dataset_root2


def test_invalid_opaque_key_and_contract_metadata(tmp_path):
    client, _, _, _, _, project_id, package = built(tmp_path)
    bridge = client.app.state.research_statistics_bridge
    for changed in (
        package.dataset.model_copy(update={"location": "C:/private/dataset.csv"}),
        package.dataset.model_copy(update={"location": f"research-dataset:{uuid4()}"}),
        package.dataset.model_copy(update={"id": str(uuid4())}),
    ):
        with pytest.raises(ResearchInputError) as exc:
            bridge.read_dataset(project_id, package, changed)
        assert code(exc) == "invalid_reference"
    for changed in (
        package.dataset.model_copy(update={"columns": ["other"]}),
        package.dataset.model_copy(update={"row_count": 99}),
        package.dataset.model_copy(update={"format": "xlsx"}),
        package.dataset.model_copy(update={"synthetic": False}),
    ):
        with pytest.raises(ResearchInputError) as exc:
            bridge.read_dataset(project_id, package, changed)
        assert code(exc) == "dataset_incompatible"


def test_inactive_missing_and_modified_file(tmp_path):
    client, settings, document_root, dataset_root, _, project_id, package = built(tmp_path)
    bridge = client.app.state.research_statistics_bridge
    second = client.post(
        document_root.split("/documents/")[0] + "/datasets",
        content=b"other\n1\n",
        headers={"X-File-Name": "other.csv"},
    ).json()["id"]
    assert (
        client.post(
            document_root.split("/documents/")[0] + f"/datasets/{second}/activate"
        ).status_code
        == 200
    )
    with pytest.raises(ResearchInputError) as exc:
        bridge.read_dataset(project_id, package, package.dataset)
    assert code(exc) == "dataset_inactive"
    assert client.post(dataset_root + "/activate").status_code == 200
    path = settings.research_datasets_path / UUID(package.dataset.id).hex
    path.write_bytes(b"habitos,nota,extra\n9,10,z\n")
    with pytest.raises(ResearchInputError) as exc:
        bridge.read_dataset(project_id, package, package.dataset)
    assert code(exc) == "package_stale"
    path.unlink()
    with pytest.raises(ResearchInputError) as exc:
        bridge.get_package(project_id, package.id)
    assert code(exc) == "dataset_inaccessible"


def test_original_xlsx_and_derived_csv(tmp_path):
    client, _, document_root, dataset_root, root, project_id, _ = built(tmp_path)
    project_root = document_root.split("/documents/")[0]
    base = project_root + "/datasets"
    source = client.post(
        base,
        content=xlsx({"Datos": [["habitos", "nota", "extra"], [4, 16, "y"]]}),
        headers={"X-File-Name": "ficticio.xlsx"},
    ).json()["id"]
    source_root = f"{base}/{source}"
    assert client.put(source_root + "/origin", json={"synthetic": True}).status_code == 200
    assert client.post(source_root + "/activate").status_code == 200
    config = client.get(root + "/configuration").json()
    config["dataset_id"] = source
    assert client.put(root + "/configuration", json=config).status_code == 200
    package = ResearchPackage.model_validate(client.post(root + "/build").json())
    bridge = client.app.state.research_statistics_bridge
    assert bridge.read_dataset(project_id, package, package.dataset).startswith(b"PK\x03\x04")

    plan = {"operations": [{"type": "drop_columns", "columns": ["nota"]}]}
    preview = client.post(source_root + "/preparation/preview", json=plan).json()
    applied = client.post(
        source_root + "/preparation/apply",
        json={
            "plan": plan,
            "preview_id": preview["preview_id"],
            "plan_hash": preview["plan_hash"],
            "confirm": True,
        },
    )
    assert applied.status_code == 201, applied.text
    derived = applied.json()["result_id"]
    assert client.post(f"{base}/{derived}/activate").status_code == 200
    config = client.get(root + "/configuration").json()
    config["dataset_id"] = derived
    config["variables"][0]["columns"] = ["habitos", "extra"]
    assert client.put(root + "/configuration", json=config).status_code == 200
    derived_package = ResearchPackage.model_validate(client.post(root + "/build").json())
    assert bridge.read_dataset(project_id, derived_package, derived_package.dataset).startswith(
        b"habitos,extra\r\n"
    )
    assert derived_package.dataset.synthetic is True
