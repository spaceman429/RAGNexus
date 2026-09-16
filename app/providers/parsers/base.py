from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(slots=True)
class ParsedDocument:
    content: str
    source_type: str
    metadata: dict = field(default_factory=dict)


class DocumentParser(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def supports(self, filename: str, mime_type: str | None = None) -> bool:
        pass

    @abstractmethod
    async def parse(self, file_bytes: bytes, *, filename: str) -> ParsedDocument:
        pass
