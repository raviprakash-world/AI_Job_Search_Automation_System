from app.core.errors import ValidationFailedError
from app.db.models import CandidateProfile
from app.schemas.resumes import (
    ResumeCertificationOut,
    ResumeEducationOut,
    ResumeExperienceOut,
    ResumeGeneration,
    ResumeProjectOut,
    StructuredResumeContent,
)


def assemble_structured_content(
    profile: CandidateProfile,
    generation: ResumeGeneration,
    *,
    email: str,
    include_projects: bool,
    include_certifications: bool,
) -> StructuredResumeContent:
    """Builds the final resume content, pulling every fact (company, title, dates,
    degree) straight from the Master Profile — never from the AI's output. The AI
    only supplied the summary text, bullet text, and which IDs to include."""

    experiences_by_id = {e.id: e for e in profile.experiences}
    projects_by_id = {p.id: p for p in profile.projects}
    certs_by_id = {c.id: c for c in profile.certifications}

    experiences = []
    for selection in generation.experience_selections:
        exp = experiences_by_id[selection.experience_id]
        experiences.append(
            ResumeExperienceOut(
                experience_id=exp.id,
                company=exp.company,
                title=exp.title,
                location=exp.location,
                start_date=exp.start_date,
                end_date=exp.end_date,
                is_current=exp.is_current,
                bullets=selection.bullets,
            )
        )

    projects = []
    if include_projects:
        for project_id in generation.selected_project_ids:
            p = projects_by_id[project_id]
            projects.append(ResumeProjectOut(name=p.name, description=p.description, technologies=p.technologies))

    certifications = []
    if include_certifications:
        for cert_id in generation.selected_certification_ids:
            c = certs_by_id[cert_id]
            certifications.append(ResumeCertificationOut(name=c.name, issuer=c.issuer))

    education = [
        ResumeEducationOut(
            institution=e.institution,
            degree=e.degree,
            field_of_study=e.field_of_study,
            start_date=e.start_date,
            end_date=e.end_date,
        )
        for e in profile.education
    ]

    return StructuredResumeContent(
        full_name=profile.full_name,
        phone=profile.phone,
        email=email,
        location=profile.location,
        links=profile.links or {},
        professional_summary=generation.professional_summary,
        skills=list(generation.selected_skill_names),
        experiences=experiences,
        education=education,
        projects=projects,
        certifications=certifications,
    )


def require_generatable_profile(profile: CandidateProfile) -> None:
    if not profile.experiences:
        raise ValidationFailedError(
            "Your Master Profile has no work experience yet — add at least one experience before generating a resume"
        )
