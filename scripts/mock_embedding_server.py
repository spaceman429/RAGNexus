#!/usr/bin/env python3
"""本地 Mock Embedding 服务（OpenAI 兼容 /v1/embeddings）。

用途：在没有真实 Embedding API Key 的情况下跑通「上传 -> 切块 -> 向量入库 -> 检索」全链路。
原理：用字符 n-gram + hashing trick 生成确定性向量，语义相近的文本向量也相近，
      因此 hybrid/vector 检索能返回有意义的结果，可真实演示链路是否通畅。

启动：python scripts/mock_embedding_server.py --port 8899
      然后在 .env 或环境变量中设置：
        MODEL_BASE_URL=http://127.0.0.1:8899/v1
        MODEL_API_KEY=mock
        EMBEDDING_MODEL=mock-embedding
注意：仅供本地开发/演示，切勿用于生产。
"""
from __future__ import annotations

import argparse
import hashlib
import math

from fastapi import FastAPI, Request

DIM_DEFAULT = 1536


def _make_dim() -> int:
    return DIM_DEFAULT


app = FastAPI(title="Mock Embedding Server")


def embed_text(text: str, dim: int) -> list[float]:
    vec = [0.0] * dim
    t = (text or "").lower()
    tokens: list[str] = list(t) + [t[i : i + 2] for i in range(max(len(t) - 1, 0))]
    for tok in tokens:
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if (h >> 20) % 2 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/v1/embeddings")
async def embeddings(request: Request) -> dict:
    body = await request.json()
    raw_input = body.get("input")
    model = body.get("model", "mock-embedding")
    dim = int(body.get("dimensions") or DIM_DEFAULT)
    if isinstance(raw_input, str):
        texts = [raw_input]
    elif isinstance(raw_input, list):
        texts = [str(x) for x in raw_input]
    else:
        texts = [""]
    data = [
        {"object": "embedding", "index": i, "embedding": embed_text(t, dim)}
        for i, t in enumerate(texts)
    ]
    return {
        "object": "list",
        "data": data,
        "model": model,
        "usage": {"prompt_tokens": sum(len(t) for t in texts), "total_tokens": 0},
    }


def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser(description="Mock OpenAI-compatible embedding server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8899)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
