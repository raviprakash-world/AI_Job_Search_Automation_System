from httpx import AsyncClient

POSTING = {
    "provider_job_id": "2001",
    "title": "Data Engineer",
    "location_text": "Austin, TX",
    "absolute_url": "https://boards.greenhouse.io/acme/jobs/2001",
    "content": "<p>Python and SQL required.</p>",
    "raw": {"id": 2001},
}

REQUIREMENTS = {"required_skills": ["Python", "SQL"], "min_years_experience": 2}


async def _discover_one_job(client: AsyncClient, headers: dict, fake_provider, mock_job_analysis, display_name="Acme Corp"):
    fake_provider([POSTING])
    mock_job_analysis(REQUIREMENTS)
    source = await client.post(
        "/api/job-sources",
        headers=headers,
        json={"provider": "greenhouse", "company_slug": "acme", "display_name": display_name},
    )
    await client.post(f"/api/job-sources/{source.json()['id']}/discover", headers=headers)
    jobs = await client.get("/api/jobs", headers=headers)
    return jobs.json()[0]


async def test_shortlist_action_persists_and_filters(client: AsyncClient, auth_headers: dict, fake_provider, mock_job_analysis):
    job = await _discover_one_job(client, auth_headers, fake_provider, mock_job_analysis)

    action = await client.post(f"/api/jobs/{job['id']}/action", headers=auth_headers, json={"action": "shortlist"})
    assert action.status_code == 200
    assert action.json()["status"] == "shortlisted"

    shortlisted = await client.get("/api/jobs", headers=auth_headers, params={"saved_status": "shortlisted"})
    assert len(shortlisted.json()) == 1

    rejected_filter = await client.get("/api/jobs", headers=auth_headers, params={"saved_status": "rejected"})
    assert rejected_filter.json() == []


async def test_action_can_be_changed(client: AsyncClient, auth_headers: dict, fake_provider, mock_job_analysis):
    job = await _discover_one_job(client, auth_headers, fake_provider, mock_job_analysis)

    await client.post(f"/api/jobs/{job['id']}/action", headers=auth_headers, json={"action": "save_for_later"})
    second = await client.post(
        f"/api/jobs/{job['id']}/action", headers=auth_headers, json={"action": "reject", "reason": "Not a fit"}
    )
    assert second.json()["status"] == "rejected"
    assert second.json()["reason"] == "Not a fit"


async def test_action_on_unknown_job_404s(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/jobs/does-not-exist/action", headers=auth_headers, json={"action": "shortlist"})
    assert resp.status_code == 404


async def test_min_score_filter(client: AsyncClient, auth_headers: dict, fake_provider, mock_job_analysis):
    await _discover_one_job(client, auth_headers, fake_provider, mock_job_analysis)

    high_bar = await client.get("/api/jobs", headers=auth_headers, params={"min_score": 999})
    assert high_bar.json() == []

    low_bar = await client.get("/api/jobs", headers=auth_headers, params={"min_score": 0})
    assert len(low_bar.json()) == 1


async def test_blacklisted_company_excluded_by_default(
    client: AsyncClient, auth_headers: dict, fake_provider, mock_job_analysis
):
    await _discover_one_job(client, auth_headers, fake_provider, mock_job_analysis, display_name="Acme Corp")

    await client.put("/api/preferences", headers=auth_headers, json={"blacklisted_companies": ["Acme Corp"]})

    default_list = await client.get("/api/jobs", headers=auth_headers)
    assert default_list.json() == []

    with_blacklisted = await client.get("/api/jobs", headers=auth_headers, params={"include_blacklisted": True})
    assert len(with_blacklisted.json()) == 1
