from pydantic import BaseModel, Field


class FeedbackRequest(BaseModel):
    trace_id: str = Field(min_length=1, max_length=64)
    log_id: str | None = Field(default=None, max_length=36)
    score: int
    comment: str | None = None


class FeedbackData(BaseModel):
    feedback_id: str
    trace_id: str
    log_id: str | None = None
    score: int
