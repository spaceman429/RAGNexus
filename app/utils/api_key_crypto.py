import hashlib
import secrets

KEY_LIVE_PREFIX = "rk_live_"


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def generate_api_key_material() -> tuple[str, str, str]:
    secret = secrets.token_hex(16)
    raw_key = f"{KEY_LIVE_PREFIX}{secret}"
    key_prefix = f"rk_{secret[:4]}"
    return raw_key, hash_api_key(raw_key), key_prefix
