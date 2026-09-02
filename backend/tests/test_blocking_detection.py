from app.browser_automation.blocking_detection import detect_blocking_condition

CLEAN_FORM = """
<html><body>
<form>
  <label for="email">Email</label>
  <input id="email" type="email" />
</form>
<!-- An invisible reCAPTCHA anchor is normal background infrastructure on
     real Greenhouse/Lever forms and must not be treated as blocking. -->
<iframe src="https://www.recaptcha.net/recaptcha/enterprise/anchor?size=invisible" style="display:none"></iframe>
</body></html>
"""

VISIBLE_CAPTCHA_FORM = """
<html><body>
<form><label for="email">Email</label><input id="email" type="email" /></form>
<iframe src="https://www.recaptcha.net/recaptcha/enterprise/anchor?size=normal"
        style="width:300px;height:78px;border:0"></iframe>
</body></html>
"""

BOT_CHALLENGE_TEXT = """
<html><body>
<h1>Please verify you are human before continuing.</h1>
</body></html>
"""

CLOSED_JOB_TEXT = """
<html><body>
<p>Sorry, this job is no longer accepting applications.</p>
</body></html>
"""


async def test_clean_form_with_invisible_recaptcha_is_not_blocked(playwright_page):
    await playwright_page.set_content(CLEAN_FORM)
    assert await detect_blocking_condition(playwright_page) is None


async def test_visible_captcha_challenge_is_blocked(playwright_page):
    await playwright_page.set_content(VISIBLE_CAPTCHA_FORM)
    reason = await detect_blocking_condition(playwright_page)
    assert reason is not None
    assert "captcha" in reason.lower()


async def test_bot_challenge_text_is_blocked(playwright_page):
    await playwright_page.set_content(BOT_CHALLENGE_TEXT)
    reason = await detect_blocking_condition(playwright_page)
    assert reason is not None
    assert "verify you are human" in reason.lower()


async def test_closed_job_text_is_blocked(playwright_page):
    await playwright_page.set_content(CLOSED_JOB_TEXT)
    reason = await detect_blocking_condition(playwright_page)
    assert reason is not None
    assert "no longer accepting" in reason.lower()
