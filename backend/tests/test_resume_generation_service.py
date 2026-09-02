from datetime import date

import pytest

from app.agents.resume_agent import _validate_grounded_references
from app.core.errors import ExtractionValidationError, ValidationFailedError
from app.db.models import CandidateProfile, Certification, Experience, Project, Skill
from app.schemas.resumes import ExperienceSelection, ResumeGeneration
from app.services.resume_generation_service import assemble_structured_content, require_generatable_profile


def _profile() -> CandidateProfile:
    profile = CandidateProfile(
        user_id="u1", full_name="Jane Doe", phone="555-1234", location="Remote", links={"github": "gh.io/jane"}
    )
    profile.experiences = [
        Experience(
            id="exp-1",
            company="Acme Corp",
            title="Senior Engineer",
            location="Remote",
            start_date=date(2020, 1, 1),
            end_date=date(2023, 1, 1),
            is_current=False,
            responsibilities=["Led backend team", "Owned API design"],
            achievements=["Reduced latency by 30%", "Shipped 12 features"],
        )
    ]
    profile.skills = [Skill(id="skill-1", name="Python", category="technical")]
    profile.projects = [Project(id="proj-1", name="Side Project", description="A thing", technologies=["Python"])]
    profile.certifications = [Certification(id="cert-1", name="AWS SAA", issuer="AWS")]
    profile.education = []
    return profile


def _generation(**overrides) -> ResumeGeneration:
    defaults = dict(
        professional_summary="Experienced backend engineer.",
        selected_skill_names=["Python"],
        experience_selections=[ExperienceSelection(experience_id="exp-1", bullets=["Led backend team of 5"])],
        selected_project_ids=["proj-1"],
        selected_certification_ids=["cert-1"],
    )
    defaults.update(overrides)
    return ResumeGeneration(**defaults)


# --- require_generatable_profile ---------------------------------------------


def test_require_generatable_profile_rejects_empty_experience():
    profile = _profile()
    profile.experiences = []
    with pytest.raises(ValidationFailedError):
        require_generatable_profile(profile)


def test_require_generatable_profile_accepts_populated_profile():
    require_generatable_profile(_profile())  # should not raise


# --- assemble_structured_content: facts come from the profile, not the AI -----


def test_assembled_content_pulls_company_title_dates_from_profile():
    content = assemble_structured_content(
        _profile(), _generation(), email="jane@example.com", include_projects=True, include_certifications=True
    )
    exp = content.experiences[0]
    assert exp.company == "Acme Corp"
    assert exp.title == "Senior Engineer"
    assert exp.start_date == date(2020, 1, 1)
    assert exp.end_date == date(2023, 1, 1)
    assert exp.bullets == ["Led backend team of 5"]  # AI-authored bullet is used verbatim


def test_assembled_content_respects_include_flags():
    content = assemble_structured_content(
        _profile(), _generation(), email="jane@example.com", include_projects=False, include_certifications=False
    )
    assert content.projects == []
    assert content.certifications == []


def test_assembled_content_uses_account_email_not_ai_output():
    content = assemble_structured_content(
        _profile(), _generation(), email="jane@example.com", include_projects=True, include_certifications=True
    )
    assert content.email == "jane@example.com"


# --- grounding validation (the hard guardrail) --------------------------------


def test_validate_grounded_references_accepts_valid_ids():
    _validate_grounded_references(_generation(), _profile())  # should not raise


def test_validate_grounded_references_rejects_unknown_experience_id():
    generation = _generation(experience_selections=[ExperienceSelection(experience_id="does-not-exist", bullets=["x"])])
    with pytest.raises(ExtractionValidationError):
        _validate_grounded_references(generation, _profile())


def test_validate_grounded_references_rejects_unknown_skill():
    generation = _generation(selected_skill_names=["Kubernetes"])  # not in profile
    with pytest.raises(ExtractionValidationError):
        _validate_grounded_references(generation, _profile())


def test_validate_grounded_references_rejects_zero_experiences():
    generation = _generation(experience_selections=[])
    with pytest.raises(ExtractionValidationError):
        _validate_grounded_references(generation, _profile())


def test_validate_grounded_references_skill_match_is_case_insensitive():
    generation = _generation(selected_skill_names=["PYTHON"])
    _validate_grounded_references(generation, _profile())  # should not raise
