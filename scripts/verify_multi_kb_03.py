#!/usr/bin/env python3
"""优化十三 03 验收：tree 多库 retrieve + eval dataset kb_ids。"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/api/v1"


def load_api_key() -> str:
    env_path = PROJECT_ROOT / "frontend" / ".env"
    if not env_path.exists():
        raise SystemExit("frontend/.env 不存在，无法读取 API_KEY")
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("API_KEY=") and not line.startswith("#"):
            return line.split("=", 1)[1].strip()
    raise SystemExit("frontend/.env 中未找到未注释的 API_KEY")


def request_json(method: str, path: str, api_key: str, payload: dict | None = None) -> dict:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {exc.code} {path}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"无法连接 {BASE_URL}，请确认后端已启动: {exc}") from exc


def list_kb_ids(api_key: str) -> list[str]:
    body = request_json("GET", "/knowledge-bases/tree", api_key)
    if body.get("code") != 0:
        raise SystemExit(f"tree 失败: {body}")
    items: list[str] = []
    for tenant in body["data"]:
        for kb in tenant.get("knowledge_bases", []):
            items.append(kb["kb_id"])
    return items


def main() -> None:
    api_key = load_api_key()
    kb_ids = list_kb_ids(api_key)
    if len(kb_ids) < 2:
        print(f"SKIP need >=2 KBs, got {len(kb_ids)}")
        return

    multi = request_json(
        "POST",
        "/rag/retrieve",
        api_key,
        {
            "kb_ids": kb_ids[:2],
            "user_id": "verify_03",
            "query": "简历筛选 招聘制度 Offer",
            "profile": "balanced",
            "top_k": 5,
        },
    )
    assert multi.get("code") == 0, multi
    data = multi["data"]
    chunks = data.get("chunks") or data.get("retrieved_chunks") or []
    retrieval = (data.get("metadata") or {}).get("retrieval") or {}
    assert retrieval.get("multi_kb") is True, retrieval
    assert retrieval.get("fusion") == "rrf", retrieval
    assert len(data.get("kb_ids") or []) >= 2, data.get("kb_ids")
    kb_names = {c.get("kb_name") for c in chunks if c.get("kb_name")}
    print(f"  多库 retrieve → OK ({len(chunks)} chunks, kb_names={kb_names})")

    ds = PROJECT_ROOT / "eval/datasets/multi_kb_cases.json"
    if not ds.exists():
        raise SystemExit("缺少 eval/datasets/multi_kb_cases.json")
    cases_doc = json.loads(ds.read_text(encoding="utf-8"))
    cases = cases_doc.get("cases") or cases_doc
    if not any(c.get("kb_ids") for c in cases):
        raise SystemExit("eval cases 缺少 kb_ids 字段")
    print(f"  eval dataset kb_ids → OK ({len(cases)} cases)")


if __name__ == "__main__":
    main()
    print("\n优化十三 03 验收通过")
