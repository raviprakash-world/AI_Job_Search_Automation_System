from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.resumes import QAReport

# --- Strict schema the CoverLetterAgent must satisfy ---------------------------


class CoverLetterGeneration(BaseModel):
    body_text: str
    referenced_experience_ids: list[str] = Field(default_factory=list)


# --- API models ---------------------------------------------------------------


class CoverLetterVersionOut(BaseModel):
    id: str
    version_number: int
    status: str
    body_text: str
    qa_report: QAReport | dict
    generated_at: datetime

    model_config = {"from_attributes": True}


class CoverLetterOut(BaseModel):
    id: str
    job_id: str
    label: str
    created_at: datetime
    latest_version: CoverLetterVersionOut | None = None
