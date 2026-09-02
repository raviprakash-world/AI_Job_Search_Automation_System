from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.profile_agent import extract_profile_data
from app.core.config import get_settings
from app.core.errors import NotFoundError, UnsupportedFileTypeError, ValidationFailedError
from app.db.models import ProfileDocument, ProfileExtraction
from app.schemas.extraction import ExtractionResolveRequest
from app.services import profile_service
from app.services.document_parsing import SUPPORTED_MIME_TYPES, parse_document
from app.services.reconciliation_service import apply_resolutions, build_conflicts


async def upload_and_extract(db: AsyncSession, *, user_id: str, upload_file: UploadFile) -> ProfileExtraction:
    settings = get_settings()

    if upload_file.content_type not in SUPPORTED_MIME_TYPES:
        raise UnsupportedFileTypeError(f"Unsupported file type: {upload_file.content_type}")

    contents = await upload_file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(contents) > max_bytes:
        raise ValidationFailedError(f"File exceeds {settings.max_upload_size_mb}MB limit")

    profile = await profile_service.get_profile_by_user(db, user_id)

    safe_filename = Path(upload_file.filename or "document").name
    document = ProfileDocument(
        profile_id=profile.id,
        filename=safe_filename,
        mime_type=upload_file.content_type,
        storage_path="",
        size_bytes=len(contents),
        parse_status="pending",
    )
    db.add(document)
    await db.flush()

    destination = settings.storage_path / f"{document.id}_{safe_filename}"
    destination.write_bytes(contents)
    document.storage_path = str(destination)

    try:
        text = parse_document(destination, upload_file.content_type)
    except Exception as exc:  # noqa: BLE001
        document.parse_status = "failed"
        document.parse_error = str(exc)
        await db.commit()
        raise

    document.parse_status = "parsed"
    await db.commit()
    await db.refresh(document)

    extracted, ai_request = await extract_profile_data(db, user_id=user_id, document_text=text)
    conflicts = build_conflicts(profile, extracted)

    extraction = ProfileExtraction(
        document_id=document.id,
        status="pending",
        extracted_data=extracted.model_dump(mode="json"),
        conflicts=[c.model_dump() for c in conflicts],
        ai_request_id=ai_request.id,
    )
    db.add(extraction)
    await db.commit()
    await db.refresh(extraction)
    return extraction


async def get_extraction(db: AsyncSession, *, user_id: str, document_id: str) -> ProfileExtraction:
    stmt = (
        select(ProfileExtraction)
        .join(ProfileDocument)
        .where(ProfileExtraction.document_id == document_id)
        .options(selectinload(ProfileExtraction.document))
    )
    extraction = await db.scalar(stmt)
    if extraction is None:
        raise NotFoundError("Extraction not found")

    profile = await profile_service.get_profile_by_user(db, user_id)
    if extraction.document.profile_id != profile.id:
        raise NotFoundError("Extraction not found")
    return extraction


async def resolve_extraction(
    db: AsyncSession, *, user_id: str, document_id: str, request: ExtractionResolveRequest
) -> ProfileExtraction:
    extraction = await get_extraction(db, user_id=user_id, document_id=document_id)
    profile = await profile_service.get_profile_by_user(db, user_id)
    await apply_resolutions(db, user_id=user_id, profile=profile, extraction=extraction, request=request)
    await db.refresh(extraction)
    return extraction
