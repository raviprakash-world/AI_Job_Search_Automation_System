from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog


async def record_audit(
    db: AsyncSession,
    *,
    user_id: str | None,
    entity_type: str,
    entity_id: str,
    action: str,
    actor: str = "user",
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor=actor,
        before_data=before,
        after_data=after,
    )
    db.add(entry)
    await db.flush()
    return entry
