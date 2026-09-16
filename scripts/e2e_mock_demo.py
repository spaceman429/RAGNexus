#!/usr/bin/env python3
"""rag-center 离线一键演示（无需真实 Embedding/LLM API Key）。

做什么：
  1) 启动本地 mock embedding 服务（OpenAI 兼容）
  2) 覆盖 MODEL_BASE_URL/MODEL_API_KEY 启动 API 与 Celery Worker
  3) 自动建租户 + API Key
  4) 建知识库 -> 上传文档 -> 轮询索引状态 -> 检索
  5) 打印每一步结果，结束自动清理进程

前置：PostgreSQL/Elasticsearch/Redis 已通过 `docker compose up -d` 启动，已执行 alembic 迁移。

用法：python scripts/e2e_mock_demo.py
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
API = "http://127.0.0.1:8000/api/v1"
MOCK_PORT = 8899
LOGS = ROOT / "logs"

ENV = os.environ.copy()
ENV["MODEL_BASE_URL"] = f"http://127.0.0.1:{MOCK_PORT}/v1"
ENV["MODEL_API_KEY"] = "mock"
ENV["EMBEDDING_MODEL"] = "mock-embedding"


def _start(cmd: list[str], log_name: str) -> subprocess.Popen:
    LOGS.mkdir(exist_ok=True)
    fh = open(LOGS / log_name, "w", encoding="utf-8")
    p = subprocess.Popen(cmd, cwd=ROOT, env=ENV, stdout=fh, stderr=subprocess.STDOUT)
    print(f"  started: {' '.join(cmd[-3:])} (pid={p.pid})")
    return p


def _wait_http(url: str, timeout: float = 40.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            httpx.get(url, timeout=3)
            return True
        except Exception:
            time.sleep(1)
    return False


def main() -> int:
    procs: list[subprocess.Popen] = []
    try:
        print("[1/6] 启动 mock embedding 服务")
        procs.append(_start([PY, "scripts/mock_embedding_server.py", "--port", str(MOCK_PORT)], "mock.log"))
        print("      health:", _wait_http(f"http://127.0.0.1:{MOCK_PORT}/health"))

        print("[2/6] 启动 API 服务")
        procs.append(
            _start([PY, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"], "api.log")
        )
        time.sleep(6)

        print("[3/6] 启动 Celery Worker")
        procs.append(
            _start(
                [PY, "-m", "celery", "-A", "app.celery_app", "worker", "--loglevel=info", "--pool=solo"],
                "worker.log",
            )
        )
        time.sleep(12)

        print("[4/6] 建租户 + 升级 plan + API Key")
        subprocess.run(
            [PY, "scripts/create_tenant.py", "--id", "tenant_demo", "--name", "Demo Tenant"],
            cwd=ROOT, env=ENV, capture_output=True, text=True,
        )
        subprocess.run(
            [PY, "scripts/update_tenant_plan.py", "--tenant-id", "tenant_demo", "--plan", "pro"],
            cwd=ROOT, env=ENV, capture_output=True, text=True,
        )
        res = subprocess.run(
            [PY, "scripts/create_api_key.py", "--tenant-id", "tenant_demo", "--name", "e2e"],
            cwd=ROOT, env=ENV, capture_output=True, text=True,
        )
        m = re.search(r"(rk_live_[A-Za-z0-9_\-]+)", res.stdout or "")
        if not m:
            print("  !! 未能生成 API Key，输出：", (res.stdout or "")[-200:], (res.stderr or "")[-300:])
            return 1
        raw_key = m.group(1)
        print(f"  api key created: {raw_key[:12]}***")

        headers = {"Authorization": f"Bearer {raw_key}"}
        client = httpx.Client(timeout=45)

        print("[5/6] 建库 -> 上传 -> 轮询索引")
        me = client.get(f"{API}/auth/me", headers=headers).json()
        print("  auth/me ->", me)
        kb = client.post(
            f"{API}/knowledge-bases/create",
            headers=headers,
            json={"name": f"退款政策知识库-{int(time.time()) % 100000}", "description": "e2e demo"},
        ).json()
        print("  create_kb ->", kb)
        kb_id = kb["data"]["kb_id"]
        up = client.post(
            f"{API}/documents/upload",
            headers=headers,
            json={
                "kb_id": kb_id,
                "title": "退款政策",
                "content": "用户可在订单完成后 7 天内申请退款。特殊商品不支持无理由退款。退款会在 3 个工作日内到账。",
            },
        ).json()
        print("  upload ->", up)
        doc_id = up["data"]["document_id"]
        status = None
        for i in range(25):
            d = client.get(f"{API}/documents/{doc_id}", headers=headers).json().get("data") or {}
            status = d.get("status")
            if status != 3:
                print(f"  poll#{i} status={status} (1=SUCCESS,2=FAILED,3=PROCESSING)")
                break
            time.sleep(2)

        print("[6/6] 检索验证")
        for prof in ("speed", "balanced"):
            rr = client.post(
                f"{API}/rag/retrieve",
                headers=headers,
                json={"kb_id": kb_id, "user_id": "u1", "query": "退款需要几天内申请？", "profile": prof},
            ).json()
            d = rr.get("data") or {}
            meta = d.get("metadata") or {}
            chs = d.get("retrieved_chunks") or []
            print(
                f"  [{prof}] code={rr.get('code')} hits={len(chs)} "
                f"latency_ms={meta.get('latency_ms')} retrieval={meta.get('retrieval')}"
            )
            for ch in chs[:2]:
                print(
                    "     -",
                    (ch.get("content") or "")[:60],
                    "| score=", ch.get("score"),
                    "| src=", ch.get("retrieval_source"),
                )
        print("\n[OK] 端到端链路跑通")
        return 0
    finally:
        for p in procs:
            try:
                p.terminate()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
