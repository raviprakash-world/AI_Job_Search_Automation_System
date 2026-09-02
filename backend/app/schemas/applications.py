from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.cover_letters import CoverLetterVersionOut
from app.schemas.resumes import ResumeVersionOut

ApplicationStatus = Literal[
    "preparing",
    "ready_for_review",
    "approved",
    "staged",
    "submission_blocked",
    "submitted",
    "rejected",
    "interview",
    "offer",
    "withdrawn",
    "error",
]
OutcomeStatus = Literal["rejected", "interview", "offer", "withdrawn"]

# --- Strict schema the ApplicationAnswerAgent must satisfy ---------------------


class AnswerResult(BaseModel):
    question: str
    answer: str | None = None
    is_grounded: bool
    flag_reason: str | None = None


class ApplicationAnswerGeneration(BaseModel):
    results: list[AnswerResult] = Field(default_factory=list)


# --- Gates ----------------------------------------------------------------


class GateResult(BaseModel):
    name: str
    passed: bool
    message: str
    overridden: bool = False


class GateReport(BaseModel):
    gates: list[GateResult] = Field(default_factory=list)
    passed: bool = False


# --- API models ---------------------------------------------------------------


class ApplicationCreate(BaseModel):
    job_id: str
    resume_version_id: str
    generate_cover_letter: bool = True
    custom_questions: list[str] = Field(default_factory=list)
    override_low_match: bool = False


class ApplicationAnswerOut(BaseModel):
    id: str
    question: str
    answer: str | None
    is_grounded: bool
    flag_reason: str | None
    reviewed: bool

    model_config = {"from_attributes": True}


class ApplicationAnswerUpdate(BaseModel):
    answer: str


class ApplicationEventOut(BaseModel):
    from_status: str | None
    to_status: str
    actor: str
    note: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class StagingNotes(BaseModel):
    fields_filled: list[str] = Field(default_factory=list)
    fields_needing_manual_input: list[str] = Field(default_factory=list)
    blocked_reason: str | None = None


class ApplicationOut(BaseModel):
    id: str
    job_id: str
    job_title: str
    company_name: str | None
    status: ApplicationStatus
    gate_report: GateReport | dict
    submitted_at: datetime | None
    outcome_note: str | None
    staging_notes: StagingNotes | dict
    has_staged_screenshot: bool
    created_at: datetime


class ApplicationDetailOut(ApplicationOut):
    resume_version: ResumeVersionOut | None = None
    cover_letter_version: CoverLetterVersionOut | None = None
    answers: list[ApplicationAnswerOut] = Field(default_factory=list)
    events: list[ApplicationEventOut] = Field(default_factory=list)


class MarkSubmittedRequest(BaseModel):
    submitted_at: datetime | None = None
    note: str | None = None


class ApplicationStatusUpdate(BaseModel):
    status: OutcomeStatus
    note: str | None = None
