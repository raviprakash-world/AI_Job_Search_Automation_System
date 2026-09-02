from pathlib import Path

from httpx import AsyncClient

from app.db.models import Application
from tests.conftest import TestSessionLocal

POSTING = {
    "provider_job_id": "1",
    "title": "Backend Engineer",
    "location_text": "Remote",
    "content": "<p>Python required. Remote role.</p>",
    "absolute_url": "https://boards.greenhouse.io/acme/jobs/1",
    "raw": {"id": 1},
}
REQUIREMENTS = {"required_skills": ["Python"], "min_years_experience": 1}


async def _build_profile(client: AsyncClient, headers: dict) -> str:
    await client.put(url="/api/profile", headers=headers, json={"full_name": "Jane Doe", "location": "Remote"})
    exp = await client.post(
        "/api/profile/experiences",
        headers=headers,
        json={"company": "Acme Corp", "title": "Senior Engineer", "start_date": "2021-01-01", "end_date": "2024-01-01"},
    )
    await client.post("/api/profile/skills", headers=headers, json={"name": "Python"})
    return exp.json()["id"]


def _resume_generation(experience_id: str) -> dict:
    return {
        "professional_summary": "Experienced backend engineer.",
        "selected_skill_names": ["Python"],
        "experience_selections": [{"experience_id": experience_id, "bullets": ["Led a backend team of 5"]}],
        "selected_project_ids": [],
        "selected_certification_ids": [],
    }


async def _approved_application(
    client: AsyncClient, headers: dict, fake_provider, mock_job_analysis, mock_resume_agent
) -> str:
    experience_id = await _build_profile(client, headers)
    fake_provider([POSTING])
    mock_job_analysis(REQUIREMENTS)
    source = await client.post(
        "/api/job-sources", headers=headers, json={"provider": "greenhouse", "company_slug": "acme", "display_name": "Acme"}
    )
    await client.post(f"/api/job-sources/{source.json()['id']}/discover", headers=headers)
    job_id = (await client.get("/api/jobs", headers=headers)).json()[0]["id"]

    mock_resume_agent(_resume_generation(experience_id))
    resume = await client.post("/api/resumes", headers=headers, json={"job_id": job_id})
    resume_version_id = resume.json()["latest_version"]["id"]

    created = await client.post(
        "/api/applications",
        headers=headers,
        json={"job_id": job_id, "resume_version_id": resume_version_id, "generate_cover_letter": False, "custom_questions": []},
    )
    application_id = created.json()["id"]
    await client.post(f"/api/applications/{application_id}/approve", headers=headers)
    return application_id


async def test_stage_success_transitions_to_staged(
    client: AsyncClient, auth_headers: dict, fake_provider, mock_job_analysis, mock_resume_agent, mock_staging
):
    application_id = await _approved_application(client, auth_headers, fake_provider, mock_job_analysis, mock_resume_agent)
    mock_staging(success=True, fields_filled=["First Name", "Email"])

    resp = await client.post(f"/api/applications/{application_id}/stage", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "staged"
    assert body["staging_notes"]["fields_filled"] == ["First Name", "Email"]


async def test_stage_blocked_transitions_to_submission_blocked(
    client: AsyncClient, auth_headers: dict, fake_provider, mock_job_analysis, mock_resume_agent, mock_staging
):
    application_id = await _approved_application(client, auth_headers, fake_provider, mock_job_analysis, mock_resume_agent)
    mock_staging(success=False, blocked_reason="A visible CAPTCHA challenge is present on the page")

    resp = await client.post(f"/api/applications/{application_id}/stage", headers=auth_headers)
    body = resp.json()
    assert body["status"] == "submission_blocked"
    assert body["staging_notes"]["blocked_reason"] == "A visible CAPTCHA challenge is present on the page"


async def test_cannot_stage_before_approval(
    client: AsyncClient, auth_headers: dict, fake_provider, mock_job_analysis, mock_resume_agent, mock_staging
):
    experience_id = await _build_profile(client, auth_headers)
    fake_provider([POSTING])
    mock_job_analysis(REQUIREMENTS)
    source = await client.post(
        "/api/job-sources", headers=auth_headers, json={"provider": "greenhouse", "company_slug": "acme", "display_name": "Acme"}
    )
    await client.post(f"/api/job-sources/{source.json()['id']}/discover", headers=auth_headers)
    job_id = (await client.get("/api/jobs", headers=auth_headers)).json()[0]["id"]
    mock_resume_agent(_resume_generation(experience_id))
    resume = await client.post("/api/resumes", headers=auth_headers, json={"job_id": job_id})
    resume_version_id = resume.json()["latest_version"]["id"]
    created = await client.post(
        "/api/applications",
        headers=auth_headers,
        json={"job_id": job_id, "resume_version_id": resume_version_id, "generate_cover_letter": False, "custom_questions": []},
    )
    # status is "ready_for_review" here, not yet approved
    resp = await client.post(f"/api/applications/{created.json()['id']}/stage", headers=auth_headers)
    assert resp.status_code == 409


async def test_can_retry_staging_after_blocked(
    client: AsyncClient, auth_headers: dict, fake_provider, mock_job_analysis, mock_resume_agent, mock_staging
):
    application_id = await _approved_application(client, auth_headers, fake_provider, mock_job_analysis, mock_resume_agent)
    mock_staging(success=False, blocked_reason="Encountered a login wall")
    first = await client.post(f"/api/applications/{application_id}/stage", headers=auth_headers)
    assert first.json()["status"] == "submission_blocked"

    mock_staging(success=True, fields_filled=["Email"])
    second = await client.post(f"/api/applications/{application_id}/stage", headers=auth_headers)
    assert second.json()["status"] == "staged"


async def test_mark_submitted_accepts_staged_and_submission_blocked(
    client: AsyncClient, auth_headers: dict, fake_provider, mock_job_analysis, mock_resume_agent, mock_staging
):
    application_id = await _approved_application(client, auth_headers, fake_provider, mock_job_analysis, mock_resume_agent)
    mock_staging(success=True)
    await client.post(f"/api/applications/{application_id}/stage", headers=auth_headers)

    resp = await client.post(f"/api/applications/{application_id}/mark-submitted", headers=auth_headers, json={})
    assert resp.status_code == 200
    assert resp.json()["status"] == "submitted"


async def test_delete_application_removes_staged_screenshot_file(
    client: AsyncClient, auth_headers: dict, fake_provider, mock_job_analysis, mock_resume_agent, mock_staging
):
    application_id = await _approved_application(client, auth_headers, fake_provider, mock_job_analysis, mock_resume_agent)
    mock_staging(success=True, fields_filled=["Email"])
    await client.post(f"/api/applications/{application_id}/stage", headers=auth_headers)

    # mock_staging stubs out the real Playwright page, so no PNG actually lands
    # on disk from that call — write one at the path the service recorded, to
    # exercise the real cleanup-on-delete path exactly as a real screenshot would.
    async with TestSessionLocal() as db:
        application = await db.get(Application, application_id)
        screenshot_path = Path(application.staged_screenshot_path)
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
    screenshot_path.write_bytes(b"fake-png-bytes")
    assert screenshot_path.exists()

    resp = await client.delete(f"/api/applications/{application_id}", headers=auth_headers)
    assert resp.status_code == 204
    assert not screenshot_path.exists()


async def test_staging_screenshot_404s_when_none_available(
    client: AsyncClient, auth_headers: dict, fake_provider, mock_job_analysis, mock_resume_agent
):
    application_id = await _approved_application(client, auth_headers, fake_provider, mock_job_analysis, mock_resume_agent)
    resp = await client.get(f"/api/applications/{application_id}/staging-screenshot", headers=auth_headers)
    assert resp.status_code == 404


async def test_stage_with_unsupported_job_board_blocks_gracefully(
    client: AsyncClient, auth_headers: dict, fake_provider, mock_job_analysis, mock_resume_agent, monkeypatch
):
    application_id = await _approved_application(client, auth_headers, fake_provider, mock_job_analysis, mock_resume_agent)
    monkeypatch.setattr("app.services.application_staging_service.detect_provider", lambda url: None)

    resp = await client.post(f"/api/applications/{application_id}/stage", headers=auth_headers)
    assert resp.json()["status"] == "submission_blocked"
    assert "no automation adapter" in resp.json()["staging_notes"]["blocked_reason"].lower()
