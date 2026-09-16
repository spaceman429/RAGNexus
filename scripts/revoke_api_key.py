#!/usr/bin/env python3
"""Platform-side API key lifecycle: list / revoke / rotate.

The tenant onboarding model is platform-side provisioning, so key lifecycle is
also handled here rather than through a public API.

Examples:
  # list every key of a tenant (read-only)
  python scripts/revoke_api_key.py --tenant-id tenant_a --list

  # revoke by key_prefix (printed once at creation, e.g. rk_a1b2)
  python scripts/revoke_api_key.py --tenant-id tenant_a --key-prefix rk_a1b2 --yes

  # revoke by remark
  python scripts/revoke_api_key.py --tenant-id tenant_a --name "prod" --yes

  # rotate: revoke the old key and issue a new one with the same remark
  python scripts/revoke_api_key.py --tenant-id tenant_a --key-prefix rk_a1b2 --rotate --yes
"""

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


def _describe(api_key: ApiKey) -> str:
    expires = api_key.expires_at.isoformat() if api_key.expires_at else "never"
    created = api_key.created_at.isoformat() if api_key.created_at else "-"
    return (
        f"  id={api_key.id}  prefix={api_key.key_prefix}  name={api_key.name!r}  "
        f"status={api_key.status}  expires_at={expires}  created_at={created}"
    )


def _confirm(prompt: str, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    if not sys.stdin.isatty():
        print(
            "error: refusing to modify non-interactively; pass --yes to confirm",
            file=sys.stderr,
        )
        return False
    try:
        answer = input(f"{prompt} [y/N] ").strip().lower()
    except EOFError:
        print("error: no input available; pass --yes to confirm", file=sys.stderr)
        return False
    return answer in {"y", "yes"}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="List, revoke or rotate a tenant API key (platform-side)."
    )
    parser.add_argument("--tenant-id", required=True, help="existing tenant_id")

    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument(
        "--list",
        action="store_true",
        dest="list_keys",
        help="list every key of the tenant (read-only)",
    )
    selector.add_argument("--key-id", help="revoke by api key id (exact)")
    selector.add_argument(
        "--key-prefix",
        help="revoke by key_prefix, prefix match is allowed (e.g. rk_a1b2)",
    )
    selector.add_argument("--name", help="revoke by remark (exact)")

    parser.add_argument(
        "--rotate",
        action="store_true",
        help="after revoking, issue a new key carrying the same remark",
    )
    parser.add_argument(
        "--expires-days",
        type=int,
        default=None,
        help="validity of the rotated key in days; omit for a non-expiring key",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="allow revoking the tenant's last active key (locks the tenant out)",
    )
    parser.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    return parser.parse_args()


def _resolve_targets(
    repository: ApiKeyRepository,
    tenant_id: str,
    args: argparse.Namespace,
) -> tuple[list[ApiKey], str | None]:
    """Return (matched keys, error message)."""
    if args.key_id:
        target = repository.get_by_id_and_tenant(args.key_id.strip(), tenant_id)
        if target is None:
            return [], f"api key not found for this tenant: {args.key_id}"
        return [target], None

    if args.key_prefix:
        prefix = args.key_prefix.strip()
        if not prefix:
            return [], "--key-prefix cannot be empty"
        matched = repository.list_by_prefix(tenant_id, prefix)
        # an exact prefix hit wins over ambiguous prefix matches
        exact = [item for item in matched if item.key_prefix == prefix]
        if len(exact) == 1:
            return exact, None
        if not matched:
            return [], f"no api key matches prefix: {prefix}"
        return matched, "ambiguous prefix; use --key-id or a longer --key-prefix"

    matched = [item for item in repository.list_by_tenant(tenant_id) if item.name == args.name]
    if not matched:
        return [], f"no api key named: {args.name}"
    if len(matched) > 1:
        # a rotated key leaves its retired twin behind with the same remark,
        # so prefer the single still-active one
        active_matched = [item for item in matched if item.status == ApiKeyStatus.ACTIVE]
        if len(active_matched) == 1:
            return active_matched, None
        return matched, "multiple keys share this remark; use --key-id or --key-prefix"
    return matched, None


def main() -> int:
    args = _parse_args()
    tenant_id = args.tenant_id.strip()
    if not tenant_id:
        print("error: --tenant-id cannot be empty", file=sys.stderr)
        return 1
    if args.expires_days is not None and args.expires_days <= 0:
        print("error: --expires-days must be a positive integer", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        tenant_repository = TenantRepository(db)
        if not tenant_repository.exists(tenant_id):
            print(
                f"error: tenant not found: {tenant_id} (run scripts/create_tenant.py first)",
                file=sys.stderr,
            )
            return 1

        repository = ApiKeyRepository(db)

        if args.list_keys:
            keys = repository.list_by_tenant(tenant_id)
            active = [item for item in keys if item.status == ApiKeyStatus.ACTIVE]
            print(f"api keys of tenant={tenant_id}: total={len(keys)} active={len(active)}")
            for item in keys:
                print(_describe(item))
            return 0

        matched, error = _resolve_targets(repository, tenant_id, args)
        if error is not None:
            print(f"error: {error}", file=sys.stderr)
            for item in matched:
                print(_describe(item), file=sys.stderr)
            return 1

        target = matched[0]
        if target.status != ApiKeyStatus.ACTIVE:
            print(
                f"api key already inactive (no-op): id={target.id} "
                f"prefix={target.key_prefix} status={target.status}"
            )
            return 0

        # capture before commit/close: session attributes expire on commit
        target_id = target.id
        target_prefix = target.key_prefix
        target_name = target.name

        active_keys = [
            item
            for item in repository.list_by_tenant(tenant_id)
            if item.status == ApiKeyStatus.ACTIVE
        ]
        if len(active_keys) == 1 and not args.rotate and not args.force:
            print(
                "error: this is the tenant's last active key; revoking it locks the tenant out "
                "(re-run with --force, or use --rotate to issue a replacement)",
                file=sys.stderr,
            )
            return 1

        print("about to revoke:")
        print(_describe(target))
        if args.rotate:
            print(f"  and issue a replacement key named {target_name!r}")
        if not _confirm("confirm revocation?", args.yes):
            print("aborted: nothing changed")
            return 1

        repository.revoke(target)

        rotated_plain: str | None = None
        rotated_prefix: str | None = None
        rotated_expires: datetime | None = None
        if args.rotate:
            expires_at = None
            if args.expires_days is not None:
                expires_at = datetime.now(timezone.utc) + timedelta(days=args.expires_days)
            raw_key, key_hash, key_prefix = generate_api_key_material()
            replacement = ApiKey(
                id=generate_uuid(),
                tenant_id=tenant_id,
                key_hash=key_hash,
                key_prefix=key_prefix,
                name=target_name,
                status=ApiKeyStatus.ACTIVE,
                expires_at=expires_at,
            )
            repository.create(replacement)
            rotated_plain = raw_key
            rotated_prefix = key_prefix
            rotated_expires = expires_at

        db.commit()
    except Exception as exc:
        db.rollback()
        print(f"error: failed to revoke api key: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()

    print(f"api key revoked: tenant_id={tenant_id} id={target_id} prefix={target_prefix}")
    if rotated_plain is not None:
        expires_label = rotated_expires.isoformat() if rotated_expires is not None else "never"
        print(
            f"replacement key created: tenant_id={tenant_id} "
            f"key_prefix={rotated_prefix} name={target_name}"
        )
        print(f"expires_at: {expires_label}")
        print(f"plain key (save now, shown once): {rotated_plain}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
