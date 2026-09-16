#!/usr/bin/env python3
"""Update knowledge base settings (synonym vocabulary) in the database.

The JSON file **fully replaces** knowledge_bases.settings for the given kb_id.
This is kb-level configuration, not document content — do not use documents/upload.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.session import SessionLocal
from app.repositories.knowledge_base_repository import KnowledgeBaseRepository


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Replace knowledge base settings (synonym vocabulary) from a JSON file."
    )
    parser.add_argument("--kb-id", required=True, help="knowledge base id")
    parser.add_argument(
        "--settings-file",
        required=True,
        help="path to JSON file (full settings object, replaces existing settings)",
    )
    args = parser.parse_args()

    kb_id = args.kb_id.strip()
    settings_path = Path(args.settings_file)
    if not kb_id:
        print("error: --kb-id cannot be empty", file=sys.stderr)
        return 1
    if not settings_path.is_file():
        print(f"error: settings file not found: {settings_path}", file=sys.stderr)
        return 1

    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON: {exc}", file=sys.stderr)
        return 1

    if not isinstance(settings, dict):
        print("error: settings file must be a JSON object", file=sys.stderr)
        return 1

    synonyms = settings.get("synonyms") or []
    synonym_group_count = len(synonyms) if isinstance(synonyms, list) else 0

    db = SessionLocal()
    try:
        repository = KnowledgeBaseRepository(db)
        knowledge_base = repository.update_settings(kb_id, settings)
        if knowledge_base is None:
            print(f"error: knowledge base not found: {kb_id}", file=sys.stderr)
            return 1
        db.commit()
        print(
            f"settings updated: kb_id={kb_id} synonym_groups={synonym_group_count}"
        )
        return 0
    except Exception as exc:
        db.rollback()
        print(f"error: failed to update settings: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
