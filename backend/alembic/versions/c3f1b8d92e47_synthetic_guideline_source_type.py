"""corpus ingestion: synthetic_guideline source type and source_venue

Two changes, both from corpus ingestion (#61).

``synthetic_guideline`` joins ``knowledge_source_type``. The corpus ships an
authored guideline set in place of NICE content, which is licensed and could not
be redistributed (ADR-023). It gets its own value rather than reusing ``nice``:
provenance is the load-bearing claim of this pillar, and labelling authored text
with a publisher that did not publish it would falsify exactly the field the
retrieval layer filters and cites on.

``knowledge_nodes.source_venue`` records the journal title for an article and
the issuing body for a guideline. A rendered citation needs the venue next to
the id, and there was previously nowhere truthful to put it.

Revision ID: c3f1b8d92e47
Revises: a26c505784c7
Create Date: 2026-08-13 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c3f1b8d92e47'
down_revision: Union[str, Sequence[str], None] = 'a26c505784c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ENUM_NAME = 'knowledge_source_type'
NEW_VALUE = 'synthetic_guideline'
OLD_VALUES = ('pubmed', 'nice')


def upgrade() -> None:
    """Add the enum value and the venue column."""
    op.add_column(
        'knowledge_nodes',
        sa.Column('source_venue', sa.String(length=512), nullable=True),
    )

    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        # SQLite renders this enum as VARCHAR with a CHECK constraint and the
        # test suite builds its schema from the models directly, so there is no
        # type to alter here.
        return
    # PostgreSQL 12+ permits ADD VALUE inside a transaction provided the new
    # value is not *used* in the same transaction. Nothing here inserts.
    op.execute(f"ALTER TYPE {ENUM_NAME} ADD VALUE IF NOT EXISTS '{NEW_VALUE}'")


def downgrade() -> None:
    """Drop the venue column and remove the enum value by recreating the type.

    PostgreSQL has no ``DROP VALUE``, so the type is rebuilt without it. Rows
    still carrying the value block the downgrade rather than being rewritten:
    silently reassigning them to ``nice`` would attribute authored guidance to
    NICE, which is the precise falsehood the value was added to avoid.
    """
    op.drop_column('knowledge_nodes', 'source_venue')

    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        return

    remaining = bind.execute(
        sa.text(
            "SELECT count(*) FROM knowledge_nodes "
            "WHERE source_type = :value"
        ),
        {'value': NEW_VALUE},
    ).scalar_one()
    if remaining:
        raise RuntimeError(
            f"{remaining} knowledge_nodes rows still use source_type "
            f"'{NEW_VALUE}'. Delete or re-source them before downgrading; "
            "they must not be silently relabelled."
        )

    values = ', '.join(f"'{value}'" for value in OLD_VALUES)
    op.execute(f"ALTER TYPE {ENUM_NAME} RENAME TO {ENUM_NAME}_old")
    op.execute(f"CREATE TYPE {ENUM_NAME} AS ENUM ({values})")
    op.execute(
        f"ALTER TABLE knowledge_nodes ALTER COLUMN source_type "
        f"TYPE {ENUM_NAME} USING source_type::text::{ENUM_NAME}"
    )
    op.execute(f"DROP TYPE {ENUM_NAME}_old")
