from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

# --- Structured output contract the ProfileAgent must satisfy -----------------


class ExtractedExperience(BaseModel):
    company: str
    title: str
    location: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool = False
    responsibilities: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)


class ExtractedEducation(BaseModel):
    institution: str
    degree: str | None = None
    field_of_study: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    gpa: str | None = None


class ExtractedSkill(BaseModel):
    name: str
    category: str = "technical"


class ExtractedCertification(BaseModel):
    name: str
    issuer: str | None = None
    issue_date: date | None = None
    expiry_date: date | None = None
    credential_url: str | None = None


class ExtractedProject(BaseModel):
    name: str
    description: str | None = None
    technologies: list[str] = Field(default_factory=list)
    url: str | None = None


class ExtractedProfileData(BaseModel):
    """Strict schema the ProfileAgent's Claude call must return as JSON.

    Every field is optional because a resume may not mention it — the agent must
    never invent a value to fill a gap.
    """

    full_name: str | None = None
    phone: str | None = None
    location: str | None = None
    professional_summary: str | None = None
    links: dict[str, str] = Field(default_factory=dict)
    experiences: list[ExtractedExperience] = Field(default_factory=list)
    education: list[ExtractedEducation] = Field(default_factory=list)
    skills: list[ExtractedSkill] = Field(default_factory=list)
    certifications: list[ExtractedCertification] = Field(default_factory=list)
    projects: list[ExtractedProject] = Field(default_factory=list)


# --- Reconciliation / review API -----------------------------------------------

ChangeKind = Literal[
    "field_update",
    "new_experience",
    "new_education",
    "new_skill",
    "new_certification",
    "new_project",
]


class ProfileChange(BaseModel):
    change_id: str
    kind: ChangeKind
    field: str | None = None
    existing_value: Any = None
    proposed_value: Any = None


class ProfileExtractionOut(BaseModel):
    id: str
    document_id: str
    status: str
    extracted_data: ExtractedProfileData | dict
    conflicts: list[ProfileChange]
    reviewed_at: datetime | None = None

    model_config = {"from_attributes": True}


class Resolution(BaseModel):
    change_id: str
    action: Literal["accept", "reject"]


class ExtractionResolveRequest(BaseModel):
    resolutions: list[Resolution]
