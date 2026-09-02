from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.profile import (
    CandidateProfileOut,
    CandidateProfileUpdate,
    CertificationIn,
    CertificationOut,
    EducationIn,
    EducationOut,
    ExperienceIn,
    ExperienceOut,
    ProjectIn,
    ProjectOut,
    SkillIn,
    SkillOut,
)
from app.services import profile_service

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=CandidateProfileOut)
async def get_profile(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await profile_service.get_profile_by_user(db, current_user.id)


@router.put("", response_model=CandidateProfileOut)
async def put_profile(
    payload: CandidateProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await profile_service.update_profile(db, current_user.id, payload)


@router.post("/experiences", response_model=ExperienceOut, status_code=status.HTTP_201_CREATED)
async def create_experience(
    payload: ExperienceIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await profile_service.add_experience(db, current_user.id, payload)


@router.delete("/experiences/{experience_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_experience(
    experience_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    await profile_service.delete_experience(db, current_user.id, experience_id)


@router.post("/education", response_model=EducationOut, status_code=status.HTTP_201_CREATED)
async def create_education(
    payload: EducationIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await profile_service.add_education(db, current_user.id, payload)


@router.delete("/education/{education_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_education(
    education_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    await profile_service.delete_education(db, current_user.id, education_id)


@router.post("/skills", response_model=SkillOut, status_code=status.HTTP_201_CREATED)
async def create_skill(
    payload: SkillIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await profile_service.add_skill(db, current_user.id, payload)


@router.delete("/skills/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_skill(
    skill_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    await profile_service.delete_skill(db, current_user.id, skill_id)


@router.post("/certifications", response_model=CertificationOut, status_code=status.HTTP_201_CREATED)
async def create_certification(
    payload: CertificationIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await profile_service.add_certification(db, current_user.id, payload)


@router.delete("/certifications/{certification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_certification(
    certification_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    await profile_service.delete_certification(db, current_user.id, certification_id)


@router.post("/projects", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await profile_service.add_project(db, current_user.id, payload)


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_project(
    project_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    await profile_service.delete_project(db, current_user.id, project_id)
