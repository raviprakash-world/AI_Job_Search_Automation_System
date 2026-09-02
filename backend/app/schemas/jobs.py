from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Provider = Literal["greenhouse", "lever"]


class JobSourceCreate(BaseModel):
    provider: Provider
    company_slug: str = Field(min_length=1, max_length=255)
    display_name: str | None = None


class JobSourceOut(BaseModel):
    id: str
    provider: str
    company_slug: str
    display_name: str | None
    is_active: bool
    last_polled_at: datetime | None

    model_config = {"from_attributes": True}


class DiscoveryResult(BaseModel):
    fetched: int
    new_jobs: int
    updated_jobs: int
    duplicates_merged: int
    matched: int


class JobRequirements(BaseModel):
    """Strict schema the JobAnalysisAgent must satisfy — omit, never invent, missing fields."""

    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    min_years_experience: int | None = None
    max_years_experience: int | None = None
    education_requirements: str | None = None
    work_authorization_requirements: str | None = None
    seniority_level: str | None = None
    key_responsibilities: list[str] = Field(default_factory=list)


class JobMatchOut(BaseModel):
    fit_score: float
    dimension_scores: dict
    hard_disqualifiers: list[str]
    strong_matches: list[str]
    gaps: list[str]
    summary: str
    computed_at: datetime

    model_config = {"from_attributes": True}


class JobSnapshotOut(BaseModel):
    provider_job_id: str
    fetched_at: datetime

    model_config = {"from_attributes": True}


class JobOut(BaseModel):
    id: str
    company_name: str | None
    title: str
    location: str | None
    remote_status: str | None
    employment_type: str | None
    salary_min: int | None
    salary_max: int | None
    salary_currency: str | None
    posting_url: str | None
    analysis_status: str
    status: str
    first_seen_at: datetime
    last_seen_at: datetime
    match: JobMatchOut | None = None
    saved_status: str | None = None


class JobDetailOut(JobOut):
    description_text: str | None
    structured_requirements: dict
    snapshots: list[JobSnapshotOut] = Field(default_factory=list)


class JobActionRequest(BaseModel):
    action: Literal["shortlist", "save_for_later", "reject", "ignore"]
    reason: str | None = None


class SavedJobOut(BaseModel):
    status: str
    reason: str | None

    model_config = {"from_attributes": True}
