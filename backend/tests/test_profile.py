from httpx import AsyncClient


async def test_new_user_has_empty_profile(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/profile", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["full_name"] is None
    assert body["experiences"] == []


async def test_update_profile_bumps_version_and_persists(client: AsyncClient, auth_headers: dict):
    resp = await client.put(
        "/api/profile",
        headers=auth_headers,
        json={"full_name": "Jane Doe", "location": "Remote", "professional_summary": "Backend engineer"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["full_name"] == "Jane Doe"
    assert body["version"] == 2

    refetched = await client.get("/api/profile", headers=auth_headers)
    assert refetched.json()["full_name"] == "Jane Doe"


async def test_add_and_delete_experience(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/api/profile/experiences",
        headers=auth_headers,
        json={
            "company": "Acme Corp",
            "title": "Senior Engineer",
            "start_date": "2020-01-01",
            "end_date": "2023-01-01",
            "responsibilities": ["Built APIs"],
            "achievements": ["Reduced latency by 30%"],
        },
    )
    assert resp.status_code == 201
    experience_id = resp.json()["id"]

    profile = await client.get("/api/profile", headers=auth_headers)
    assert len(profile.json()["experiences"]) == 1

    delete_resp = await client.delete(f"/api/profile/experiences/{experience_id}", headers=auth_headers)
    assert delete_resp.status_code == 204

    profile_after = await client.get("/api/profile", headers=auth_headers)
    assert profile_after.json()["experiences"] == []


async def test_add_skill_certification_project(client: AsyncClient, auth_headers: dict):
    skill = await client.post("/api/profile/skills", headers=auth_headers, json={"name": "Python"})
    assert skill.status_code == 201

    cert = await client.post(
        "/api/profile/certifications", headers=auth_headers, json={"name": "AWS SAA", "issuer": "AWS"}
    )
    assert cert.status_code == 201

    project = await client.post(
        "/api/profile/projects",
        headers=auth_headers,
        json={"name": "Job Search Bot", "technologies": ["Python", "FastAPI"]},
    )
    assert project.status_code == 201

    profile = await client.get("/api/profile", headers=auth_headers)
    body = profile.json()
    assert len(body["skills"]) == 1
    assert len(body["certifications"]) == 1
    assert len(body["projects"]) == 1


async def test_cannot_delete_another_users_experience(client: AsyncClient):
    await client.post(
        "/api/auth/register", json={"email": "userA@example.com", "password": "password123", "name": "A"}
    )
    login_a = await client.post("/api/auth/login", json={"email": "userA@example.com", "password": "password123"})
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    exp = await client.post(
        "/api/profile/experiences",
        headers=headers_a,
        json={"company": "Acme", "title": "Engineer"},
    )
    experience_id = exp.json()["id"]

    await client.post("/api/auth/register", json={"email": "userB@example.com", "password": "password123", "name": "B"})
    login_b = await client.post("/api/auth/login", json={"email": "userB@example.com", "password": "password123"})
    headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

    resp = await client.delete(f"/api/profile/experiences/{experience_id}", headers=headers_b)
    assert resp.status_code == 404
