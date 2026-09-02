from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AutomationRun, JobSource, User
from app.services import automation_run_service, job_pipeline_service


async def run_discovery(db: AsyncSession, *, user_id: str | None = None) -> AutomationRun:
    """Runs discovery across active job sources.

    Scoped to one user's sources for a manual trigger, or every user's sources
    for the scheduled system-wide run. One failing source is recorded as a
    failed step and does not abort the rest of the run (section 30: recoverable
    per-source failures, not an all-or-nothing crash).
    """
    run = await automation_run_service.start_run(
        db, run_type="discovery", triggered_by="user" if user_id else "scheduler", user_id=user_id
    )

    stmt = select(JobSource).where(JobSource.is_active.is_(True))
    if user_id:
        stmt = stmt.where(JobSource.user_id == user_id)
    sources = list(await db.scalars(stmt))

    totals = {
        "sources": len(sources),
        "fetched": 0,
        "new_jobs": 0,
        "updated_jobs": 0,
        "duplicates_merged": 0,
        "matched": 0,
        "failed": 0,
    }

    for source in sources:
        step_name = f"{source.provider}:{source.company_slug}"
        owner = await db.get(User, source.user_id)
        try:
            result = await job_pipeline_service.run_discovery_and_match(db, owner, source)
            await automation_run_service.add_step(
                db, run, step_name=step_name, status="success", detail=result.model_dump(mode="json")
            )
            totals["fetched"] += result.fetched
            totals["new_jobs"] += result.new_jobs
            totals["updated_jobs"] += result.updated_jobs
            totals["duplicates_merged"] += result.duplicates_merged
            totals["matched"] += result.matched
        except Exception as exc:  # noqa: BLE001 - one source failing must not abort the whole run
            await automation_run_service.add_step(db, run, step_name=step_name, status="failed", error=str(exc))
            totals["failed"] += 1

    overall_status = "failed" if sources and totals["failed"] == len(sources) else "completed"
    return await automation_run_service.complete_run(db, run, status=overall_status, summary=totals)
