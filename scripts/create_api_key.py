#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.session import SessionLocal
from app.models.api_key import ApiKey
from app.repositories.api_key_repository import ApiKeyRepository
from app.repositories.tenant_repository import TenantRepository
from app.utils.api_key_crypto import generate_api_key_material
from app.utils.id_generator import generate_uuid
from app.utils.tenant_status import ApiKeyStatus


def main() -> int:
    parser = argparse.ArgumentParser(description="Create an API key for a tenant.")
    parser.add_argument("--tenant-id", required=True, help="existing tenant_id")
    parser.add_argument("--name", required=True, help="key remark, e.g. local dev")
    parser.add_argument(
        "--expires-days",
        type=int,
        default=None,
        help="key validity in days; omit for a non-expiring key",
    )
    args = parser.parse_args()

    tenant_id = args.tenant_id.strip()
    name = args.name.strip()
    if not tenant_id or not name:
        print("error: --tenant-id and --name cannot be empty", file=sys.stderr)
        return 1

    expires_at = None
    if args.expires_days is not None:
        if args.expires_days <= 0:
            print("error: --expires-days must be a positive integer", file=sys.stderr)
            return 1
        expires_at = datetime.now(timezone.utc) + timedelta(days=args.expires_days)

    db = SessionLocal()
    try:
        tenant_repository = TenantRepository(db)
        if not tenant_repository.exists(tenant_id):
            print(
                f"error: tenant not found: {tenant_id} (run scripts/create_tenant.py first)",
                file=sys.stderr,
            )
            return 1

        raw_key, key_hash, key_prefix = generate_api_key_material()
        api_key = ApiKey(
            id=generate_uuid(),
            tenant_id=tenant_id,
            key_hash=key_hash,
            key_prefix=key_prefix,
            name=name,
            status=ApiKeyStatus.ACTIVE,
            expires_at=expires_at,
        )
        ApiKeyRepository(db).create(api_key)
        db.commit()

        expires_label = expires_at.isoformat() if expires_at is not None else "never"
        print(f"api key created: tenant_id={tenant_id} key_prefix={key_prefix} name={name}")
        print(f"expires_at: {expires_label}")
        print(f"plain key (save now, shown once): {raw_key}")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"error: failed to create api key: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
