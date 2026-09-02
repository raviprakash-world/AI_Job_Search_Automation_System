from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import ConflictError, NotFoundError
from app.db.base import utcnow
from app.db.models import (
    Application,
    ApplicationAnswer,
    ApplicationEvent,
    CandidateProfile,
    Job,
    JobMatch,
    ResumeVersion,
    User,
    UserPreference,
)
from app.schemas.applications import ApplicationAnswerUpdate, ApplicationCreate, ApplicationStatusUpdate, MarkSubmittedRequest
from app.services import application_answer_service, application_gates_service, cover_letter_service, profile_service
from app.services.matching_service import DEFAULT_SHORTLIST_THRESHOLDS

_APPLICATION_LOAD_OPTIONS = (
    selectinload(Application.events),
    selectinload(Application.answers),
    selectinload(Application.resume_version),
    selectinload(Application.cover_letter_version),
)

_RETRYABLE_STATUSES = {"error", "preparing", "ready_for_review"}


def record_transition(db: AsyncSession, application: Application, to_status: str, *, actor: str = "user", note: str | None = None) -> None:
    db.add(
        ApplicationEvent(
            application_id=application.id, from_status=application.status, to_status=to_status, actor=actor, note=note
        )
    )
    application.status = to_status


async def _get_job(db: AsyncSession, job_id: str) -> Job:
    job = await db.get(Job, job_id, options=[selectinload(Job.company)])
    if job is None:
        raise NotFoundError("Job not found")
    return job


async def _get_owned_resume_version(db: AsyncSession, user_id: str, resume_version_id: str) -> ResumeVersion:
    version = await db.get(
        ResumeVersion, resume_version_id, options=[selectinload(ResumeVersion.resume)], populate_existing=True
    )
    if version is None or version.resume.user_id != user_id:
        raise NotFoundError("Resume version not found")
    return version


async def _get_match_threshold(db: AsyncSession, user_id: str) -> float:
    pref = await db.scalar(select(UserPreference).where(UserPreference.user_id == user_id))
    thresholds = (pref.shortlist_thresholds if pref and pref.shortlist_thresholds else None) or DEFAULT_SHORTLIST_THRESHOLDS
    return float(thresholds.get("review", DEFAULT_SHORTLIST_THRESHOLDS["review"]))


async def _run_prepare_pipeline(
    db: AsyncSession,
    user: User,
    application: Application,
    *,
    job: Job,
    profile: CandidateProfile,
    resume_version: ResumeVersion,
) -> None:
    cover_letter_version = None
    if application.generate_cover_letter:
        cover_letter_version = await cover_letter_service.prepare_cover_letter(
            db, user, profile=profile, job=job, resume_version=resume_version
        )
        application.cover_letter_version_id = cover_letter_version.id

    # Preserve existing answers (especially ones the user has already reviewed/edited)
    # across re-prepares — only generate for questions that don't have one yet.
    kept_answers = [a for a in application.answers if a.question in application.custom_questions]
    for stale_answer in application.answers:
        if stale_answer not in kept_answers:
            await db.delete(stale_answer)
    already_answered = {a.question for a in kept_answers}
    missing_questions = [q for q in application.custom_questions if q not in already_answered]
    await db.flush()

    new_answers = await application_answer_service.generate_answers(
        db, user, application.id, profile=profile, job=job, questions=missing_questions
    )
    answers = kept_answers + new_answers

    job_match = await db.scalar(select(JobMatch).where(JobMatch.job_id == job.id, JobMatch.user_id == user.id))
    threshold = await _get_match_threshold(db, user.id)
    other_applications = list(
        await db.scalars(
            select(Application).where(
                Application.job_id == job.id, Application.user_id == user.id, Application.id != application.id
            )
        )
    )

    gate_report = application_gates_service.run_all_gates(
        job=job,
        other_applications_for_job=other_applications,
        profile=profile,
        resume_version=resume_version,
        job_match=job_match,
        match_threshold=threshold,
        override_low_match=application.override_low_match,
        cover_letter_version=cover_letter_version,
        answers=answers,
    )
    application.gate_report = gate_report.model_dump(mode="json")

    if gate_report.passed:
        record_transition(db, application, "ready_for_review", actor="system", note="All gates passed")
    else:
        failed_messages = "; ".join(g.message for g in gate_report.gates if not g.passed)
        record_transition(db, application, "error", actor="system", note=failed_messages)

    await db.commit()


async def create_application(db: AsyncSession, user: User, payload: ApplicationCreate) -> Application:
    job = await _get_job(db, payload.job_id)
    resume_version = await _get_owned_resume_version(db, user.id, payload.resume_version_id)
    profile = await profile_service.get_profile_by_user(db, user.id)

    application = Application(
        user_id=user.id,
        job_id=job.id,
        resume_version_id=resume_version.id,
        status="preparing",
        custom_questions=payload.custom_questions,
        generate_cover_letter=payload.generate_cover_letter,
        override_low_match=payload.override_low_match,
    )
    application.events = []
    application.answers = []
    db.add(application)
    await db.flush()
    db.add(ApplicationEvent(application_id=application.id, from_status=None, to_status="preparing", actor="user"))
    await db.flush()

    await _run_prepare_pipeline(db, user, application, job=job, profile=profile, resume_version=resume_version)
    return await get_owned_application(db, user.id, application.id)


async def retry_preparation(db: AsyncSession, user: User, application_id: str) -> Application:
    application = await get_owned_application(db, user.id, application_id)
    if application.status not in _RETRYABLE_STATUSES:
        raise ConflictError(f"Cannot re-prepare an application in status '{application.status}'")

    job = await _get_job(db, application.job_id)
    resume_version = await _get_owned_resume_version(db, user.id, application.resume_version_id)
    profile = await profile_service.get_profile_by_user(db, user.id)

    await _run_prepare_pipeline(db, user, application, job=job, profile=profile, resume_version=resume_version)
    return await get_owned_application(db, user.id, application.id)


async def approve_application(db: AsyncSession, user_id: str, application_id: str) -> Application:
    application = await get_owned_application(db, user_id, application_id)
    if application.status != "ready_for_review":
        raise ConflictError(f"Cannot approve an application in status '{application.status}'")
    record_transition(db, application, "approved", actor="user", note="Approved by user")
    await db.commit()
    return await get_owned_application(db, user_id, application_id)


_SUBMITTABLE_STATUSES = {"approved", "staged", "submission_blocked"}


async def mark_submitted(db: AsyncSession, user_id: str, application_id: str, payload: MarkSubmittedRequest) -> Application:
    application = await get_owned_application(db, user_id, application_id)
    if application.status not in _SUBMITTABLE_STATUSES:
        raise ConflictError(f"Cannot mark submitted from status '{application.status}' — approve it first")
    application.submitted_at = payload.submitted_at or utcnow()
    record_transition(db, application, "submitted", actor="user", note=payload.note)
    await db.commit()
    return await get_owned_application(db, user_id, application_id)


async def update_outcome(db: AsyncSession, user_id: str, application_id: str, payload: ApplicationStatusUpdate) -> Application:
    application = await get_owned_application(db, user_id, application_id)
    if application.status not in {"submitted", "interview", "rejected", "offer", "approved"}:
        raise ConflictError(f"Cannot record an outcome from status '{application.status}'")
    application.outcome_note = payload.note
    record_transition(db, application, payload.status, actor="user", note=payload.note)
    await db.commit()
    return await get_owned_application(db, user_id, application_id)


async def review_answer(
    db: AsyncSession, user_id: str, application_id: str, answer_id: str, payload: ApplicationAnswerUpdate
) -> ApplicationAnswer:
    application = await get_owned_application(db, user_id, application_id)
    answer = next((a for a in application.answers if a.id == answer_id), None)
    if answer is None:
        raise NotFoundError("Application answer not found")

    answer.answer = payload.answer
    answer.is_grounded = True
    answer.reviewed = True
    answer.flag_reason = None
    await db.commit()
    await db.refresh(answer)
    return answer


async def list_applications(db: AsyncSession, user_id: str) -> list[Application]:
    stmt = (
        select(Application)
        .where(Application.user_id == user_id)
        .options(*_APPLICATION_LOAD_OPTIONS, selectinload(Application.job).selectinload(Job.company))
    )
    return list(await db.scalars(stmt))


async def get_owned_application(db: AsyncSession, user_id: str, application_id: str) -> Application:
    stmt = (
        select(Application)
        .where(Application.id == application_id, Application.user_id == user_id)
        .options(*_APPLICATION_LOAD_OPTIONS, selectinload(Application.job).selectinload(Job.company))
        .execution_options(populate_existing=True)
    )
    application = await db.scalar(stmt)
    if application is None:
        raise NotFoundError("Application not found")
    return application


async def delete_application(db: AsyncSession, user_id: str, application_id: str) -> None:
    application = await get_owned_application(db, user_id, application_id)
    if application.status == "submitted" or application.submitted_at is not None:
        raise ConflictError("A submitted application record cannot be deleted, only tracked further")
    if application.staged_screenshot_path:
        Path(application.staged_screenshot_path).unlink(missing_ok=True)
    await db.delete(application)
    await db.commit()
