_BLOCKING_PHRASES = (
    "verify you are human",
    "verify you're human",
    "unusual traffic",
    "are you a robot",
    "complete the security check",
    "please verify you are not a robot",
    "access denied",
)
_CLOSED_PHRASES = (
    "no longer accepting applications",
    "position has been filled",
    "this job is closed",
)


async def detect_blocking_condition(page) -> str | None:
    """Deterministic checks only — never a judgment call. Any hit means the
    caller stops immediately rather than attempting to proceed or work around it.

    An *invisible* reCAPTCHA/hCaptcha anchor iframe is normal background
    infrastructure present on most Greenhouse/Lever forms (it only triggers a
    real challenge at submit time, which this phase never reaches) — only a
    visibly rendered challenge counts as blocking.
    """
    url = page.url.lower()
    if "login" in url or "sign-in" in url or "signin" in url:
        password_fields = await page.locator('input[type="password"]').count()
        if password_fields > 0:
            return "Encountered a login wall — this apply page unexpectedly requires signing in"

    try:
        body_text = (await page.inner_text("body")).lower()
    except Exception:  # noqa: BLE001 - if we can't even read the page, treat it as blocked, not as success
        return "Could not read the page content"

    for phrase in _BLOCKING_PHRASES:
        if phrase in body_text:
            return f"Bot-detection challenge presented on the page ('{phrase}')"

    for phrase in _CLOSED_PHRASES:
        if phrase in body_text:
            return "This job posting is no longer accepting applications"

    captcha_iframes = page.locator('iframe[src*="captcha" i]')
    count = await captcha_iframes.count()
    for i in range(count):
        frame = captcha_iframes.nth(i)
        src = await frame.get_attribute("src") or ""
        if "size=invisible" in src:
            continue
        if await frame.is_visible():
            box = await frame.bounding_box()
            if box and box["width"] > 0 and box["height"] > 0:
                return "A visible CAPTCHA challenge is present on the page"

    return None
