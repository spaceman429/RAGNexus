"""document source file fields

Revision ID: 0008_document_source_file
Revises: 0007_retrieval_log_kb_ids
Create Date: 2026-06-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0008_document_source_file"
down_revision: str | None = "0007_retrieval_log_kb_ids"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("source_file_path", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("source_filename", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("documents", "source_filename")
    op.drop_column("documents", "source_file_path")
