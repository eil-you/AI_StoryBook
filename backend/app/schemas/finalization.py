"""
Pydantic DTOs for the Sweet Book API `/v1/books/{bookUid}/finalization` endpoint.

Reference: https://api.sweetbook.com/docs/guides/finalization/
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class FinalizationData(BaseModel):
    result: str           # "created" (201) or "updated" (200 idempotent)
    pageCount: int
    finalizedAt: datetime


class FinalizationResponse(BaseModel):
    """Wrapper returned by POST /v1/books/{bookUid}/finalization."""

    success: bool
    data: FinalizationData
    message: str | None = None
