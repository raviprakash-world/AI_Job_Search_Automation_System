from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.dashboard import ActivityItem, AlertItem, OverviewOut
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview", response_model=OverviewOut)
async def get_overview(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await dashboard_service.get_overview(db, current_user.id)


@router.get("/activity", response_model=list[ActivityItem])
async def get_activity(limit: int = 20, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await dashboard_service.get_activity(db, current_user.id, limit=limit)


@router.get("/alerts", response_model=list[AlertItem])
async def get_alerts(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await dashboard_service.get_alerts(db, current_user.id)
