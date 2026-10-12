from datetime import datetime

from pydantic import BaseModel, Field


class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)


class ReviewOut(BaseModel):
    id: str
    rating: int
    comment: str | None
    reviewer_name: str
    created_at: datetime


class ReviewListOut(BaseModel):
    items: list[ReviewOut]
    page: int
    page_size: int
    total: int