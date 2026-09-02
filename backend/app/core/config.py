from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/job_search"

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    enable_rate_limiting: bool = True

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"

    file_storage_dir: str = "./storage/documents"
    max_upload_size_mb: int = 15

    cors_origins: list[str] = ["http://localhost:5173"]

    enable_scheduler: bool = True
    discovery_interval_minutes: int = 360
    digest_hour_utc: int = 8
    stale_check_hour_utc: int = 9
    stale_application_days: int = 7

    @property
    def storage_path(self) -> Path:
        path = Path(self.file_storage_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def resume_storage_path(self) -> Path:
        path = Path(self.file_storage_dir).parent / "resumes"
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()
