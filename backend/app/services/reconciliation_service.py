from datetime import date, datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ValidationFailedError
from app.db.models import (
    CandidateProfile,
    Certification,
    Education,
    Experience,
    Project,
    ProfileExtraction,
    Skill,
)
from app.schemas.extraction import ExtractedProfileData, ExtractionResolveRequest, ProfileChange
from app.services.audit_service import record_audit

_SCALAR_FIELDS = ("full_name", "phone", "location", "professional_summary")


def build_conflicts(profile: CandidateProfile, extracted: ExtractedProfileData) -> list[ProfileChange]:
    """Diff extracted data against the current Master Profile.

    Never returns a decision — every difference becomes a change the user must
    explicitly accept or reject. Matched existing entries are left untouched;
    only genuinely new items or differing scalar fields are surfaced.
    """
    changes: list[ProfileChange] = []

    for field in _SCALAR_FIELDS:
        proposed = getattr(extracted, field)
        existing = getattr(profile, field)
        if proposed is not None and proposed != existing:
            changes.append(
                ProfileChange(
                    change_id=f"field:{field}",
                    kind="field_update",
                    field=field,
                    existing_value=existing,
                    proposed_value=proposed,
                )
            )

    if extracted.links and extracted.links != (profile.links or {}):
        merged = {**(profile.links or {}), **extracted.links}
        if merged != (profile.links or {}):
            changes.append(
                ProfileChange(
                    change_id="field:links",
                    kind="field_update",
                    field="links",
                    existing_value=profile.links,
                    proposed_value=merged,
                )
            )

    existing_exp_keys = {(e.company.strip().lower(), e.title.strip().lower()) for e in profile.experiences}
    for idx, exp in enumerate(extracted.experiences):
        if (exp.company.strip().lower(), exp.title.strip().lower()) not in existing_exp_keys:
            changes.append(
                ProfileChange(
                    change_id=f"experience:{idx}",
                    kind="new_experience",
                    existing_value=None,
                    proposed_value=exp.model_dump(mode="json"),
                )
            )

    existing_edu_keys = {(e.institution.strip().lower(), (e.degree or "").strip().lower()) for e in profile.education}
    for idx, edu in enumerate(extracted.education):
        if (edu.institution.strip().lower(), (edu.degree or "").strip().lower()) not in existing_edu_keys:
            changes.append(
                ProfileChange(
                    change_id=f"education:{idx}",
                    kind="new_education",
                    existing_value=None,
                    proposed_value=edu.model_dump(mode="json"),
                )
            )

    existing_skill_names = {s.name.strip().lower() for s in profile.skills}
    for idx, skill in enumerate(extracted.skills):
        if skill.name.strip().lower() not in existing_skill_names:
            changes.append(
                ProfileChange(
                    change_id=f"skill:{idx}",
                    kind="new_skill",
                    existing_value=None,
                    proposed_value=skill.model_dump(mode="json"),
                )
            )

    existing_cert_names = {c.name.strip().lower() for c in profile.certifications}
    for idx, cert in enumerate(extracted.certifications):
        if cert.name.strip().lower() not in existing_cert_names:
            changes.append(
                ProfileChange(
                    change_id=f"certification:{idx}",
                    kind="new_certification",
                    existing_value=None,
                    proposed_value=cert.model_dump(mode="json"),
                )
            )

    existing_project_names = {p.name.strip().lower() for p in profile.projects}
    for idx, project in enumerate(extracted.projects):
        if project.name.strip().lower() not in existing_project_names:
            changes.append(
                ProfileChange(
                    change_id=f"project:{idx}",
                    kind="new_project",
                    existing_value=None,
                    proposed_value=project.model_dump(mode="json"),
                )
            )

    return changes


def _parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


async def apply_resolutions(
    db: AsyncSession,
    *,
    user_id: str,
    profile: CandidateProfile,
    extraction: ProfileExtraction,
    request: ExtractionResolveRequest,
) -> str:
    """Applies only the changes the user explicitly accepted. Returns the resulting status."""
    conflicts_by_id = {c["change_id"]: c for c in extraction.conflicts}
    accepted_ids = set()
    rejected_ids = set()

    for resolution in request.resolutions:
        change = conflicts_by_id.get(resolution.change_id)
        if change is None:
            raise ValidationFailedError(f"Unknown change_id: {resolution.change_id}")
        if resolution.action == "accept":
            accepted_ids.add(resolution.change_id)
            _apply_change(db, profile=profile, change=change)
        else:
            rejected_ids.add(resolution.change_id)

    if accepted_ids:
        profile.version += 1
        await record_audit(
            db,
            user_id=user_id,
            entity_type="candidate_profile",
            entity_id=profile.id,
            action="apply_extraction",
            actor="ai",
            after={"accepted_change_ids": sorted(accepted_ids), "document_id": extraction.document_id},
        )

    total = len(conflicts_by_id)
    resolved = len(accepted_ids) + len(rejected_ids)
    if resolved < total:
        status = "pending"
    elif accepted_ids and rejected_ids:
        status = "partially_applied"
    elif accepted_ids:
        status = "approved"
    else:
        status = "rejected"

    extraction.status = status
    extraction.reviewed_at = datetime.now(timezone.utc)
    await db.commit()
    return status


def _apply_change(db: AsyncSession, *, profile: CandidateProfile, change: dict) -> None:
    kind = change["kind"]
    proposed = change["proposed_value"]

    if kind == "field_update":
        setattr(profile, change["field"], proposed)
    elif kind == "new_experience":
        db.add(
            Experience(
                profile_id=profile.id,
                company=proposed["company"],
                title=proposed["title"],
                location=proposed.get("location"),
                start_date=_parse_date(proposed.get("start_date")),
                end_date=_parse_date(proposed.get("end_date")),
                is_current=proposed.get("is_current", False),
                responsibilities=proposed.get("responsibilities", []),
                achievements=proposed.get("achievements", []),
            )
        )
    elif kind == "new_education":
        db.add(
            Education(
                profile_id=profile.id,
                institution=proposed["institution"],
                degree=proposed.get("degree"),
                field_of_study=proposed.get("field_of_study"),
                start_date=_parse_date(proposed.get("start_date")),
                end_date=_parse_date(proposed.get("end_date")),
                gpa=proposed.get("gpa"),
            )
        )
    elif kind == "new_skill":
        db.add(Skill(profile_id=profile.id, name=proposed["name"], category=proposed.get("category", "technical")))
    elif kind == "new_certification":
        db.add(
            Certification(
                profile_id=profile.id,
                name=proposed["name"],
                issuer=proposed.get("issuer"),
                issue_date=_parse_date(proposed.get("issue_date")),
                expiry_date=_parse_date(proposed.get("expiry_date")),
                credential_url=proposed.get("credential_url"),
            )
        )
    elif kind == "new_project":
        db.add(
            Project(
                profile_id=profile.id,
                name=proposed["name"],
                description=proposed.get("description"),
                technologies=proposed.get("technologies", []),
                url=proposed.get("url"),
            )
        )
