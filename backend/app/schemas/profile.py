from datetime import date

from pydantic import BaseModel, Field


class ExperienceIn(BaseModel):
    company: str
    title: str
    location: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool = False
    responsibilities: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    display_order: int = 0


class ExperienceOut(ExperienceIn):
    id: str
    model_config = {"from_attributes": True}


class EducationIn(BaseModel):
    institution: str
    degree: str | None = None
    field_of_study: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    gpa: str | None = None
    display_order: int = 0


class EducationOut(EducationIn):
    id: str
    model_config = {"from_attributes": True}


class SkillIn(BaseModel):
    name: str
    category: str = "technical"
    proficiency: str | None = None


class SkillOut(SkillIn):
    id: str
    model_config = {"from_attributes": True}


class CertificationIn(BaseModel):
    name: str
    issuer: str | None = None
    issue_date: date | None = None
    expiry_date: date | None = None
    credential_url: str | None = None


class CertificationOut(CertificationIn):
    id: str
    model_config = {"from_attributes": True}


class ProjectIn(BaseModel):
    name: str
    description: str | None = None
    technologies: list[str] = Field(default_factory=list)
    url: str | None = None
    start_date: date | None = None
    end_date: date | None = None


class ProjectOut(ProjectIn):
    id: str
    model_config = {"from_attributes": True}


class CandidateProfileUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    location: str | None = None
    preferred_locations: list[str] | None = None
    work_authorization: str | None = None
    professional_summary: str | None = None
    target_roles: list[str] | None = None
    salary_expectation_min: int | None = None
    salary_expectation_max: int | None = None
    notice_period: str | None = None
    remote_preference: str | None = None
    links: dict | None = None


class CandidateProfileOut(BaseModel):
    id: str
    full_name: str | None
    phone: str | None
    location: str | None
    preferred_locations: list[str]
    work_authorization: str | None
    professional_summary: str | None
    target_roles: list[str]
    salary_expectation_min: int | None
    salary_expectation_max: int | None
    notice_period: str | None
    remote_preference: str | None
    links: dict
    version: int
    experiences: list[ExperienceOut] = Field(default_factory=list)
    education: list[EducationOut] = Field(default_factory=list)
    skills: list[SkillOut] = Field(default_factory=list)
    certifications: list[CertificationOut] = Field(default_factory=list)
    projects: list[ProjectOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}
