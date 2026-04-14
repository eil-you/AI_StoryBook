"""
Pydantic DTOs for the Sweet Book API `/v1/orders` endpoints.

Reference: https://api.sweetbook.com/docs/guides/orders/
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request payloads (outbound)
# ---------------------------------------------------------------------------


class OrderItemPayload(BaseModel):
    bookUid: str
    quantity: int = Field(..., ge=1, le=100)


class ShippingPayload(BaseModel):
    recipientName: str = Field(..., max_length=100)
    recipientPhone: str = Field(..., max_length=20)
    postalCode: str = Field(..., max_length=10)
    address1: str = Field(..., max_length=200)
    address2: str | None = Field(None, max_length=200)
    memo: str | None = Field(None, max_length=200)


class CreateOrderPayload(BaseModel):
    items: list[OrderItemPayload]
    shipping: ShippingPayload
    externalRef: str | None = Field(None, max_length=100)


# ---------------------------------------------------------------------------
# Response DTOs (inbound)
# ---------------------------------------------------------------------------


class OrderItemDto(BaseModel):
    bookUid: str
    quantity: int


class ShippingDto(BaseModel):
    recipientName: str
    recipientPhone: str
    postalCode: str
    address1: str
    address2: str | None = None
    memo: str | None = None


class OrderDto(BaseModel):
    orderUid: str
    status: int                       # 20 = PAID
    paidCreditAmount: Decimal
    shippingAmount: Decimal
    packagingAmount: Decimal
    items: list[OrderItemDto]
    shipping: ShippingDto
    externalRef: str | None = None


class CreateOrderResponse(BaseModel):
    """Wrapper returned by POST /v1/orders."""

    success: bool
    message: str
    data: OrderDto


class OrderListData(BaseModel):
    orders: list[OrderDto]


class OrderListResponse(BaseModel):
    """Wrapper returned by GET /v1/orders."""

    success: bool
    message: str
    data: OrderListData


class OrderDetailResponse(BaseModel):
    """Wrapper returned by GET /v1/orders/{orderUid}."""

    success: bool
    message: str
    data: OrderDto


# ---------------------------------------------------------------------------
# Estimate
# ---------------------------------------------------------------------------


class EstimateItemPayload(BaseModel):
    bookUid: str
    quantity: int = Field(..., ge=1, le=100)


class CreateEstimatePayload(BaseModel):
    items: list[EstimateItemPayload]


class EstimateDto(BaseModel):
    totalAmount: Decimal
    shippingAmount: Decimal
    packagingAmount: Decimal


class EstimateResponse(BaseModel):
    """Wrapper returned by POST /v1/orders/estimate."""

    success: bool
    message: str
    data: EstimateDto
