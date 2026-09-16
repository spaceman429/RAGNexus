from pathlib import Path

from app.core.config import PROJECT_ROOT, settings


def get_storage_root() -> Path:
    root = Path(settings.document_storage_path)
    if not root.is_absolute():
        root = PROJECT_ROOT / root
    root.mkdir(parents=True, exist_ok=True)
    return root


def save_document_file(
    *,
    tenant_id: str,
    document_id: str,
    filename: str,
    file_bytes: bytes,
) -> str:
    safe_name = Path(filename).name
    target_dir = get_storage_root() / tenant_id / document_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / safe_name
    target_path.write_bytes(file_bytes)
    return str(Path(settings.document_storage_path) / tenant_id / document_id / safe_name)


def resolve_storage_path(relative_path: str) -> Path:
    path = Path(relative_path)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def read_document_file(relative_path: str) -> bytes:
    path = resolve_storage_path(relative_path)
    if not path.is_file():
        raise FileNotFoundError(f"document file not found: {relative_path}")
    return path.read_bytes()
