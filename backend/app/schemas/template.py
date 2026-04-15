"""
Pydantic DTOs for the Sweet Book API `/v1/templates` endpoints.

Reference: https://api.sweetbook.com/docs/guides/templates/
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any
from typing import Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TemplateScope(str, enum.Enum):
    public = "public"
    private = "private"
    all = "all"


class TemplateKind(str, enum.Enum):
    cover = "cover"
    content = "content"
    divider = "divider"
    publish = "publish"


class BindingKind(str, enum.Enum):
    text = "text"
    file = "file"
    row_gallery = "rowGallery"


# ---------------------------------------------------------------------------
# Nested models — list
# ---------------------------------------------------------------------------


class ThumbnailsDto(BaseModel):
    layout: str | None = Field(None, description="URL of the layout thumbnail image")


class TemplateDto(BaseModel):
    """Represents a single template item returned in the list response."""

    template_uid: str = Field(..., alias="templateUid")
    account_uid: str = Field(..., alias="accountUid")
    template_name: str = Field(..., alias="templateName")
    description: str | None = Field(None, alias="description")
    template_kind: TemplateKind = Field(..., alias="templateKind")
    category: str | None = Field(None, alias="category")
    theme: str = Field(..., alias="theme")
    book_spec_uid: str = Field(..., alias="bookSpecUid")
    book_spec_name: str = Field(..., alias="bookSpecName")
    is_public: bool = Field(..., alias="isPublic")
    status: str = Field(..., alias="status")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")
    thumbnails: ThumbnailsDto = Field(..., alias="thumbnails")

    model_config = {"populate_by_name": True}


class PaginationDto(BaseModel):
    total: int
    limit: int
    offset: int
    has_next: bool = Field(..., alias="hasNext")

    model_config = {"populate_by_name": True}


class TemplateListData(BaseModel):
    templates: list[TemplateDto]
    pagination: PaginationDto


# ---------------------------------------------------------------------------
# Nested models — detail
# ---------------------------------------------------------------------------


class ParameterDefinition(BaseModel):
    binding: BindingKind
    type: str
    required: bool
    default: Any = None
    description: str
    item_type: str | None = Field(None, alias="itemType")
    min_items: int | None = Field(None, alias="minItems")

    model_config = {"populate_by_name": True}


class ParametersDto(BaseModel):
    definitions: dict[str, ParameterDefinition]


class TemplateDetailDto(BaseModel):
    """Full template detail returned by GET /v1/templates/{templateUid}."""

    parameters: ParametersDto | None = None
    layout: Optional[dict] = None
    layout_rules: dict[str, Any] | None = Field(None, alias="layoutRules")
    base_layer: dict[str, Any] | None = Field(None, alias="baseLayer")
    thumbnails: ThumbnailsDto | None = None

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Response wrappers
# ---------------------------------------------------------------------------


class TemplateListResponse(BaseModel):
    """Wrapper returned by GET /v1/templates."""

    success: bool
    message: str
    data: TemplateListData


class TemplateDetailResponse(BaseModel):
    """Wrapper returned by GET /v1/templates/{templateUid}."""

    success: bool
    message: str
    data: TemplateDetailDto
