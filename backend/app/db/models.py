from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utcnow

# --- Auth -------------------------------------------------------------------


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    profile: Mapped["CandidateProfile"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    preferences: Mapped["UserPreference"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")


class UserPreference(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "user_preferences"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    automation_mode: Mapped[str] = mapped_column(String(20), default="semi_automated", nullable=False)
    notification_settings: Mapped[dict] = mapped_column(JSON, default=dict)
    scoring_weights: Mapped[dict] = mapped_column(JSON, default=dict)
    shortlist_thresholds: Mapped[dict] = mapped_column(JSON, default=dict)
    blacklisted_companies: Mapped[list] = mapped_column(JSON, default=list)
    blacklisted_roles: Mapped[list] = mapped_column(JSON, default=list)
    prioritized_companies: Mapped[list] = mapped_column(JSON, default=list)

    user: Mapped["User"] = relationship(back_populates="preferences")


# --- Master Profile -----------------------------------------------------------


class CandidateProfile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "candidate_profiles"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)

    full_name: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(50))
    location: Mapped[str | None] = mapped_column(String(255))
    preferred_locations: Mapped[list] = mapped_column(JSON, default=list)
    work_authorization: Mapped[str | None] = mapped_column(String(255))

    professional_summary: Mapped[str | None] = mapped_column(Text)
    target_roles: Mapped[list] = mapped_column(JSON, default=list)
    salary_expectation_min: Mapped[int | None] = mapped_column(Integer)
    salary_expectation_max: Mapped[int | None] = mapped_column(Integer)
    notice_period: Mapped[str | None] = mapped_column(String(100))
    remote_preference: Mapped[str | None] = mapped_column(String(50))
    links: Mapped[dict] = mapped_column(JSON, default=dict)

    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    user: Mapped["User"] = relationship(back_populates="profile")
    experiences: Mapped[list["Experience"]] = relationship(back_populates="profile", cascade="all, delete-orphan", order_by="Experience.display_order")
    education: Mapped[list["Education"]] = relationship(back_populates="profile", cascade="all, delete-orphan", order_by="Education.display_order")
    skills: Mapped[list["Skill"]] = relationship(back_populates="profile", cascade="all, delete-orphan")
    certifications: Mapped[list["Certification"]] = relationship(back_populates="profile", cascade="all, delete-orphan")
    projects: Mapped[list["Project"]] = relationship(back_populates="profile", cascade="all, delete-orphan")


class Experience(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "experiences"

    profile_id: Mapped[str] = mapped_column(ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    responsibilities: Mapped[list] = mapped_column(JSON, default=list)
    achievements: Mapped[list] = mapped_column(JSON, default=list)
    display_order: Mapped[int] = mapped_column(Integer, default=0)

    profile: Mapped["CandidateProfile"] = relationship(back_populates="experiences")


class Education(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "education"

    profile_id: Mapped[str] = mapped_column(ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False)
    institution: Mapped[str] = mapped_column(String(255), nullable=False)
    degree: Mapped[str | None] = mapped_column(String(255))
    field_of_study: Mapped[str | None] = mapped_column(String(255))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    gpa: Mapped[str | None] = mapped_column(String(20))
    display_order: Mapped[int] = mapped_column(Integer, default=0)

    profile: Mapped["CandidateProfile"] = relationship(back_populates="education")


class Skill(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "skills"

    profile_id: Mapped[str] = mapped_column(ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(50), default="technical")
    proficiency: Mapped[str | None] = mapped_column(String(50))

    profile: Mapped["CandidateProfile"] = relationship(back_populates="skills")


class Certification(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "certifications"

    profile_id: Mapped[str] = mapped_column(ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    issuer: Mapped[str | None] = mapped_column(String(255))
    issue_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    credential_url: Mapped[str | None] = mapped_column(String(500))

    profile: Mapped["CandidateProfile"] = relationship(back_populates="certifications")


class Project(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "projects"

    profile_id: Mapped[str] = mapped_column(ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    technologies: Mapped[list] = mapped_column(JSON, default=list)
    url: Mapped[str | None] = mapped_column(String(500))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)

    profile: Mapped["CandidateProfile"] = relationship(back_populates="projects")


# --- Document ingestion -------------------------------------------------------


class ProfileDocument(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "profile_documents"

    profile_id: Mapped[str] = mapped_column(ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    parse_status: Mapped[str] = mapped_column(String(30), default="pending")
    parse_error: Mapped[str | None] = mapped_column(Text)

    extraction: Mapped["ProfileExtraction"] = relationship(
        back_populates="document", uselist=False, cascade="all, delete-orphan"
    )


class ProfileExtraction(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "profile_extractions"

    document_id: Mapped[str] = mapped_column(
        ForeignKey("profile_documents.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(30), default="pending")  # pending/approved/rejected/partially_applied/failed
    extracted_data: Mapped[dict] = mapped_column(JSON, default=dict)
    conflicts: Mapped[list] = mapped_column(JSON, default=list)
    ai_request_id: Mapped[str | None] = mapped_column(ForeignKey("ai_requests.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    document: Mapped["ProfileDocument"] = relationship(back_populates="extraction")


# --- AI auditability -----------------------------------------------------------


class AIRequest(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ai_requests"

    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    input_data: Mapped[dict] = mapped_column(JSON, default=dict)

    response: Mapped["AIResponse"] = relationship(back_populates="request", uselist=False, cascade="all, delete-orphan")


class AIResponse(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ai_responses"

    request_id: Mapped[str] = mapped_column(ForeignKey("ai_requests.id", ondelete="CASCADE"), unique=True, nullable=False)
    output_data: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence: Mapped[float | None] = mapped_column(Float)
    validation_status: Mapped[str] = mapped_column(String(30), default="pending")  # valid/invalid/pending
    error: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[int | None] = mapped_column(Integer)

    request: Mapped["AIRequest"] = relationship(back_populates="response")


# --- Job engine ---------------------------------------------------------------


class Company(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    domain: Mapped[str | None] = mapped_column(String(255))

    jobs: Mapped[list["Job"]] = relationship(back_populates="company")


class JobSource(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "job_sources"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)  # greenhouse/lever
    company_slug: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Job(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "jobs"

    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    location: Mapped[str | None] = mapped_column(String(255))
    remote_status: Mapped[str | None] = mapped_column(String(30))  # remote/hybrid/onsite/unknown
    employment_type: Mapped[str | None] = mapped_column(String(50))
    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_max: Mapped[int | None] = mapped_column(Integer)
    salary_currency: Mapped[str | None] = mapped_column(String(10))
    description_text: Mapped[str | None] = mapped_column(Text)
    posting_url: Mapped[str | None] = mapped_column(String(1000))

    structured_requirements: Mapped[dict] = mapped_column(JSON, default=dict)
    analysis_status: Mapped[str] = mapped_column(String(30), default="pending")  # pending/analyzed/failed
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)

    status: Mapped[str] = mapped_column(String(20), default="open")  # open/closed
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    company: Mapped["Company | None"] = relationship(back_populates="jobs")
    snapshots: Mapped[list["JobSnapshot"]] = relationship(back_populates="job", cascade="all, delete-orphan")


class JobSnapshot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "job_snapshots"
    __table_args__ = (UniqueConstraint("job_source_id", "provider_job_id", name="uq_job_snapshot_source_provider_job"),)

    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    job_source_id: Mapped[str] = mapped_column(ForeignKey("job_sources.id", ondelete="CASCADE"), nullable=False)
    provider_job_id: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    job: Mapped["Job"] = relationship(back_populates="snapshots")


class JobMatch(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "job_matches"
    __table_args__ = (UniqueConstraint("job_id", "user_id", name="uq_job_match_job_user"),)

    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    fit_score: Mapped[float] = mapped_column(Float, nullable=False)
    dimension_scores: Mapped[dict] = mapped_column(JSON, default=dict)
    hard_disqualifiers: Mapped[list] = mapped_column(JSON, default=list)
    strong_matches: Mapped[list] = mapped_column(JSON, default=list)
    gaps: Mapped[list] = mapped_column(JSON, default=list)
    summary: Mapped[str] = mapped_column(Text, default="")
    scoring_weights_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    job: Mapped["Job"] = relationship(foreign_keys=[job_id])


class SavedJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "saved_jobs"
    __table_args__ = (UniqueConstraint("job_id", "user_id", name="uq_saved_job_job_user"),)

    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)  # shortlisted/saved_for_later/rejected/ignored
    reason: Mapped[str | None] = mapped_column(Text)


# --- Resume engine --------------------------------------------------------------


class Resume(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "resumes"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"))
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    include_projects: Mapped[bool] = mapped_column(Boolean, default=True)
    include_certifications: Mapped[bool] = mapped_column(Boolean, default=True)

    versions: Mapped[list["ResumeVersion"]] = relationship(
        back_populates="resume", cascade="all, delete-orphan", order_by="ResumeVersion.version_number"
    )


class ResumeVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "resume_versions"
    __table_args__ = (UniqueConstraint("resume_id", "version_number", name="uq_resume_version_number"),)

    resume_id: Mapped[str] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)  # ready/qa_failed/generation_failed
    structured_content: Mapped[dict] = mapped_column(JSON, default=dict)
    file_path: Mapped[str | None] = mapped_column(String(1000))
    qa_report: Mapped[dict] = mapped_column(JSON, default=dict)
    ai_request_id: Mapped[str | None] = mapped_column(ForeignKey("ai_requests.id"))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    resume: Mapped["Resume"] = relationship(back_populates="versions")


# --- Application engine ---------------------------------------------------------


class CoverLetter(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "cover_letters"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    resume_version_id: Mapped[str | None] = mapped_column(ForeignKey("resume_versions.id", ondelete="SET NULL"))
    label: Mapped[str] = mapped_column(String(255), nullable=False)

    versions: Mapped[list["CoverLetterVersion"]] = relationship(
        back_populates="cover_letter", cascade="all, delete-orphan", order_by="CoverLetterVersion.version_number"
    )


class CoverLetterVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "cover_letter_versions"
    __table_args__ = (UniqueConstraint("cover_letter_id", "version_number", name="uq_cover_letter_version_number"),)

    cover_letter_id: Mapped[str] = mapped_column(ForeignKey("cover_letters.id", ondelete="CASCADE"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)  # ready/qa_failed/generation_failed
    body_text: Mapped[str] = mapped_column(Text, default="")
    file_path: Mapped[str | None] = mapped_column(String(1000))
    qa_report: Mapped[dict] = mapped_column(JSON, default=dict)
    ai_request_id: Mapped[str | None] = mapped_column(ForeignKey("ai_requests.id"))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    cover_letter: Mapped["CoverLetter"] = relationship(back_populates="versions")


class Application(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "applications"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    resume_version_id: Mapped[str | None] = mapped_column(ForeignKey("resume_versions.id", ondelete="SET NULL"))
    cover_letter_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("cover_letter_versions.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="preparing")
    custom_questions: Mapped[list] = mapped_column(JSON, default=list)
    generate_cover_letter: Mapped[bool] = mapped_column(Boolean, default=True)
    override_low_match: Mapped[bool] = mapped_column(Boolean, default=False)
    gate_report: Mapped[dict] = mapped_column(JSON, default=dict)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcome_note: Mapped[str | None] = mapped_column(Text)
    staged_screenshot_path: Mapped[str | None] = mapped_column(String(1000))
    staging_notes: Mapped[dict] = mapped_column(JSON, default=dict)

    events: Mapped[list["ApplicationEvent"]] = relationship(
        back_populates="application", cascade="all, delete-orphan", order_by="ApplicationEvent.created_at"
    )
    answers: Mapped[list["ApplicationAnswer"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    job: Mapped["Job"] = relationship(foreign_keys=[job_id])
    resume_version: Mapped["ResumeVersion | None"] = relationship(foreign_keys=[resume_version_id])
    cover_letter_version: Mapped["CoverLetterVersion | None"] = relationship(foreign_keys=[cover_letter_version_id])


class ApplicationEvent(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "application_events"

    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(30))
    to_status: Mapped[str] = mapped_column(String(30), nullable=False)
    actor: Mapped[str] = mapped_column(String(20), default="user")  # user/ai/system
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    application: Mapped["Application"] = relationship(back_populates="events")


class ApplicationAnswer(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "application_answers"

    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text)
    is_grounded: Mapped[bool] = mapped_column(Boolean, default=False)
    flag_reason: Mapped[str | None] = mapped_column(Text)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_request_id: Mapped[str | None] = mapped_column(ForeignKey("ai_requests.id"))

    application: Mapped["Application"] = relationship(back_populates="answers")


# --- Automation -------------------------------------------------------------


class AutomationRun(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "automation_runs"

    run_type: Mapped[str] = mapped_column(String(30), nullable=False)  # discovery/digest/stale_check
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")  # running/completed/failed
    triggered_by: Mapped[str] = mapped_column(String(20), nullable=False)  # scheduler/user
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))  # null = system-wide
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)

    steps: Mapped[list["AutomationStep"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="AutomationStep.created_at"
    )


class AutomationStep(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "automation_steps"

    run_id: Mapped[str] = mapped_column(ForeignKey("automation_runs.id", ondelete="CASCADE"), nullable=False)
    step_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # success/failed
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    run: Mapped["AutomationRun"] = relationship(back_populates="steps")


class Notification(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "notifications"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)  # digest/stale_application
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, default="")
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


# --- Audit -----------------------------------------------------------------


class AuditLog(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "audit_logs"

    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    actor: Mapped[str] = mapped_column(String(20), default="user")  # user/ai/system
    before_data: Mapped[dict | None] = mapped_column(JSON)
    after_data: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
