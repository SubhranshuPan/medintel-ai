"""embeddings: optional document parent, guarded by a check constraint

Indexing (#62) writes one ``Embedding`` row per corpus chunk. Those chunks have
no ``Document`` row and should not have one: since ADR-021 the unit of truth for
corpus content is the ``KnowledgeNode``, and minting a ``Document`` purely to
satisfy a NOT NULL foreign key would duplicate the node's title and text to no
purpose.

So ``document_id`` becomes nullable — and a check constraint takes over the job
it was doing. A chunk with neither parent is text retrieval can surface and
generation cannot attribute to anything; the constraint makes that unstorable
rather than merely discouraged.

Revision ID: d7e4a1c60b93
Revises: c3f1b8d92e47
Create Date: 2026-08-13 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd7e4a1c60b93'
down_revision: Union[str, Sequence[str], None] = 'c3f1b8d92e47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CHECK_NAME = 'ck_embeddings_has_parent'


def upgrade() -> None:
    """Relax the FK to nullable and add the has-a-parent check."""
    op.alter_column(
        'embeddings',
        'document_id',
        existing_type=sa.Uuid(),
        nullable=True,
    )
    op.create_check_constraint(
        CHECK_NAME,
        'embeddings',
        'document_id IS NOT NULL OR node_id IS NOT NULL',
    )


def downgrade() -> None:
    """Restore NOT NULL, refusing to run if corpus chunks would be orphaned."""
    op.drop_constraint(CHECK_NAME, 'embeddings', type_='check')

    bind = op.get_bind()
    orphans = bind.execute(
        sa.text('SELECT count(*) FROM embeddings WHERE document_id IS NULL')
    ).scalar_one()
    if orphans:
        raise RuntimeError(
            f'{orphans} embeddings rows have no document_id. Re-establish the '
            'constraint by deleting the corpus chunk rows (they are rebuilt by '
            'a re-index) before downgrading; this migration will not delete '
            'them for you.'
        )

    op.alter_column(
        'embeddings',
        'document_id',
        existing_type=sa.Uuid(),
        nullable=False,
    )
