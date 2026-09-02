from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.automation import NotificationOut
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    unread: bool = False, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await notification_service.list_notifications(db, current_user.id, unread_only=unread)


@router.post("/{notification_id}/read", response_model=NotificationOut)
async def mark_read(
    notification_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await notification_service.mark_read(db, current_user.id, notification_id)


@router.post("/read-all")
async def mark_all_read(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    count = await notification_service.mark_all_read(db, current_user.id)
    return {"marked_read": count}
