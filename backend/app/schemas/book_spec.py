"""
Pydantic DTOs for the Sweet Book API `/v1/book-specs` endpoints.

Reference: https://api.sweetbook.com/docs/guides/book-specs/
"""

from __future__ import annotations

import enum
from decimal import Decimal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class CoverType(str, enum.Enum):
    hardcover = "Hardcover"
    softcover = "Softcover"


# ---------------------------------------------------------------------------
# Nested models
# ---------------------------------------------------------------------------


class CoverPaperDto(BaseModel):
    paper: str = Field(..., description="Cover paper stock name, e.g. 'Snow 150g'")


class InnerPaperDto(BaseModel):
    paper: str = Field(..., description="Inner paper stock name, e.g. 'Arte 130g'")


class PaperDto(BaseModel):
    cover: CoverPaperDto
    inner: InnerPaperDto
    lamination: str = Field(..., description="Lamination finish, e.g. 'Silk'")


# ---------------------------------------------------------------------------
# Primary DTO
# ---------------------------------------------------------------------------


class BookSpecDto(BaseModel):
    """
    Represents a single book specification returned by GET /v1/book-specs
    and GET /v1/book-specs/{bookSpecUid}.
    """

    book_spec_uid: str = Field(
        ...,
        alias="bookSpecUid",
        description="Unique spec identifier, e.g. 'PHOTOBOOK_A4_SC'",
    )
    name: str = Field(..., description="Human-readable spec name")

    # --- Dimensions (mm) ---
    inner_trim_width_mm: int = Field(
        ..., alias="innerTrimWidthMm", description="Inner trim width in mm"
    )
    inner_trim_height_mm: int = Field(
        ..., alias="innerTrimHeightMm", description="Inner trim height in mm"
    )

    # --- Page constraints ---
    page_min: int = Field(..., alias="pageMin", description="Minimum page count")
    page_max: int = Field(..., alias="pageMax", description="Maximum page count")
    page_default: int = Field(..., alias="pageDefault", description="Default page count")
    page_increment: int = Field(
        ..., alias="pageIncrement", description="Page count must increase by this unit"
    )

    # --- Binding ---
    cover_type: CoverType = Field(..., alias="coverType")
    binding_type: str = Field(
        ..., alias="bindingType", description="Binding method, e.g. 'PUR'"
    )
    binding_edge: str = Field(
        ..., alias="bindingEdge", description="Binding direction, e.g. 'left'"
    )

    # --- Pricing ---
    price_currency: str = Field(
        "KRW", alias="priceCurrency", description="ISO 4217 currency code"
    )
    sandbox_price_base: Decimal | None = Field(
        None, alias="sandboxPriceBase", description="Sandbox flat base price"
    )
    sandbox_price_per_increment: Decimal | None = Field(
        None,
        alias="sandboxPricePerIncrement",
        description="Sandbox price added per page increment",
    )

    # --- Paper ---
    paper: PaperDto

    model_config = {"populate_by_name": True}

    # ------------------------------------------------------------------
    # Derived helpers
    # ------------------------------------------------------------------

    def is_valid_page_count(self, pages: int) -> bool:
        """Return True if *pages* satisfies min/max and increment constraints."""
        if pages < self.page_min or pages > self.page_max:
            return False
        return (pages - self.page_min) % self.page_increment == 0

    def calculate_sandbox_price(self, pages: int) -> Decimal | None:
        """
        Return the sandbox price for *pages* pages, or None if pricing
        is not configured for this spec.
        """
        if self.sandbox_price_base is None or self.sandbox_price_per_increment is None:
            return None
        increments = (pages - self.page_default) // self.page_increment
        return self.sandbox_price_base + self.sandbox_price_per_increment * increments


# ---------------------------------------------------------------------------
# Response wrapper
# ---------------------------------------------------------------------------


class BookSpecListResponse(BaseModel):
    """Wrapper returned by GET /v1/book-specs."""

    success: bool
    message: str
    data: list[BookSpecDto]


class BookSpecResponse(BaseModel):
    """Wrapper returned by GET /v1/book-specs/{bookSpecUid}."""

    success: bool
    message: str
    data: BookSpecDto
