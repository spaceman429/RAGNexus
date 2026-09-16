"""Shared helpers for offline retrieval evaluation scripts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
from openai import OpenAI

from app.core.config import settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FEEDBACK_SCORE_NAME = "user_feedback"
EVAL_USER_ID = "eval_runner"

METRIC_LABELS: dict[str, str] = {
    "context_precision": "上下文精确率",
    "context_recall": "上下文召回率",
}

METRIC_HINTS: dict[str, str] = {
    "context_precision": "召回来的 chunk 有多少真的和问题相关",
    "context_recall": "标准答案里的要点有没有出现在召回内容里",
}

PROFILE_HINTS: dict[str, str] = {
    "speed": "vector 向量检索，top_k=3，无改写/重排",
    "balanced": "hybrid 混合检索，top_k=5，无改写/重排",
    "quality": "hybrid 混合检索，top_k=8，开启改写 + 重排",
    "custom": "自定义参数（由请求体决定）",
}


def load_dataset(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"dataset not found: {path}")
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"dataset root must be an object: {path}")
    if "cases" not in data or not isinstance(data["cases"], list):
        raise ValueError(f"dataset must contain a cases array: {path}")
    return data


def save_dataset(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def ground_truth_ready(case: dict[str, Any]) -> bool:
    return bool(str(case.get("ground_truth") or "").strip())


def merge_cases(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    merged = list(existing)
    seen = {str(case.get("question") or "").strip() for case in existing if case.get("question")}
    added = 0
    for case in incoming:
        question = str(case.get("question") or "").strip()
        if not question or question in seen:
            continue
        merged.append(case)
        seen.add(question)
        added += 1
    return merged, added


def get_langfuse_for_scripts() -> Any:
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        raise RuntimeError(
            "Langfuse keys missing: set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY in .env"
        )

    from langfuse import Langfuse

    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
        httpx_client=httpx.Client(trust_env=False),
    )


def extract_trace_question(trace_input: Any) -> str | None:
    if isinstance(trace_input, dict):
        for key in ("query", "question", "user_input"):
            value = trace_input.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None
    if isinstance(trace_input, str) and trace_input.strip():
        return trace_input.strip()
    return None


def extract_trace_metadata(trace: Any) -> dict[str, Any]:
    metadata = getattr(trace, "metadata", None)
    if isinstance(metadata, dict):
        return metadata
    return {}


def build_ragas_llm():
    from ragas.llms import llm_factory

    base_url = settings.llm_base_url or settings.model_base_url
    api_key = settings.llm_api_key or settings.model_api_key
    model = settings.llm_model
    if not api_key or api_key in {"your-api-key", "your-deepseek-api-key"}:
        raise RuntimeError(
            "LLM API key missing: set LLM_API_KEY or MODEL_API_KEY in .env for RAGAS evaluation"
        )

    client = OpenAI(base_url=base_url, api_key=api_key)
    return llm_factory(model, client=client)


def load_ragas_metrics():
    from ragas.metrics import context_precision, context_recall

    metrics: list[Any] = []
    for metric in (context_precision, context_recall):
        if isinstance(metric, type):
            metrics.append(metric())
        else:
            metrics.append(metric)
    return metrics[0], metrics[1]
