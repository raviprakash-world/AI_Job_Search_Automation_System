from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import NotFoundError
from app.db.models import (
    CandidateProfile,
    Certification,
    Education,
    Experience,
    Project,
    Skill,
)
from app.schemas.profile import (
    CandidateProfileUpdate,
    CertificationIn,
    EducationIn,
    ExperienceIn,
    ProjectIn,
    SkillIn,
)
from app.services.audit_service import record_audit

_PROFILE_LOAD_OPTIONS = (
    selectinload(CandidateProfile.experiences),
    selectinload(CandidateProfile.education),
    selectinload(CandidateProfile.skills),
    selectinload(CandidateProfile.certifications),
    selectinload(CandidateProfile.projects),
)


async def get_profile_by_user(db: AsyncSession, user_id: str) -> CandidateProfile:
    stmt = select(CandidateProfile).where(CandidateProfile.user_id == user_id).options(*_PROFILE_LOAD_OPTIONS)
    profile = await db.scalar(stmt)
    if profile is None:
        raise NotFoundError("Candidate profile not found")
    return profile


async def update_profile(
    db: AsyncSession, user_id: str, payload: CandidateProfileUpdate
) -> CandidateProfile:
    profile = await get_profile_by_user(db, user_id)
    before = _profile_snapshot(profile)

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(profile, field, value)
    profile.version += 1

    await record_audit(
        db,
        user_id=user_id,
        entity_type="candidate_profile",
        entity_id=profile.id,
        action="update",
        before=before,
        after=_profile_snapshot(profile),
    )
    await db.commit()
    await db.refresh(profile)
    return await get_profile_by_user(db, user_id)


def _profile_snapshot(profile: CandidateProfile) -> dict:
    return {
        "full_name": profile.full_name,
        "phone": profile.phone,
        "location": profile.location,
        "professional_summary": profile.professional_summary,
        "target_roles": profile.target_roles,
        "salary_expectation_min": profile.salary_expectation_min,
        "salary_expectation_max": profile.salary_expectation_max,
        "notice_period": profile.notice_period,
        "remote_preference": profile.remote_preference,
        "links": profile.links,
    }


# --- Child entity CRUD -------------------------------------------------------
# Each function validates ownership via profile_id -> user_id join implicitly by
# requiring the caller to have already resolved the profile for this user.


async def _get_owned_profile_id(db: AsyncSession, user_id: str) -> str:
    profile = await db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user_id))
    if profile is None:
        raise NotFoundError("Candidate profile not found")
    return profile.id


async def add_experience(db: AsyncSession, user_id: str, payload: ExperienceIn) -> Experience:
    profile_id = await _get_owned_profile_id(db, user_id)
    exp = Experience(profile_id=profile_id, **payload.model_dump())
    db.add(exp)
    await db.flush()
    await record_audit(
        db, user_id=user_id, entity_type="experience", entity_id=exp.id, action="create", after=payload.model_dump(mode="json")
    )
    await db.commit()
    await db.refresh(exp)
    return exp


async def delete_experience(db: AsyncSession, user_id: str, experience_id: str) -> None:
    profile_id = await _get_owned_profile_id(db, user_id)
    exp = await db.get(Experience, experience_id)
    if exp is None or exp.profile_id != profile_id:
        raise NotFoundError("Experience not found")
    await record_audit(db, user_id=user_id, entity_type="experience", entity_id=exp.id, action="delete", before={"company": exp.company, "title": exp.title})
    await db.delete(exp)
    await db.commit()


async def add_education(db: AsyncSession, user_id: str, payload: EducationIn) -> Education:
    profile_id = await _get_owned_profile_id(db, user_id)
    edu = Education(profile_id=profile_id, **payload.model_dump())
    db.add(edu)
    await db.flush()
    await record_audit(db, user_id=user_id, entity_type="education", entity_id=edu.id, action="create", after=payload.model_dump(mode="json"))
    await db.commit()
    await db.refresh(edu)
    return edu


async def delete_education(db: AsyncSession, user_id: str, education_id: str) -> None:
    profile_id = await _get_owned_profile_id(db, user_id)
    edu = await db.get(Education, education_id)
    if edu is None or edu.profile_id != profile_id:
        raise NotFoundError("Education entry not found")
    await record_audit(db, user_id=user_id, entity_type="education", entity_id=edu.id, action="delete", before={"institution": edu.institution})
    await db.delete(edu)
    await db.commit()


async def add_skill(db: AsyncSession, user_id: str, payload: SkillIn) -> Skill:
    profile_id = await _get_owned_profile_id(db, user_id)
    skill = Skill(profile_id=profile_id, **payload.model_dump())
    db.add(skill)
    await db.flush()
    await record_audit(db, user_id=user_id, entity_type="skill", entity_id=skill.id, action="create", after=payload.model_dump(mode="json"))
    await db.commit()
    await db.refresh(skill)
    return skill


async def delete_skill(db: AsyncSession, user_id: str, skill_id: str) -> None:
    profile_id = await _get_owned_profile_id(db, user_id)
    skill = await db.get(Skill, skill_id)
    if skill is None or skill.profile_id != profile_id:
        raise NotFoundError("Skill not found")
    await record_audit(db, user_id=user_id, entity_type="skill", entity_id=skill.id, action="delete", before={"name": skill.name})
    await db.delete(skill)
    await db.commit()


async def add_certification(db: AsyncSession, user_id: str, payload: CertificationIn) -> Certification:
    profile_id = await _get_owned_profile_id(db, user_id)
    cert = Certification(profile_id=profile_id, **payload.model_dump())
    db.add(cert)
    await db.flush()
    await record_audit(db, user_id=user_id, entity_type="certification", entity_id=cert.id, action="create", after=payload.model_dump(mode="json"))
    await db.commit()
    await db.refresh(cert)
    return cert


async def delete_certification(db: AsyncSession, user_id: str, certification_id: str) -> None:
    profile_id = await _get_owned_profile_id(db, user_id)
    cert = await db.get(Certification, certification_id)
    if cert is None or cert.profile_id != profile_id:
        raise NotFoundError("Certification not found")
    await record_audit(db, user_id=user_id, entity_type="certification", entity_id=cert.id, action="delete", before={"name": cert.name})
    await db.delete(cert)
    await db.commit()


async def add_project(db: AsyncSession, user_id: str, payload: ProjectIn) -> Project:
    profile_id = await _get_owned_profile_id(db, user_id)
    project = Project(profile_id=profile_id, **payload.model_dump())
    db.add(project)
    await db.flush()
    await record_audit(db, user_id=user_id, entity_type="project", entity_id=project.id, action="create", after=payload.model_dump(mode="json"))
    await db.commit()
    await db.refresh(project)
    return project


async def delete_project(db: AsyncSession, user_id: str, project_id: str) -> None:
    profile_id = await _get_owned_profile_id(db, user_id)
    project = await db.get(Project, project_id)
    if project is None or project.profile_id != profile_id:
        raise NotFoundError("Project not found")
    await record_audit(db, user_id=user_id, entity_type="project", entity_id=project.id, action="delete", before={"name": project.name})
    await db.delete(project)
    await db.commit()
