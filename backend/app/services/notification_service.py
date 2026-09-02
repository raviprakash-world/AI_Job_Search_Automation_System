from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.db.models import Notification


async def list_notifications(db: AsyncSession, user_id: str, *, unread_only: bool = False) -> list[Notification]:
    stmt = select(Notification).where(Notification.user_id == user_id).order_by(Notification.created_at.desc())
    if unread_only:
        stmt = stmt.where(Notification.read.is_(False))
    return list(await db.scalars(stmt))


async def mark_read(db: AsyncSession, user_id: str, notification_id: str) -> Notification:
    notification = await db.get(Notification, notification_id)
    if notification is None or notification.user_id != user_id:
        raise NotFoundError("Notification not found")
    notification.read = True
    await db.commit()
    await db.refresh(notification)
    return notification


async def mark_all_read(db: AsyncSession, user_id: str) -> int:
    notifications = await list_notifications(db, user_id, unread_only=True)
    for notification in notifications:
        notification.read = True
    await db.commit()
    return len(notifications)
