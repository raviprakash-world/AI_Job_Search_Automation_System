from datetime import datetime

import httpx

from app.core.errors import ProviderError
from app.providers.base import JobSourceProvider, RawPosting

BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class GreenhouseProvider(JobSourceProvider):
    name = "greenhouse"

    async def fetch_postings(self, company_slug: str) -> list[RawPosting]:
        url = BASE_URL.format(slug=company_slug)
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(url, params={"content": "true"})
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            raise ProviderError(f"Greenhouse request failed for '{company_slug}': {exc}") from exc

        jobs = data.get("jobs", [])
        postings = []
        for job in jobs:
            location = job.get("location") or {}
            postings.append(
                RawPosting(
                    provider_job_id=str(job.get("id")),
                    title=job.get("title", ""),
                    location_text=location.get("name"),
                    absolute_url=job.get("absolute_url"),
                    content=job.get("content", "") or "",
                    raw=job,
                    posted_at=_parse_datetime(job.get("updated_at")),
                )
            )
        return postings
