from app.browser_automation.base import ApplicationAdapter
from app.browser_automation.greenhouse_adapter import GreenhouseApplicationAdapter
from app.browser_automation.lever_adapter import LeverApplicationAdapter

_ADAPTERS: dict[str, ApplicationAdapter] = {
    "greenhouse": GreenhouseApplicationAdapter(),
    "lever": LeverApplicationAdapter(),
}


def detect_provider(posting_url: str) -> str | None:
    if "greenhouse.io" in posting_url:
        return "greenhouse"
    if "lever.co" in posting_url:
        return "lever"
    return None


def get_adapter(provider: str) -> ApplicationAdapter | None:
    return _ADAPTERS.get(provider)
