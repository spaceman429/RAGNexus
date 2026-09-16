from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class CreateKnowledgeBaseRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class UpdateKnowledgeBaseRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    settings: dict | None = None

    @model_validator(mode="after")
    def validate_at_least_one_field(self) -> "UpdateKnowledgeBaseRequest":
        if self.name is None and self.description is None and self.settings is None:
            raise ValueError("至少提供一个待更新字段")
        return self


class KnowledgeBaseData(BaseModel):
    kb_id: str
    name: str
    tenant_id: str
    created_at: datetime


class KnowledgeBaseDetailData(BaseModel):
    kb_id: str
    tenant_id: str
    name: str
    description: str | None
    settings: dict
    document_count: int
    created_at: datetime
    updated_at: datetime


class DocumentTreeItem(BaseModel):
    document_id: str
    title: str
    status: int
    chunk_count: int
    error_message: str | None = None
    created_at: datetime


class KnowledgeBaseTreeItem(BaseModel):
    kb_id: str
    name: str
    description: str | None
    created_at: datetime
    documents: list[DocumentTreeItem]


class TenantTreeItem(BaseModel):
    tenant_id: str
    knowledge_bases: list[KnowledgeBaseTreeItem]
