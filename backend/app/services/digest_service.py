from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.base import utcnow
from app.db.models import AutomationRun, Job, JobMatch, Notification, User
from app.services import automation_run_service

_DEFAULT_LOOKBACK_DAYS = 7
_TOP_MATCHES_IN_BODY = 5


async def _target_users(db: AsyncSession, user_id: str | None) -> list[User]:
    if user_id:
        user = await db.get(User, user_id)
        return [user] if user else []
    return list(await db.scalars(select(User)))


async def _since_last_digest(db: AsyncSession, user_id: str):
    last = await db.scalar(
        select(Notification)
        .where(Notification.user_id == user_id, Notification.type == "digest")
        .order_by(Notification.created_at.desc())
    )
    if last:
        return last.created_at
    return utcnow() - timedelta(days=_DEFAULT_LOOKBACK_DAYS)


def _format_digest_body(matches: list[JobMatch]) -> str:
    lines = []
    for m in matches[:_TOP_MATCHES_IN_BODY]:
        company = m.job.company.name if m.job.company else "Unknown company"
        lines.append(f"{m.job.title} at {company} — {m.fit_score:.0f}% match")
    return "\n".join(lines)


async def generate_digests(db: AsyncSession, *, user_id: str | None = None) -> AutomationRun:
    """Creates one digest Notification per user summarizing job matches new
    since their last digest — skips users with nothing new rather than sending
    an empty digest (section 22: avoid duplicate/noise notifications)."""
    run = await automation_run_service.start_run(
        db, run_type="digest", triggered_by="user" if user_id else "scheduler", user_id=user_id
    )

    users = await _target_users(db, user_id)
    totals = {"users_checked": len(users), "digests_created": 0, "users_skipped": 0}

    for user in users:
        since = await _since_last_digest(db, user.id)
        stmt = (
            select(JobMatch)
            .where(JobMatch.user_id == user.id, JobMatch.computed_at > since)
            .options(selectinload(JobMatch.job).selectinload(Job.company))
            .order_by(JobMatch.fit_score.desc())
        )
        new_matches = list(await db.scalars(stmt))

        if not new_matches:
            await automation_run_service.add_step(
                db, run, step_name=f"user:{user.email}", status="success", detail={"new_matches": 0, "skipped": True}
            )
            totals["users_skipped"] += 1
            continue

        notification = Notification(
            user_id=user.id,
            type="digest",
            title=f"{len(new_matches)} new job match{'es' if len(new_matches) != 1 else ''}",
            body=_format_digest_body(new_matches),
            data={"job_ids": [m.job_id for m in new_matches], "match_count": len(new_matches)},
        )
        db.add(notification)
        await db.commit()

        await automation_run_service.add_step(
            db, run, step_name=f"user:{user.email}", status="success", detail={"new_matches": len(new_matches)}
        )
        totals["digests_created"] += 1

    return await automation_run_service.complete_run(db, run, status="completed", summary=totals)
