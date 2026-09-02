from pydantic import BaseModel


class PreferencesUpdate(BaseModel):
    automation_mode: str | None = None
    notification_settings: dict | None = None
    scoring_weights: dict[str, float] | None = None
    shortlist_thresholds: dict[str, float] | None = None
    blacklisted_companies: list[str] | None = None
    blacklisted_roles: list[str] | None = None
    prioritized_companies: list[str] | None = None


class PreferencesOut(BaseModel):
    automation_mode: str
    notification_settings: dict
    scoring_weights: dict
    shortlist_thresholds: dict
    blacklisted_companies: list[str]
    blacklisted_roles: list[str]
    prioritized_companies: list[str]

    model_config = {"from_attributes": True}
