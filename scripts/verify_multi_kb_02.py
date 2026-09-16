#!/usr/bin/env python3
"""优化十三 02 集成验收：跨库 RRF + plan 限制。"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "http://127.0.0.1:8000/api/v1"


def load_api_key(name: str) -> str:
    env_path = PROJECT_ROOT / "frontend" / ".env"
    text = env_path.read_text(encoding="utf-8")
    marker = f"# {name}"
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if marker in line:
            for next_line in lines[index + 1 :]:
                stripped = next_line.strip()
                if not stripped:
                    continue
                if stripped.startswith("# API_KEY="):
                    return stripped.split("=", 1)[1].strip()
                if stripped.startswith("API_KEY="):
                    return stripped.split("=", 1)[1].strip()
    raise SystemExit(f"frontend/.env 中未找到 {name} 对应的 API_KEY")


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
        try:
            return json.loads(detail)
        except json.JSONDecodeError:
            raise SystemExit(f"HTTP {exc.code} {path}: {detail}") from exc


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
    base_url = sys.argv[1] if len(sys.argv) > 1 else BASE_URL
    globals()["BASE_URL"] = base_url

    standard_key = load_api_key("标准档")
    free_key = load_api_key("免费档")
    kb_ids = list_kb_ids(standard_key)
    if len(kb_ids) < 2:
        raise SystemExit("standard tenant 需要至少 2 个知识库做双库 RRF 验收")

    multi = request_json(
        "POST",
        "/rag/retrieve",
        standard_key,
        {
            "kb_ids": kb_ids[:2],
            "user_id": "multi_kb_verify_02",
            "query": "会员补偿与退款",
            "profile": "balanced",
            "top_k": 5,
        },
    )
    assert multi.get("code") == 0, multi
    retrieval = (multi["data"].get("metadata") or {}).get("retrieval") or {}
    assert retrieval.get("multi_kb") is True
    assert retrieval.get("fusion") == "rrf"
    assert retrieval.get("kb_count") == 2
    print("  standard 双库 RRF → OK")

    free_kbs = list_kb_ids(free_key)
    if len(free_kbs) >= 2:
        denied = request_json(
            "POST",
            "/rag/retrieve",
            free_key,
            {
                "kb_ids": free_kbs[:2],
                "user_id": "multi_kb_verify_02",
                "query": "test",
                "profile": "speed",
            },
        )
        assert denied.get("code") == 20013, denied
        print("  free 双库 → 20013 → OK")
    else:
        print("  跳过 free 双库 HTTP 验收（free tenant 仅 1 个库；plan 限制见单测）")
    print("\n优化十三 02 集成验收全部通过。")


if __name__ == "__main__":
    main()
