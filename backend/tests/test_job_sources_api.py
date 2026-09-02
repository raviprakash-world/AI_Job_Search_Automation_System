from httpx import AsyncClient

BACKEND_ENGINEER_POSTING = {
    "provider_job_id": "1001",
    "title": "Senior Backend Engineer",
    "location_text": "Remote - US",
    "absolute_url": "https://boards.greenhouse.io/acme/jobs/1001",
    "content": "<p>We need Python and PostgreSQL experience. 5+ years required.</p>",
    "raw": {"id": 1001},
}

JOB_REQUIREMENTS = {
    "required_skills": ["Python", "PostgreSQL"],
    "preferred_skills": ["AWS"],
    "min_years_experience": 5,
    "seniority_level": "senior",
}


async def _add_source(client: AsyncClient, headers: dict, slug="acme", display_name="Acme Corp", provider="greenhouse"):
    resp = await client.post(
        "/api/job-sources",
        headers=headers,
        json={"provider": provider, "company_slug": slug, "display_name": display_name},
    )
    assert resp.status_code == 201
    return resp.json()


async def test_create_list_delete_job_source(client: AsyncClient, auth_headers: dict):
    created = await _add_source(client, auth_headers)
    assert created["provider"] == "greenhouse"
    assert created["company_slug"] == "acme"

    listed = await client.get("/api/job-sources", headers=auth_headers)
    assert len(listed.json()) == 1

    delete_resp = await client.delete(f"/api/job-sources/{created['id']}", headers=auth_headers)
    assert delete_resp.status_code == 204

    listed_after = await client.get("/api/job-sources", headers=auth_headers)
    assert listed_after.json() == []


async def test_discover_creates_job_analyzes_and_computes_match(
    client: AsyncClient, auth_headers: dict, fake_provider, mock_job_analysis
):
    fake_provider([BACKEND_ENGINEER_POSTING])
    mock_job_analysis(JOB_REQUIREMENTS)

    source = await _add_source(client, auth_headers)
    result = await client.post(f"/api/job-sources/{source['id']}/discover", headers=auth_headers)
    assert result.status_code == 200
    body = result.json()
    assert body["fetched"] == 1
    assert body["new_jobs"] == 1
    assert body["matched"] == 1

    jobs = await client.get("/api/jobs", headers=auth_headers)
    job_list = jobs.json()
    assert len(job_list) == 1
    job = job_list[0]
    assert job["title"] == "Senior Backend Engineer"
    assert job["analysis_status"] == "analyzed"
    assert job["match"] is not None
    assert job["match"]["fit_score"] > 0

    detail = await client.get(f"/api/jobs/{job['id']}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["structured_requirements"]["required_skills"] == ["Python", "PostgreSQL"]
    assert len(detail.json()["snapshots"]) == 1


async def test_rediscovering_unchanged_posting_skips_reanalysis(
    client: AsyncClient, auth_headers: dict, fake_provider, mock_job_analysis
):
    fake_provider([BACKEND_ENGINEER_POSTING])
    mock_job_analysis(JOB_REQUIREMENTS)

    source = await _add_source(client, auth_headers)
    first = await client.post(f"/api/job-sources/{source['id']}/discover", headers=auth_headers)
    assert first.json()["new_jobs"] == 1

    second = await client.post(f"/api/job-sources/{source['id']}/discover", headers=auth_headers)
    body = second.json()
    assert body["new_jobs"] == 0
    assert body["updated_jobs"] == 0
    assert body["matched"] == 0  # nothing changed, so nothing was re-matched


async def test_cannot_access_another_users_job_source(client: AsyncClient, auth_headers: dict):
    created = await _add_source(client, auth_headers)

    await client.post("/api/auth/register", json={"email": "other@example.com", "password": "password123", "name": "Other"})
    other_login = await client.post("/api/auth/login", json={"email": "other@example.com", "password": "password123"})
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

    delete_resp = await client.delete(f"/api/job-sources/{created['id']}", headers=other_headers)
    assert delete_resp.status_code == 404

    discover_resp = await client.post(f"/api/job-sources/{created['id']}/discover", headers=other_headers)
    assert discover_resp.status_code == 404

    # the owner's source is untouched
    still_listed = await client.get("/api/job-sources", headers=auth_headers)
    assert len(still_listed.json()) == 1


async def test_discover_merges_duplicate_posting_across_sources(
    client: AsyncClient, auth_headers: dict, fake_provider, mock_job_analysis
):
    mock_job_analysis(JOB_REQUIREMENTS)

    fake_provider([BACKEND_ENGINEER_POSTING])
    source_a = await _add_source(client, auth_headers, slug="acme-gh", display_name="Acme Corp", provider="greenhouse")
    result_a = await client.post(f"/api/job-sources/{source_a['id']}/discover", headers=auth_headers)
    assert result_a.json()["new_jobs"] == 1

    same_job_different_source = {**BACKEND_ENGINEER_POSTING, "provider_job_id": "lever-9999"}
    fake_provider([same_job_different_source])
    source_b = await _add_source(client, auth_headers, slug="acme-lever", display_name="Acme Corp", provider="lever")
    result_b = await client.post(f"/api/job-sources/{source_b['id']}/discover", headers=auth_headers)
    body_b = result_b.json()
    assert body_b["new_jobs"] == 0
    assert body_b["duplicates_merged"] == 1

    jobs = await client.get("/api/jobs", headers=auth_headers)
    assert len(jobs.json()) == 1  # still just one canonical job

    detail = await client.get(f"/api/jobs/{jobs.json()[0]['id']}", headers=auth_headers)
    assert len(detail.json()["snapshots"]) == 2  # attributed to both sources
