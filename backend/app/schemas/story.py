from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import BookStatus


class StoryRequest(BaseModel):
    prompt_text: str = Field(
        ...,
        min_length=10,
        max_length=1000,
        description="The theme or prompt describing the story to generate",
    )
    user_id: int = Field(..., description="ID of the user creating the book")


class PageOut(BaseModel):
    page_number: int
    text_content: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BookCreatedResponse(BaseModel):
    book_id: int
    title: str
    status: BookStatus
    created_at: datetime
    updated_at: datetime
    pages: list[PageOut]

    model_config = {"from_attributes": True}


class StorySummary(BaseModel):
    """Lightweight projection returned by the list-all-stories endpoint."""

    id: int
    title: str
    created_at: datetime

    model_config = {"from_attributes": True}


class StoryDetail(BaseModel):
    """Full story detail including all pages, returned by the single-story endpoint."""

    id: int
    title: str
    status: BookStatus
    content_summary: str | None
    created_at: datetime
    updated_at: datetime
    pages: list[PageOut]

    model_config = {"from_attributes": True}
