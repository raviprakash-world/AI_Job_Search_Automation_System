from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import NotFoundError
from app.db.base import utcnow
from app.db.models import AutomationRun, AutomationStep


async def start_run(db: AsyncSession, *, run_type: str, triggered_by: str, user_id: str | None = None) -> AutomationRun:
    run = AutomationRun(run_type=run_type, status="running", triggered_by=triggered_by, user_id=user_id)
    run.steps = []  # avoid a lazy-load on this fresh object (see resume_service.py for the same pattern)
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def add_step(
    db: AsyncSession, run: AutomationRun, *, step_name: str, status: str, detail: dict | None = None, error: str | None = None
) -> AutomationStep:
    step = AutomationStep(run_id=run.id, step_name=step_name, status=status, detail=detail or {}, error=error)
    db.add(step)
    await db.commit()
    return step


async def complete_run(
    db: AsyncSession, run: AutomationRun, *, status: str, summary: dict | None = None, error: str | None = None
) -> AutomationRun:
    run.status = status
    run.completed_at = utcnow()
    run.summary = summary or {}
    run.error = error
    await db.commit()
    await db.refresh(run)
    return run


async def list_runs(db: AsyncSession, *, user_id: str | None, run_type: str | None = None) -> list[AutomationRun]:
    stmt = select(AutomationRun).where(AutomationRun.user_id == user_id).order_by(AutomationRun.started_at.desc())
    if run_type:
        stmt = stmt.where(AutomationRun.run_type == run_type)
    return list(await db.scalars(stmt))


async def get_owned_run(db: AsyncSession, user_id: str, run_id: str) -> AutomationRun:
    stmt = (
        select(AutomationRun)
        .where(AutomationRun.id == run_id, AutomationRun.user_id == user_id)
        .options(selectinload(AutomationRun.steps))
        .execution_options(populate_existing=True)
    )
    run = await db.scalar(stmt)
    if run is None:
        raise NotFoundError("Automation run not found")
    return run
