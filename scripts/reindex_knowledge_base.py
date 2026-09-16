#!/usr/bin/env python3
"""按知识库或指定文档批量重建索引（优化十一 03）。"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.session import SessionLocal
from app.models.knowledge_base import KnowledgeBase
from app.repositories.document_repository import DocumentRepository
from app.repositories.knowledge_base_repository import KnowledgeBaseRepository
from app.services.reindex_service import queue_document_reindex
from app.utils.status import DocumentStatus


def resolve_kb(db, kb_id: str, tenant_id: str | None) -> KnowledgeBase:
    repository = KnowledgeBaseRepository(db)
    if tenant_id:
        kb = repository.get_by_id_and_tenant(kb_id, tenant_id)
    else:
        kb = repository.get_by_id(kb_id)
    if kb is None:
        raise SystemExit(f"知识库不存在: kb_id={kb_id}")
    return kb


async def reindex_documents(
    document_ids: list[str],
    *,
    kb_id: str | None = None,
    reparse: bool = False,
) -> tuple[dict[str, int], list[str]]:
    stats = {"queued": 0, "skipped": 0, "failed": 0}
    failed_ids: list[str] = []
    queued_ids: list[str] = []

    db = SessionLocal()
    try:
        repository = DocumentRepository(db)
        for document_id in document_ids:
            document = repository.get_by_id(document_id)
            if document is None:
                print(f"SKIP not found: {document_id}")
                stats["skipped"] += 1
                continue
            if kb_id and document.kb_id != kb_id:
                print(f"SKIP kb mismatch: {document_id}")
                stats["skipped"] += 1
                continue
            if document.status == DocumentStatus.PROCESSING:
                print(f"SKIP processing: {document_id}")
                stats["skipped"] += 1
                continue
            if document.status != DocumentStatus.SUCCESS:
                print(f"SKIP status={document.status}: {document_id}")
                stats["skipped"] += 1
                continue
            try:
                await queue_document_reindex(db, document, reparse=reparse)
                print(f"QUEUED {document.title} ({document_id})")
                stats["queued"] += 1
                queued_ids.append(document_id)
            except Exception as exc:
                print(f"FAILED {document_id}: {exc}", file=sys.stderr)
                stats["failed"] += 1
                failed_ids.append(document_id)
    finally:
        db.close()

    if failed_ids:
        print(f"failed document_ids: {', '.join(failed_ids)}", file=sys.stderr)
    return stats, queued_ids


def wait_for_documents(document_ids: list[str], timeout_sec: int) -> None:
    deadline = time.time() + timeout_sec
    pending = set(document_ids)
    db = SessionLocal()
    try:
        repository = DocumentRepository(db)
        while pending and time.time() < deadline:
            done: set[str] = set()
            for document_id in pending:
                document = repository.get_by_id(document_id)
                if document is None:
                    done.add(document_id)
                    continue
                if document.status == DocumentStatus.SUCCESS:
                    print(f"DONE success: {document.title} ({document_id})")
                    done.add(document_id)
                elif document.status == DocumentStatus.FAILED:
                    print(
                        f"DONE failed: {document.title} ({document_id}) "
                        f"error={document.error_message}",
                        file=sys.stderr,
                    )
                    done.add(document_id)
            pending -= done
            if pending:
                time.sleep(2)
        if pending:
            raise SystemExit(f"等待索引超时，仍未完成: {', '.join(sorted(pending))}")
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild document indexes for a knowledge base.")
    parser.add_argument("--kb-id", required=True, help="knowledge base id")
    parser.add_argument("--tenant-id", help="optional tenant id for kb lookup")
    parser.add_argument(
        "--document-id",
        action="append",
        default=[],
        help="reindex specific document id(s); default all SUCCESS docs in kb",
    )
    parser.add_argument(
        "--wait",
        action="store_true",
        help="wait until queued documents finish indexing",
    )
    parser.add_argument(
        "--wait-timeout",
        type=int,
        default=600,
        help="seconds to wait when --wait is set (default 600)",
    )
    parser.add_argument(
        "--reparse",
        action="store_true",
        help="re-parse from source_file_path before reindex (file uploads only)",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        kb = resolve_kb(db, args.kb_id.strip(), args.tenant_id.strip() if args.tenant_id else None)
        repository = DocumentRepository(db)
        if args.document_id:
            document_ids = args.document_id
        else:
            documents = repository.list_by_kb_id_and_status(kb.id, DocumentStatus.SUCCESS)
            document_ids = [document.id for document in documents]
            print(f"kb={kb.id} tenant={kb.tenant_id} success_documents={len(document_ids)}")
    finally:
        db.close()

    if not document_ids:
        print("没有需要 reindex 的 SUCCESS 文档")
        return 0

    stats, queued_ids = asyncio.run(
        reindex_documents(document_ids, kb_id=kb.id, reparse=args.reparse)
    )
    print(
        f"\nSummary: queued={stats['queued']} skipped={stats['skipped']} failed={stats['failed']}"
    )

    if stats["failed"] > 0:
        return 1

    if args.wait and queued_ids:
        wait_for_documents(queued_ids, args.wait_timeout)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
