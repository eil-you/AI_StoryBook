"""
Pydantic DTOs for the Sweet Book API `/v1/books/{bookUid}/photos` endpoints.

Reference: https://api.sweetbook.com/docs/guides/images/
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------


class PhotoDto(BaseModel):
    """A photo that has been uploaded to a book."""

    file_name: str = Field(..., alias="fileName")
    original_name: str = Field(..., alias="originalName")
    size: int = Field(..., description="File size in bytes")
    mime_type: str = Field(..., alias="mimeType")
    uploaded_at: datetime = Field(..., alias="uploadedAt")
    hash: str = Field(..., description="MD5 hash of the file content")

    model_config = {"populate_by_name": True}


class UploadPhotoData(PhotoDto):
    """Extended photo info returned immediately after upload."""

    is_duplicate: bool = Field(..., alias="isDuplicate")


class PhotoListData(BaseModel):
    photos: list[PhotoDto]
    total_count: int = Field(..., alias="totalCount")

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Response wrappers
# ---------------------------------------------------------------------------


class UploadPhotoResponse(BaseModel):
    """Wrapper returned by POST /v1/books/{bookUid}/photos."""

    success: bool
    message: str | None = None
    data: UploadPhotoData


class PhotoListResponse(BaseModel):
    """Wrapper returned by GET /v1/books/{bookUid}/photos."""

    success: bool
    message: str | None = None
    data: PhotoListData
