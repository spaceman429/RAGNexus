from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.auth import TenantContext, resolve_tenant_context
from app.db.session import get_db


def get_current_tenant(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
) -> TenantContext:
    return resolve_tenant_context(db, authorization)
