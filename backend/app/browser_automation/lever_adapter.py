from app.browser_automation.base import ApplicationAdapter


class LeverApplicationAdapter(ApplicationAdapter):
    name = "lever"

    def resolve_apply_url(self, posting_url: str) -> str:
        # Lever's job posting page only links to the actual application form
        # at {posting_url}/apply — confirmed against a live posting (read-only).
        trimmed = posting_url.rstrip("/")
        return trimmed if trimmed.endswith("/apply") else f"{trimmed}/apply"
