from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.automation import AutomationRunDetailOut, AutomationRunOut, RunType
from app.services import automation_run_service, digest_service, discovery_automation_service

router = APIRouter(prefix="/automation", tags=["automation"])


@router.get("/runs", response_model=list[AutomationRunOut])
async def list_runs(
    run_type: RunType | None = None, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await automation_run_service.list_runs(db, user_id=current_user.id, run_type=run_type)


@router.get("/runs/{run_id}", response_model=AutomationRunDetailOut)
async def get_run(run_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await automation_run_service.get_owned_run(db, current_user.id, run_id)


@router.post("/discovery/run", response_model=AutomationRunOut)
async def run_discovery(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await discovery_automation_service.run_discovery(db, user_id=current_user.id)


@router.post("/digest/run", response_model=AutomationRunOut)
async def run_digest(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await digest_service.generate_digests(db, user_id=current_user.id)
