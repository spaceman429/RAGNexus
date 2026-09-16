from typing import Any

from pydantic import BaseModel

from app.core.exceptions import ErrorCode


class ApiResponse(BaseModel):
    code: int = 0
    msg: str = "success"
    data: Any = None


def success_response(data: Any) -> dict:
    return {"code": 0, "msg": "success", "data": data}


def error_response(code: int | ErrorCode, msg: str | None = None, data: Any = None) -> dict:
    if isinstance(code, ErrorCode):
        return {"code": code.code, "msg": msg or code.msg, "data": data}
    return {"code": code, "msg": msg or "请求失败", "data": data}
