import re
from dataclasses import dataclass, field

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
FENCE_RE = re.compile(r"^\s*```")
HORIZONTAL_RULE_RE = re.compile(r"^-{3,}\s*$")
SECTION_SPLIT_MIN_LEVEL = 1
SECTION_SPLIT_MAX_LEVEL = 2


@dataclass(slots=True)
class SplitPiece:
    text: str
    metadata: dict = field(default_factory=dict)


@dataclass(slots=True)
class _Section:
    heading_line: str | None
    heading_path: str
    body_lines: list[str]


@dataclass(slots=True)
class _ContentBlock:
    kind: str  # prose | code | table
    lines: list[str]


class MarkdownStructuredSplitter:
    def __init__(
        self,
        chunk_size: int,
        chunk_overlap: int,
        *,
        table_max_rows_per_chunk: int = 10,
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.table_max_rows_per_chunk = table_max_rows_per_chunk

    def split(self, text: str) -> list[SplitPiece]:
        normalized = text.replace("\r\n", "\n").strip()
        if not normalized:
            return []

        sections = self._split_into_sections(normalized.split("\n"))
        pieces: list[SplitPiece] = []
        for section in sections:
            pieces.extend(self._chunk_section(section))
        return [piece for piece in pieces if piece.text.strip()]

    def _split_into_sections(self, lines: list[str]) -> list[_Section]:
        sections: list[_Section] = []
        heading_stack: list[tuple[int, str]] = []
        current_heading_line: str | None = None
        current_heading_path = ""
        current_body: list[str] = []

        def flush() -> None:
            nonlocal current_heading_line, current_heading_path, current_body
            if current_heading_line is not None or current_body:
                sections.append(
                    _Section(
                        heading_line=current_heading_line,
                        heading_path=current_heading_path,
                        body_lines=current_body,
                    )
                )
            current_heading_line = None
            current_body = []

        for line in lines:
            if self._is_horizontal_rule(line):
                continue

            match = HEADING_RE.match(line)
            if match:
                level = len(match.group(1))
                title = match.group(2).strip()
                while heading_stack and heading_stack[-1][0] >= level:
                    heading_stack.pop()
                heading_stack.append((level, title))
                heading_path = "/".join(item[1] for item in heading_stack)

                if SECTION_SPLIT_MIN_LEVEL <= level <= SECTION_SPLIT_MAX_LEVEL:
                    flush()
                    current_heading_line = line
                    current_heading_path = heading_path
                else:
                    current_body.append(line)
                continue

            if current_heading_line is None and not heading_stack:
                current_body.append(line)
                continue
            current_body.append(line)

        flush()

        if not sections and lines:
            return [_Section(heading_line=None, heading_path="", body_lines=lines)]
        return sections

    def _chunk_section(self, section: _Section) -> list[SplitPiece]:
        blocks = self._parse_blocks(section.body_lines)
        pieces: list[SplitPiece] = []
        heading_prefix = f"{section.heading_line}\n\n" if section.heading_line else ""
        heading_used = False

        for block in blocks:
            if block.kind == "table":
                if not heading_used and heading_prefix:
                    # 标题仅随本节第一个块；表格块单独成 chunk，不拼标题行
                    heading_used = True
                pieces.extend(self._chunk_table(block.lines, section.heading_path))
                continue

            block_pieces = self._chunk_prose_block(block.lines, section.heading_path, block.kind)
            for index, piece in enumerate(block_pieces):
                if not heading_used and heading_prefix and index == 0:
                    piece.text = heading_prefix + piece.text
                    heading_used = True
                pieces.append(piece)

        if not blocks and section.heading_line:
            pieces.append(
                SplitPiece(
                    text=section.heading_line,
                    metadata={
                        "heading_path": section.heading_path,
                        "chunk_type": "section",
                    },
                )
            )
        return pieces

    def _parse_blocks(self, lines: list[str]) -> list[_ContentBlock]:
        blocks: list[_ContentBlock] = []
        index = 0
        while index < len(lines):
            line = lines[index]
            if FENCE_RE.match(line):
                fence_lines = [line]
                index += 1
                while index < len(lines) and not FENCE_RE.match(lines[index]):
                    fence_lines.append(lines[index])
                    index += 1
                if index < len(lines):
                    fence_lines.append(lines[index])
                    index += 1
                blocks.append(_ContentBlock(kind="code", lines=fence_lines))
                continue

            if self._is_table_line(line):
                table_lines = [line]
                index += 1
                while index < len(lines) and self._is_table_line(lines[index]):
                    table_lines.append(lines[index])
                    index += 1
                blocks.append(_ContentBlock(kind="table", lines=table_lines))
                continue

            prose_lines: list[str] = []
            while index < len(lines):
                current = lines[index]
                if FENCE_RE.match(current) or self._is_table_line(current):
                    break
                prose_lines.append(current)
                index += 1
            if prose_lines:
                blocks.append(_ContentBlock(kind="prose", lines=prose_lines))

        return blocks

    def _chunk_prose_block(
        self,
        lines: list[str],
        heading_path: str,
        kind: str,
    ) -> list[SplitPiece]:
        text = "\n".join(lines).strip()
        if not text:
            return []

        chunk_type = "code" if kind == "code" else "section"
        if len(text) <= self.chunk_size:
            return [
                SplitPiece(
                    text=text,
                    metadata={"heading_path": heading_path, "chunk_type": chunk_type},
                )
            ]

        if kind == "code":
            return self._split_by_characters(text, heading_path, chunk_type)

        paragraphs = re.split(r"\n\s*\n", text)
        return self._split_paragraphs(paragraphs, heading_path, chunk_type)

    def _chunk_table(self, table_lines: list[str], heading_path: str) -> list[SplitPiece]:
        cleaned_lines = [line for line in table_lines if line.strip()]
        if not cleaned_lines:
            return []

        header_line, body_start = self._resolve_table_header(cleaned_lines)
        data_rows = cleaned_lines[body_start:]
        header_summary = self._table_header_summary(header_line)

        def build_table_chunk(row_group: list[str], part: int) -> SplitPiece:
            body = "\n".join([header_line, *row_group]) if row_group else header_line
            if header_summary:
                content = f"{header_summary}\n{body}"
            else:
                content = body
            metadata: dict = {
                "heading_path": heading_path,
                "chunk_type": "table",
            }
            if part > 0:
                metadata["table_part"] = part
            return SplitPiece(text=content.strip(), metadata=metadata)

        full_table = "\n".join(cleaned_lines)
        if len(full_table) <= self.chunk_size:
            content = f"{header_summary}\n{full_table}".strip() if header_summary else full_table
            return [
                SplitPiece(
                    text=content,
                    metadata={
                        "heading_path": heading_path,
                        "chunk_type": "table",
                        "table_part": 1,
                    },
                )
            ]

        pieces: list[SplitPiece] = []
        part = 1
        for start in range(0, max(len(data_rows), 1), self.table_max_rows_per_chunk):
            group = data_rows[start : start + self.table_max_rows_per_chunk]
            if not group and part > 1:
                break
            candidate = build_table_chunk(group, part)
            if len(candidate.text) > self.chunk_size and len(group) > 1:
                for row in group:
                    pieces.append(build_table_chunk([row], part))
                    part += 1
                continue
            pieces.append(candidate)
            part += 1

        return pieces

    def _resolve_table_header(self, lines: list[str]) -> tuple[str, int]:
        if len(lines) >= 2 and self._is_table_separator(lines[1]):
            return lines[0], 2
        return lines[0], 1

    def _table_header_summary(self, header_line: str) -> str:
        cells = [cell.strip() for cell in header_line.strip().strip("|").split("|")]
        cells = [cell for cell in cells if cell]
        if not cells:
            return ""
        return f"【表头】{' | '.join(cells)}"

    def _split_paragraphs(
        self,
        paragraphs: list[str],
        heading_path: str,
        chunk_type: str,
    ) -> list[SplitPiece]:
        pieces: list[SplitPiece] = []
        buffer: list[str] = []
        buffer_len = 0

        def flush_buffer() -> None:
            nonlocal buffer, buffer_len
            if not buffer:
                return
            text = "\n\n".join(buffer).strip()
            if text:
                pieces.append(
                    SplitPiece(
                        text=text,
                        metadata={"heading_path": heading_path, "chunk_type": chunk_type},
                    )
                )
            buffer = []
            buffer_len = 0

        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            extra = len(paragraph) + (2 if buffer else 0)
            if buffer and buffer_len + extra > self.chunk_size:
                flush_buffer()
            if len(paragraph) > self.chunk_size:
                flush_buffer()
                pieces.extend(self._split_by_characters(paragraph, heading_path, chunk_type))
                continue
            buffer.append(paragraph)
            buffer_len += extra

        flush_buffer()
        return pieces

    def _split_by_characters(
        self,
        text: str,
        heading_path: str,
        chunk_type: str,
    ) -> list[SplitPiece]:
        if len(text) <= self.chunk_size:
            return [
                SplitPiece(
                    text=text,
                    metadata={"heading_path": heading_path, "chunk_type": chunk_type},
                )
            ]

        pieces: list[SplitPiece] = []
        start = 0
        step = max(self.chunk_size - self.chunk_overlap, 1)
        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end].strip()
            if chunk:
                pieces.append(
                    SplitPiece(
                        text=chunk,
                        metadata={"heading_path": heading_path, "chunk_type": chunk_type},
                    )
                )
            if end >= len(text):
                break
            start += step
        return pieces

    @staticmethod
    def _is_horizontal_rule(line: str) -> bool:
        return bool(HORIZONTAL_RULE_RE.match(line.strip()))

    @staticmethod
    def _is_table_line(line: str) -> bool:
        stripped = line.strip()
        if not stripped.startswith("|"):
            return False
        return stripped.count("|") >= 2

    @staticmethod
    def _is_table_separator(line: str) -> bool:
        stripped = line.strip().strip("|").replace(" ", "")
        if not stripped:
            return False
        return bool(re.fullmatch(r"[\|:_-]+", stripped))
