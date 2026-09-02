import hashlib
import html
import re

from bs4 import BeautifulSoup

_REMOTE_KEYWORDS = ("remote", "work from home", "wfh")
_HYBRID_KEYWORDS = ("hybrid",)
_ONSITE_KEYWORDS = ("on-site", "onsite", "in office", "in-office")


def normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def html_to_text(content: str) -> str:
    if not content:
        return ""
    # Some providers (e.g. Greenhouse) return the description as HTML-escaped HTML
    # (entities encoded once more on top of real markup) rather than plain markup.
    # Unescaping first is a no-op for already-plain HTML/text, so it's safe either way.
    unescaped = html.unescape(content)
    soup = BeautifulSoup(unescaped, "html.parser")
    text = soup.get_text(separator="\n")
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def infer_remote_status(location_text: str | None, remote_flag: bool | None, description_text: str) -> str:
    if remote_flag is True:
        return "remote"
    if remote_flag is False:
        return "onsite"

    haystack = f"{location_text or ''} {description_text[:2000]}".lower()
    if any(kw in haystack for kw in _REMOTE_KEYWORDS):
        return "remote"
    if any(kw in haystack for kw in _HYBRID_KEYWORDS):
        return "hybrid"
    if any(kw in haystack for kw in _ONSITE_KEYWORDS):
        return "onsite"
    return "unknown"


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
