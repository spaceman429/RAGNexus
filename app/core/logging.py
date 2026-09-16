from __future__ import annotations

import asyncio
import atexit
import contextvars
import functools
import json
import logging
import logging.handlers
import os
import queue
import time
from collections.abc import Callable
from typing import Any, TypeVar
from uuid import uuid4

from app.core.config import settings

F = TypeVar("F", bound=Callable[..., Any])

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
_listener: logging.handlers.QueueListener | None = None


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get("-")
        return True


class ColorFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: "\033[36m",
        logging.INFO: "\033[32m",
        logging.WARNING: "\033[33m",
        logging.ERROR: "\033[31m",
        logging.CRITICAL: "\033[35m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelno, "")
        original_levelname = record.levelname
        record.levelname = f"{color}{record.levelname}{self.RESET}" if color else record.levelname
        try:
            return super().format(record)
        finally:
            record.levelname = original_levelname


def generate_request_id() -> str:
    return str(uuid4())


def set_request_id(request_id: str) -> contextvars.Token[str]:
    return request_id_var.set(request_id)


def reset_request_id(token: contextvars.Token[str]) -> None:
    request_id_var.reset(token)


def get_request_id() -> str:
    return request_id_var.get("-")


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def configure_logging() -> None:
    global _listener
    if _listener is not None:
        return

    os.makedirs(settings.log_dir, exist_ok=True)

    fmt = (
        "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | "
        "request_id=%(request_id)s | %(message)s"
    )
    datefmt = "%Y-%m-%d %H:%M:%S"

    request_filter = RequestIdFilter()
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(ColorFormatter(fmt=fmt, datefmt=datefmt))
    console_handler.addFilter(request_filter)

    size_handler = logging.handlers.RotatingFileHandler(
        os.path.join(settings.log_dir, "app.log"),
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count,
        encoding="utf-8",
    )
    size_handler.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))
    size_handler.addFilter(request_filter)

    error_handler = logging.handlers.RotatingFileHandler(
        os.path.join(settings.log_dir, "error.log"),
        maxBytes=settings.log_error_max_bytes,
        backupCount=settings.log_error_backup_count,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))
    error_handler.addFilter(request_filter)

    time_handler = logging.handlers.TimedRotatingFileHandler(
        os.path.join(settings.log_dir, "app.daily.log"),
        when="midnight",
        backupCount=settings.log_daily_backup_count,
        encoding="utf-8",
    )
    time_handler.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))
    time_handler.addFilter(request_filter)

    log_queue: queue.Queue[logging.LogRecord] = queue.Queue(-1)
    queue_handler = logging.handlers.QueueHandler(log_queue)
    queue_handler.addFilter(request_filter)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(settings.log_level.upper())
    root.addHandler(queue_handler)

    _listener = logging.handlers.QueueListener(
        log_queue,
        console_handler,
        size_handler,
        error_handler,
        time_handler,
        respect_handler_level=True,
    )
    _listener.start()
    atexit.register(stop_logging)


def stop_logging() -> None:
    global _listener
    if _listener is None:
        return
    _listener.stop()
    _listener = None


def safe_json(value: Any, *, max_length: int | None = None) -> str:
    limit = max_length or settings.log_body_max_chars
    try:
        text = json.dumps(value, ensure_ascii=False, default=str)
    except TypeError:
        text = str(value)
    return truncate_text(text, limit)


def truncate_text(value: Any, max_length: int | None = None) -> str:
    limit = max_length or settings.log_body_max_chars
    text = value if isinstance(value, str) else str(value)
    if len(text) <= limit:
        return text
    return f"{text[:limit]}...(truncated, total={len(text)})"


def log_api_call(func: F) -> F:
    logger = get_logger(func.__module__)

    if asyncio.iscoroutinefunction(func):

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            started_at = time.perf_counter()
            logger.info(
                "API_REQUEST | %s | args=%s | kwargs=%s",
                func.__name__,
                safe_json(args),
                safe_json(kwargs),
            )
            try:
                result = await func(*args, **kwargs)
                cost_ms = (time.perf_counter() - started_at) * 1000
                logger.info(
                    "API_RESPONSE | %s | cost=%.2fms | result=%s",
                    func.__name__,
                    cost_ms,
                    safe_json(result),
                )
                return result
            except Exception:
                cost_ms = (time.perf_counter() - started_at) * 1000
                logger.exception("API_EXCEPTION | %s | cost=%.2fms", func.__name__, cost_ms)
                raise

        return async_wrapper  # type: ignore[return-value]

    @functools.wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        started_at = time.perf_counter()
        logger.info(
            "API_REQUEST | %s | args=%s | kwargs=%s",
            func.__name__,
            safe_json(args),
            safe_json(kwargs),
        )
        try:
            result = func(*args, **kwargs)
            cost_ms = (time.perf_counter() - started_at) * 1000
            logger.info(
                "API_RESPONSE | %s | cost=%.2fms | result=%s",
                func.__name__,
                cost_ms,
                safe_json(result),
            )
            return result
        except Exception:
            cost_ms = (time.perf_counter() - started_at) * 1000
            logger.exception("API_EXCEPTION | %s | cost=%.2fms", func.__name__, cost_ms)
            raise

    return sync_wrapper  # type: ignore[return-value]


def log_llm_request(*, model: str, prompt: Any, extra: dict[str, Any] | None = None) -> None:
    logger = get_logger("app.llm")
    logger.info(
        "LLM_REQUEST | model=%s | prompt=%s | extra=%s",
        model,
        safe_json(prompt, max_length=settings.log_llm_max_chars),
        safe_json(extra or {}),
    )


def log_llm_response(
    *,
    model: str,
    response: Any,
    cost_ms: float,
    extra: dict[str, Any] | None = None,
) -> None:
    logger = get_logger("app.llm")
    logger.info(
        "LLM_RESPONSE | model=%s | cost=%.2fms | response=%s | extra=%s",
        model,
        cost_ms,
        safe_json(response, max_length=settings.log_llm_max_chars),
        safe_json(extra or {}),
    )


def log_llm_error(
    *,
    model: str,
    error: Exception,
    cost_ms: float,
    prompt: Any | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    logger = get_logger("app.llm")
    logger.exception(
        "LLM_EXCEPTION | model=%s | cost=%.2fms | error_type=%s | error=%s | prompt=%s | extra=%s",
        model,
        cost_ms,
        type(error).__name__,
        str(error),
        safe_json(prompt, max_length=settings.log_llm_max_chars) if prompt is not None else "-",
        safe_json(extra or {}),
    )
