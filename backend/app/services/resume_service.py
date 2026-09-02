from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.resume_agent import generate_resume_content
from app.core.config import get_settings
from app.core.errors import ExtractionValidationError, NotFoundError
from app.db.models import Job, Resume, ResumeVersion, User
from app.schemas.resumes import ResumeCreate
from app.services import profile_service
from app.services.resume_generation_service import assemble_structured_content, require_generatable_profile
from app.services.resume_qa_service import run_qa
from app.services.resume_rendering_service import render_resume_docx

_RESUME_LOAD_OPTIONS = (selectinload(Resume.versions),)


async def _get_job(db: AsyncSession, job_id: str | None) -> Job | None:
    if not job_id:
        return None
    job = await db.get(Job, job_id, options=[selectinload(Job.company)])
    if job is None:
        raise NotFoundError("Target job not found")
    return job


async def _generate_version(db: AsyncSession, user: User, resume: Resume) -> ResumeVersion:
    profile = await profile_service.get_profile_by_user(db, user.id)
    require_generatable_profile(profile)
    job = await _get_job(db, resume.job_id)

    next_version_number = max((v.version_number for v in resume.versions), default=0) + 1

    try:
        generation, ai_request = await generate_resume_content(db, user_id=user.id, profile=profile, job=job)
    except ExtractionValidationError as exc:
        version = ResumeVersion(
            resume_id=resume.id,
            version_number=next_version_number,
            status="generation_failed",
            structured_content={},
            qa_report={"errors": [str(exc)], "warnings": [], "matched_keywords": [], "missing_keywords": [], "word_count": 0},
        )
        db.add(version)
        await db.commit()
        await db.refresh(version)
        return version

    content = assemble_structured_content(
        profile,
        generation,
        email=user.email,
        include_projects=resume.include_projects,
        include_certifications=resume.include_certifications,
    )

    settings = get_settings()
    docx_path = settings.resume_storage_path / resume.id / f"v{next_version_number}.docx"
    render_resume_docx(content, docx_path)

    qa_report = run_qa(profile=profile, content=content, docx_path=docx_path, job=job)
    status = "qa_failed" if qa_report.errors else "ready"

    version = ResumeVersion(
        resume_id=resume.id,
        version_number=next_version_number,
        status=status,
        structured_content=content.model_dump(mode="json"),
        file_path=str(docx_path),
        qa_report=qa_report.model_dump(mode="json"),
        ai_request_id=ai_request.id,
    )
    db.add(version)
    await db.commit()
    await db.refresh(version)
    return version


def _default_label(job: Job | None) -> str:
    if job is None:
        return "General resume"
    if job.company:
        return f"Tailored for {job.title} at {job.company.name}"
    return f"Tailored for {job.title}"


async def create_resume(db: AsyncSession, user: User, payload: ResumeCreate) -> Resume:
    job = await _get_job(db, payload.job_id)
    label = payload.label or _default_label(job)

    resume = Resume(
        user_id=user.id,
        job_id=payload.job_id,
        label=label,
        include_projects=payload.include_projects,
        include_certifications=payload.include_certifications,
    )
    resume.versions = []  # mark the collection as loaded so _generate_version can read it without a lazy-load
    db.add(resume)
    await db.flush()

    await _generate_version(db, user, resume)
    await db.refresh(resume, attribute_names=["versions"])
    return resume


async def regenerate_resume(db: AsyncSession, user: User, resume_id: str) -> Resume:
    resume = await get_owned_resume(db, user.id, resume_id)
    await _generate_version(db, user, resume)
    await db.refresh(resume, attribute_names=["versions"])
    return resume


async def list_resumes(db: AsyncSession, user_id: str) -> list[Resume]:
    stmt = select(Resume).where(Resume.user_id == user_id).options(*_RESUME_LOAD_OPTIONS)
    result = await db.scalars(stmt)
    return list(result)


async def get_owned_resume(db: AsyncSession, user_id: str, resume_id: str) -> Resume:
    stmt = select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id).options(*_RESUME_LOAD_OPTIONS)
    resume = await db.scalar(stmt)
    if resume is None:
        raise NotFoundError("Resume not found")
    return resume


async def get_owned_version(db: AsyncSession, user_id: str, resume_id: str, version_id: str) -> ResumeVersion:
    resume = await get_owned_resume(db, user_id, resume_id)
    version = next((v for v in resume.versions if v.id == version_id), None)
    if version is None:
        raise NotFoundError("Resume version not found")
    return version


async def delete_resume(db: AsyncSession, user_id: str, resume_id: str) -> None:
    resume = await get_owned_resume(db, user_id, resume_id)
    for version in resume.versions:
        if version.file_path:
            Path(version.file_path).unlink(missing_ok=True)
    await db.delete(resume)
    await db.commit()
