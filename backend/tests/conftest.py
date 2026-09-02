import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app

# Defense-in-depth: the test client's ASGITransport never triggers the FastAPI
# lifespan (so the scheduler never actually starts today), but disable it
# explicitly too in case lifespan handling is ever added to the test harness.
get_settings().enable_scheduler = False

# The rate limiters are process-global singletons that would otherwise persist
# across every test function in the session (ASGITransport gives every request
# the same client identity), so the same handful of buckets would fill up
# after only a few tests. Rate-limiting behavior itself is unit-tested directly
# against SlidingWindowRateLimiter in test_rate_limit.py.
get_settings().enable_rate_limiting = False

TEST_DATABASE_URL = "sqlite+aiosqlite://"

test_engine = create_async_engine(
    TEST_DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool
)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)


async def _override_get_db():
    async with TestSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = _override_get_db


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient) -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"email": "test@example.com", "password": "password123", "name": "Test User"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class FakeToolUseBlock:
    type = "tool_use"

    def __init__(self, input_data: dict):
        self.input = input_data


class FakeMessage:
    def __init__(self, content: list):
        self.content = content


class FakeAnthropicMessages:
    def __init__(self, tool_input: dict):
        self._tool_input = tool_input

    async def create(self, **kwargs):
        return FakeMessage([FakeToolUseBlock(self._tool_input)])


class FakeAnthropicClient:
    """Stand-in for AsyncAnthropic so tests never call the live API."""

    def __init__(self, tool_input: dict, api_key: str | None = None):
        self.messages = FakeAnthropicMessages(tool_input)


@pytest.fixture
def mock_anthropic(monkeypatch):
    def _install(tool_input: dict):
        monkeypatch.setattr(
            "app.agents.profile_agent.AsyncAnthropic",
            lambda api_key=None: FakeAnthropicClient(tool_input, api_key=api_key),
        )

    return _install


@pytest.fixture
def mock_job_analysis(monkeypatch):
    def _install(tool_input: dict):
        monkeypatch.setattr(
            "app.agents.job_analysis_agent.AsyncAnthropic",
            lambda api_key=None: FakeAnthropicClient(tool_input, api_key=api_key),
        )

    return _install


@pytest.fixture
def mock_resume_agent(monkeypatch):
    def _install(tool_input: dict):
        monkeypatch.setattr(
            "app.agents.resume_agent.AsyncAnthropic",
            lambda api_key=None: FakeAnthropicClient(tool_input, api_key=api_key),
        )

    return _install


@pytest.fixture
def mock_cover_letter_agent(monkeypatch):
    def _install(tool_input: dict):
        monkeypatch.setattr(
            "app.agents.cover_letter_agent.AsyncAnthropic",
            lambda api_key=None: FakeAnthropicClient(tool_input, api_key=api_key),
        )

    return _install


@pytest.fixture
def mock_answer_agent(monkeypatch):
    def _install(tool_input: dict):
        monkeypatch.setattr(
            "app.agents.application_answer_agent.AsyncAnthropic",
            lambda api_key=None: FakeAnthropicClient(tool_input, api_key=api_key),
        )

    return _install


@pytest.fixture
def fake_provider(monkeypatch):
    """Stand-in for a JobSourceProvider so tests never call a live job board API."""
    from app.providers.base import RawPosting

    class FakeProvider:
        def __init__(self, postings: list[RawPosting]):
            self._postings = postings

        async def fetch_postings(self, company_slug: str) -> list[RawPosting]:
            return self._postings

    def _install(postings: list[dict]):
        raw_postings = [RawPosting(**p) for p in postings]
        monkeypatch.setattr(
            "app.services.job_discovery_service.get_provider", lambda name: FakeProvider(raw_postings)
        )

    return _install


@pytest_asyncio.fixture
async def playwright_page():
    """A real headless Chromium page for browser-automation tests — always
    loaded via page.set_content() with a local fixture, never a live URL."""
    from playwright.async_api import async_playwright

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            yield page
        finally:
            await browser.close()


@pytest.fixture
def mock_staging(monkeypatch):
    """Stubs the browser layer for application-staging API tests — these test
    the state machine (approved -> staged/submission_blocked), not the real
    adapter fill logic, which has its own dedicated browser-based tests."""
    from contextlib import asynccontextmanager
    from unittest.mock import AsyncMock

    from app.browser_automation.base import FillResult

    def _install(*, success: bool, blocked_reason: str | None = None, fields_filled: list[str] | None = None):
        result = FillResult(
            success=success, fields_filled=fields_filled or [], blocked_reason=blocked_reason
        )

        class _FakeAdapter:
            async def fill_application(self, page, apply_url, context):
                return result

        @asynccontextmanager
        async def _fake_browser_page():
            page = AsyncMock()
            yield page

        monkeypatch.setattr("app.services.application_staging_service.get_adapter", lambda provider: _FakeAdapter())
        monkeypatch.setattr("app.services.application_staging_service.detect_provider", lambda url: "greenhouse")
        monkeypatch.setattr("app.services.application_staging_service.browser_page", _fake_browser_page)

    return _install
