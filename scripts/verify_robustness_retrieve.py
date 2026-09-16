#!/usr/bin/env python3
"""优化十四 02 集成验收：hybrid 降级、空 query、多库 partial（HTTP）。"""

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
        body = exc.read().decode("utf-8", errors="replace")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            raise SystemExit(f"HTTP {exc.code} {path}: {body}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"无法连接 {BASE_URL}，请确认后端已启动: {exc}") from exc


def list_kb_ids(api_key: str) -> list[str]:
    body = request_json("GET", "/knowledge-bases/tree", api_key)
    if body.get("code") != 0:
        raise SystemExit(f"tree 失败: {body}")
    kb_ids: list[str] = []
    for tenant in body["data"]:
        for kb in tenant.get("knowledge_bases", []):
            kb_ids.append(kb["kb_id"])
    return kb_ids


def main() -> None:
    api_key = load_api_key()
    kb_ids = list_kb_ids(api_key)
    if not kb_ids:
        raise SystemExit("当前 tenant 无知识库，无法验收")
    kb_id = kb_ids[0]

    blank = request_json(
        "POST",
        "/rag/retrieve",
        api_key,
        {
            "kb_id": kb_id,
            "user_id": "verify_robustness",
            "query": "   ",
            "profile": "balanced",
        },
    )
    assert blank.get("code") == 20002, blank
    print("  空 query 拒绝 → OK")

    retrieve = request_json(
        "POST",
        "/rag/retrieve",
        api_key,
        {
            "kb_id": kb_id,
            "user_id": "verify_robustness",
            "query": "简历筛选 招聘制度",
            "profile": "balanced",
            "top_k": 3,
        },
    )
    assert retrieve.get("code") == 0, retrieve
    retrieval = (retrieve.get("data") or {}).get("metadata", {}).get("retrieval") or {}
    if retrieval.get("degraded"):
        assert "bm25" in (retrieval.get("degraded_reason") or "").lower() or retrieval.get(
            "degraded_reason"
        ), retrieval
        print(f"  hybrid 降级 retrieve → OK ({retrieval.get('degraded_reason')})")
    else:
        print("  hybrid 正常 retrieve（无 degraded）→ OK")

    if len(kb_ids) >= 2:
        multi = request_json(
            "POST",
            "/rag/retrieve",
            api_key,
            {
                "kb_ids": kb_ids[:2],
                "user_id": "verify_robustness",
                "query": "简历筛选 Offer 模板",
                "profile": "balanced",
                "top_k": 5,
            },
        )
        assert multi.get("code") == 0, multi
        multi_retrieval = (multi.get("data") or {}).get("metadata", {}).get("retrieval") or {}
        assert multi_retrieval.get("multi_kb") is True
        print("  双库 retrieve → OK")

    print("\n优化十四 02 HTTP 验收通过")


if __name__ == "__main__":
    main()
