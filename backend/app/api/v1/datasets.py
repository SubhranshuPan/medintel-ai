"""Dataset upload endpoint (ADR-009). Patient-data path — audited (#31)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_object_store
from app.core.config import get_settings
from app.core.db import get_db
from app.repositories.dataset import DatasetRepository, DatasetVersionRepository
from app.schemas.dataset import DatasetRead, DatasetVersionRead
from app.services.dataset import (
    DatasetForbiddenError,
    DatasetNotFoundError,
    DatasetService,
    InvalidCsvError,
    UploadTooLargeError,
)
from app.storage.object_store import ObjectStore

router = APIRouter(prefix="/datasets", tags=["datasets"])

_ALLOWED_CONTENT_TYPES = {
    "text/csv",
    "application/csv",
    "application/vnd.ms-excel",
    "application/octet-stream",
}


def _service(db: AsyncSession, store: ObjectStore) -> DatasetService:
    return DatasetService(
        DatasetRepository(db), DatasetVersionRepository(db), store, get_settings()
    )


@router.post("", response_model=DatasetRead, status_code=status.HTTP_201_CREATED)
async def upload_dataset(
    request: Request,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    store: Annotated[ObjectStore, Depends(get_object_store)],
    name: Annotated[str, Form(max_length=255)],
    file: Annotated[UploadFile, File()],
    description: Annotated[str | None, Form()] = None,
) -> DatasetRead:
    """Upload a clinical CSV. Stores the raw artifact immutably and records v1.

    PHI note: treated as patient-level data regardless of synthetic origin
    (TRD §9) — audited by AuditLogMiddleware, RBAC-gated to authenticated users.
    """
    if file.content_type not in _ALLOWED_CONTENT_TYPES or not (
        file.filename or ""
    ).lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only .csv files are accepted",
        )

    content = await file.read()
    try:
        dataset, version = await _service(db, store).create_from_upload(
            name=name,
            description=description,
            filename=file.filename,
            content=content,
            owner=current_user,
        )
    except UploadTooLargeError:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds the upload size limit",
        ) from None
    except InvalidCsvError:
        # Deliberately generic: the underlying parser message can echo raw file
        # bytes/content (e.g. UnicodeDecodeError's byte snippet) back to the
        # client — treated as PHI, so it never belongs in an API response body.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File could not be parsed as CSV",
        ) from None

    # Enriches the AuditLogMiddleware row with the resource this request created.
    request.state.audit_resource_id = str(dataset.id)
    request.state.audit_detail = {"filename": file.filename, "row_count": version.row_count}

    return DatasetRead(
        id=dataset.id,
        name=dataset.name,
        description=dataset.description,
        owner_id=dataset.owner_id,
        created_at=dataset.created_at,
        latest_version=DatasetVersionRead.model_validate(version),
    )


@router.post("/{dataset_id}/validate", response_model=DatasetVersionRead)
async def revalidate_dataset(
    dataset_id: UUID,
    request: Request,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    store: Annotated[ObjectStore, Depends(get_object_store)],
) -> DatasetVersionRead:
    """Re-run validation against the dataset's latest version (TRD §12, ADR-014)."""
    try:
        version = await _service(db, store).revalidate_latest(
            dataset_id, requester=current_user
        )
    except DatasetNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found"
        ) from None
    except DatasetForbiddenError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not permitted to validate this dataset",
        ) from None

    request.state.audit_resource_id = str(dataset_id)
    request.state.audit_detail = {"validation_status": version.validation_status.value}

    return DatasetVersionRead.model_validate(version)


@router.post(
    "/{dataset_id}/clean", response_model=DatasetVersionRead, status_code=status.HTTP_201_CREATED
)
async def clean_dataset(
    dataset_id: UUID,
    request: Request,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    store: Annotated[ObjectStore, Depends(get_object_store)],
) -> DatasetVersionRead:
    """Derive a new cleaned version from the dataset's latest version (ADR-009, #34)."""
    try:
        version = await _service(db, store).clean_latest(dataset_id, requester=current_user)
    except DatasetNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found"
        ) from None
    except DatasetForbiddenError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not permitted to clean this dataset",
        ) from None

    request.state.audit_resource_id = str(dataset_id)
    request.state.audit_detail = {"origin": "cleaned", "version_number": version.version_number}

    return DatasetVersionRead.model_validate(version)
