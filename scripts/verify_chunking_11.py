#!/usr/bin/env python3
"""优化十一 01/02 集成验收：upload → 索引 → 查 chunk / retrieve。"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "http://127.0.0.1:8000/api/v1"
POLL_INTERVAL_SEC = 2
POLL_TIMEOUT_SEC = 120


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
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {exc.code} {path}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"无法连接 {BASE_URL}，请确认后端已启动: {exc}") from exc
    if body.get("code") != 0:
        raise SystemExit(f"API 失败 {path}: {body}")
    return body["data"]


def wait_document_success(api_key: str, document_id: str) -> dict:
    deadline = time.time() + POLL_TIMEOUT_SEC
    while time.time() < deadline:
        detail = request_json("GET", f"/documents/{document_id}", api_key)
        status = detail.get("status")
        if status == 1:
            return detail
        if status == 2:
            raise SystemExit(f"文档索引失败: {detail.get('error_message')}")
        time.sleep(POLL_INTERVAL_SEC)
    raise SystemExit(f"等待索引超时 document_id={document_id}")


def verify_heading_upload(api_key: str, kb_id: str) -> None:
    print("\n[01] 标题切块 upload + retrieve 验收")
    content = (
        "# 测试知识库\n\n"
        "## 第一节\n\n"
        "这是第一节的内容。\n\n"
        "## 第二节\n\n"
        "这是第二节的内容。"
    )
    upload = request_json(
        "POST",
        "/documents/upload",
        api_key,
        {"kb_id": kb_id, "title": "heading_test.md", "content": content},
    )
    document_id = upload["document_id"]
    detail = wait_document_success(api_key, document_id)
    print(f"  document_id={document_id} chunk_count={detail.get('chunk_count')}")
    assert detail.get("chunk_count", 0) >= 2, "应至少 2 个 chunk"

    result = request_json(
        "POST",
        "/rag/retrieve",
        api_key,
        {
            "kb_id": kb_id,
            "user_id": "chunk_verify",
            "query": "第一节内容",
            "profile": "balanced",
        },
    )
    top = (result.get("retrieved_chunks") or [None])[0]
    assert top is not None, "应有召回结果"
    assert "第一节" in top.get("content", ""), "Top chunk 应来自第一节"
    assert "第二节的内容" not in top.get("content", ""), "Top chunk 不应混入第二节"
    print("  retrieve Top1 命中第一节，未混入第二节 → OK")


def verify_table_upload(api_key: str, kb_id: str) -> None:
    print("\n[02] 表格切块 upload + retrieve 验收")
    promo_path = PROJECT_ROOT / "data/ecommerce/促销活动与优惠券使用规则.md"
    content = promo_path.read_text(encoding="utf-8")
    upload = request_json(
        "POST",
        "/documents/upload",
        api_key,
        {"kb_id": kb_id, "title": "促销活动与优惠券使用规则.md", "content": content},
    )
    document_id = upload["document_id"]
    detail = wait_document_success(api_key, document_id)
    print(f"  document_id={document_id} chunk_count={detail.get('chunk_count')}")

    result = request_json(
        "POST",
        "/rag/retrieve",
        api_key,
        {
            "kb_id": kb_id,
            "user_id": "chunk_verify",
            "query": "满减和优惠券能叠加吗",
            "profile": "balanced",
        },
    )
    chunks = result.get("retrieved_chunks") or []
    assert chunks, "应有召回结果"
    top_content = chunks[0].get("content", "")
    assert "【表头】" in top_content or "满减" in top_content, "Top chunk 应含表格或满减相关语义"
    orphan = re.search(r"^\|\s*否\s*\|", top_content, re.MULTILINE)
    assert not orphan or "满减" in top_content or "优惠券" in top_content, "不应只有半行表格残片"
    print("  retrieve Top1 含完整表格语义 → OK")


def main() -> None:
    api_key = load_api_key()
    kb_id = sys.argv[1] if len(sys.argv) > 1 else "b0646f80-13ee-46fb-890c-c01a7a75b449"
    print(f"使用 kb_id={kb_id}")
    verify_heading_upload(api_key, kb_id)
    verify_table_upload(api_key, kb_id)
    print("\n优化十一 01/02 集成验收全部通过。")


if __name__ == "__main__":
    main()
