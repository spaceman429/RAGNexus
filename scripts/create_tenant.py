#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.session import SessionLocal
from app.models.tenant import Tenant
from app.repositories.tenant_repository import TenantRepository
from app.utils.tenant_status import TenantStatus


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a tenant for rag-center.")
    parser.add_argument("--id", required=True, help="tenant_id, e.g. tenant_demo")
    parser.add_argument("--name", required=True, help="display name")
    args = parser.parse_args()

    tenant_id = args.id.strip()
    name = args.name.strip()
    if not tenant_id or not name:
        print("error: --id and --name cannot be empty", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        repository = TenantRepository(db)
        if repository.exists(tenant_id):
            print(f"error: tenant already exists: {tenant_id}", file=sys.stderr)
            return 1

        tenant = Tenant(
            id=tenant_id,
            name=name,
            status=TenantStatus.ACTIVE,
        )
        repository.create(tenant)
        db.commit()
        print(f"tenant created: id={tenant_id} name={name}")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"error: failed to create tenant: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
