from httpx import AsyncClient

from tests.conftest import TestSessionLocal

POSTING = {
    "provider_job_id": "1",
    "title": "Backend Engineer",
    "location_text": "Remote",
    "content": "<p>Python required. Remote role.</p>",
    "raw": {"id": 1},
}
REQUIREMENTS = {"required_skills": ["Python"], "min_years_experience": 1}


async def _build_profile(client: AsyncClient, headers: dict) -> None:
    await client.put(url="/api/profile", headers=headers, json={"full_name": "Jane Doe", "location": "Remote"})
    await client.post(
        "/api/profile/experiences",
        headers=headers,
        json={"company": "Acme Corp", "title": "Senior Engineer", "start_date": "2021-01-01", "end_date": "2024-01-01"},
    )
    await client.post("/api/profile/skills", headers=headers, json={"name": "Python"})


async def test_manual_discovery_run_creates_automation_run_with_steps(
    client: AsyncClient, auth_headers: dict, fake_provider, mock_job_analysis
):
    fake_provider([POSTING])
    mock_job_analysis(REQUIREMENTS)
    await client.post(
        "/api/job-sources", headers=auth_headers, json={"provider": "greenhouse", "company_slug": "acme", "display_name": "Acme"}
    )

    resp = await client.post("/api/automation/discovery/run", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["run_type"] == "discovery"
    assert body["status"] == "completed"
    assert body["triggered_by"] == "user"
    assert body["summary"]["sources"] == 1
    assert body["summary"]["new_jobs"] == 1

    detail = await client.get(f"/api/automation/runs/{body['id']}", headers=auth_headers)
    assert detail.status_code == 200
    steps = detail.json()["steps"]
    assert len(steps) == 1
    assert steps[0]["status"] == "success"


async def test_discovery_run_with_no_sources_completes_cleanly(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/automation/discovery/run", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"
    assert resp.json()["summary"]["sources"] == 0


async def test_discovery_isolates_one_failing_source(
    client: AsyncClient, auth_headers: dict, monkeypatch, mock_job_analysis
):
    from app.providers.base import RawPosting

    class FlakyProvider:
        async def fetch_postings(self, company_slug: str) -> list[RawPosting]:
            if company_slug == "broken-co":
                raise RuntimeError("upstream board is down")
            return [RawPosting(**POSTING)]

    monkeypatch.setattr("app.services.job_discovery_service.get_provider", lambda name: FlakyProvider())
    mock_job_analysis(REQUIREMENTS)

    await client.post(
        "/api/job-sources", headers=auth_headers, json={"provider": "greenhouse", "company_slug": "acme", "display_name": "Acme"}
    )
    await client.post(
        "/api/job-sources",
        headers=auth_headers,
        json={"provider": "greenhouse", "company_slug": "broken-co", "display_name": "Broken Co"},
    )

    resp = await client.post("/api/automation/discovery/run", headers=auth_headers)
    body = resp.json()
    assert body["status"] == "completed"  # one success out of two keeps the run "completed", not "failed"
    assert body["summary"]["sources"] == 2
    assert body["summary"]["failed"] == 1
    assert body["summary"]["new_jobs"] == 1

    detail = await client.get(f"/api/automation/runs/{body['id']}", headers=auth_headers)
    statuses = {s["step_name"]: s["status"] for s in detail.json()["steps"]}
    assert statuses["greenhouse:acme"] == "success"
    assert statuses["greenhouse:broken-co"] == "failed"


async def test_digest_creates_notification_with_new_matches(
    client: AsyncClient, auth_headers: dict, fake_provider, mock_job_analysis
):
    await _build_profile(client, auth_headers)
    fake_provider([POSTING])
    mock_job_analysis(REQUIREMENTS)
    source = await client.post(
        "/api/job-sources", headers=auth_headers, json={"provider": "greenhouse", "company_slug": "acme", "display_name": "Acme"}
    )
    await client.post(f"/api/job-sources/{source.json()['id']}/discover", headers=auth_headers)

    resp = await client.post("/api/automation/digest/run", headers=auth_headers)
    assert resp.json()["summary"]["digests_created"] == 1

    notifications = await client.get("/api/notifications", headers=auth_headers)
    body = notifications.json()
    assert len(body) == 1
    assert body[0]["type"] == "digest"
    assert body[0]["read"] is False


async def test_digest_skips_when_nothing_new_since_last_digest(
    client: AsyncClient, auth_headers: dict, fake_provider, mock_job_analysis
):
    await _build_profile(client, auth_headers)
    fake_provider([POSTING])
    mock_job_analysis(REQUIREMENTS)
    source = await client.post(
        "/api/job-sources", headers=auth_headers, json={"provider": "greenhouse", "company_slug": "acme", "display_name": "Acme"}
    )
    await client.post(f"/api/job-sources/{source.json()['id']}/discover", headers=auth_headers)

    first = await client.post("/api/automation/digest/run", headers=auth_headers)
    assert first.json()["summary"]["digests_created"] == 1

    second = await client.post("/api/automation/digest/run", headers=auth_headers)
    assert second.json()["summary"]["digests_created"] == 0
    assert second.json()["summary"]["users_skipped"] == 1

    notifications = await client.get("/api/notifications", headers=auth_headers)
    assert len(notifications.json()) == 1  # no duplicate/empty digest notification


async def test_notifications_mark_read_and_read_all(
    client: AsyncClient, auth_headers: dict, fake_provider, mock_job_analysis
):
    await _build_profile(client, auth_headers)
    fake_provider([POSTING])
    mock_job_analysis(REQUIREMENTS)
    source = await client.post(
        "/api/job-sources", headers=auth_headers, json={"provider": "greenhouse", "company_slug": "acme", "display_name": "Acme"}
    )
    await client.post(f"/api/job-sources/{source.json()['id']}/discover", headers=auth_headers)
    await client.post("/api/automation/digest/run", headers=auth_headers)

    notifications = (await client.get("/api/notifications", headers=auth_headers)).json()
    notification_id = notifications[0]["id"]

    read_one = await client.post(f"/api/notifications/{notification_id}/read", headers=auth_headers)
    assert read_one.json()["read"] is True

    unread = await client.get("/api/notifications", headers=auth_headers, params={"unread": True})
    assert unread.json() == []

    mark_all = await client.post("/api/notifications/read-all", headers=auth_headers)
    assert mark_all.json()["marked_read"] == 0  # already all read


async def test_cannot_mark_another_users_notification_read(
    client: AsyncClient, auth_headers: dict, fake_provider, mock_job_analysis
):
    await _build_profile(client, auth_headers)
    fake_provider([POSTING])
    mock_job_analysis(REQUIREMENTS)
    source = await client.post(
        "/api/job-sources", headers=auth_headers, json={"provider": "greenhouse", "company_slug": "acme", "display_name": "Acme"}
    )
    await client.post(f"/api/job-sources/{source.json()['id']}/discover", headers=auth_headers)
    await client.post("/api/automation/digest/run", headers=auth_headers)

    notifications = (await client.get("/api/notifications", headers=auth_headers)).json()
    notification_id = notifications[0]["id"]

    await client.post("/api/auth/register", json={"email": "other@example.com", "password": "password123", "name": "Other"})
    other_login = await client.post("/api/auth/login", json={"email": "other@example.com", "password": "password123"})
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

    resp = await client.post(f"/api/notifications/{notification_id}/read", headers=other_headers)
    assert resp.status_code == 404

    # the owner's notification is still unread
    still_unread = await client.get("/api/notifications", headers=auth_headers, params={"unread": True})
    assert len(still_unread.json()) == 1


async def test_automation_run_scoped_to_owning_user(
    client: AsyncClient, auth_headers: dict, fake_provider, mock_job_analysis
):
    await client.post(
        "/api/job-sources", headers=auth_headers, json={"provider": "greenhouse", "company_slug": "acme", "display_name": "Acme"}
    )
    fake_provider([POSTING])
    mock_job_analysis(REQUIREMENTS)
    run = await client.post("/api/automation/discovery/run", headers=auth_headers)
    run_id = run.json()["id"]

    await client.post("/api/auth/register", json={"email": "other@example.com", "password": "password123", "name": "Other"})
    other_login = await client.post("/api/auth/login", json={"email": "other@example.com", "password": "password123"})
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

    resp = await client.get(f"/api/automation/runs/{run_id}", headers=other_headers)
    assert resp.status_code == 404

    own_list = await client.get("/api/automation/runs", headers=other_headers)
    assert own_list.json() == []


async def test_stale_check_flags_idle_application_after_threshold(client: AsyncClient, auth_headers: dict):
    from datetime import datetime, timedelta, timezone

    from app.db.models import Application, Company, Job, User

    me = await client.get("/api/auth/me", headers=auth_headers)
    user_id = me.json()["id"]

    async with TestSessionLocal() as session:
        user = await session.get(User, user_id)
        company = Company(name="Acme Corp", normalized_name="acme corp")
        session.add(company)
        await session.flush()
        job = Job(company_id=company.id, title="Backend Engineer", normalized_title="backend engineer", status="open")
        session.add(job)
        await session.flush()
        old_time = datetime.now(timezone.utc) - timedelta(days=30)
        application = Application(user_id=user.id, job_id=job.id, status="submitted", submitted_at=old_time)
        session.add(application)
        await session.commit()
        application.updated_at = old_time
        await session.commit()
        application_id = application.id

    resp = await client.post("/api/automation/discovery/run", headers=auth_headers)  # no-op, just to exercise auth path
    assert resp.status_code == 200

    from app.services.stale_application_service import check_stale_applications

    async with TestSessionLocal() as session:
        run = await check_stale_applications(session, user_id=user_id)
        assert run.summary["flagged"] == 1

    notifications = await client.get("/api/notifications", headers=auth_headers)
    stale = [n for n in notifications.json() if n["type"] == "stale_application"]
    assert len(stale) == 1
    assert stale[0]["data"]["application_id"] == application_id

    # Running the check again without any change should not re-flag it.
    async with TestSessionLocal() as session:
        run2 = await check_stale_applications(session, user_id=user_id)
        assert run2.summary["flagged"] == 0
