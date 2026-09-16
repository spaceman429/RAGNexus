from dataclasses import dataclass


@dataclass(slots=True)
class TextSplitter:
    chunk_size: int
    chunk_overlap: int

    def split(self, text: str) -> list[str]:
        normalized = text.strip()
        if not normalized:
            return []

        if len(normalized) <= self.chunk_size:
            return [normalized]

        chunks: list[str] = []
        start = 0
        step = max(self.chunk_size - self.chunk_overlap, 1)

        while start < len(normalized):
            end = start + self.chunk_size
            chunks.append(normalized[start:end].strip())
            if end >= len(normalized):
                break
            start += step

        return [chunk for chunk in chunks if chunk]

