from httpx import AsyncClient

POSTING = {
    "provider_job_id": "1",
    "title": "Backend Engineer",
    "location_text": "Remote",
    "content": "<p>Python required. Remote role.</p>",
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


async def _discover_job(client: AsyncClient, headers: dict, fake_provider, mock_job_analysis) -> str:
    fake_provider([POSTING])
    mock_job_analysis(REQUIREMENTS)
    source = await client.post(
        "/api/job-sources", headers=headers, json={"provider": "greenhouse", "company_slug": "acme", "display_name": "Acme"}
    )
    await client.post(f"/api/job-sources/{source.json()['id']}/discover", headers=headers)
    jobs = (await client.get("/api/jobs", headers=headers)).json()
    return jobs[0]["id"]


def _resume_generation(experience_id: str) -> dict:
    return {
        "professional_summary": "Experienced backend engineer.",
        "selected_skill_names": ["Python"],
        "experience_selections": [{"experience_id": experience_id, "bullets": ["Led a backend team of 5"]}],
        "selected_project_ids": [],
        "selected_certification_ids": [],
    }


async def test_overview_is_all_zero_for_a_fresh_user(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/dashboard/overview", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"]["jobs_discovered"] == 0
    assert body["summary"]["rejection_rate"] == 0.0
    assert body["summary"]["response_rate"] == 0.0
    assert body["pipeline"] == {
        "discovered": 0,
        "shortlisted": 0,
        "prepared": 0,
        "applied": 0,
        "interview": 0,
        "offer": 0,
    }


async def test_overview_counts_through_the_full_pipeline(
    client: AsyncClient, auth_headers: dict, fake_provider, mock_job_analysis, mock_resume_agent
):
    experience_id = await _build_profile(client, auth_headers)
    job_id = await _discover_job(client, auth_headers, fake_provider, mock_job_analysis)

    await client.post(f"/api/jobs/{job_id}/action", headers=auth_headers, json={"action": "shortlist"})

    mock_resume_agent(_resume_generation(experience_id))
    resume = await client.post("/api/resumes", headers=auth_headers, json={"job_id": job_id})
    resume_version_id = resume.json()["latest_version"]["id"]

    created = await client.post(
        "/api/applications",
        headers=auth_headers,
        json={"job_id": job_id, "resume_version_id": resume_version_id, "generate_cover_letter": False, "custom_questions": []},
    )
    application_id = created.json()["id"]
    await client.post(f"/api/applications/{application_id}/approve", headers=auth_headers)
    await client.post(f"/api/applications/{application_id}/mark-submitted", headers=auth_headers, json={})
    await client.post(f"/api/applications/{application_id}/status", headers=auth_headers, json={"status": "interview"})
    await client.post(f"/api/applications/{application_id}/status", headers=auth_headers, json={"status": "offer"})

    resp = await client.get("/api/dashboard/overview", headers=auth_headers)
    body = resp.json()

    assert body["summary"]["jobs_discovered"] == 1
    assert body["summary"]["jobs_shortlisted"] == 1
    assert body["summary"]["applications_submitted"] == 1
    assert body["summary"]["interviews"] == 1  # counted even though it later moved on to "offer"
    assert body["summary"]["offers"] == 1
    assert body["summary"]["rejections"] == 0
    assert body["summary"]["rejection_rate"] == 0.0
    assert body["summary"]["response_rate"] == 1.0  # reached interview -> "the company responded"

    assert body["pipeline"]["discovered"] == 1
    assert body["pipeline"]["shortlisted"] == 1
    assert body["pipeline"]["prepared"] == 1
    assert body["pipeline"]["applied"] == 1
    assert body["pipeline"]["interview"] == 1
    assert body["pipeline"]["offer"] == 1


async def test_rejection_rate_math(
    client: AsyncClient, auth_headers: dict, fake_provider, mock_job_analysis, mock_resume_agent
):
    experience_id = await _build_profile(client, auth_headers)
    job_id = await _discover_job(client, auth_headers, fake_provider, mock_job_analysis)

    mock_resume_agent(_resume_generation(experience_id))
    resume = await client.post("/api/resumes", headers=auth_headers, json={"job_id": job_id})
    resume_version_id = resume.json()["latest_version"]["id"]

    created = await client.post(
        "/api/applications",
        headers=auth_headers,
        json={"job_id": job_id, "resume_version_id": resume_version_id, "generate_cover_letter": False, "custom_questions": []},
    )
    application_id = created.json()["id"]
    await client.post(f"/api/applications/{application_id}/approve", headers=auth_headers)
    await client.post(f"/api/applications/{application_id}/mark-submitted", headers=auth_headers, json={})
    await client.post(f"/api/applications/{application_id}/status", headers=auth_headers, json={"status": "rejected"})

    resp = await client.get("/api/dashboard/overview", headers=auth_headers)
    body = resp.json()
    assert body["summary"]["rejections"] == 1
    assert body["summary"]["rejection_rate"] == 1.0
    assert body["summary"]["response_rate"] == 1.0  # rejection is still "a response"


async def test_activity_merges_sources_and_sorts_by_recency(
    client: AsyncClient, auth_headers: dict, fake_provider, mock_job_analysis
):
    await client.put(url="/api/profile", headers=auth_headers, json={"full_name": "Jane Doe"})  # -> AuditLog entry
    await _discover_job(client, auth_headers, fake_provider, mock_job_analysis)  # -> AutomationRun-less (Phase 2 endpoint)
    await client.post("/api/automation/discovery/run", headers=auth_headers)  # -> AutomationRun entry

    resp = await client.get("/api/dashboard/activity", headers=auth_headers, params={"limit": 20})
    assert resp.status_code == 200
    items = resp.json()
    types_seen = {item["type"] for item in items}
    assert "audit" in types_seen
    assert "automation_run" in types_seen

    created_ats = [item["created_at"] for item in items]
    assert created_ats == sorted(created_ats, reverse=True)


async def test_alerts_surface_failed_resume_and_flagged_answer(
    client: AsyncClient, auth_headers: dict, fake_provider, mock_job_analysis, mock_resume_agent, mock_answer_agent
):
    experience_id = await _build_profile(client, auth_headers)
    job_id = await _discover_job(client, auth_headers, fake_provider, mock_job_analysis)

    # A resume generation that references an experience_id not in the profile -> generation_failed
    mock_resume_agent(_resume_generation("does-not-exist"))
    resume = await client.post("/api/resumes", headers=auth_headers, json={"job_id": job_id})
    assert resume.json()["latest_version"]["status"] == "generation_failed"

    # A valid resume so an application can actually be created
    mock_resume_agent(_resume_generation(experience_id))
    resume2 = await client.post("/api/resumes", headers=auth_headers, json={"job_id": job_id, "label": "second"})
    resume_version_id = resume2.json()["latest_version"]["id"]

    mock_answer_agent(
        {"results": [{"question": "Expected salary?", "answer": None, "is_grounded": False, "flag_reason": "Not in profile"}]}
    )
    await client.post(
        "/api/applications",
        headers=auth_headers,
        json={
            "job_id": job_id,
            "resume_version_id": resume_version_id,
            "generate_cover_letter": False,
            "custom_questions": ["Expected salary?"],
        },
    )

    resp = await client.get("/api/dashboard/alerts", headers=auth_headers)
    alerts = resp.json()
    alert_types = {a["type"] for a in alerts}
    assert "resume_failed" in alert_types
    assert "answer_flagged" in alert_types


async def test_dashboard_is_scoped_to_the_requesting_user(
    client: AsyncClient, auth_headers: dict, fake_provider, mock_job_analysis
):
    await _discover_job(client, auth_headers, fake_provider, mock_job_analysis)

    await client.post("/api/auth/register", json={"email": "other@example.com", "password": "password123", "name": "Other"})
    other_login = await client.post("/api/auth/login", json={"email": "other@example.com", "password": "password123"})
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

    resp = await client.get("/api/dashboard/overview", headers=other_headers)
    assert resp.json()["summary"]["jobs_discovered"] == 0

    activity = await client.get("/api/dashboard/activity", headers=other_headers)
    assert activity.json() == []
