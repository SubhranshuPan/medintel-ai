"""ORM models package.

Importing every model here ensures the declarative registry is fully populated
before mapper configuration (string-based relationships resolve) and before
Alembic autogenerate inspects ``Base.metadata``.
"""

from app.models.base import Base
from app.models.citation import Citation
from app.models.conversation import Conversation
from app.models.dataset import Dataset, DatasetVersion, ValidationStatus, VersionOrigin
from app.models.document import Document
from app.models.embedding import Embedding
from app.models.message import Message, MessageRole
from app.models.user import User, UserRole

__all__ = [
    "Base",
    "Citation",
    "Conversation",
    "Dataset",
    "DatasetVersion",
    "Document",
    "Embedding",
    "Message",
    "MessageRole",
    "User",
    "UserRole",
    "ValidationStatus",
    "VersionOrigin",
]
