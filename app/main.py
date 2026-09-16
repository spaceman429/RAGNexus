from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.exceptions import AppError, ErrorCode
from app.core.logging import configure_logging, get_logger
from app.core.middleware import request_response_log_middleware
from app.schemas.common import error_response

configure_logging()
logger = get_logger(__name__)

app = FastAPI(title="RAG Center", version="0.1.0")
app.middleware("http")(request_response_log_middleware)
app.include_router(api_router)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    logger.error(
        "APP_ERROR | path=%s | error_name=%s | code=%s | msg=%s | internal_msg=%s | context=%s",
        request.url.path,
        exc.error_name,
        exc.code,
        exc.msg,
        exc.internal_msg,
        exc.context,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return JSONResponse(content=error_response(exc.code, exc.msg, exc.data))


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    logger.warning(
        "REQUEST_VALIDATION_ERROR | path=%s | errors=%s",
        request.url.path,
        exc.errors(),
    )
    return JSONResponse(
        content=error_response(
            ErrorCode.REQUEST_VALIDATION_ERROR,
            ErrorCode.REQUEST_VALIDATION_ERROR.msg,
            jsonable_encoder(exc.errors()),
        )
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "UNHANDLED_EXCEPTION | path=%s | error_type=%s | error=%s",
        request.url.path,
        type(exc).__name__,
        str(exc),
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return JSONResponse(
        status_code=500,
        content=error_response(ErrorCode.SERVER_ERROR, ErrorCode.SERVER_ERROR.msg),
    )
