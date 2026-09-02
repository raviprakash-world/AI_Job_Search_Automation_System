from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.jobs import DiscoveryResult, JobSourceCreate, JobSourceOut
from app.services import job_source_service
from app.services.job_pipeline_service import run_discovery_and_match

router = APIRouter(prefix="/job-sources", tags=["job-sources"])


@router.post("", response_model=JobSourceOut, status_code=status.HTTP_201_CREATED)
async def create_job_source(
    payload: JobSourceCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await job_source_service.create_job_source(db, current_user.id, payload)


@router.get("", response_model=list[JobSourceOut])
async def list_job_sources(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await job_source_service.list_job_sources(db, current_user.id)


@router.delete("/{job_source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job_source(
    job_source_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    await job_source_service.delete_job_source(db, current_user.id, job_source_id)


@router.post("/{job_source_id}/discover", response_model=DiscoveryResult)
async def discover(
    job_source_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    job_source = await job_source_service.get_owned_job_source(db, current_user.id, job_source_id)
    return await run_discovery_and_match(db, current_user, job_source)
