"""Synthetic review flows; no external model calls or personal data."""

from concurrent.futures import ThreadPoolExecutor

from app.modules.research.dev_app import create_app
from tests.research.test_methodology import FakeProvider, setup


def manual(value):
    return {"value": value, "kind": "manual", "evidence": []}


def test_manual_edit_confirm_restart_and_cleanup(tmp_path):
    provider = FakeProvider()
    provider.configured = False
    client, root, settings, provider = setup(tmp_path, provider=provider)
    created = client.post(root + "/methodology/review")
    assert created.status_code == 201
    review = created.json()
    assert review["origin"] == "manual"
    assert provider.calls == []
    assert client.post(root + "/methodology/review/confirm", json={"version": 0}).status_code == 422
    content = review["content"]
    content["title"] = manual("Título sintético corregido")
    content["general_objective"] = manual("Medir hábitos")
    content["research_design"] = manual("Transversal")
    content["specific_objectives"] = [manual("Describir hábitos")]
    content["specific_hypotheses"] = [manual("Existe una asociación")]
    content["variables"] = [
        {
            "id": "11111111-1111-4111-8111-111111111111",
            "name": manual("Hábitos"),
            "role": manual("independent"),
            "measurement_scale": manual("ordinal"),
            "dimensions": [manual("Frecuencia")],
            "indicators": [manual("Días")],
            "instrument_items": [manual("¿Cuántos días?")],
        }
    ]
    saved = client.put(root + "/methodology/review", json={"version": 0, "content": content})
    assert saved.status_code == 200, saved.text
    assert saved.json()["version"] == 1
    assert saved.json()["review_status"] == "unreviewed"
    assert (
        client.put(
            root + "/methodology/review", json={"version": 0, "content": content}
        ).status_code
        == 409
    )
    restarted = client.__class__(create_app(settings=settings, methodology_provider=provider))
    assert restarted.get(root + "/methodology/review").json()["content"] == content
    confirmed = restarted.post(root + "/methodology/review/confirm", json={"version": 1})
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["review_status"] == "reviewed"
    assert confirmed.json()["pending_fields"]
    content["title"] = manual("Nuevo título")
    assert (
        restarted.put(root + "/methodology/review", json={"version": 2, "content": content}).json()[
            "review_status"
        ]
        == "unreviewed"
    )
    assert restarted.delete(root).status_code == 204
    assert restarted.get(root + "/methodology/review").status_code == 404


def test_ai_draft_is_immutable_and_manual_provenance(tmp_path):
    client, root, _, provider = setup(tmp_path)
    assert (
        client.post(root + "/methodology/extract", json={"send_to_external_ai": True}).status_code
        == 200
    )
    original = client.get(root + "/methodology").json()
    review = client.post(root + "/methodology/review").json()
    assert review["origin"] == "ai"
    assert review["content"]["title"]["kind"] == "quotation"
    content = review["content"]
    content["title"] = manual("Título corregido")
    content["specific_objectives"] = [manual("Objetivo nuevo")]
    assert (
        client.put(
            root + "/methodology/review", json={"version": 0, "content": content}
        ).status_code
        == 200
    )
    assert client.get(root + "/methodology").json() == original
    assert client.get(root + "/methodology/review").json()["content"]["title"]["evidence"] == []
    assert len(provider.calls) == 1


def test_validation_ownership_and_concurrency(tmp_path):
    client, root, _, _ = setup(tmp_path)
    review = client.post(root + "/methodology/review").json()
    content = review["content"]
    content["variables"] = [
        {
            "id": "11111111-1111-4111-8111-111111111111",
            "name": manual("X"),
            "role": manual("invalid"),
            "measurement_scale": manual("nominal"),
            "dimensions": [],
            "indicators": [],
            "instrument_items": [],
        }
    ]
    assert (
        client.put(
            root + "/methodology/review", json={"version": 0, "content": content}
        ).status_code
        == 422
    )
    content["variables"][0]["role"] = manual("independent")
    content["variables"].append(content["variables"][0])
    assert (
        client.put(
            root + "/methodology/review", json={"version": 0, "content": content}
        ).status_code
        == 422
    )
    content["variables"].pop()
    content["title"] = {"value": "Fake quote", "kind": "quotation", "evidence": ["Fake quote"]}
    assert (
        client.put(
            root + "/methodology/review", json={"version": 0, "content": content}
        ).status_code
        == 422
    )
    content["title"] = manual("Valid")
    assert (
        client.put(
            root + "/methodology/review", json={"version": 0, "content": content, "unexpected": 1}
        ).status_code
        == 422
    )
    foreign = root.replace("/projects/", "/projects/00000000-0000-4000-8000-000000000000/")
    assert client.get(foreign + "/methodology/review").status_code == 404


def test_simultaneous_saves_and_project_cleanup(tmp_path):
    client, root, settings, provider = setup(tmp_path)
    review = client.post(root + "/methodology/review").json()
    content = review["content"]
    content["title"] = manual("Título sintético")

    def save():
        return client.put(
            root + "/methodology/review", json={"version": 0, "content": content}
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: save(), range(2))) == [200, 409]
    project_path = root.split("/documents/")[0]
    assert client.delete(project_path).status_code == 204
    restarted = client.__class__(create_app(settings=settings, methodology_provider=provider))
    assert restarted.get(root + "/methodology/review").status_code == 404
