from fastapi import APIRouter

from app.shared.instruments_v2 import (
    InstrumentConfirm,
    InstrumentContextV2,
    InstrumentEdit,
    InstrumentMappingV2,
    MappingEdit,
    ScoreConfirm,
    ScorePreviewRequest,
    ScorePreviewV2,
    ScoreRecordV2,
)


def create_router(instruments, scores):
    router = APIRouter(
        prefix="/api/v2/research/projects/{project_id}/instruments", tags=["instruments-v2"]
    )

    @router.get("", response_model=list[InstrumentContextV2])
    def list_(project_id: str):
        return instruments.list(project_id)

    @router.post("", response_model=InstrumentContextV2, status_code=201)
    def create(project_id: str, body: InstrumentEdit):
        return instruments.save(project_id, body)

    @router.get("/{id_}", response_model=InstrumentContextV2)
    def get(project_id: str, id_: str):
        return instruments.get(project_id, id_)

    @router.patch("/{id_}", response_model=InstrumentContextV2)
    def edit(project_id: str, id_: str, body: InstrumentEdit):
        return instruments.save(project_id, body, id_)

    @router.post("/{id_}/confirm", response_model=InstrumentContextV2)
    def confirm(project_id: str, id_: str, body: InstrumentConfirm):
        return instruments.confirm(project_id, id_, body)

    @router.get("/{id_}/revisions", response_model=list[InstrumentContextV2])
    def history(project_id: str, id_: str):
        return instruments.revisions(project_id, id_)

    @router.get("/{id_}/mapping", response_model=InstrumentMappingV2)
    def mapping(project_id: str, id_: str):
        return instruments.mapping(project_id, id_)

    @router.get("/{id_}/mapping/revisions", response_model=list[InstrumentMappingV2])
    def mappings(project_id: str, id_: str):
        instruments.raw(project_id, id_)
        return instruments.repository.revisions(project_id, "mapping", id_)

    @router.put("/{id_}/mapping", response_model=InstrumentMappingV2)
    def map_(project_id: str, id_: str, body: MappingEdit):
        return instruments.save_mapping(project_id, id_, body)

    @router.post("/{id_}/score-previews", response_model=ScorePreviewV2, status_code=201)
    def preview(project_id: str, id_: str, body: ScorePreviewRequest):
        return scores.preview(project_id, id_, body)

    @router.post("/{id_}/scores", response_model=ScoreRecordV2, status_code=201)
    def score(project_id: str, id_: str, body: ScoreConfirm):
        return scores.confirm(project_id, id_, body)

    @router.get("/{id_}/scores", response_model=list[ScoreRecordV2])
    def records(project_id: str, id_: str):
        return scores.records(project_id, id_)

    return router
