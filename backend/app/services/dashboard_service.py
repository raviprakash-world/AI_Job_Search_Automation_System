from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    Application,
    ApplicationAnswer,
    ApplicationEvent,
    AuditLog,
    AutomationRun,
    CoverLetter,
    JobMatch,
    Resume,
    SavedJob,
)
from app.schemas.dashboard import ActivityItem, AlertItem, AlertLink, OverviewOut, PipelineOut, SummaryOut

_RESPONSE_STATUSES = ("interview", "offer", "rejected")


async def _distinct_applications_reaching(db: AsyncSession, user_id: str, statuses: tuple[str, ...]) -> int:
    stmt = (
        select(func.count(func.distinct(ApplicationEvent.application_id)))
        .join(Application, Application.id == ApplicationEvent.application_id)
        .where(Application.user_id == user_id, ApplicationEvent.to_status.in_(statuses))
    )
    return (await db.scalar(stmt)) or 0


async def get_overview(db: AsyncSession, user_id: str) -> OverviewOut:
    jobs_discovered = (
        await db.scalar(select(func.count(func.distinct(JobMatch.job_id))).where(JobMatch.user_id == user_id))
    ) or 0
    jobs_shortlisted = (
        await db.scalar(
            select(func.count())
            .select_from(SavedJob)
            .where(SavedJob.user_id == user_id, SavedJob.status == "shortlisted")
        )
    ) or 0
    prepared = (await db.scalar(select(func.count()).select_from(Application).where(Application.user_id == user_id))) or 0
    applications_submitted = (
        await db.scalar(
            select(func.count())
            .select_from(Application)
            .where(Application.user_id == user_id, Application.submitted_at.is_not(None))
        )
    ) or 0

    interviews = await _distinct_applications_reaching(db, user_id, ("interview",))
    offers = await _distinct_applications_reaching(db, user_id, ("offer",))
    rejections = await _distinct_applications_reaching(db, user_id, ("rejected",))
    responded = await _distinct_applications_reaching(db, user_id, _RESPONSE_STATUSES)

    rejection_rate = rejections / applications_submitted if applications_submitted else 0.0
    response_rate = responded / applications_submitted if applications_submitted else 0.0

    summary = SummaryOut(
        jobs_discovered=jobs_discovered,
        jobs_shortlisted=jobs_shortlisted,
        applications_submitted=applications_submitted,
        interviews=interviews,
        offers=offers,
        rejections=rejections,
        rejection_rate=round(rejection_rate, 3),
        response_rate=round(response_rate, 3),
    )
    pipeline = PipelineOut(
        discovered=jobs_discovered,
        shortlisted=jobs_shortlisted,
        prepared=prepared,
        applied=applications_submitted,
        interview=interviews,
        offer=offers,
    )
    return OverviewOut(summary=summary, pipeline=pipeline)


async def get_activity(db: AsyncSession, user_id: str, limit: int = 20) -> list[ActivityItem]:
    items: list[ActivityItem] = []

    audit_rows = await db.scalars(
        select(AuditLog).where(AuditLog.user_id == user_id).order_by(AuditLog.created_at.desc()).limit(limit)
    )
    for entry in audit_rows:
        items.append(
            ActivityItem(
                type="audit",
                title=f"{entry.action.replace('_', ' ').title()}: {entry.entity_type.replace('_', ' ')}",
                detail=f"by {entry.actor}",
                status="info",
                created_at=entry.created_at,
            )
        )

    event_rows = await db.scalars(
        select(ApplicationEvent)
        .join(Application, Application.id == ApplicationEvent.application_id)
        .where(Application.user_id == user_id)
        .options(selectinload(ApplicationEvent.application).selectinload(Application.job))
        .order_by(ApplicationEvent.created_at.desc())
        .limit(limit)
    )
    for event in event_rows:
        job_title = event.application.job.title if event.application.job else "a job"
        items.append(
            ActivityItem(
                type="application_event",
                title=f"Application {event.to_status.replace('_', ' ')}: {job_title}",
                detail=event.note,
                status="error" if event.to_status == "error" else "success",
                created_at=event.created_at,
            )
        )

    run_rows = await db.scalars(
        select(AutomationRun)
        .where(AutomationRun.user_id == user_id)
        .order_by(AutomationRun.started_at.desc())
        .limit(limit)
    )
    for run in run_rows:
        summary_text = ", ".join(f"{k}: {v}" for k, v in run.summary.items()) if run.summary else None
        items.append(
            ActivityItem(
                type="automation_run",
                title=f"{run.run_type.replace('_', ' ').title()} run {run.status}",
                detail=summary_text,
                status="error" if run.status == "failed" else ("info" if run.status == "running" else "success"),
                created_at=run.started_at,
            )
        )

    items.sort(key=lambda i: i.created_at, reverse=True)
    return items[:limit]


async def get_alerts(db: AsyncSession, user_id: str) -> list[AlertItem]:
    alerts: list[AlertItem] = []

    failed_applications = await db.scalars(
        select(Application)
        .where(Application.user_id == user_id, Application.status == "error")
        .options(selectinload(Application.job))
    )
    for application in failed_applications:
        job_title = application.job.title if application.job else "a job"
        failed_gates = [g["message"] for g in application.gate_report.get("gates", []) if not g.get("passed")]
        detail = "; ".join(failed_gates) if failed_gates else "Preparation failed"
        alerts.append(
            AlertItem(
                type="application_error",
                title=f"Application needs attention: {job_title}",
                detail=detail,
                link=AlertLink(kind="application", id=application.id),
                created_at=application.updated_at,
            )
        )

    resumes = await db.scalars(
        select(Resume).where(Resume.user_id == user_id).options(selectinload(Resume.versions))
    )
    for resume in resumes:
        latest = resume.versions[-1] if resume.versions else None
        if latest and latest.status in ("generation_failed", "qa_failed"):
            errors = latest.qa_report.get("errors", []) if latest.qa_report else []
            alerts.append(
                AlertItem(
                    type="resume_failed",
                    title=f"Resume needs attention: {resume.label}",
                    detail="; ".join(errors) if errors else f"Status: {latest.status}",
                    link=AlertLink(kind="resume", id=resume.id),
                    created_at=latest.generated_at,
                )
            )

    cover_letters = await db.scalars(
        select(CoverLetter).where(CoverLetter.user_id == user_id).options(selectinload(CoverLetter.versions))
    )
    for cover_letter in cover_letters:
        latest = cover_letter.versions[-1] if cover_letter.versions else None
        if latest and latest.status in ("generation_failed", "qa_failed"):
            errors = latest.qa_report.get("errors", []) if latest.qa_report else []
            alerts.append(
                AlertItem(
                    type="cover_letter_failed",
                    title=f"Cover letter needs attention: {cover_letter.label}",
                    detail="; ".join(errors) if errors else f"Status: {latest.status}",
                    link=AlertLink(kind="cover_letter", id=cover_letter.id),
                    created_at=latest.generated_at,
                )
            )

    flagged_answers = await db.scalars(
        select(ApplicationAnswer)
        .join(Application, Application.id == ApplicationAnswer.application_id)
        .where(Application.user_id == user_id, ApplicationAnswer.is_grounded.is_(False), ApplicationAnswer.reviewed.is_(False))
        .options(selectinload(ApplicationAnswer.application).selectinload(Application.job))
    )
    for answer in flagged_answers:
        job_title = answer.application.job.title if answer.application.job else "a job"
        alerts.append(
            AlertItem(
                type="answer_flagged",
                title=f"Application answer needs your input: {job_title}",
                detail=answer.flag_reason or answer.question,
                link=AlertLink(kind="application", id=answer.application_id),
                created_at=answer.updated_at,
            )
        )

    alerts.sort(key=lambda a: a.created_at, reverse=True)
    return alerts
