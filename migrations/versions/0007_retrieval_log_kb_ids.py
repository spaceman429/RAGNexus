"""retrieval log kb_ids column

Revision ID: 0007_retrieval_log_kb_ids
Revises: 0006_retrieval_log_observability
Create Date: 2026-06-27
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0007_retrieval_log_kb_ids"
down_revision: str | None = "0006_retrieval_log_observability"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("retrieval_logs", sa.Column("kb_ids", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("retrieval_logs", "kb_ids")
