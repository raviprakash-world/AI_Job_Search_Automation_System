from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.db.base import utcnow
from app.db.models import Application, AutomationRun, Job, Notification, User
from app.services import automation_run_service

_STALE_STATUSES = ("submitted", "approved", "ready_for_review")


def _as_aware(value: datetime) -> datetime:
    """SQLite doesn't preserve tzinfo on round-trip even for DateTime(timezone=True)
    columns, unlike Postgres — normalize so comparisons/arithmetic work on both."""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


async def _target_users(db: AsyncSession, user_id: str | None) -> list[User]:
    if user_id:
        user = await db.get(User, user_id)
        return [user] if user else []
    return list(await db.scalars(select(User)))


def already_flagged_since_update(
    existing_notifications: list[Notification], application_id: str, updated_at: datetime
) -> bool:
    """True if this application already has a stale-application notification
    created after its last update — avoids re-flagging the same stale state
    on every scheduled run."""
    updated_at = _as_aware(updated_at)
    return any(
        n.data.get("application_id") == application_id and _as_aware(n.created_at) > updated_at
        for n in existing_notifications
    )


async def check_stale_applications(db: AsyncSession, *, user_id: str | None = None) -> AutomationRun:
    """Flags applications sitting too long in an active status with a
    recommendation to follow up — never sends anything to a recruiter or any
    external party, per spec section 21's explicit 'recommend, don't auto-send'
    rule. Re-checking an already-flagged, unchanged application is a no-op."""
    settings = get_settings()
    run = await automation_run_service.start_run(
        db, run_type="stale_check", triggered_by="user" if user_id else "scheduler", user_id=user_id
    )

    cutoff = utcnow() - timedelta(days=settings.stale_application_days)

    users = await _target_users(db, user_id)
    totals = {"applications_checked": 0, "flagged": 0}

    for user in users:
        stmt = (
            select(Application)
            .where(
                Application.user_id == user.id,
                Application.status.in_(_STALE_STATUSES),
                Application.updated_at < cutoff,
            )
            .options(selectinload(Application.job).selectinload(Job.company))
        )
        stale_applications = list(await db.scalars(stmt))
        if not stale_applications:
            continue

        existing_notifications = list(
            await db.scalars(
                select(Notification).where(Notification.user_id == user.id, Notification.type == "stale_application")
            )
        )

        for application in stale_applications:
            totals["applications_checked"] += 1
            updated_at = _as_aware(application.updated_at)
            if already_flagged_since_update(existing_notifications, application.id, updated_at):
                continue

            company = application.job.company.name if application.job.company else "the company"
            days_idle = (utcnow() - updated_at).days
            notification = Notification(
                user_id=user.id,
                type="stale_application",
                title=f"Consider following up: {application.job.title} at {company}",
                body=(
                    f"This application has been in '{application.status.replace('_', ' ')}' for {days_idle} days "
                    "with no update. Consider following up, if appropriate."
                ),
                data={"application_id": application.id, "job_id": application.job_id, "status": application.status},
            )
            db.add(notification)
            await db.commit()
            await automation_run_service.add_step(
                db,
                run,
                step_name=f"application:{application.id}",
                status="success",
                detail={"days_idle": days_idle, "status": application.status},
            )
            totals["flagged"] += 1

    return await automation_run_service.complete_run(db, run, status="completed", summary=totals)
