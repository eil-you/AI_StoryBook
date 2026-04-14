"""
Pydantic DTOs for the Sweet Book API `/v1/books/{bookUid}/cover` endpoint.

Reference: https://api.sweetbook.com/docs/guides/cover/
"""

from __future__ import annotations

from pydantic import BaseModel


class CoverData(BaseModel):
    result: str  # "inserted"


class CoverResponse(BaseModel):
    """Wrapper returned by POST /v1/books/{bookUid}/cover."""

    success: bool
    message: str
    data: CoverData
