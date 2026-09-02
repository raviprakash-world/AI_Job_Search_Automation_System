from fastapi import APIRouter, Depends, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.errors import NotFoundError
from app.db.models import Application, User
from app.db.session import get_db
from app.schemas.applications import (
    ApplicationAnswerOut,
    ApplicationAnswerUpdate,
    ApplicationCreate,
    ApplicationDetailOut,
    ApplicationEventOut,
    ApplicationOut,
    ApplicationStatusUpdate,
    MarkSubmittedRequest,
)
from app.schemas.cover_letters import CoverLetterVersionOut
from app.schemas.resumes import ResumeVersionOut
from app.services import application_service, application_staging_service

router = APIRouter(prefix="/applications", tags=["applications"])


def _to_out(application: Application) -> ApplicationOut:
    return ApplicationOut(
        id=application.id,
        job_id=application.job_id,
        job_title=application.job.title,
        company_name=application.job.company.name if application.job.company else None,
        status=application.status,
        gate_report=application.gate_report,
        submitted_at=application.submitted_at,
        outcome_note=application.outcome_note,
        staging_notes=application.staging_notes,
        has_staged_screenshot=bool(application.staged_screenshot_path),
        created_at=application.created_at,
    )


def _to_detail_out(application: Application) -> ApplicationDetailOut:
    base = _to_out(application)
    return ApplicationDetailOut(
        **base.model_dump(),
        resume_version=ResumeVersionOut.model_validate(application.resume_version) if application.resume_version else None,
        cover_letter_version=(
            CoverLetterVersionOut.model_validate(application.cover_letter_version)
            if application.cover_letter_version
            else None
        ),
        answers=[ApplicationAnswerOut.model_validate(a) for a in application.answers],
        events=[ApplicationEventOut.model_validate(e) for e in application.events],
    )


@router.post("", response_model=ApplicationDetailOut, status_code=status.HTTP_201_CREATED)
async def create_application(
    payload: ApplicationCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    application = await application_service.create_application(db, current_user, payload)
    return _to_detail_out(application)


@router.get("", response_model=list[ApplicationOut])
async def list_applications(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    applications = await application_service.list_applications(db, current_user.id)
    return [_to_out(a) for a in applications]


@router.get("/{application_id}", response_model=ApplicationDetailOut)
async def get_application(
    application_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    application = await application_service.get_owned_application(db, current_user.id, application_id)
    return _to_detail_out(application)


@router.post("/{application_id}/retry-preparation", response_model=ApplicationDetailOut)
async def retry_preparation(
    application_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    application = await application_service.retry_preparation(db, current_user, application_id)
    return _to_detail_out(application)


@router.post("/{application_id}/approve", response_model=ApplicationDetailOut)
async def approve_application(
    application_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    application = await application_service.approve_application(db, current_user.id, application_id)
    return _to_detail_out(application)


@router.post("/{application_id}/stage", response_model=ApplicationDetailOut)
async def stage_application(
    application_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    application = await application_staging_service.stage_application(db, current_user, application_id)
    return _to_detail_out(application)


@router.get("/{application_id}/staging-screenshot")
async def get_staging_screenshot(
    application_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    application = await application_service.get_owned_application(db, current_user.id, application_id)
    if not application.staged_screenshot_path:
        raise NotFoundError("No staging screenshot available for this application")
    return FileResponse(application.staged_screenshot_path, media_type="image/png", filename="staged_application.png")


@router.post("/{application_id}/mark-submitted", response_model=ApplicationDetailOut)
async def mark_submitted(
    application_id: str,
    payload: MarkSubmittedRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    application = await application_service.mark_submitted(db, current_user.id, application_id, payload)
    return _to_detail_out(application)


@router.post("/{application_id}/status", response_model=ApplicationDetailOut)
async def update_outcome(
    application_id: str,
    payload: ApplicationStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    application = await application_service.update_outcome(db, current_user.id, application_id, payload)
    return _to_detail_out(application)


@router.put("/{application_id}/answers/{answer_id}", response_model=ApplicationAnswerOut)
async def update_answer(
    application_id: str,
    answer_id: str,
    payload: ApplicationAnswerUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    answer = await application_service.review_answer(db, current_user.id, application_id, answer_id, payload)
    return answer


@router.get("/{application_id}/cover-letter/download")
async def download_cover_letter(
    application_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    application = await application_service.get_owned_application(db, current_user.id, application_id)
    if application.cover_letter_version is None or not application.cover_letter_version.file_path:
        raise NotFoundError("This application has no generated cover letter file")
    return FileResponse(
        application.cover_letter_version.file_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="cover_letter.docx",
    )


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application(
    application_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    await application_service.delete_application(db, current_user.id, application_id)
