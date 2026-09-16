from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.api_key import ApiKey
from app.utils.tenant_status import ApiKeyStatus, TenantStatus


class ApiKeyRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, api_key: ApiKey) -> ApiKey:
        self.db.add(api_key)
        self.db.flush()
        return api_key

    def get_active_by_hash(self, key_hash: str, *, now: datetime | None = None) -> ApiKey | None:
        checked_at = now or datetime.now(timezone.utc)
        stmt = (
            select(ApiKey)
            .options(joinedload(ApiKey.tenant))
            .where(
                ApiKey.key_hash == key_hash,
                ApiKey.status == ApiKeyStatus.ACTIVE,
            )
        )
        api_key = self.db.scalar(stmt)
        if api_key is None:
            return None
        if api_key.expires_at is not None and api_key.expires_at <= checked_at:
            return None
        if api_key.tenant is None or api_key.tenant.status != TenantStatus.ACTIVE:
            return None
        return api_key

    def list_by_tenant(self, tenant_id: str) -> list[ApiKey]:
        stmt = (
            select(ApiKey).where(ApiKey.tenant_id == tenant_id).order_by(ApiKey.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def get_by_id_and_tenant(self, api_key_id: str, tenant_id: str) -> ApiKey | None:
        stmt = select(ApiKey).where(
            ApiKey.id == api_key_id,
            ApiKey.tenant_id == tenant_id,
        )
        return self.db.scalar(stmt)

    def list_by_prefix(self, tenant_id: str, key_prefix: str) -> list[ApiKey]:
        stmt = (
            select(ApiKey)
            .where(
                ApiKey.tenant_id == tenant_id,
                ApiKey.key_prefix.like(f"{key_prefix}%"),
            )
            .order_by(ApiKey.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def revoke(self, api_key: ApiKey) -> ApiKey:
        api_key.status = ApiKeyStatus.REVOKED
        self.db.flush()
        return api_key
