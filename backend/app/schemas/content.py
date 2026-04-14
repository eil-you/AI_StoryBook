"""
Pydantic DTOs for the Sweet Book API `/v1/books/{bookUid}/contents` endpoint.

Reference: https://api.sweetbook.com/docs/guides/contents/
"""

from __future__ import annotations

import enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class BreakBefore(str, enum.Enum):
    page = "page"      # Start on a new page (default for divider/publish templates)
    column = "column"  # Start in a new column
    none = "none"      # Append directly to previous content (default for content templates)


class PageSide(str, enum.Enum):
    left = "left"
    right = "right"


class ContentResult(str, enum.Enum):
    inserted = "inserted"  # New page(s) added → 201
    updated = "updated"    # Existing page on same slot updated → 200


# ---------------------------------------------------------------------------
# Response DTOs
# ---------------------------------------------------------------------------


class ContentData(BaseModel):
    result: ContentResult
    break_before: BreakBefore = Field(..., alias="breakBefore")
    page_num: int = Field(..., alias="pageNum")
    page_side: PageSide = Field(..., alias="pageSide")
    page_count: int = Field(..., alias="pageCount")

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Response wrapper
# ---------------------------------------------------------------------------


class ContentResponse(BaseModel):
    """Wrapper returned by POST /v1/books/{bookUid}/contents."""

    success: bool
    message: str
    data: ContentData
