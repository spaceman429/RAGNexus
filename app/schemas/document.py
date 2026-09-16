from datetime import datetime

from pydantic import BaseModel, Field


class UploadDocumentRequest(BaseModel):
    kb_id: str = Field(min_length=1, max_length=36)
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)


class UploadDocumentData(BaseModel):
    document_id: str
    kb_id: str
    status: int
    chunk_count: int


class DocumentDetailData(BaseModel):
    document_id: str
    kb_id: str
    title: str
    status: int
    error_message: str | None
    chunk_count: int
    source_type: str | None = None
    source_filename: str | None = None
    created_at: datetime
    updated_at: datetime


class ReindexDocumentData(BaseModel):
    document_id: str
    kb_id: str
    status: int
    chunk_count: int

