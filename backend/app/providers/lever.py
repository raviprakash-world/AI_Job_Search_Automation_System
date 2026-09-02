from datetime import datetime, timezone

import httpx

from app.core.errors import ProviderError
from app.providers.base import JobSourceProvider, RawPosting

BASE_URL = "https://api.lever.co/v0/postings/{slug}"


def _parse_epoch_ms(value: int | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    except (ValueError, OSError):
        return None


class LeverProvider(JobSourceProvider):
    name = "lever"

    async def fetch_postings(self, company_slug: str) -> list[RawPosting]:
        url = BASE_URL.format(slug=company_slug)
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(url, params={"mode": "json"})
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            raise ProviderError(f"Lever request failed for '{company_slug}': {exc}") from exc

        postings = []
        for job in data:
            categories = job.get("categories") or {}
            workplace_type = job.get("workplaceType")
            postings.append(
                RawPosting(
                    provider_job_id=str(job.get("id")),
                    title=job.get("text", ""),
                    location_text=categories.get("location"),
                    remote_flag=(workplace_type == "remote") if workplace_type else None,
                    department=categories.get("team"),
                    absolute_url=job.get("hostedUrl"),
                    content=job.get("descriptionPlain") or job.get("description") or "",
                    raw=job,
                    posted_at=_parse_epoch_ms(job.get("createdAt")),
                )
            )
        return postings
