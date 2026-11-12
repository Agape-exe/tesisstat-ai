from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from app.modules.statistics.presentation_v2 import present
from app.shared.tutor_v2 import (
    ExplanationReviewV2,
    GuidedDescriptiveRequestV2,
    MessageDraftV2,
    ResultExplanationV2,
    TutorConsentV2,
    TutorSelectionV2,
)


def create_router(tutor, reports):
    router = APIRouter(prefix="/api/v2/research/projects/{project_id}", tags=["tutor-reports-v2"])

    @router.get("/conversations/status")
    def status(project_id: str, selection: Annotated[TutorSelectionV2, Depends()]):
        return tutor.status(project_id, selection)

    @router.post("/conversations/actions")
    def action(project_id: str, body: GuidedDescriptiveRequestV2):
        from app.modules.conversation.guided_service import prepare_descriptive

        return prepare_descriptive(tutor, project_id, body)

    @router.get("/conversations/consent")
    def consent(project_id: str):
        return tutor.consent(project_id)

    @router.put("/conversations/consent")
    def set_consent(project_id: str, body: TutorConsentV2):
        return tutor.set_consent(project_id, body)

    @router.post("/conversations/{conversation_id}/messages")
    def send(project_id: str, conversation_id: UUID, body: MessageDraftV2):
        return tutor.send(project_id, conversation_id, body)

    @router.get("/analysis/results/{result_id}/presentation")
    def presentation(project_id: str, result_id: str):
        return present(tutor.analysis.result(project_id, result_id))

    @router.get("/analysis/results/{result_id}/figures")
    def figures(project_id: str, result_id: str):
        return reports.figures(project_id, result_id)

    @router.get(
        "/analysis/results/{result_id}/interpretations", response_model=list[ResultExplanationV2]
    )
    def explanations(project_id: str, result_id: str):
        return tutor.explanations(project_id, result_id)

    @router.post(
        "/analysis/results/{result_id}/interpretations/{explanation_id}/review",
        response_model=ResultExplanationV2,
    )
    def review(project_id: str, result_id: str, explanation_id: str, body: ExplanationReviewV2):
        return tutor.review(project_id, result_id, explanation_id, body)

    @router.get(
        "/analysis/results/{result_id}/interpretations/{explanation_id}/revisions",
        response_model=list[ResultExplanationV2],
    )
    def explanation_revisions(project_id: str, result_id: str, explanation_id: str):
        return tutor.explanation_history(project_id, result_id, explanation_id)

    @router.get("/analysis/results/{result_id}/export")
    def export(project_id: str, result_id: str, format: Literal["txt", "docx", "pdf"] = "txt"):
        payload = reports.export(project_id, result_id, format)
        media = {
            "txt": "text/plain; charset=utf-8",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "pdf": "application/pdf",
        }[format]
        return Response(
            payload,
            media_type=media,
            headers={
                "Content-Disposition": f'attachment; filename="resultado-{result_id}.{format}"',
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    return router
