from httpx import AsyncClient

GOOD_POSTING = {
    "provider_job_id": "1",
    "title": "Backend Engineer",
    "location_text": "Remote",
    "content": "<p>Python required. Remote role.</p>",
    "raw": {"id": 1},
}
GOOD_REQUIREMENTS = {"required_skills": ["Python"], "min_years_experience": 1}

LOW_MATCH_POSTING = {
    "provider_job_id": "2",
    "title": "Platform Engineer",
    "location_text": "Remote",
    "content": "<p>Kubernetes expert needed. Remote role.</p>",
    "raw": {"id": 2},
}
LOW_MATCH_REQUIREMENTS = {"required_skills": ["Kubernetes"], "min_years_experience": 10}


async def _build_profile(client: AsyncClient, headers: dict) -> str:
    await client.put(url="/api/profile", headers=headers, json={"full_name": "Jane Doe", "location": "Remote"})
    exp = await client.post(
        "/api/profile/experiences",
        headers=headers,
        json={
            "company": "Acme Corp",
            "title": "Senior Engineer",
            "start_date": "2021-01-01",
            "end_date": "2024-01-01",
            "responsibilities": ["Led backend team"],
            "achievements": ["Reduced latency by 30%"],
        },
    )
    await client.post("/api/profile/skills", headers=headers, json={"name": "Python"})
    return exp.json()["id"]


async def _discover_job(client: AsyncClient, headers: dict, fake_provider, mock_job_analysis, posting, requirements, slug) -> str:
    fake_provider([posting])
    mock_job_analysis(requirements)
    source = await client.post(
        "/api/job-sources", headers=headers, json={"provider": "greenhouse", "company_slug": slug, "display_name": "Acme"}
    )
    await client.post(f"/api/job-sources/{source.json()['id']}/discover", headers=headers)
    jobs = (await client.get("/api/jobs", headers=headers, params={"company": "Acme"})).json()
    return next(j["id"] for j in jobs if j["title"] == posting["title"])


def _resume_generation(experience_id: str) -> dict:
    return {
        "professional_summary": "Experienced backend engineer.",
        "selected_skill_names": ["Python"],
        "experience_selections": [{"experience_id": experience_id, "bullets": ["Led a backend team of 5"]}],
        "selected_project_ids": [],
        "selected_certification_ids": [],
    }


def _cover_letter_generation(experience_id: str) -> dict:
    return {
        "body_text": "I'm excited to apply for this role given my backend engineering background.\n\nI led a team of 5 engineers.",
        "referenced_experience_ids": [experience_id],
    }


async def _setup_ready_resume(
    client: AsyncClient, headers: dict, fake_provider, mock_job_analysis, mock_resume_agent, posting, requirements, slug
) -> tuple[str, str, str]:
    experience_id = await _build_profile(client, headers)
    job_id = await _discover_job(client, headers, fake_provider, mock_job_analysis, posting, requirements, slug)
    mock_resume_agent(_resume_generation(experience_id))
    resume = await client.post("/api/resumes", headers=headers, json={"job_id": job_id})
    resume_version_id = resume.json()["latest_version"]["id"]
    return job_id, resume_version_id, experience_id


async def test_create_application_reaches_ready_for_review(
    client: AsyncClient, auth_headers: dict, fake_provider, mock_job_analysis, mock_resume_agent, mock_cover_letter_agent
):
    job_id, resume_version_id, experience_id = await _setup_ready_resume(
        client, auth_headers, fake_provider, mock_job_analysis, mock_resume_agent, GOOD_POSTING, GOOD_REQUIREMENTS, "acme"
    )
    mock_cover_letter_agent(_cover_letter_generation(experience_id))

    resp = await client.post(
        "/api/applications",
        headers=auth_headers,
        json={"job_id": job_id, "resume_version_id": resume_version_id, "generate_cover_letter": True, "custom_questions": []},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "ready_for_review"
    assert body["gate_report"]["passed"] is True
    assert body["cover_letter_version"]["status"] == "ready"
    assert len(body["events"]) == 2  # preparing -> ready_for_review


async def test_create_application_without_cover_letter(
    client: AsyncClient, auth_headers: dict, fake_provider, mock_job_analysis, mock_resume_agent
):
    job_id, resume_version_id, _ = await _setup_ready_resume(
        client, auth_headers, fake_provider, mock_job_analysis, mock_resume_agent, GOOD_POSTING, GOOD_REQUIREMENTS, "acme"
    )

    resp = await client.post(
        "/api/applications",
        headers=auth_headers,
        json={"job_id": job_id, "resume_version_id": resume_version_id, "generate_cover_letter": False, "custom_questions": []},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["cover_letter_version"] is None
    assert body["status"] == "ready_for_review"


async def test_flagged_answer_blocks_progression_until_reviewed(
    client: AsyncClient, auth_headers: dict, fake_provider, mock_job_analysis, mock_resume_agent, mock_answer_agent
):
    job_id, resume_version_id, _ = await _setup_ready_resume(
        client, auth_headers, fake_provider, mock_job_analysis, mock_resume_agent, GOOD_POSTING, GOOD_REQUIREMENTS, "acme"
    )
    mock_answer_agent(
        {"results": [{"question": "Expected salary?", "answer": None, "is_grounded": False, "flag_reason": "Not in profile"}]}
    )

    resp = await client.post(
        "/api/applications",
        headers=auth_headers,
        json={
            "job_id": job_id,
            "resume_version_id": resume_version_id,
            "generate_cover_letter": False,
            "custom_questions": ["Expected salary?"],
        },
    )
    body = resp.json()
    assert body["status"] == "error"
    assert body["gate_report"]["passed"] is False
    answer_id = body["answers"][0]["id"]

    review = await client.put(
        f"/api/applications/{body['id']}/answers/{answer_id}", headers=auth_headers, json={"answer": "$150,000"}
    )
    assert review.status_code == 200
    assert review.json()["reviewed"] is True

    retried = await client.post(f"/api/applications/{body['id']}/retry-preparation", headers=auth_headers)
    assert retried.json()["status"] == "ready_for_review"


async def test_duplicate_active_application_is_blocked(
    client: AsyncClient, auth_headers: dict, fake_provider, mock_job_analysis, mock_resume_agent
):
    job_id, resume_version_id, _ = await _setup_ready_resume(
        client, auth_headers, fake_provider, mock_job_analysis, mock_resume_agent, GOOD_POSTING, GOOD_REQUIREMENTS, "acme"
    )
    first = await client.post(
        "/api/applications",
        headers=auth_headers,
        json={"job_id": job_id, "resume_version_id": resume_version_id, "generate_cover_letter": False, "custom_questions": []},
    )
    assert first.json()["status"] == "ready_for_review"

    second = await client.post(
        "/api/applications",
        headers=auth_headers,
        json={"job_id": job_id, "resume_version_id": resume_version_id, "generate_cover_letter": False, "custom_questions": []},
    )
    assert second.json()["status"] == "error"
    gate_names = {g["name"]: g["passed"] for g in second.json()["gate_report"]["gates"]}
    assert gate_names["job_valid"] is False


async def test_low_match_blocked_without_override_and_allowed_with_override(
    client: AsyncClient, auth_headers: dict, fake_provider, mock_job_analysis, mock_resume_agent
):
    job_id, resume_version_id, _ = await _setup_ready_resume(
        client, auth_headers, fake_provider, mock_job_analysis, mock_resume_agent, LOW_MATCH_POSTING, LOW_MATCH_REQUIREMENTS, "acme2"
    )

    blocked = await client.post(
        "/api/applications",
        headers=auth_headers,
        json={"job_id": job_id, "resume_version_id": resume_version_id, "generate_cover_letter": False, "custom_questions": []},
    )
    assert blocked.json()["status"] == "error"
    gates = {g["name"]: g for g in blocked.json()["gate_report"]["gates"]}
    assert gates["match_quality"]["passed"] is False

    overridden = await client.post(
        "/api/applications",
        headers=auth_headers,
        json={
            "job_id": job_id,
            "resume_version_id": resume_version_id,
            "generate_cover_letter": False,
            "custom_questions": [],
            "override_low_match": True,
        },
    )
    assert overridden.json()["status"] == "ready_for_review"
    gates2 = {g["name"]: g for g in overridden.json()["gate_report"]["gates"]}
    assert gates2["match_quality"]["passed"] is True
    assert gates2["match_quality"]["overridden"] is True


async def test_approve_and_mark_submitted_happy_path(
    client: AsyncClient, auth_headers: dict, fake_provider, mock_job_analysis, mock_resume_agent
):
    job_id, resume_version_id, _ = await _setup_ready_resume(
        client, auth_headers, fake_provider, mock_job_analysis, mock_resume_agent, GOOD_POSTING, GOOD_REQUIREMENTS, "acme"
    )
    created = await client.post(
        "/api/applications",
        headers=auth_headers,
        json={"job_id": job_id, "resume_version_id": resume_version_id, "generate_cover_letter": False, "custom_questions": []},
    )
    application_id = created.json()["id"]

    approved = await client.post(f"/api/applications/{application_id}/approve", headers=auth_headers)
    assert approved.json()["status"] == "approved"

    submitted = await client.post(
        f"/api/applications/{application_id}/mark-submitted", headers=auth_headers, json={"note": "Applied via company site"}
    )
    assert submitted.json()["status"] == "submitted"
    assert submitted.json()["submitted_at"] is not None

    statuses = [e["to_status"] for e in submitted.json()["events"]]
    assert statuses == ["preparing", "ready_for_review", "approved", "submitted"]


async def test_cannot_mark_submitted_before_approval(
    client: AsyncClient, auth_headers: dict, fake_provider, mock_job_analysis, mock_resume_agent
):
    job_id, resume_version_id, _ = await _setup_ready_resume(
        client, auth_headers, fake_provider, mock_job_analysis, mock_resume_agent, GOOD_POSTING, GOOD_REQUIREMENTS, "acme"
    )
    created = await client.post(
        "/api/applications",
        headers=auth_headers,
        json={"job_id": job_id, "resume_version_id": resume_version_id, "generate_cover_letter": False, "custom_questions": []},
    )
    resp = await client.post(f"/api/applications/{created.json()['id']}/mark-submitted", headers=auth_headers, json={})
    assert resp.status_code == 409


async def test_update_outcome_after_submission(
    client: AsyncClient, auth_headers: dict, fake_provider, mock_job_analysis, mock_resume_agent
):
    job_id, resume_version_id, _ = await _setup_ready_resume(
        client, auth_headers, fake_provider, mock_job_analysis, mock_resume_agent, GOOD_POSTING, GOOD_REQUIREMENTS, "acme"
    )
    created = await client.post(
        "/api/applications",
        headers=auth_headers,
        json={"job_id": job_id, "resume_version_id": resume_version_id, "generate_cover_letter": False, "custom_questions": []},
    )
    application_id = created.json()["id"]
    await client.post(f"/api/applications/{application_id}/approve", headers=auth_headers)
    await client.post(f"/api/applications/{application_id}/mark-submitted", headers=auth_headers, json={})

    outcome = await client.post(
        f"/api/applications/{application_id}/status", headers=auth_headers, json={"status": "interview", "note": "Phone screen scheduled"}
    )
    assert outcome.json()["status"] == "interview"
    assert outcome.json()["outcome_note"] == "Phone screen scheduled"


async def test_cannot_delete_submitted_application(
    client: AsyncClient, auth_headers: dict, fake_provider, mock_job_analysis, mock_resume_agent
):
    job_id, resume_version_id, _ = await _setup_ready_resume(
        client, auth_headers, fake_provider, mock_job_analysis, mock_resume_agent, GOOD_POSTING, GOOD_REQUIREMENTS, "acme"
    )
    created = await client.post(
        "/api/applications",
        headers=auth_headers,
        json={"job_id": job_id, "resume_version_id": resume_version_id, "generate_cover_letter": False, "custom_questions": []},
    )
    application_id = created.json()["id"]
    await client.post(f"/api/applications/{application_id}/approve", headers=auth_headers)
    await client.post(f"/api/applications/{application_id}/mark-submitted", headers=auth_headers, json={})

    resp = await client.delete(f"/api/applications/{application_id}", headers=auth_headers)
    assert resp.status_code == 409


async def test_delete_allowed_before_submission(
    client: AsyncClient, auth_headers: dict, fake_provider, mock_job_analysis, mock_resume_agent
):
    job_id, resume_version_id, _ = await _setup_ready_resume(
        client, auth_headers, fake_provider, mock_job_analysis, mock_resume_agent, GOOD_POSTING, GOOD_REQUIREMENTS, "acme"
    )
    created = await client.post(
        "/api/applications",
        headers=auth_headers,
        json={"job_id": job_id, "resume_version_id": resume_version_id, "generate_cover_letter": False, "custom_questions": []},
    )
    resp = await client.delete(f"/api/applications/{created.json()['id']}", headers=auth_headers)
    assert resp.status_code == 204


async def test_download_cover_letter(
    client: AsyncClient, auth_headers: dict, fake_provider, mock_job_analysis, mock_resume_agent, mock_cover_letter_agent
):
    job_id, resume_version_id, experience_id = await _setup_ready_resume(
        client, auth_headers, fake_provider, mock_job_analysis, mock_resume_agent, GOOD_POSTING, GOOD_REQUIREMENTS, "acme"
    )
    mock_cover_letter_agent(_cover_letter_generation(experience_id))
    created = await client.post(
        "/api/applications",
        headers=auth_headers,
        json={"job_id": job_id, "resume_version_id": resume_version_id, "generate_cover_letter": True, "custom_questions": []},
    )
    application_id = created.json()["id"]

    download = await client.get(f"/api/applications/{application_id}/cover-letter/download", headers=auth_headers)
    assert download.status_code == 200
    assert download.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert len(download.content) > 0


async def test_download_cover_letter_404s_when_none_generated(
    client: AsyncClient, auth_headers: dict, fake_provider, mock_job_analysis, mock_resume_agent
):
    job_id, resume_version_id, _ = await _setup_ready_resume(
        client, auth_headers, fake_provider, mock_job_analysis, mock_resume_agent, GOOD_POSTING, GOOD_REQUIREMENTS, "acme"
    )
    created = await client.post(
        "/api/applications",
        headers=auth_headers,
        json={"job_id": job_id, "resume_version_id": resume_version_id, "generate_cover_letter": False, "custom_questions": []},
    )
    resp = await client.get(f"/api/applications/{created.json()['id']}/cover-letter/download", headers=auth_headers)
    assert resp.status_code == 404


async def test_cannot_access_another_users_application(
    client: AsyncClient, auth_headers: dict, fake_provider, mock_job_analysis, mock_resume_agent
):
    job_id, resume_version_id, _ = await _setup_ready_resume(
        client, auth_headers, fake_provider, mock_job_analysis, mock_resume_agent, GOOD_POSTING, GOOD_REQUIREMENTS, "acme"
    )
    created = await client.post(
        "/api/applications",
        headers=auth_headers,
        json={"job_id": job_id, "resume_version_id": resume_version_id, "generate_cover_letter": False, "custom_questions": []},
    )
    application_id = created.json()["id"]

    await client.post("/api/auth/register", json={"email": "other@example.com", "password": "password123", "name": "Other"})
    other_login = await client.post("/api/auth/login", json={"email": "other@example.com", "password": "password123"})
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

    resp = await client.get(f"/api/applications/{application_id}", headers=other_headers)
    assert resp.status_code == 404
