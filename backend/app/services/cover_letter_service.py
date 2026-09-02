from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.cover_letter_agent import generate_cover_letter_content
from app.core.config import get_settings
from app.core.errors import ExtractionValidationError
from app.db.models import CandidateProfile, CoverLetter, CoverLetterVersion, Job, ResumeVersion, User
from app.services.cover_letter_qa_service import run_qa
from app.services.cover_letter_rendering_service import render_cover_letter_docx


async def _get_or_create_cover_letter(
    db: AsyncSession, user: User, job: Job, resume_version: ResumeVersion
) -> CoverLetter:
    stmt = (
        select(CoverLetter)
        .where(CoverLetter.user_id == user.id, CoverLetter.job_id == job.id)
        .options(selectinload(CoverLetter.versions))
    )
    cover_letter = await db.scalar(stmt)
    if cover_letter is not None:
        cover_letter.resume_version_id = resume_version.id
        return cover_letter

    company_name = job.company.name if job.company else job.title
    cover_letter = CoverLetter(
        user_id=user.id,
        job_id=job.id,
        resume_version_id=resume_version.id,
        label=f"Cover letter for {job.title} at {company_name}",
    )
    cover_letter.versions = []  # avoid a lazy-load on the fresh object (same fix as resume_service.py)
    db.add(cover_letter)
    await db.flush()
    return cover_letter


async def prepare_cover_letter(
    db: AsyncSession, user: User, *, profile: CandidateProfile, job: Job, resume_version: ResumeVersion
) -> CoverLetterVersion:
    cover_letter = await _get_or_create_cover_letter(db, user, job, resume_version)
    next_version_number = max((v.version_number for v in cover_letter.versions), default=0) + 1

    company_name = job.company.name if job.company else job.title

    try:
        generation, ai_request = await generate_cover_letter_content(
            db, user_id=user.id, profile=profile, job=job, resume_version=resume_version
        )
    except ExtractionValidationError as exc:
        version = CoverLetterVersion(
            cover_letter_id=cover_letter.id,
            version_number=next_version_number,
            status="generation_failed",
            body_text="",
            qa_report={"errors": [str(exc)], "warnings": [], "matched_keywords": [], "missing_keywords": [], "word_count": 0},
        )
        db.add(version)
        await db.commit()
        await db.refresh(version)
        return version

    settings = get_settings()
    docx_path = settings.resume_storage_path.parent / "cover_letters" / cover_letter.id / f"v{next_version_number}.docx"
    render_cover_letter_docx(
        full_name=profile.full_name,
        email=user.email,
        phone=profile.phone,
        company_name=company_name,
        body_text=generation.body_text,
        destination=docx_path,
    )

    qa_report = run_qa(
        profile=profile,
        generation=generation,
        docx_path=docx_path,
        job=job,
        full_name=profile.full_name,
        email=user.email,
        phone=profile.phone,
        company_name=company_name,
    )
    status = "qa_failed" if qa_report.errors else "ready"

    version = CoverLetterVersion(
        cover_letter_id=cover_letter.id,
        version_number=next_version_number,
        status=status,
        body_text=generation.body_text,
        file_path=str(docx_path),
        qa_report=qa_report.model_dump(mode="json"),
        ai_request_id=ai_request.id,
    )
    db.add(version)
    await db.commit()
    await db.refresh(version)
    return version
