from pathlib import Path

from app.db.models import CandidateProfile, Experience, Job
from app.schemas.resumes import ResumeExperienceOut, StructuredResumeContent
from app.services.resume_qa_service import run_qa
from app.services.resume_rendering_service import render_resume_docx


def _profile_with_experience(responsibilities=None, achievements=None) -> CandidateProfile:
    profile = CandidateProfile(user_id="u1", full_name="Jane Doe")
    profile.experiences = [
        Experience(
            id="exp-1",
            company="Acme Corp",
            title="Senior Engineer",
            responsibilities=responsibilities or [],
            achievements=achievements or [],
        )
    ]
    return profile


def _content(bullets: list[str], email="jane@example.com", phone="555-1234") -> StructuredResumeContent:
    return StructuredResumeContent(
        full_name="Jane Doe",
        phone=phone,
        email=email,
        professional_summary="Backend engineer with a track record of shipping reliable systems at scale.",
        skills=["Python", "PostgreSQL"],
        experiences=[
            ResumeExperienceOut(experience_id="exp-1", company="Acme Corp", title="Senior Engineer", bullets=bullets)
        ],
    )


def _render(tmp_path: Path, content: StructuredResumeContent) -> Path:
    destination = tmp_path / "resume.docx"
    render_resume_docx(content, destination)
    return destination


def test_qa_passes_for_well_formed_resume(tmp_path: Path):
    profile = _profile_with_experience(achievements=["Reduced latency by 30%"])
    content = _content(["Reduced latency by 30% through query optimization"] * 20)  # pad for word count
    docx_path = _render(tmp_path, content)

    report = run_qa(profile=profile, content=content, docx_path=docx_path, job=None)

    assert report.errors == []


def test_qa_flags_missing_company_when_content_and_render_disagree(tmp_path: Path):
    profile = _profile_with_experience()
    rendered_content = _content(["Did great things"])
    docx_path = _render(tmp_path, rendered_content)

    # Simulate a corrupted/mismatched render: the content we validate against
    # claims a different company than what's actually in the file.
    mismatched_content = rendered_content.model_copy(deep=True)
    mismatched_content.experiences[0].company = "Umbrella Corp"

    report = run_qa(profile=profile, content=mismatched_content, docx_path=docx_path, job=None)

    assert any("Umbrella Corp" in e for e in report.errors)


def test_qa_flags_missing_email_when_content_and_render_disagree(tmp_path: Path):
    profile = _profile_with_experience()
    rendered_content = _content(["Did great things"], email="jane@example.com")
    docx_path = _render(tmp_path, rendered_content)

    mismatched_content = rendered_content.model_copy(deep=True)
    mismatched_content.email = "someone-else@example.com"

    report = run_qa(profile=profile, content=mismatched_content, docx_path=docx_path, job=None)

    assert any("Email" in e for e in report.errors)


def test_qa_warns_on_short_resume(tmp_path: Path):
    profile = _profile_with_experience()
    content = _content(["Short bullet"])
    docx_path = _render(tmp_path, content)

    report = run_qa(profile=profile, content=content, docx_path=docx_path, job=None)

    assert report.word_count < 150
    assert any("short" in w.lower() for w in report.warnings)


def test_qa_ats_coverage_computes_matched_and_missing(tmp_path: Path):
    profile = _profile_with_experience()
    content = _content(["Built APIs using Python and PostgreSQL"])
    docx_path = _render(tmp_path, content)
    job = Job(title="Backend Engineer", structured_requirements={"required_skills": ["Python", "Kubernetes"]})

    report = run_qa(profile=profile, content=content, docx_path=docx_path, job=job)

    assert report.ats_keyword_coverage == 50.0
    assert "Python" in report.matched_keywords
    assert "Kubernetes" in report.missing_keywords


def test_qa_ats_coverage_is_none_without_job(tmp_path: Path):
    profile = _profile_with_experience()
    content = _content(["Built APIs"])
    docx_path = _render(tmp_path, content)

    report = run_qa(profile=profile, content=content, docx_path=docx_path, job=None)

    assert report.ats_keyword_coverage is None


def test_qa_flags_bullet_metric_not_present_in_source(tmp_path: Path):
    profile = _profile_with_experience(achievements=["Improved reliability"])  # no numbers in source
    content = _content(["Improved reliability by 45%"])
    docx_path = _render(tmp_path, content)

    report = run_qa(profile=profile, content=content, docx_path=docx_path, job=None)

    assert any("45%" in w for w in report.warnings)


def test_qa_does_not_flag_metric_present_in_source(tmp_path: Path):
    profile = _profile_with_experience(achievements=["Reduced latency by 30%"])
    content = _content(["Reduced latency by 30% via caching"])
    docx_path = _render(tmp_path, content)

    report = run_qa(profile=profile, content=content, docx_path=docx_path, job=None)

    assert not any("30%" in w for w in report.warnings)
