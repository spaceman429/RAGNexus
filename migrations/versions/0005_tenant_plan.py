"""tenant plan column

Revision ID: 0005_tenant_plan
Revises: 0004_document_content
Create Date: 2026-06-25
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0005_tenant_plan"
down_revision: str | None = "0004_document_content"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column(
            "plan",
            sa.String(length=32),
            nullable=False,
            server_default="free",
        ),
    )
    # Existing tenants were created before plan tiers — keep them on standard.
    op.execute(sa.text("UPDATE tenants SET plan = 'standard'"))
    op.execute(sa.text("UPDATE tenants SET plan = 'pro' WHERE id = 'tenant_demo'"))


def downgrade() -> None:
    op.drop_column("tenants", "plan")
