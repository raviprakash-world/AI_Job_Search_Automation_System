from httpx import AsyncClient

from tests.conftest import TestSessionLocal


async def _build_profile_with_experience(client: AsyncClient, headers: dict) -> str:
    await client.put(headers=headers, url="/api/profile", json={"full_name": "Jane Doe", "location": "Remote"})
    exp = await client.post(
        "/api/profile/experiences",
        headers=headers,
        json={
            "company": "Acme Corp",
            "title": "Senior Engineer",
            "start_date": "2020-01-01",
            "end_date": "2023-01-01",
            "responsibilities": ["Led backend team", "Owned API design"],
            "achievements": ["Reduced latency by 30%"],
        },
    )
    await client.post("/api/profile/skills", headers=headers, json={"name": "Python"})
    await client.post("/api/profile/skills", headers=headers, json={"name": "PostgreSQL"})
    return exp.json()["id"]


def _valid_generation(experience_id: str, skills: list[str] | None = None) -> dict:
    return {
        "professional_summary": "Experienced backend engineer focused on reliability and scale.",
        "selected_skill_names": skills or ["Python"],
        "experience_selections": [
            {"experience_id": experience_id, "bullets": ["Led a backend team of 5 engineers"]}
        ],
        "selected_project_ids": [],
        "selected_certification_ids": [],
    }


async def test_create_resume_without_job_generates_ready_version(
    client: AsyncClient, auth_headers: dict, mock_resume_agent
):
    experience_id = await _build_profile_with_experience(client, auth_headers)
    mock_resume_agent(_valid_generation(experience_id))

    resp = await client.post("/api/resumes", headers=auth_headers, json={})
    assert resp.status_code == 201
    body = resp.json()
    assert body["job_id"] is None
    assert body["latest_version"]["status"] == "ready"
    assert body["latest_version"]["version_number"] == 1
    assert body["latest_version"]["structured_content"]["experiences"][0]["company"] == "Acme Corp"


async def test_create_resume_rejects_profile_with_no_experience(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/resumes", headers=auth_headers, json={})
    assert resp.status_code == 422
    assert "experience" in resp.json()["error"]["message"].lower()


async def test_download_resume_version(client: AsyncClient, auth_headers: dict, mock_resume_agent):
    experience_id = await _build_profile_with_experience(client, auth_headers)
    mock_resume_agent(_valid_generation(experience_id))

    created = await client.post("/api/resumes", headers=auth_headers, json={})
    resume_id = created.json()["id"]
    version_id = created.json()["latest_version"]["id"]

    download = await client.get(f"/api/resumes/{resume_id}/versions/{version_id}/download", headers=auth_headers)
    assert download.status_code == 200
    assert download.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert len(download.content) > 0


async def test_regenerate_creates_new_version_without_touching_old(
    client: AsyncClient, auth_headers: dict, mock_resume_agent
):
    experience_id = await _build_profile_with_experience(client, auth_headers)
    mock_resume_agent(_valid_generation(experience_id))

    created = await client.post("/api/resumes", headers=auth_headers, json={})
    resume_id = created.json()["id"]
    v1_id = created.json()["latest_version"]["id"]

    mock_resume_agent(_valid_generation(experience_id, skills=["Python", "PostgreSQL"]))
    regenerated = await client.post(f"/api/resumes/{resume_id}/regenerate", headers=auth_headers)
    assert regenerated.status_code == 200
    body = regenerated.json()
    assert body["latest_version"]["version_number"] == 2
    assert len(body["versions"]) == 2
    assert body["versions"][0]["id"] == v1_id  # original version untouched and still present


async def test_resume_tied_to_job_reports_ats_coverage(
    client: AsyncClient, auth_headers: dict, mock_resume_agent, fake_provider, mock_job_analysis
):
    experience_id = await _build_profile_with_experience(client, auth_headers)

    fake_provider(
        [
            {
                "provider_job_id": "1",
                "title": "Backend Engineer",
                "location_text": "Remote",
                "content": "<p>Python and PostgreSQL required.</p>",
                "raw": {"id": 1},
            }
        ]
    )
    mock_job_analysis({"required_skills": ["Python", "PostgreSQL"], "min_years_experience": 2})
    source = await client.post(
        "/api/job-sources", headers=auth_headers, json={"provider": "greenhouse", "company_slug": "acme"}
    )
    await client.post(f"/api/job-sources/{source.json()['id']}/discover", headers=auth_headers)
    job = (await client.get("/api/jobs", headers=auth_headers)).json()[0]

    mock_resume_agent(_valid_generation(experience_id, skills=["Python"]))
    resp = await client.post("/api/resumes", headers=auth_headers, json={"job_id": job["id"]})
    assert resp.status_code == 201
    qa = resp.json()["latest_version"]["qa_report"]
    assert qa["ats_keyword_coverage"] == 50.0
    assert "Python" in qa["matched_keywords"]
    assert "PostgreSQL" in qa["missing_keywords"]


async def test_generation_fails_gracefully_when_ai_references_unknown_experience(
    client: AsyncClient, auth_headers: dict, mock_resume_agent
):
    await _build_profile_with_experience(client, auth_headers)
    mock_resume_agent(_valid_generation("does-not-exist"))

    resp = await client.post("/api/resumes", headers=auth_headers, json={})
    assert resp.status_code == 201  # the Resume itself is created; the version records the failure
    latest = resp.json()["latest_version"]
    assert latest["status"] == "generation_failed"
    assert latest["qa_report"]["errors"]

    async with TestSessionLocal() as session:
        from sqlalchemy import select

        from app.db.models import AIRequest, AIResponse

        requests = (await session.scalars(select(AIRequest).where(AIRequest.agent_name == "ResumeAgent"))).all()
        assert len(requests) == 1  # both the initial attempt and its retry share one AIRequest/AIResponse pair
        responses = (await session.scalars(select(AIResponse).where(AIResponse.request_id == requests[0].id))).all()
        assert len(responses) == 1
        assert responses[0].validation_status == "invalid"


async def test_create_resume_with_unknown_job_id_404s(client: AsyncClient, auth_headers: dict):
    await _build_profile_with_experience(client, auth_headers)
    resp = await client.post("/api/resumes", headers=auth_headers, json={"job_id": "does-not-exist"})
    assert resp.status_code == 404


async def test_delete_resume(client: AsyncClient, auth_headers: dict, mock_resume_agent):
    experience_id = await _build_profile_with_experience(client, auth_headers)
    mock_resume_agent(_valid_generation(experience_id))
    created = await client.post("/api/resumes", headers=auth_headers, json={})
    resume_id = created.json()["id"]

    delete_resp = await client.delete(f"/api/resumes/{resume_id}", headers=auth_headers)
    assert delete_resp.status_code == 204

    get_resp = await client.get(f"/api/resumes/{resume_id}", headers=auth_headers)
    assert get_resp.status_code == 404


async def test_cannot_access_another_users_resume(client: AsyncClient, auth_headers: dict, mock_resume_agent):
    experience_id = await _build_profile_with_experience(client, auth_headers)
    mock_resume_agent(_valid_generation(experience_id))
    created = await client.post("/api/resumes", headers=auth_headers, json={})
    resume_id = created.json()["id"]

    await client.post("/api/auth/register", json={"email": "other@example.com", "password": "password123", "name": "Other"})
    other_login = await client.post("/api/auth/login", json={"email": "other@example.com", "password": "password123"})
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

    resp = await client.get(f"/api/resumes/{resume_id}", headers=other_headers)
    assert resp.status_code == 404
