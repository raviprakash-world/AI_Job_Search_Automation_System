from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class SummaryOut(BaseModel):
    jobs_discovered: int
    jobs_shortlisted: int
    applications_submitted: int
    interviews: int
    offers: int
    rejections: int
    rejection_rate: float
    response_rate: float


class PipelineOut(BaseModel):
    discovered: int
    shortlisted: int
    prepared: int
    applied: int
    interview: int
    offer: int


class OverviewOut(BaseModel):
    summary: SummaryOut
    pipeline: PipelineOut


ActivityType = Literal["audit", "application_event", "automation_run"]
ActivityStatus = Literal["success", "error", "info"]


class ActivityItem(BaseModel):
    type: ActivityType
    title: str
    detail: str | None = None
    status: ActivityStatus
    created_at: datetime


AlertType = Literal["application_error", "resume_failed", "cover_letter_failed", "answer_flagged"]


class AlertLink(BaseModel):
    kind: Literal["application", "resume", "cover_letter"]
    id: str


class AlertItem(BaseModel):
    type: AlertType
    title: str
    detail: str
    link: AlertLink
    created_at: datetime
