from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.db.models import JobSource
from app.schemas.jobs import JobSourceCreate


async def create_job_source(db: AsyncSession, user_id: str, payload: JobSourceCreate) -> JobSource:
    source = JobSource(
        user_id=user_id,
        provider=payload.provider,
        company_slug=payload.company_slug,
        display_name=payload.display_name or payload.company_slug,
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return source


async def list_job_sources(db: AsyncSession, user_id: str) -> list[JobSource]:
    result = await db.scalars(select(JobSource).where(JobSource.user_id == user_id))
    return list(result)


async def get_owned_job_source(db: AsyncSession, user_id: str, job_source_id: str) -> JobSource:
    source = await db.get(JobSource, job_source_id)
    if source is None or source.user_id != user_id:
        raise NotFoundError("Job source not found")
    return source


async def delete_job_source(db: AsyncSession, user_id: str, job_source_id: str) -> None:
    source = await get_owned_job_source(db, user_id, job_source_id)
    await db.delete(source)
    await db.commit()
