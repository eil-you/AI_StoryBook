"""
Pydantic DTOs for the Sweet Book API `/v1/books` endpoints.

Reference: https://api.sweetbook.com/docs/guides/books/
"""

from __future__ import annotations

import enum
from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class BookStatus(str, enum.Enum):
    draft = "draft"
    finalized = "finalized"


# ---------------------------------------------------------------------------
# Request body
# ---------------------------------------------------------------------------


class CreateBookBody(BaseModel):
    """Request body for POST /api/v1/books."""

    title: str = Field(..., min_length=1, max_length=255, description="Book title")
    book_spec_uid: str = Field(..., description="Product spec UID from book-specs")
    spec_profile_uid: str | None = Field(None, description="Spec profile UID for validation")
    external_ref: str | None = Field(
        None, max_length=100, description="Partner system identifier (returned in order queries)"
    )


# ---------------------------------------------------------------------------
# Response DTOs
# ---------------------------------------------------------------------------


class CreateBookData(BaseModel):
    book_uid: str = Field(..., alias="bookUid")

    model_config = {"populate_by_name": True}


class BookDto(BaseModel):
    """Represents a single book item returned by GET /v1/books."""

    book_uid: str = Field(..., alias="bookUid")
    title: str
    book_spec_uid: str = Field(..., alias="bookSpecUid")
    spec_profile_uid: str | None = Field(None, alias="specProfileUid")
    external_ref: str | None = Field(None, alias="externalRef")
    status: BookStatus
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    model_config = {"populate_by_name": True}


class BookPaginationDto(BaseModel):
    total: int
    limit: int
    offset: int
    has_next: bool = Field(..., alias="hasNext")

    model_config = {"populate_by_name": True}


class BookListData(BaseModel):
    books: list[BookDto]
    pagination: BookPaginationDto


# ---------------------------------------------------------------------------
# Response wrappers
# ---------------------------------------------------------------------------


class CreateBookResponse(BaseModel):
    """Wrapper returned by POST /v1/books."""

    success: bool
    message: str
    data: CreateBookData


class BookListResponse(BaseModel):
    """Wrapper returned by GET /v1/books."""

    success: bool
    message: str
    data: BookListData
