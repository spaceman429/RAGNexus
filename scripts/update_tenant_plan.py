#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.session import SessionLocal
from app.repositories.tenant_repository import TenantRepository
from app.tenant.plan_presets import VALID_PLANS


def main() -> int:
    parser = argparse.ArgumentParser(description="Update tenant plan (free | standard | pro).")
    parser.add_argument("--tenant-id", required=True, help="tenant id")
    parser.add_argument(
        "--plan",
        required=True,
        help="plan tier: free, standard, or pro",
    )
    args = parser.parse_args()

    tenant_id = args.tenant_id.strip()
    plan = args.plan.strip().lower()

    if not tenant_id:
        print("error: --tenant-id cannot be empty", file=sys.stderr)
        return 1

    if plan not in VALID_PLANS:
        print(
            f"error: plan must be one of: {', '.join(sorted(VALID_PLANS))} (got: {args.plan!r})",
            file=sys.stderr,
        )
        return 1

    db = SessionLocal()
    try:
        repository = TenantRepository(db)
        tenant = repository.get_by_id(tenant_id)
        if tenant is None:
            print(
                f"error: tenant not found: {tenant_id} (create it first with create_tenant.py)",
                file=sys.stderr,
            )
            return 1

        repository.update_plan(tenant, plan)
        db.commit()
        print(f"tenant plan updated: id={tenant_id} plan={plan}")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"error: failed to update plan: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
