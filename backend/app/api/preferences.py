from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.preferences import PreferencesOut, PreferencesUpdate
from app.services import preferences_service

router = APIRouter(prefix="/preferences", tags=["preferences"])


@router.get("", response_model=PreferencesOut)
async def get_preferences(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await preferences_service.get_preferences(db, current_user.id)


@router.put("", response_model=PreferencesOut)
async def update_preferences(
    payload: PreferencesUpdate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await preferences_service.update_preferences(db, current_user.id, payload)
