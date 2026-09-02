from app.db.models import CandidateProfile, Experience
from app.schemas.extraction import ExtractedExperience, ExtractedProfileData, ExtractedSkill
from app.services.reconciliation_service import build_conflicts


def _empty_profile(**overrides) -> CandidateProfile:
    profile = CandidateProfile(user_id="u1", links={}, **overrides)
    profile.experiences = []
    profile.education = []
    profile.skills = []
    profile.certifications = []
    profile.projects = []
    return profile


def test_new_scalar_field_is_flagged_as_change():
    profile = _empty_profile(full_name=None, location="Remote")
    extracted = ExtractedProfileData(full_name="Jane Doe")

    changes = build_conflicts(profile, extracted)

    assert any(c.change_id == "field:full_name" and c.proposed_value == "Jane Doe" for c in changes)


def test_matching_scalar_field_is_not_flagged():
    profile = _empty_profile(full_name="Jane Doe")
    extracted = ExtractedProfileData(full_name="Jane Doe")

    changes = build_conflicts(profile, extracted)

    assert not any(c.field == "full_name" for c in changes)


def test_extraction_never_overwrites_existing_value_silently():
    """A differing scalar field must surface as a pending change, not auto-apply."""
    profile = _empty_profile(full_name="Existing Name")
    extracted = ExtractedProfileData(full_name="Different Name From Resume")

    changes = build_conflicts(profile, extracted)
    change = next(c for c in changes if c.field == "full_name")

    assert change.existing_value == "Existing Name"
    assert change.proposed_value == "Different Name From Resume"
    assert profile.full_name == "Existing Name"  # unchanged until explicitly resolved


def test_existing_experience_is_not_duplicated():
    profile = _empty_profile()
    profile.experiences = [Experience(company="Acme", title="Engineer")]
    extracted = ExtractedProfileData(
        experiences=[
            ExtractedExperience(company="Acme", title="Engineer"),
            ExtractedExperience(company="NewCo", title="Lead Engineer"),
        ]
    )

    changes = build_conflicts(profile, extracted)
    new_experience_changes = [c for c in changes if c.kind == "new_experience"]

    assert len(new_experience_changes) == 1
    assert new_experience_changes[0].proposed_value["company"] == "NewCo"


def test_experience_match_is_case_insensitive():
    profile = _empty_profile()
    profile.experiences = [Experience(company="Acme Corp", title="Software Engineer")]
    extracted = ExtractedProfileData(
        experiences=[ExtractedExperience(company="ACME CORP", title="software engineer")]
    )

    changes = build_conflicts(profile, extracted)

    assert not any(c.kind == "new_experience" for c in changes)


def test_new_skill_is_flagged():
    profile = _empty_profile()
    extracted = ExtractedProfileData(skills=[ExtractedSkill(name="Kubernetes")])

    changes = build_conflicts(profile, extracted)

    assert any(c.kind == "new_skill" and c.proposed_value["name"] == "Kubernetes" for c in changes)


def test_empty_extraction_produces_no_changes():
    profile = _empty_profile(full_name="Jane Doe", location="Remote")
    extracted = ExtractedProfileData()

    changes = build_conflicts(profile, extracted)

    assert changes == []
