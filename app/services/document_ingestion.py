from app.core.exceptions import AppError, ErrorCode
from app.core.logging import get_logger
from app.providers.parsers.base import ParsedDocument
from app.providers.parsers.registry import get_document_parser
from app.utils.document_storage import read_document_file

logger = get_logger(__name__)


async def prepare_document_content(
    *,
    content: str | None,
    file_path: str | None,
    filename: str | None,
) -> ParsedDocument:
    if content and content.strip():
        normalized = content.replace("\r\n", "\n").strip()
        source_type = "markdown"
        if filename and not filename.lower().endswith((".md", ".markdown")):
            source_type = "text"
        return ParsedDocument(
            content=normalized,
            source_type=source_type,
            metadata={"parser": "pass-through"},
        )

    if not file_path:
        raise AppError(ErrorCode.DOCUMENT_CONTENT_EMPTY)

    try:
        file_bytes = read_document_file(file_path)
    except FileNotFoundError as exc:
        raise AppError(
            ErrorCode.DOCUMENT_PARSE_FAILED,
            msg="原文件不存在，无法解析",
            internal_msg=str(exc),
            context={"file_path": file_path},
        ) from exc

    parse_name = filename or file_path
    parser = get_document_parser(parse_name)
    logger.info(
        "BUSINESS_NODE | document_parse_start | filename=%s | parser=%s",
        parse_name,
        parser.name,
    )
    try:
        parsed = await parser.parse(file_bytes, filename=parse_name)
    except AppError:
        raise
    except Exception as exc:
        raise AppError(
            ErrorCode.DOCUMENT_PARSE_FAILED,
            msg=f"文档解析失败: {exc}",
            internal_msg=str(exc),
            context={"filename": parse_name, "parser": parser.name},
        ) from exc

    if not parsed.content.strip():
        raise AppError(
            ErrorCode.DOCUMENT_PARSE_FAILED,
            msg="文档解析结果为空",
            context={"filename": parse_name, "parser": parser.name},
        )

    logger.info(
        "BUSINESS_NODE | document_parse_success | filename=%s | parser=%s | content_chars=%s",
        parse_name,
        parser.name,
        len(parsed.content),
    )
    return parsed
