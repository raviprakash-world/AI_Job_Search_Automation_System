# Contributing

Thanks for considering a contribution. This is a personal project, but it's
open to fixes, improvements, and discussion.

## Project principles (please read before contributing)

This system automates a genuinely consequential part of someone's life — their
job search — so a few rules are non-negotiable in any contribution:

- **Never fabricate candidate information.** AI-generated content (resumes,
  cover letters, application answers) may only reference facts already present
  in the candidate's Master Profile. If you're touching an agent
  (`backend/app/agents/`), preserve the existing pattern: the model selects
  IDs / writes prose, but company names, job titles, dates, and metrics are
  always injected by our own code, never emitted by the model.
- **No fake success states.** If something failed, degraded, or is unverified,
  say so — don't show a generic success UI over it.
- **Human approval for consequential/external actions.** Nothing gets
  submitted to a real employer without an explicit user action. Automation
  that touches a real employer's site stops at the first sign of friction
  (CAPTCHA, login wall, navigation failure) and hands off to the user —
  never retried automatically, never worked around.
- **No CAPTCHA solving or bot-detection evasion, ever**, regardless of what a
  feature request asks for.

If a change conflicts with one of these, it isn't a good fit for this repo
even if it technically works.

## Dev setup

See the [README](README.md#local-development) for the full setup (Postgres via
Docker, Python venv + `pip install`, Playwright browser install, `npm install`).

## Before opening a PR

**Backend** (`backend/`):
```bash
pytest
ruff check app tests
```

**Frontend** (`frontend/`):
```bash
npx tsc -b
npm run test
npm run lint
npm run build
```

All of the above should pass. If you're changing browser automation
(`app/browser_automation/`), test against local HTML fixtures only — never a
real employer's site (see `tests/conftest.py`'s `playwright_page` fixture and
the existing adapter tests for the pattern).

## Style

- No comments explaining *what* code does — names should do that. A comment
  is only worth adding when it explains a non-obvious *why* (a workaround, a
  subtle invariant, a constraint that isn't visible from the code itself).
- Prefer extending an existing pattern over introducing a new one — this repo
  reuses a small number of patterns deliberately (the provider/adapter
  registry, the forced-tool-use agent pattern, the ownership-scoped
  `get_owned_*` service functions, append-only event/audit logs). Check
  `backend/app/services/` and `backend/app/agents/` for a similar case before
  adding something new.
- Match the existing commit style: a short imperative summary line, and a body
  only when the *why* isn't obvious from the diff.

## Reporting issues

Open a GitHub issue with what you expected, what happened instead, and
repro steps. For anything security-related, please don't open a public issue —
see below.

## Security

If you find a security issue (an authorization gap, an injection vector, a
way to bypass the human-approval boundary on submission, etc.), please report
it privately rather than opening a public issue — use GitHub's "Report a
vulnerability" flow under the repo's **Security** tab.
