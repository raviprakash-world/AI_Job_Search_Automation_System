import httpx
import pytest

from app.core.errors import ProviderError
from app.providers.greenhouse import GreenhouseProvider
from app.providers.lever import LeverProvider


@pytest.fixture
def mock_transport_factory(monkeypatch):
    """Redirects httpx.AsyncClient(...) to use a MockTransport for this test only."""

    def _install(handler):
        real_async_client = httpx.AsyncClient

        def _factory(*args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            return real_async_client(*args, **kwargs)

        monkeypatch.setattr(httpx, "AsyncClient", _factory)

    return _install


async def test_greenhouse_provider_parses_postings(mock_transport_factory):
    def handler(request: httpx.Request) -> httpx.Response:
        assert "boards-api.greenhouse.io" in str(request.url)
        return httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "id": 12345,
                        "title": "Senior Backend Engineer",
                        "location": {"name": "Remote - US"},
                        "absolute_url": "https://boards.greenhouse.io/acme/jobs/12345",
                        "content": "<p>Build our platform.</p>",
                        "updated_at": "2026-01-15T10:00:00Z",
                    }
                ]
            },
        )

    mock_transport_factory(handler)
    postings = await GreenhouseProvider().fetch_postings("acme")

    assert len(postings) == 1
    posting = postings[0]
    assert posting.provider_job_id == "12345"
    assert posting.title == "Senior Backend Engineer"
    assert posting.location_text == "Remote - US"
    assert "Build our platform" in posting.content


async def test_greenhouse_provider_raises_provider_error_on_http_failure(mock_transport_factory):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal error")

    mock_transport_factory(handler)
    with pytest.raises(ProviderError):
        await GreenhouseProvider().fetch_postings("broken-co")


async def test_lever_provider_parses_postings(mock_transport_factory):
    def handler(request: httpx.Request) -> httpx.Response:
        assert "api.lever.co" in str(request.url)
        return httpx.Response(
            200,
            json=[
                {
                    "id": "abc-123",
                    "text": "Product Designer",
                    "categories": {"location": "New York", "team": "Design"},
                    "hostedUrl": "https://jobs.lever.co/acme/abc-123",
                    "descriptionPlain": "Design delightful things.",
                    "createdAt": 1700000000000,
                    "workplaceType": "hybrid",
                }
            ],
        )

    mock_transport_factory(handler)
    postings = await LeverProvider().fetch_postings("acme")

    assert len(postings) == 1
    posting = postings[0]
    assert posting.provider_job_id == "abc-123"
    assert posting.title == "Product Designer"
    assert posting.location_text == "New York"
    assert posting.remote_flag is False  # workplaceType "hybrid" is explicitly not "remote"
    assert posting.content == "Design delightful things."


async def test_lever_provider_raises_provider_error_on_http_failure(mock_transport_factory):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")

    mock_transport_factory(handler)
    with pytest.raises(ProviderError):
        await LeverProvider().fetch_postings("broken-co")
