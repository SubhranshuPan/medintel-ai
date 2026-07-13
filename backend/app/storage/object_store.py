"""Immutable object storage for dataset artifacts (ADR-009).

Content-addressed: the key IS the sha256 of the bytes, so writing the same
content twice is a no-op and an existing object can never be overwritten with
different content. Local disk in development; the same Protocol is what an
S3/MinIO backend implements in production.
"""

import hashlib
from pathlib import Path
from typing import Protocol


class ObjectStore(Protocol):
    """Write-once blob storage."""

    def put(self, data: bytes) -> str:
        """Store bytes immutably; return a storage URI."""

    def get(self, uri: str) -> bytes:
        """Read back the object at ``uri``."""


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ponytail: no S3 backend, no MinIO container yet — the Protocol is the seam.
# Add S3ObjectStore when a deploy target actually needs it (ADR-009 sanctions it).
class LocalObjectStore:
    """Filesystem-backed content-addressed store (development)."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def put(self, data: bytes) -> str:
        digest = sha256_hex(data)
        # Fan out by prefix to avoid one huge flat directory.
        path = self.root / digest[:2] / digest
        if not path.exists():                      # write-once
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        return f"file://{digest}"

    def get(self, uri: str) -> bytes:
        digest = uri.removeprefix("file://")
        return (self.root / digest[:2] / digest).read_bytes()
