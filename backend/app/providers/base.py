from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel


class RawPosting(BaseModel):
    """Normalized shape every provider must produce, before job-level normalization."""

    provider_job_id: str
    title: str
    location_text: str | None = None
    remote_flag: bool | None = None
    department: str | None = None
    absolute_url: str | None = None
    content: str = ""
    raw: dict = {}
    posted_at: datetime | None = None


class JobSourceProvider(ABC):
    name: str

    @abstractmethod
    async def fetch_postings(self, company_slug: str) -> list[RawPosting]:
        """Fetch all current postings for a company from this provider.

        Implementations call only public, unauthenticated, read-only endpoints.
        """
        raise NotImplementedError
