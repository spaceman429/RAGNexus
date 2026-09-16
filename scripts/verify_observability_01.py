#!/usr/bin/env python3
"""Verify optimization 10-01 retrieve observability fields."""

from __future__ import annotations

import json
import sys
from urllib import error, request

import psycopg

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8002"
KB_ID = sys.argv[2] if len(sys.argv) > 2 else "5c97fcc6-95b1-47bb-80c3-437da2095a91"
DB_URL = "postgresql://postgres:postgres@localhost:5432/rag_center"


def main() -> int:
    payload = json.dumps(
        {
            "kb_id": KB_ID,
            "user_id": "obs_test",
            "query": "退款几天内可以申请？",
            "profile": "balanced",
        }
    ).encode()
    req = request.Request(
        f"{BASE_URL}/api/v1/rag/retrieve",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=120) as resp:
            body = json.load(resp)
    except error.HTTPError as exc:
        print("retrieve failed:", exc.read().decode())
        return 1

    if body.get("code") != 0:
        print("unexpected code:", body)
        return 1

    metadata = body["data"]["metadata"]
    log_id = metadata.get("log_id")
    trace_id = metadata.get("trace_id")
    latency_ms = metadata.get("latency_ms")
    print("log_id:", log_id)
    print("trace_id:", trace_id)
    print("latency_ms:", latency_ms)

    if not log_id:
        print("FAIL: missing log_id")
        return 1
    if latency_ms is None:
        print("FAIL: missing latency_ms")
        return 1

    with psycopg.connect(DB_URL) as conn:
        row = conn.execute(
            """
            SELECT id, trace_id, profile, search_query, effective_query, latency_ms
            FROM retrieval_logs
            WHERE id = %s
            """,
            (log_id,),
        ).fetchone()

    if row is None:
        print("FAIL: retrieval_logs row not found")
        return 1

    print("db row:", row)
    if row[0] != log_id:
        print("FAIL: db id mismatch")
        return 1
    if row[1] != trace_id:
        print("FAIL: trace_id mismatch")
        return 1
    if row[2] != "balanced":
        print("FAIL: profile mismatch")
        return 1

    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
