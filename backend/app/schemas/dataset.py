"""Dataset / DatasetVersion API contracts."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.dataset import ValidationStatus, VersionOrigin


class DatasetVersionRead(BaseModel):
    """Public representation of one immutable dataset snapshot."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version_number: int
    parent_version_id: uuid.UUID | None
    origin: VersionOrigin
    checksum: str
    size_bytes: int
    row_count: int | None
    column_names: list[str] | None
    validation_status: ValidationStatus
    validation_report: dict | None
    transformation: dict | None
    created_at: datetime


class DatasetRead(BaseModel):
    """Public representation of a logical dataset."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    owner_id: uuid.UUID
    created_at: datetime
    latest_version: DatasetVersionRead | None = None


class DatasetDetail(DatasetRead):
    """Dataset with its full version history."""

    versions: list[DatasetVersionRead] = []
