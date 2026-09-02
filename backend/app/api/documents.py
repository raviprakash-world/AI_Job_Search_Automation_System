from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.extraction import ExtractionResolveRequest, ProfileExtractionOut
from app.services import document_service

router = APIRouter(prefix="/profile/documents", tags=["documents"])


@router.post("", response_model=ProfileExtractionOut, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await document_service.upload_and_extract(db, user_id=current_user.id, upload_file=file)


@router.get("/{document_id}/extraction", response_model=ProfileExtractionOut)
async def get_extraction(
    document_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await document_service.get_extraction(db, user_id=current_user.id, document_id=document_id)


@router.post("/{document_id}/extraction/resolve", response_model=ProfileExtractionOut)
async def resolve_extraction(
    document_id: str,
    payload: ExtractionResolveRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await document_service.resolve_extraction(db, user_id=current_user.id, document_id=document_id, request=payload)
