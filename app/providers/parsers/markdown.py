from pathlib import Path

from app.providers.parsers.base import DocumentParser, ParsedDocument


class MarkdownParser(DocumentParser):
    @property
    def name(self) -> str:
        return "markdown"

    def supports(self, filename: str, mime_type: str | None = None) -> bool:
        suffix = Path(filename).suffix.lower()
        return suffix in {".md", ".txt", ".markdown"}

    async def parse(self, file_bytes: bytes, *, filename: str) -> ParsedDocument:
        text = file_bytes.decode("utf-8", errors="replace").replace("\r\n", "\n").strip()
        suffix = Path(filename).suffix.lower()
        source_type = "markdown" if suffix in {".md", ".markdown"} else "text"
        return ParsedDocument(
            content=text,
            source_type=source_type,
            metadata={"parser": self.name},
        )
