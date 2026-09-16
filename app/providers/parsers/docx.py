import io
import re
from pathlib import Path

import mammoth
from markdownify import markdownify

from app.providers.parsers.base import DocumentParser, ParsedDocument

_EMPTY_TABLE_ROW_RE = re.compile(r"^\|\s*(\|\s*)+\|\s*$")
_TABLE_ROW_RE = re.compile(r"^\|.+\|$")
_TABLE_SEPARATOR_RE = re.compile(r"^\|\s*[-:\s|]+\|\s*$")
_BOOKMARK_ANCHOR_RE = re.compile(r'<a\s+id="[^"]*"\s*></a>', re.IGNORECASE)
_RESIDUAL_BOOKMARK_RE = re.compile(r'<a\s+id="[^"]*"\s*></a>\s*', re.IGNORECASE)


def _strip_html_bookmarks(html: str) -> str:
    """Word/Pandoc 导出的 docx 常在标题前插入书签锚点，需在转 Markdown 前去掉。"""
    return _BOOKMARK_ANCHOR_RE.sub("", html)


def _strip_residual_html(markdown: str) -> str:
    return _RESIDUAL_BOOKMARK_RE.sub("", markdown)


def _clean_markdownify_tables(markdown: str) -> str:
    """Remove markdownify's leading empty table header row + separator."""
    lines = markdown.split("\n")
    cleaned: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if (
            index + 1 < len(lines)
            and _EMPTY_TABLE_ROW_RE.match(line.strip())
            and re.match(r"^\|\s*[-:\s|]+\|\s*$", lines[index + 1].strip())
        ):
            index += 2
            continue
        cleaned.append(line)
        index += 1
    return "\n".join(cleaned)


def _ensure_gfm_table_separators(markdown: str) -> str:
    """Insert GFM header separator row once after the first table header row."""
    lines = markdown.split("\n")
    result: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        result.append(line)
        if (
            _TABLE_ROW_RE.match(line.strip())
            and index + 1 < len(lines)
            and _TABLE_ROW_RE.match(lines[index + 1].strip())
            and not _TABLE_SEPARATOR_RE.match(lines[index + 1].strip())
        ):
            columns = line.strip().strip("|").split("|")
            separator = "| " + " | ".join("---" for _ in columns) + " |"
            result.append(separator)
            index += 1
            while index < len(lines):
                row = lines[index]
                if not _TABLE_ROW_RE.match(row.strip()):
                    break
                if _TABLE_SEPARATOR_RE.match(row.strip()):
                    index += 1
                    continue
                result.append(row)
                index += 1
            continue
        index += 1
    return "\n".join(result)


def docx_html_to_markdown(html: str) -> str:
    markdown = markdownify(
        _strip_html_bookmarks(html),
        heading_style="ATX",
        bullets="-",
        strip=["script", "style"],
    )
    normalized = _clean_markdownify_tables(markdown.replace("\r\n", "\n"))
    cleaned = _strip_residual_html(_ensure_gfm_table_separators(normalized))
    return cleaned.strip()


class DocxParser(DocumentParser):
    @property
    def name(self) -> str:
        return "docx"

    def supports(self, filename: str, mime_type: str | None = None) -> bool:
        return Path(filename).suffix.lower() == ".docx"

    async def parse(self, file_bytes: bytes, *, filename: str) -> ParsedDocument:
        # mammoth.convert_to_markdown 不会输出 Markdown 表格；先转 HTML 再 markdownify。
        html_result = mammoth.convert_to_html(io.BytesIO(file_bytes))
        markdown = docx_html_to_markdown(html_result.value)
        warnings = [message.message for message in html_result.messages]
        return ParsedDocument(
            content=markdown,
            source_type="docx",
            metadata={"parser": self.name, "warnings": warnings},
        )
