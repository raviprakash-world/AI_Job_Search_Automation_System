from io import BytesIO

from docx import Document
from httpx import AsyncClient

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _make_docx_bytes(paragraphs: list[str]) -> bytes:
    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


async def test_upload_creates_pending_extraction_with_conflicts(
    client: AsyncClient, auth_headers: dict, mock_anthropic
):
    mock_anthropic(
        {
            "full_name": "Jane Doe",
            "professional_summary": "Backend engineer",
            "experiences": [
                {"company": "Acme Corp", "title": "Senior Engineer", "responsibilities": [], "achievements": []}
            ],
            "skills": [{"name": "Python", "category": "technical"}],
        }
    )

    file_bytes = _make_docx_bytes(["Jane Doe", "Senior Engineer at Acme Corp"])
    resp = await client.post(
        "/api/profile/documents",
        headers=auth_headers,
        files={"file": ("resume.docx", file_bytes, DOCX_MIME)},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "pending"
    change_ids = {c["change_id"] for c in body["conflicts"]}
    assert "field:full_name" in change_ids
    assert "experience:0" in change_ids
    assert "skill:0" in change_ids


async def test_resolve_accept_applies_only_accepted_changes(
    client: AsyncClient, auth_headers: dict, mock_anthropic
):
    mock_anthropic(
        {
            "full_name": "Jane Doe",
            "experiences": [
                {"company": "Acme Corp", "title": "Senior Engineer", "responsibilities": [], "achievements": []}
            ],
            "skills": [{"name": "Python", "category": "technical"}],
        }
    )
    file_bytes = _make_docx_bytes(["Jane Doe resume"])
    upload = await client.post(
        "/api/profile/documents",
        headers=auth_headers,
        files={"file": ("resume.docx", file_bytes, DOCX_MIME)},
    )
    document_id = upload.json()["document_id"]
    conflicts = {c["change_id"]: c for c in upload.json()["conflicts"]}

    resolve_resp = await client.post(
        f"/api/profile/documents/{document_id}/extraction/resolve",
        headers=auth_headers,
        json={
            "resolutions": [
                {"change_id": "field:full_name", "action": "accept"},
                {"change_id": next(cid for cid in conflicts if cid.startswith("skill:")), "action": "reject"},
                {"change_id": next(cid for cid in conflicts if cid.startswith("experience:")), "action": "accept"},
            ]
        },
    )
    assert resolve_resp.status_code == 200
    assert resolve_resp.json()["status"] == "partially_applied"

    profile = await client.get("/api/profile", headers=auth_headers)
    profile_body = profile.json()
    assert profile_body["full_name"] == "Jane Doe"
    assert len(profile_body["experiences"]) == 1
    assert profile_body["skills"] == []  # rejected, must not be applied


async def test_resolve_rejects_unknown_change_id(client: AsyncClient, auth_headers: dict, mock_anthropic):
    mock_anthropic({"full_name": "Jane Doe"})
    file_bytes = _make_docx_bytes(["Jane Doe resume"])
    upload = await client.post(
        "/api/profile/documents",
        headers=auth_headers,
        files={"file": ("resume.docx", file_bytes, DOCX_MIME)},
    )
    document_id = upload.json()["document_id"]

    resp = await client.post(
        f"/api/profile/documents/{document_id}/extraction/resolve",
        headers=auth_headers,
        json={"resolutions": [{"change_id": "field:does_not_exist", "action": "accept"}]},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_failed"


async def test_upload_rejects_unsupported_file_type(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/api/profile/documents",
        headers=auth_headers,
        files={"file": ("resume.txt", b"plain text", "text/plain")},
    )
    assert resp.status_code == 415


async def test_extraction_schema_validation_failure_is_not_silently_swallowed(
    client: AsyncClient, auth_headers: dict, mock_anthropic
):
    # Extracted data with a field of the wrong type should fail Pydantic validation.
    mock_anthropic({"experiences": [{"company": "Acme"}]})  # missing required "title"

    file_bytes = _make_docx_bytes(["Broken resume"])
    resp = await client.post(
        "/api/profile/documents",
        headers=auth_headers,
        files={"file": ("resume.docx", file_bytes, DOCX_MIME)},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "extraction_validation_failed"
