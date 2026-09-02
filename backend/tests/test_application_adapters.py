import http.server
import threading

import pytest

from app.browser_automation.base import CustomAnswer, FillContext
from app.browser_automation.greenhouse_adapter import GreenhouseApplicationAdapter
from app.browser_automation.lever_adapter import LeverApplicationAdapter

# Mirrors the real structure observed on a live Greenhouse hosted apply page
# (boards.greenhouse.io — read-only inspection, no data ever submitted there):
# id-based standard fields, a generic "Attach" label on the resume upload, and
# custom questions with their own <label for=...>.
GREENHOUSE_FIXTURE = """
<html><body>
<form>
  <label for="first_name">First Name*</label><input id="first_name" type="text" />
  <label for="last_name">Last Name*</label><input id="last_name" type="text" />
  <label for="email">Email*</label><input id="email" type="text" />
  <label for="phone">Phone*</label><input id="phone" type="tel" />
  <label for="resume">Attach</label><input id="resume" type="file" />
  <label for="question_1">Why do you want to join Acme? *</label><textarea id="question_1"></textarea>
  <label for="question_2">What's your favorite color?</label><input id="question_2" type="text" />
  <button type="submit">Submit application</button>
</form>
</body></html>
"""

BLOCKED_FIXTURE = GREENHOUSE_FIXTURE.replace(
    "<form>", "<form><p>Please verify you are human before continuing.</p>"
)

# Mirrors the real structure observed on a live Lever hosted apply page
# (jobs.lever.co/.../apply — read-only inspection, no data ever submitted
# there): name-based fields, a single full-name field, custom questions in
# wrapper divs with their own label.
LEVER_FIXTURE = """
<html><body>
<form>
  <div class="application-question">
    <label class="application-label">Full name*</label>
    <input name="name" type="text" />
  </div>
  <div class="application-question">
    <label class="application-label">Email*</label>
    <input name="email" type="email" />
  </div>
  <div class="application-question">
    <label class="application-label">Phone*</label>
    <input name="phone" type="tel" />
  </div>
  <input name="resume" type="file" />
  <div class="application-question">
    <label class="application-label">Do you now or in the future require sponsorship to work in the United States? *</label>
    <textarea name="cards[abc][field0]"></textarea>
  </div>
  <select name="eeo[gender]"><option>Select...</option><option>Male</option><option>Female</option></select>
  <button type="submit">Submit application</button>
</form>
</body></html>
"""


def _make_handler(routes: dict[str, str]) -> type[http.server.BaseHTTPRequestHandler]:
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - required name by http.server
            content = routes.get(self.path)
            if content is None:
                self.send_response(404)
                self.end_headers()
                return
            body = content.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):  # noqa: A002 - silence request logging in test output
            pass

    return Handler


@pytest.fixture
def html_server():
    """A minimal local HTTP server serving exact-path routes as text/html —
    never a real employer site, just an in-memory fixture for these tests."""
    routes: dict[str, str] = {}
    server = http.server.HTTPServer(("127.0.0.1", 0), _make_handler(routes))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        yield f"http://127.0.0.1:{port}", routes
    finally:
        server.shutdown()
        thread.join(timeout=2)


def _context(**overrides) -> FillContext:
    defaults = dict(
        full_name="Jane Doe",
        email="jane@example.com",
        phone="555-1234",
        links={"linkedin": "https://linkedin.com/in/janedoe"},
    )
    defaults.update(overrides)
    return FillContext(**defaults)


async def test_greenhouse_adapter_fills_standard_and_custom_fields(playwright_page, html_server, tmp_path):
    base_url, routes = html_server
    routes["/greenhouse"] = GREENHOUSE_FIXTURE
    resume_path = tmp_path / "resume.docx"
    resume_path.write_text("dummy resume content")

    context = _context(
        resume_file_path=str(resume_path),
        custom_answers=[CustomAnswer(question="Why do you want to join Acme?", answer="I love the mission")],
    )
    adapter = GreenhouseApplicationAdapter()
    result = await adapter.fill_application(playwright_page, f"{base_url}/greenhouse", context)

    assert result.success is True
    assert result.blocked_reason is None
    assert await playwright_page.input_value("#first_name") == "Jane"
    assert await playwright_page.input_value("#last_name") == "Doe"
    assert await playwright_page.input_value("#email") == "jane@example.com"
    assert await playwright_page.input_value("#phone") == "555-1234"
    assert await playwright_page.input_value("#question_1") == "I love the mission"
    # The unrelated custom question has no matching answer and is never guessed at.
    assert "What's your favorite color?" in result.fields_needing_manual_input
    assert await playwright_page.input_value("#question_2") == ""


async def test_greenhouse_adapter_never_clicks_submit(playwright_page, html_server, tmp_path):
    base_url, routes = html_server
    routes["/greenhouse"] = GREENHOUSE_FIXTURE

    adapter = GreenhouseApplicationAdapter()
    await adapter.fill_application(playwright_page, f"{base_url}/greenhouse", _context())

    # Still on the apply page — no navigation triggered by a submit click.
    assert playwright_page.url == f"{base_url}/greenhouse"


async def test_lever_adapter_resolves_apply_url_and_fills_fields(playwright_page, html_server, tmp_path):
    base_url, routes = html_server
    routes["/lever/apply"] = LEVER_FIXTURE

    context = _context(
        custom_answers=[
            CustomAnswer(
                question="Do you now or in the future require sponsorship to work in the United States?",
                answer="No",
            )
        ]
    )
    adapter = LeverApplicationAdapter()
    # Pass the posting URL (without /apply) — the adapter should resolve it itself.
    result = await adapter.fill_application(playwright_page, f"{base_url}/lever", context)

    assert result.success is True
    assert playwright_page.url == f"{base_url}/lever/apply"
    assert await playwright_page.input_value('input[name="name"]') == "Jane Doe"
    assert await playwright_page.input_value('input[name="email"]') == "jane@example.com"
    assert await playwright_page.input_value('textarea[name="cards[abc][field0]"]') == "No"
    # EEO demographic select is never guessed at — there's no profile data source for it.
    assert result.fields_needing_manual_input  # the gender select has no answer and is reported, not skipped silently


async def test_adapter_stops_at_a_blocking_condition_without_filling_anything(playwright_page, html_server, tmp_path):
    base_url, routes = html_server
    routes["/blocked"] = BLOCKED_FIXTURE

    adapter = GreenhouseApplicationAdapter()
    result = await adapter.fill_application(playwright_page, f"{base_url}/blocked", _context())

    assert result.success is False
    assert "verify you are human" in (result.blocked_reason or "").lower()
    assert result.fields_filled == []
    # Nothing was typed into the form before stopping.
    assert await playwright_page.input_value("#first_name") == ""
