from httpx import AsyncClient


async def test_get_preferences_returns_sensible_defaults(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/preferences", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["automation_mode"] == "semi_automated"
    assert set(body["scoring_weights"].keys()) >= {"skills", "experience", "location"}
    assert body["shortlist_thresholds"]["excellent"] == 90


async def test_update_preferences_persists(client: AsyncClient, auth_headers: dict):
    resp = await client.put(
        "/api/preferences",
        headers=auth_headers,
        json={
            "scoring_weights": {"skills": 0.8, "experience": 0.2},
            "blacklisted_companies": ["Bad Co"],
            "prioritized_companies": ["Dream Co"],
        },
    )
    assert resp.status_code == 200
    assert resp.json()["scoring_weights"] == {"skills": 0.8, "experience": 0.2}

    refetched = await client.get("/api/preferences", headers=auth_headers)
    assert refetched.json()["blacklisted_companies"] == ["Bad Co"]
    assert refetched.json()["prioritized_companies"] == ["Dream Co"]


async def test_partial_update_leaves_other_fields_untouched(client: AsyncClient, auth_headers: dict):
    await client.put("/api/preferences", headers=auth_headers, json={"blacklisted_roles": ["Sales"]})
    resp = await client.put("/api/preferences", headers=auth_headers, json={"automation_mode": "fully_automated"})

    assert resp.json()["automation_mode"] == "fully_automated"
    assert resp.json()["blacklisted_roles"] == ["Sales"]
