from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UserPreference
from app.schemas.preferences import PreferencesUpdate
from app.services.matching_service import DEFAULT_SCORING_WEIGHTS, DEFAULT_SHORTLIST_THRESHOLDS


async def get_preferences(db: AsyncSession, user_id: str) -> UserPreference:
    pref = await db.scalar(select(UserPreference).where(UserPreference.user_id == user_id))
    if pref is None:
        pref = UserPreference(user_id=user_id)
        db.add(pref)
        await db.commit()
        await db.refresh(pref)

    if not pref.scoring_weights:
        pref.scoring_weights = DEFAULT_SCORING_WEIGHTS
    if not pref.shortlist_thresholds:
        pref.shortlist_thresholds = DEFAULT_SHORTLIST_THRESHOLDS
    return pref


async def update_preferences(db: AsyncSession, user_id: str, payload: PreferencesUpdate) -> UserPreference:
    pref = await get_preferences(db, user_id)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(pref, field, value)
    await db.commit()
    await db.refresh(pref)
    return pref
