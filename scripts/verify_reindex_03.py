#!/usr/bin/env python3
"""优化十一 03 验收：整库 reindex + metadata + retrieve。"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
KB_ID = "b0646f80-13ee-46fb-890c-c01a7a75b449"
BASE_URL = "http://127.0.0.1:8000/api/v1"


def load_api_key() -> str:
    for line in (PROJECT_ROOT / "frontend" / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("API_KEY=") and not line.startswith("#"):
            return line.split("=", 1)[1].strip()
    raise SystemExit("frontend/.env 中未找到 API_KEY")


def api(method: str, path: str, api_key: str, payload: dict | None = None) -> dict:
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=None if payload is None else json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = json.loads(resp.read())
    if body.get("code") != 0:
        raise SystemExit(f"API 失败 {path}: {body}")
    return body["data"]


def main() -> None:
    api_key = load_api_key()
    kb_id = sys.argv[1] if len(sys.argv) > 1 else KB_ID
    print(f"[1] 整库 reindex kb_id={kb_id}")
    result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "reindex_knowledge_base.py"),
            "--kb-id",
            kb_id,
            "--wait",
            "--wait-timeout",
            "600",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        raise SystemExit(result.returncode)

    print("[2] 抽查 chunk metadata（SQLAlchemy）")
    sys.path.insert(0, str(PROJECT_ROOT))
    from app.db.session import SessionLocal
    from app.models.chunk import Chunk

    with SessionLocal() as db:
        sample = (
            db.query(Chunk)
            .filter(Chunk.kb_id == kb_id)
            .order_by(Chunk.created_at.desc())
            .limit(20)
            .all()
        )
        with_heading = [c for c in sample if c.metadata_.get("heading_path")]
        with_table = [c for c in sample if c.metadata_.get("chunk_type") == "table"]
        print(f"  recent_chunks={len(sample)} with_heading_path={len(with_heading)} table_chunks={len(with_table)}")
        if not with_heading:
            raise SystemExit("未找到含 heading_path 的 chunk")
        if with_table:
            table = with_table[0]
            assert "【表头】" in table.content or "|" in table.content
            print(f"  table sample heading_path={table.metadata_.get('heading_path')}")

    print("[3] retrieve 目视")
    for query in ("满减和优惠券能否叠加", "现货订单多久必须揽收"):
        data = api(
            "POST",
            "/rag/retrieve",
            api_key,
            {
                "kb_id": kb_id,
                "user_id": "reindex_verify",
                "query": query,
                "profile": "balanced",
            },
        )
        top = (data.get("retrieved_chunks") or [None])[0]
        if top is None:
            raise SystemExit(f"query={query!r} 无召回")
        meta = top.get("metadata") or {}
        preview = top.get("content", "")[:120].replace("\n", " ")
        print(f"  query={query!r} heading_path={meta.get('heading_path')} chunk_type={meta.get('chunk_type')}")
        print(f"    preview={preview!r}")

    print("\n优化十一 03 验收通过。")


if __name__ == "__main__":
    main()
