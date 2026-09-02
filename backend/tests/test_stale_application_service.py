from datetime import datetime, timedelta, timezone

from app.db.models import Notification
from app.services.stale_application_service import already_flagged_since_update


def _notification(application_id: str, created_at: datetime) -> Notification:
    return Notification(type="stale_application", data={"application_id": application_id}, created_at=created_at)


def test_not_flagged_when_no_notifications_exist():
    now = datetime.now(timezone.utc)
    assert already_flagged_since_update([], "app-1", now) is False


def test_flagged_when_notification_created_after_update():
    updated_at = datetime.now(timezone.utc) - timedelta(days=1)
    notification = _notification("app-1", created_at=updated_at + timedelta(hours=1))
    assert already_flagged_since_update([notification], "app-1", updated_at) is True


def test_not_flagged_when_notification_predates_the_update():
    # e.g. the application changed status again after being flagged — should be eligible to flag again
    updated_at = datetime.now(timezone.utc)
    notification = _notification("app-1", created_at=updated_at - timedelta(days=5))
    assert already_flagged_since_update([notification], "app-1", updated_at) is False


def test_notification_for_a_different_application_does_not_count():
    updated_at = datetime.now(timezone.utc) - timedelta(days=1)
    notification = _notification("app-2", created_at=updated_at + timedelta(hours=1))
    assert already_flagged_since_update([notification], "app-1", updated_at) is False
