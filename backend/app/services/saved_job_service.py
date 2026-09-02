from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.db.models import Job, SavedJob
from app.schemas.jobs import JobActionRequest
from app.services.audit_service import record_audit

_ACTION_TO_STATUS = {
    "shortlist": "shortlisted",
    "save_for_later": "saved_for_later",
    "reject": "rejected",
    "ignore": "ignored",
}


async def apply_action(db: AsyncSession, user_id: str, job_id: str, payload: JobActionRequest) -> SavedJob:
    job = await db.get(Job, job_id)
    if job is None:
        raise NotFoundError("Job not found")

    saved = await db.scalar(select(SavedJob).where(SavedJob.job_id == job_id, SavedJob.user_id == user_id))
    status = _ACTION_TO_STATUS[payload.action]
    before = {"status": saved.status} if saved else None

    if saved is None:
        saved = SavedJob(job_id=job_id, user_id=user_id, status=status, reason=payload.reason)
        db.add(saved)
    else:
        saved.status = status
        saved.reason = payload.reason

    await record_audit(
        db,
        user_id=user_id,
        entity_type="saved_job",
        entity_id=job_id,
        action=payload.action,
        before=before,
        after={"status": status, "reason": payload.reason},
    )
    await db.commit()
    await db.refresh(saved)
    return saved
