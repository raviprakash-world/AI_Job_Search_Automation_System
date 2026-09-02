from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import async_session_factory
from app.services import digest_service, discovery_automation_service, stale_application_service

logger = get_logger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def _run_discovery_job() -> None:
    async with async_session_factory() as db:
        try:
            run = await discovery_automation_service.run_discovery(db, user_id=None)
            logger.info("scheduled_discovery_completed", run_id=run.id, summary=run.summary)
        except Exception as exc:  # noqa: BLE001 - a scheduled job must never crash the process
            logger.error("scheduled_discovery_failed", error=str(exc))


async def _run_digest_job() -> None:
    async with async_session_factory() as db:
        try:
            run = await digest_service.generate_digests(db, user_id=None)
            logger.info("scheduled_digest_completed", run_id=run.id, summary=run.summary)
        except Exception as exc:  # noqa: BLE001
            logger.error("scheduled_digest_failed", error=str(exc))


async def _run_stale_check_job() -> None:
    async with async_session_factory() as db:
        try:
            run = await stale_application_service.check_stale_applications(db, user_id=None)
            logger.info("scheduled_stale_check_completed", run_id=run.id, summary=run.summary)
        except Exception as exc:  # noqa: BLE001
            logger.error("scheduled_stale_check_failed", error=str(exc))


def start_scheduler() -> AsyncIOScheduler | None:
    global _scheduler
    settings = get_settings()
    if not settings.enable_scheduler:
        logger.info("scheduler_disabled")
        return None

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _run_discovery_job,
        IntervalTrigger(minutes=settings.discovery_interval_minutes),
        id="discovery",
        replace_existing=True,
    )
    scheduler.add_job(
        _run_digest_job, CronTrigger(hour=settings.digest_hour_utc, minute=0), id="digest", replace_existing=True
    )
    scheduler.add_job(
        _run_stale_check_job,
        CronTrigger(hour=settings.stale_check_hour_utc, minute=0),
        id="stale_check",
        replace_existing=True,
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info(
        "scheduler_started",
        discovery_interval_minutes=settings.discovery_interval_minutes,
        digest_hour_utc=settings.digest_hour_utc,
        stale_check_hour_utc=settings.stale_check_hour_utc,
    )
    return scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
