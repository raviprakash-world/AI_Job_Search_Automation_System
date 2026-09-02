from datetime import date, datetime

from pydantic import BaseModel, Field

# --- Strict schema the ResumeAgent must satisfy --------------------------------
# Deliberately excludes company/title/dates/degree entirely — see resume_agent.py.


class ExperienceSelection(BaseModel):
    experience_id: str
    bullets: list[str] = Field(min_length=1)


class ResumeGeneration(BaseModel):
    professional_summary: str
    selected_skill_names: list[str] = Field(default_factory=list)
    experience_selections: list[ExperienceSelection] = Field(default_factory=list)
    selected_project_ids: list[str] = Field(default_factory=list)
    selected_certification_ids: list[str] = Field(default_factory=list)


# --- API models ---------------------------------------------------------------


class ResumeCreate(BaseModel):
    job_id: str | None = None
    label: str | None = None
    include_projects: bool = True
    include_certifications: bool = True


class ResumeExperienceOut(BaseModel):
    experience_id: str
    company: str
    title: str
    location: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool = False
    bullets: list[str]


class ResumeEducationOut(BaseModel):
    institution: str
    degree: str | None = None
    field_of_study: str | None = None
    start_date: date | None = None
    end_date: date | None = None


class ResumeProjectOut(BaseModel):
    name: str
    description: str | None = None
    technologies: list[str] = Field(default_factory=list)


class ResumeCertificationOut(BaseModel):
    name: str
    issuer: str | None = None


class StructuredResumeContent(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    email: str | None = None
    location: str | None = None
    links: dict[str, str] = Field(default_factory=dict)
    professional_summary: str
    skills: list[str] = Field(default_factory=list)
    experiences: list[ResumeExperienceOut] = Field(default_factory=list)
    education: list[ResumeEducationOut] = Field(default_factory=list)
    projects: list[ResumeProjectOut] = Field(default_factory=list)
    certifications: list[ResumeCertificationOut] = Field(default_factory=list)


class QAReport(BaseModel):
    ats_keyword_coverage: float | None = None
    matched_keywords: list[str] = Field(default_factory=list)
    missing_keywords: list[str] = Field(default_factory=list)
    word_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ResumeVersionOut(BaseModel):
    id: str
    resume_id: str
    version_number: int
    status: str
    structured_content: StructuredResumeContent | dict
    qa_report: QAReport | dict
    generated_at: datetime

    model_config = {"from_attributes": True}


class ResumeOut(BaseModel):
    id: str
    job_id: str | None
    label: str
    created_at: datetime
    latest_version: ResumeVersionOut | None = None


class ResumeDetailOut(ResumeOut):
    versions: list[ResumeVersionOut] = Field(default_factory=list)
