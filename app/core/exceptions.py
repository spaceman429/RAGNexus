from enum import Enum
from typing import Any


class ErrorCode(Enum):
    SUCCESS = (0, "成功")

    # API / HTTP / request: 20000-29999
    PARAM_ERROR = (20001, "参数错误")
    REQUEST_VALIDATION_ERROR = (20002, "请求参数校验失败")
    API_REQUEST_ERROR = (20003, "接口请求失败")
    API_TIMEOUT = (20004, "接口请求超时")
    API_RATE_LIMIT = (20005, "接口调用超限")
    NOT_FOUND = (20006, "资源不存在")
    METHOD_ERROR = (20007, "请求方法错误")
    KNOWLEDGE_BASE_NOT_FOUND = (20008, "知识库不存在")
    DOCUMENT_CONTENT_EMPTY = (20009, "文档内容为空")
    UNAUTHORIZED = (20010, "未授权")
    DOCUMENT_NOT_FOUND = (20011, "文档不存在")
    DOCUMENT_PROCESSING = (20012, "文档正在索引中")
    FEATURE_NOT_ALLOWED = (20013, "当前套餐不支持该功能")
    QUOTA_EXCEEDED = (20014, "配额已用尽")
    FEEDBACK_FAILED = (20020, "反馈提交失败")
    FEEDBACK_LOG_MISMATCH = (20021, "检索记录与 trace 不匹配或无权访问")
    FEEDBACK_INVALID_SCORE = (20022, "评分须在 1～5 之间")
    DOCUMENT_PARSE_FAILED = (20023, "文档解析失败")

    # Database / storage: 30000-39999
    DB_ERROR = (30001, "数据库操作失败")
    DATA_DUPLICATE = (30002, "数据已存在")
    DOCUMENT_INDEX_FAILED = (30003, "文档索引失败")
    VECTOR_STORE_ERROR = (30004, "向量存储操作失败")
    KEYWORD_SEARCH_ERROR = (30005, "关键词检索服务异常")

    # LLM: 40000-49999
    LLM_ERROR = (40000, "大模型调用失败")
    LLM_TIMEOUT = (40001, "大模型响应超时")
    LLM_NO_RESPONSE = (40002, "大模型未返回有效内容")
    LLM_CONTENT_VIOLATION = (40003, "内容违规，大模型拒绝生成")
    LLM_TOKEN_LIMIT = (40004, "上下文长度超限")
    LLM_RATE_LIMIT = (40005, "大模型调用频率超限")
    LLM_MODEL_ERROR = (40006, "模型不存在或未部署")
    EMBEDDING_FAILED = (40007, "向量模型调用失败")
    LLM_PROVIDER_FAILED = (40008, "大模型服务调用失败")
    RERANK_FAILED = (40009, "大模型重排失败")

    # System / service: 50000-59999
    SERVER_ERROR = (50000, "服务器异常")
    SYSTEM_BUSY = (50001, "系统繁忙，请稍后再试")
    RETRIEVAL_FAILED = (50002, "检索服务异常")

    @property
    def code(self) -> int:
        return self.value[0]

    @property
    def msg(self) -> str:
        return self.value[1]


class AppError(Exception):
    def __init__(
        self,
        error_code: ErrorCode | int,
        msg: str | None = None,
        data: Any = None,
        *,
        internal_msg: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        if isinstance(error_code, ErrorCode):
            self.code = error_code.code
            self.msg = msg or error_code.msg
            self.error_name = error_code.name
        else:
            self.code = int(error_code)
            self.msg = msg or "请求失败"
            self.error_name = "CUSTOM_ERROR"

        self.data = data
        self.internal_msg = internal_msg or self.msg
        self.context = context or {}
        super().__init__(self.internal_msg)


def raise_app_error(
    error_code: ErrorCode,
    msg: str | None = None,
    data: Any = None,
    *,
    internal_msg: str | None = None,
    context: dict[str, Any] | None = None,
) -> None:
    raise AppError(
        error_code,
        msg,
        data,
        internal_msg=internal_msg,
        context=context,
    )
