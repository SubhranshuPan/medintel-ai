"""Dataset CRUD + upload/validate/clean endpoints (ADR-009). Patient-data path — audited (#31)."""

from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_object_store
from app.core.config import get_settings
from app.core.db import get_db
from app.repositories.dataset import DatasetRepository, DatasetVersionRepository
from app.schemas.dataset import DatasetDetail, DatasetRead, DatasetVersionRead
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


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")


def _forbidden() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted to access this dataset"
    )


@router.get("", response_model=list[DatasetRead])
async def list_datasets(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    store: Annotated[ObjectStore, Depends(get_object_store)],
    limit: Annotated[int, Query(le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[DatasetRead]:
    """List live datasets — own datasets only, unless admin (#35)."""
    pairs = await _service(db, store).list_for_owner(
        requester=current_user, limit=limit, offset=offset
    )
    return [
        DatasetRead(
            id=dataset.id,
            name=dataset.name,
            description=dataset.description,
            owner_id=dataset.owner_id,
            created_at=dataset.created_at,
            latest_version=DatasetVersionRead.model_validate(latest) if latest else None,
        )
        for dataset, latest in pairs
    ]


@router.get("/{dataset_id}", response_model=DatasetDetail)
async def get_dataset(
    dataset_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    store: Annotated[ObjectStore, Depends(get_object_store)],
) -> DatasetDetail:
    """Dataset detail with full version history (#35). Owner-or-admin only."""
    try:
        dataset, versions = await _service(db, store).get_detail(
            dataset_id, requester=current_user
        )
    except DatasetNotFoundError:
        raise _not_found() from None
    except DatasetForbiddenError:
        raise _forbidden() from None

    return DatasetDetail(
        id=dataset.id,
        name=dataset.name,
        description=dataset.description,
        owner_id=dataset.owner_id,
        created_at=dataset.created_at,
        latest_version=DatasetVersionRead.model_validate(versions[-1]) if versions else None,
        versions=[DatasetVersionRead.model_validate(v) for v in versions],
    )


@router.get("/{dataset_id}/versions", response_model=list[DatasetVersionRead])
async def list_dataset_versions(
    dataset_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    store: Annotated[ObjectStore, Depends(get_object_store)],
) -> list[DatasetVersionRead]:
    """Version history, oldest -> newest (#35). Owner-or-admin only."""
    try:
        versions = await _service(db, store).list_versions(dataset_id, requester=current_user)
    except DatasetNotFoundError:
        raise _not_found() from None
    except DatasetForbiddenError:
        raise _forbidden() from None

    return [DatasetVersionRead.model_validate(v) for v in versions]


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset(
    dataset_id: UUID,
    request: Request,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    store: Annotated[ObjectStore, Depends(get_object_store)],
) -> None:
    """Soft-delete a dataset (#35). Artifacts are kept — see ``soft_delete`` docstring."""
    try:
        await _service(db, store).soft_delete(dataset_id, requester=current_user)
    except DatasetNotFoundError:
        raise _not_found() from None
    except DatasetForbiddenError:
        raise _forbidden() from None

    request.state.audit_resource_id = str(dataset_id)
