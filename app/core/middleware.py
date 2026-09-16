from __future__ import annotations

import time

from fastapi import Request
from starlette.concurrency import iterate_in_threadpool

from app.core.config import settings
from app.core.logging import (
    generate_request_id,
    get_logger,
    reset_request_id,
    safe_json,
    set_request_id,
    truncate_text,
)

logger = get_logger(__name__)


async def request_response_log_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or generate_request_id()
    token = set_request_id(request_id)
    started_at = time.perf_counter()
    request_body_text = ""

    try:
        body = await request.body()
        await _reset_request_body(request, body)
        request_body_text = _decode_body(body) if settings.log_request_body else "-"
        logger.info(
            "HTTP_REQUEST | method=%s | url=%s | body=%s",
            request.method,
            request.url.path,
            truncate_text(request_body_text),
        )

        response = await call_next(request)
        response_body = b""
        if settings.log_response_body:
            chunks = [chunk async for chunk in response.body_iterator]
            response_body = b"".join(chunks)
            response.body_iterator = iterate_in_threadpool(iter(chunks))

        cost_ms = (time.perf_counter() - started_at) * 1000
        logger.info(
            "HTTP_RESPONSE | method=%s | url=%s | status_code=%s | cost=%.2fms | body=%s",
            request.method,
            request.url.path,
            response.status_code,
            cost_ms,
            truncate_text(_decode_body(response_body)) if settings.log_response_body else "-",
        )
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception:
        cost_ms = (time.perf_counter() - started_at) * 1000
        logger.exception(
            "HTTP_EXCEPTION | method=%s | url=%s | cost=%.2fms | request_body=%s",
            request.method,
            request.url.path,
            cost_ms,
            truncate_text(request_body_text),
        )
        raise
    finally:
        reset_request_id(token)


def _decode_body(body: bytes) -> str:
    if not body:
        return ""
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError:
        return safe_json({"binary_body_bytes": len(body)})


async def _reset_request_body(request: Request, body: bytes) -> None:
    async def receive() -> dict:
        return {"type": "http.request", "body": body, "more_body": False}

    request._receive = receive  # noqa: SLF001
