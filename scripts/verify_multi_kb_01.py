#!/usr/bin/env python3
"""优化十三 01 集成验收：单库兼容 + 多库 kb_ids + 非法 kb。"""

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


def list_kb_ids(api_key: str) -> list[tuple[str, str]]:
    body = request_json("GET", "/knowledge-bases/tree", api_key)
    if body.get("code") != 0:
        raise SystemExit(f"tree 失败: {body}")
    items: list[tuple[str, str]] = []
    for tenant in body["data"]:
        for kb in tenant.get("knowledge_bases", []):
            items.append((kb["kb_id"], kb.get("name") or kb["kb_id"]))
    return items


def main() -> None:
    api_key = load_api_key()
    kb_list = list_kb_ids(api_key)
    if not kb_list:
        raise SystemExit("当前 tenant 无知识库，无法验收")
    kb_a, name_a = kb_list[0]
    print(f"使用单库: {name_a} ({kb_a})")

    single = request_json(
        "POST",
        "/rag/retrieve",
        api_key,
        {
            "kb_id": kb_a,
            "user_id": "multi_kb_verify",
            "query": "退款时限",
            "profile": "balanced",
        },
    )
    assert single.get("code") == 0, single
    data = single["data"]
    assert data["kb_id"] == kb_a
    assert data["kb_ids"] == [kb_a]
    chunks = data.get("retrieved_chunks") or []
    assert chunks, "单库应有召回"
    assert all(chunk.get("kb_id") == kb_a for chunk in chunks), "单库 chunk 应带 kb_id"
    print("  单库 kb_id 兼容 → OK")

    if len(kb_list) >= 2:
        kb_b, name_b = kb_list[1]
        print(f"使用双库: {name_a} + {name_b}")
        multi = request_json(
            "POST",
            "/rag/retrieve",
            api_key,
            {
                "kb_ids": [kb_a, kb_b],
                "user_id": "multi_kb_verify",
                "query": "会员补偿与退款",
                "profile": "balanced",
                "top_k": 5,
            },
        )
        assert multi.get("code") == 0, multi
        multi_data = multi["data"]
        assert multi_data["kb_ids"] == [kb_a, kb_b]
        multi_chunks = multi_data.get("retrieved_chunks") or []
        assert multi_chunks, "多库应有召回"
        assert all(chunk.get("kb_id") in {kb_a, kb_b} for chunk in multi_chunks)
        assert all(chunk.get("kb_id") for chunk in multi_chunks)
        retrieval = (multi_data.get("metadata") or {}).get("retrieval") or {}
        assert retrieval.get("multi_kb") is True
        print("  多库 kb_ids 召回 + kb_id 标记 → OK")
    else:
        print("  跳过双库验收：当前 tenant 仅 1 个知识库")

    bad = request_json(
        "POST",
        "/rag/retrieve",
        api_key,
        {
            "kb_ids": [kb_a, "00000000-0000-0000-0000-000000000000"],
            "user_id": "multi_kb_verify",
            "query": "test",
            "profile": "balanced",
        },
    )
    assert bad.get("code") != 0, "非法 kb 应失败"
    print("  非法 kb_id → 拒绝 → OK")
    print("\n优化十三 01 集成验收全部通过。")


if __name__ == "__main__":
    main()
