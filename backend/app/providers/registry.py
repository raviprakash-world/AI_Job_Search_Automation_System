from app.providers.base import JobSourceProvider
from app.providers.greenhouse import GreenhouseProvider
from app.providers.lever import LeverProvider

_PROVIDERS: dict[str, JobSourceProvider] = {
    "greenhouse": GreenhouseProvider(),
    "lever": LeverProvider(),
}


def get_provider(name: str) -> JobSourceProvider:
    provider = _PROVIDERS.get(name)
    if provider is None:
        raise ValueError(f"Unknown job source provider: {name}")
    return provider
