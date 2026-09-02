from fastapi import APIRouter, Depends, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.errors import NotFoundError
from app.db.models import Resume, ResumeVersion, User
from app.db.session import get_db
from app.schemas.resumes import ResumeCreate, ResumeDetailOut, ResumeOut, ResumeVersionOut
from app.services import resume_service

router = APIRouter(prefix="/resumes", tags=["resumes"])


def _latest_version(resume: Resume) -> ResumeVersion | None:
    return resume.versions[-1] if resume.versions else None


def _to_resume_out(resume: Resume) -> ResumeOut:
    latest = _latest_version(resume)
    return ResumeOut(
        id=resume.id,
        job_id=resume.job_id,
        label=resume.label,
        created_at=resume.created_at,
        latest_version=ResumeVersionOut.model_validate(latest) if latest else None,
    )


def _to_resume_detail_out(resume: Resume) -> ResumeDetailOut:
    base = _to_resume_out(resume)
    return ResumeDetailOut(**base.model_dump(), versions=[ResumeVersionOut.model_validate(v) for v in resume.versions])


@router.post("", response_model=ResumeDetailOut, status_code=status.HTTP_201_CREATED)
async def create_resume(
    payload: ResumeCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    resume = await resume_service.create_resume(db, current_user, payload)
    return _to_resume_detail_out(resume)


@router.get("", response_model=list[ResumeOut])
async def list_resumes(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    resumes = await resume_service.list_resumes(db, current_user.id)
    return [_to_resume_out(r) for r in resumes]


@router.get("/{resume_id}", response_model=ResumeDetailOut)
async def get_resume(resume_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    resume = await resume_service.get_owned_resume(db, current_user.id, resume_id)
    return _to_resume_detail_out(resume)


@router.post("/{resume_id}/regenerate", response_model=ResumeDetailOut)
async def regenerate_resume(
    resume_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    resume = await resume_service.regenerate_resume(db, current_user, resume_id)
    return _to_resume_detail_out(resume)


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resume(resume_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await resume_service.delete_resume(db, current_user.id, resume_id)


@router.get("/{resume_id}/versions/{version_id}/download")
async def download_resume_version(
    resume_id: str,
    version_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    version = await resume_service.get_owned_version(db, current_user.id, resume_id, version_id)
    if not version.file_path:
        raise NotFoundError("This resume version has no generated file")
    filename = f"resume_v{version.version_number}.docx"
    return FileResponse(
        version.file_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename,
    )
