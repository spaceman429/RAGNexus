from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AppError, ErrorCode
from app.repositories.api_key_repository import ApiKeyRepository
from app.repositories.tenant_repository import TenantRepository
from app.utils.api_key_crypto import hash_api_key

DEFAULT_DEV_TENANT_ID = "tenant_demo"


@dataclass(frozen=True)
class TenantContext:
    tenant_id: str
    tenant_name: str
    key_id: str | None
    key_prefix: str | None
    key_name: str | None


def parse_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return None
    token = token.strip()
    return token or None


def resolve_tenant_context(db: Session, authorization: str | None) -> TenantContext:
    if not settings.auth_enabled:
        tenant_repository = TenantRepository(db)
        tenant = tenant_repository.get_by_id(DEFAULT_DEV_TENANT_ID)
        tenant_name = tenant.name if tenant is not None else DEFAULT_DEV_TENANT_ID
        return TenantContext(
            tenant_id=DEFAULT_DEV_TENANT_ID,
            tenant_name=tenant_name,
            key_id=None,
            key_prefix=None,
            key_name=None,
        )

    raw_key = parse_bearer_token(authorization)
    if raw_key is None:
        raise AppError(ErrorCode.UNAUTHORIZED)

    api_key_repository = ApiKeyRepository(db)
    api_key = api_key_repository.get_active_by_hash(hash_api_key(raw_key))
    if api_key is None or api_key.tenant is None:
        raise AppError(ErrorCode.UNAUTHORIZED)

    return TenantContext(
        tenant_id=api_key.tenant_id,
        tenant_name=api_key.tenant.name,
        key_id=api_key.id,
        key_prefix=api_key.key_prefix,
        key_name=api_key.name,
    )
