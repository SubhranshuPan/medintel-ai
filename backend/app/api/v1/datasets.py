"""Dataset upload endpoint (ADR-009). Patient-data path — audited (#31)."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_object_store
from app.core.config import get_settings
from app.core.db import get_db
from app.repositories.dataset import DatasetRepository, DatasetVersionRepository
from app.schemas.dataset import DatasetRead, DatasetVersionRead
from app.services.dataset import DatasetService, InvalidCsvError, UploadTooLargeError
from app.storage.object_store import ObjectStore

router = APIRouter(prefix="/datasets", tags=["datasets"])

_ALLOWED_CONTENT_TYPES = {"text/csv", "application/vnd.ms-excel", "application/octet-stream"}


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
    if file.content_type not in _ALLOWED_CONTENT_TYPES or not (file.filename or "").endswith(
        ".csv"
    ):
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
    except InvalidCsvError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid CSV: {exc}",
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
