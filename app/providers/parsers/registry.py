from pathlib import Path

from app.core.exceptions import AppError, ErrorCode
from app.providers.parsers.base import DocumentParser
from app.providers.parsers.markdown import MarkdownParser

SUPPORTED_UPLOAD_EXTENSIONS = {".md", ".txt", ".markdown", ".pdf", ".docx"}


def _build_parsers() -> list[DocumentParser]:
    parsers: list[DocumentParser] = []
    try:
        from app.providers.parsers.docx import DocxParser

        parsers.append(DocxParser())
    except ImportError:
        pass
    try:
        from app.providers.parsers.pdf import PdfParser

        parsers.append(PdfParser())
    except ImportError:
        pass
    parsers.append(MarkdownParser())
    return parsers


def get_document_parser(filename: str, mime_type: str | None = None) -> DocumentParser:
    for parser in _build_parsers():
        if parser.supports(filename, mime_type):
            return parser
    raise AppError(
        ErrorCode.PARAM_ERROR,
        msg=f"不支持的文档格式: {Path(filename).suffix or filename}",
        context={"filename": filename, "mime_type": mime_type},
    )


def validate_upload_extension(filename: str) -> None:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_UPLOAD_EXTENSIONS:
        raise AppError(
            ErrorCode.PARAM_ERROR,
            msg=f"不支持的文件扩展名: {suffix or '(无)'}，允许: {', '.join(sorted(SUPPORTED_UPLOAD_EXTENSIONS))}",
            context={"filename": filename, "extension": suffix},
        )
