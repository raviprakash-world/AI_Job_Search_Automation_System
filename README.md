# AI Job Search Automation System

An AI-powered job search operating system: Master Profile → job discovery → matching →
tailored applications → tracking → analytics, with the user in control of every
consequential action.

This repo currently implements **Phase 1 (Foundation)** through **Phase 8
(Hardening & Security Audit)**. The full core loop from the original spec is
built end to end and has been audited for security, performance, AI
hallucination risk, data consistency, automation failure handling, UX, and
test coverage.

## What's implemented

**Phase 1 — Foundation**
- User auth (register/login, JWT access + refresh tokens)
- Master Profile (summary, experience, education, skills, certifications, projects)
- Document ingestion: upload a DOCX/PDF, parse it, extract structured data via Claude
  (strict JSON schema, no fabrication), and require **explicit per-field user
  approval** before anything touches the Master Profile — conflicts are surfaced,
  never auto-applied
- Full audit trail: every AI call (`AIRequest`/`AIResponse`) and every profile
  mutation (`AuditLog`) is recorded
- Structured logging with request correlation IDs, consistent JSON error envelope

**Phase 2 — Job Engine**
- Job discovery from Greenhouse and Lever public job-board APIs (read-only, no auth)
- Deterministic + fuzzy duplicate detection across sources (normalized title/location
  match, `difflib` similarity fallback) — verified against live company boards
- AI-assisted job-requirement extraction (`JobAnalysisAgent`, same schema-validated/
  audited/cached pattern as the Phase 1 `ProfileAgent`) — cached per posting by
  content hash, so an unchanged posting is never re-analyzed
- **Fully deterministic** fit-score matching and explanation (skills, experience,
  location, seniority, salary) — no AI call per match, reproducible and cheap;
  missing data is excluded from scoring rather than penalized or fabricated
  (see `app/services/matching_service.py`)
- Configurable scoring weights, shortlist thresholds, and company/role blacklists
  (`/api/preferences`)
- Shortlist/save/reject/ignore workflow per job

**Phase 3 — Resume Engine**
- AI-tailored resume generation (`ResumeAgent`) that **architecturally cannot
  fabricate facts**: it only writes a summary and bullet text, and selects which
  existing experiences/skills/projects/certifications to include by ID — company
  names, job titles, and dates are always pulled verbatim from the Master Profile
  by our own code, never emitted by the model (see `app/agents/resume_agent.py`)
- Deterministic QA on every generated resume: re-parses the rendered DOCX to
  verify contact info and company names survived generation intact, ATS keyword
  coverage against the target job's requirements (reuses Phase 2's
  `JobAnalysisAgent` output — no recomputation), length bounds, and a heuristic
  that flags any bullet containing a number not present in the source profile text
  for human review
- Renders to an ATS-safe `.docx` (single column, no tables/text boxes/images) via
  `python-docx`
- Immutable version history per resume — regenerating creates a new version
  rather than overwriting the last one; every version stays downloadable
- "Tailor resume" action on any discovered job carries the JD straight into
  Resume Studio

**Phase 4 — Application Engine**
- **Scope boundary, by design**: this phase prepares a complete, human-reviewed
  application package and stops at explicit user approval — it does not itself
  fill out or submit forms on real company sites (that's Phase 7, added later,
  and even there the automation still never clicks the real Submit button). The
  spec's own default is "semi-automated" (user reviews, approves, submits), and
  full automation is explicitly opt-in even in the source spec, not the default
- AI-tailored cover letter generation (`CoverLetterAgent`) using the same
  ID-grounded pattern as the resume engine — it only references experiences
  already vetted for the candidate's resume, never invents new claims
- Grounded application-answer generation (`ApplicationAnswerAgent`) for custom
  questions the user adds — every answer is either truthfully grounded in the
  profile or explicitly flagged for the user to fill in themselves, never guessed
- Four automated quality gates (job validity + duplicate check, candidate/resume
  readiness, match quality vs. your configured threshold, content QA) that must
  all pass before an application reaches `ready_for_review` — a low-match or
  disqualifier gate can be explicitly overridden by the user, and the override is
  logged, never silent
- An explicit state machine (`preparing → ready_for_review → approved → submitted
  → {rejected, interview, offer, withdrawn}`, or `error` on a gate failure) with
  every transition logged to an append-only `ApplicationEvent` timeline — no
  status is ever presented as more automated than it actually is
- Application Workspace (job/match context, gate results, resume + cover letter
  preview and download, answer review, approve/submit/outcome actions) and an
  Application Tracker list view

**Phase 5 — Automation Scheduler**
- Recurring background job discovery (default every 6h), daily digest generation,
  and daily stale-application checks, all wired via `APScheduler` into the FastAPI
  process — no separate worker or broker needed at this scale
- Unlike Phase 4, this automation runs **on by default**: discovery and digest/
  reminder generation only fetch public job data and create in-app notifications —
  nothing is ever sent externally and no application is ever submitted, so it's
  safe to run without a human approval gate (the spec's own "automate low-risk
  operations aggressively" principle)
- Every run — scheduled or manually triggered — is recorded as an `AutomationRun`
  with one `AutomationStep` per job source or user, so one failing source (e.g. a
  job board temporarily down) never hides what the rest of the run accomplished
- Stale-application reminders only ever **recommend** following up — the system
  never messages a recruiter or any external party on the user's behalf, and an
  application already flagged and unchanged since is never re-flagged
- Automation Center page: run history with expandable per-step detail, manual
  "run now" triggers, and a notifications list (with a live unread-count badge
  in the nav bar)

**Phase 6 — Dashboard & Analytics**
- Entirely a **read-only aggregation layer** — no new domain entity, no new AI
  agent. Summary counts and the pipeline funnel (Discovered → Shortlisted →
  Prepared → Applied → Interview → Offer) are derived from `JobMatch`,
  `SavedJob`, `Application`, and `ApplicationEvent`; interview/offer/rejection
  counts reflect *ever reaching* that status (via the event history), not just
  current state, so an application that moved interview → offer is counted
  correctly under both
- The activity feed merges three already-existing append-only logs —
  `AuditLog`, `ApplicationEvent`, `AutomationRun` — into one sorted timeline,
  rather than introducing a fourth log table
- Alerts surface things needing attention right now (failed application prep,
  failed/QA-flagged resume or cover letter versions, unreviewed flagged
  application answers) — distinct from Phase 5's `Notification`, which is for
  already-delivered digest/stale-check messages
- Top job recommendations reuse `GET /api/jobs` (Phase 2) directly rather than
  a duplicate endpoint

**Phase 7 — Live Application Submission (staging only)**
- **Scope boundary, confirmed with the user before building**: Playwright drives
  a real browser to fill out the real application form on the employer's own
  hosted apply page (Greenhouse/Lever) and stops right before the Submit
  button, with a full-page screenshot staged for review. It never clicks
  Submit — the user does that themselves on the real page. This was a
  deliberate, explicit decision, not a technical limitation
- **Non-negotiable regardless of configuration**: no CAPTCHA solving, no
  bot-detection evasion, no "looks human" timing tricks. Any friction on the
  real site — a visible CAPTCHA challenge, an unexpected login wall, a closed
  posting — stops the automation immediately and hands off to the user
  (`app/browser_automation/blocking_detection.py`); an *invisible* reCAPTCHA/
  hCaptcha anchor (normal background infrastructure present on most real
  Greenhouse/Lever forms) is correctly not treated as blocking, since it only
  triggers a real challenge at submit time, which this phase never reaches
- Fields are discovered generically from the live DOM and matched by label
  text (`app/browser_automation/field_matching.py`) rather than hardcoded
  selectors, since each job's custom questions differ even though the
  platform's own hosted-form template doesn't — matched against known targets
  (name/email/phone/resume) or against the free-text `ApplicationAnswer`s
  already on file; anything that can't be confidently matched is left blank
  and listed for the user, never guessed at (checkboxes/radios/selects,
  including EEO demographic questions, are never filled at all in this phase)
- Extends the Phase 4 state machine additively:
  `approved → staged (screenshot ready for review) → submitted`, or
  `→ submission_blocked` with the exact reason recorded — `mark-submitted`
  still accepts a fallback from either state, since "submitted" has always
  honestly meant "the user told us," never "we submitted it"
- **Testing never touches a real employer's site** — field-matching is
  unit-tested standalone, and the adapters/blocking-detection are verified
  with real headless-Chromium runs against local HTML fixtures mirroring the
  real Greenhouse/Lever hosted-form structure (calibrated via one read-only,
  fill-nothing/submit-nothing DOM inspection of a live Greenhouse apply page)

**Phase 8 — Hardening & Security Audit**
- A retrospective audit across everything built in Phases 1–7, not new
  features. Covered: security (injection, IDOR/authZ, file handling, error
  disclosure, secrets), performance (query patterns), AI hallucination risk,
  data consistency (cascades/orphaned files), automation failure handling,
  UX, and test coverage — matching the spec's own Phase 8 scope
- **Confirmed clean, no change needed**: no raw SQL/`eval`/`pickle`/`os.system`
  anywhere (ORM only); every user-owned entity fetched by ID is
  ownership-checked before use, with `Job` correctly left unscoped since it's
  shared, global data, not per-user; all three file-download endpoints serve
  DB-stored server-generated paths behind an ownership check, so there's no
  path-traversal surface; uploaded filenames are sanitized to strip directory
  components; unhandled exceptions are logged in full server-side but return
  only a generic error to the client; scheduled jobs are isolated so one
  failing run (or one failing source within a run) can never crash the
  process or hide the rest of a run's results; the main list/dashboard
  queries use eager loading and batched lookups, not N+1 per-row queries
- **Fixed**: added rate limiting to `/auth/login` and `/auth/register`
  (`app/core/rate_limit.py` — an in-process sliding window, since this is a
  single-process deployment) to stop unlimited password-guessing; added a
  startup guard that refuses to boot if `ENVIRONMENT=production` and
  `JWT_SECRET` is still the shipped placeholder, rather than silently running
  insecurely; wired up the previously-issued-but-unused `refresh_token` end
  to end (`POST /api/auth/refresh` + a frontend interceptor that retries once
  on a `401` before forcing logout), so a session no longer silently breaks
  30 minutes after login; fixed `delete_application` to remove the staged
  screenshot file from disk (it already removed the DB row, but was leaking
  the file — the same pattern `delete_resume` already used correctly for
  resume files); added IDOR regression tests for `job_sources` and
  `notifications`, the two ownership-checked endpoints that didn't already
  have one (applications/profile/resumes already did)

## Stack

- **Backend**: Python, FastAPI, SQLAlchemy 2.0 (async), Alembic, PostgreSQL, Anthropic Claude API
- **Frontend**: React + TypeScript (Vite), TanStack Query, React Router, Tailwind CSS

## Local development

### 1. Database

```bash
docker compose up -d postgres
```

Postgres is mapped to host port **5434** (not 5432) to avoid colliding with other
local projects — see `docker-compose.yml`.

### 2. Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium   # browser binary for application staging (Phase 7)
cp .env.example .env   # fill in ANTHROPIC_API_KEY to enable document extraction
alembic upgrade head
uvicorn app.main:app --reload
```

Runs on `http://localhost:8000`. Health check: `GET /api/health`.

Run tests: `pytest` (uses an in-memory SQLite DB and a mocked Anthropic client —
no live API calls or Docker required). Lint: `ruff check app tests`.

### 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Runs on `http://localhost:5173`. Run tests: `npm run test`. Type-check: `npx tsc -b`.
Build: `npm run build`.

## Notes

- Without `ANTHROPIC_API_KEY` set, document upload, job analysis, resume
  generation, cover letter generation, and application-answer generation all
  parse/run successfully but the AI step itself fails gracefully
  (`extraction_validation_failed`) rather than fabricating data or crashing — this
  is intentional guardrail behavior, not a bug. A resume/cover letter in this
  state is created with a version marked `generation_failed`, never shown as a
  fake success. Matching and the application quality gates still work without a
  key, since neither calls AI.
- `ProfileVersion` and other entities from the full system design are
  deliberately not created yet; they belong to later phases.
- The scheduler is controlled by `ENABLE_SCHEDULER` (default on); the test suite
  forces it off so the test run never starts real background timers. Discovery
  interval and digest/stale-check times are configurable via `.env`
  (`DISCOVERY_INTERVAL_MINUTES`, `DIGEST_HOUR_UTC`, `STALE_CHECK_HOUR_UTC`,
  `STALE_APPLICATION_DAYS`).
- Login/register rate limiting is controlled by `ENABLE_RATE_LIMITING` (default
  on); the test suite forces it off for the same reason it forces the
  scheduler off (a process-global limiter would otherwise fill up across
  unrelated tests) — its behavior is unit-tested directly instead.
  `JWT_SECRET` must be changed from the shipped placeholder before running
  with `ENVIRONMENT=production`; the app refuses to start otherwise.
- `POST /api/job-sources/{id}/discover` (Phase 2, single source) and
  `POST /api/automation/discovery/run` (Phase 5, all of a user's active sources)
  both still exist — the former was left as-is rather than retrofitted, since it
  was already working and tested.
- Staging screenshots are saved under `storage/staging_screenshots/` (same base
  directory as resumes/documents) and served back only to the owning user via
  `GET /api/applications/{id}/staging-screenshot`.
- Automation only has adapters for Greenhouse and Lever (the two providers this
  project already integrates for discovery). Staging a job from any other
  source correctly reports "no automation adapter available" and moves to
  `submission_blocked` rather than silently doing nothing.
