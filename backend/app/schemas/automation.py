from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

RunType = Literal["discovery", "digest", "stale_check"]
RunStatus = Literal["running", "completed", "failed"]


class AutomationStepOut(BaseModel):
    step_name: str
    status: str
    detail: dict
    error: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AutomationRunOut(BaseModel):
    id: str
    run_type: RunType
    status: RunStatus
    triggered_by: str
    started_at: datetime
    completed_at: datetime | None
    summary: dict
    error: str | None

    model_config = {"from_attributes": True}


class AutomationRunDetailOut(AutomationRunOut):
    steps: list[AutomationStepOut] = Field(default_factory=list)


class NotificationOut(BaseModel):
    id: str
    type: str
    title: str
    body: str
    data: dict
    read: bool
    created_at: datetime

    model_config = {"from_attributes": True}
