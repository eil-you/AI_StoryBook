from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.order_service import (
    OrderServiceError,
    cancel_order,
    create_order,
    estimate_order,
    get_order,
    list_orders,
    update_shipping,
)

router = APIRouter(prefix="/api/v1/orders", tags=["Orders"])


# ---------------------------------------------------------------------------
# Estimate
# ---------------------------------------------------------------------------


class EstimateRequest(BaseModel):
    book_id: int = Field(..., description="로컬 Book ID")
    quantity: int = Field(1, ge=1, le=100, description="주문 수량")


class EstimateResponse(BaseModel):
    success: bool
    total_amount: Decimal
    shipping_amount: Decimal
    packaging_amount: Decimal


@router.post("/estimate", response_model=EstimateResponse)
async def estimate(
    body: EstimateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EstimateResponse:
    """주문 전 예상 금액을 조회합니다."""
    try:
        data = await estimate_order(
            book_id=body.book_id,
            quantity=body.quantity,
            db=db,
        )
    except OrderServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return EstimateResponse(
        success=True,
        total_amount=data.totalAmount,
        shipping_amount=data.shippingAmount,
        packaging_amount=data.packagingAmount,
    )


# ---------------------------------------------------------------------------
# Create order
# ---------------------------------------------------------------------------


class CreateOrderRequest(BaseModel):
    book_id: int = Field(..., description="로컬 Book ID (FINALIZED 상태여야 함)")
    quantity: int = Field(1, ge=1, le=100, description="주문 수량")
    recipient_name: str = Field(..., max_length=100, description="수령인 이름")
    recipient_phone: str = Field(..., max_length=20, description="수령인 전화번호")
    postal_code: str = Field(..., max_length=10, description="우편번호")
    address1: str = Field(..., max_length=200, description="기본 주소")
    address2: str | None = Field(None, max_length=200, description="상세 주소")
    memo: str | None = Field(None, max_length=200, description="배송 메모")


class CreateOrderResponse(BaseModel):
    success: bool
    message: str
    order_uid: str
    status: int
    paid_amount: Decimal
    shipping_amount: Decimal


@router.post("", response_model=CreateOrderResponse, status_code=201)
async def place_order(
    body: CreateOrderRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CreateOrderResponse:
    """FINALIZED 책으로 주문을 생성합니다. 크레딧이 즉시 차감됩니다."""
    try:
        data = await create_order(
            book_id=body.book_id,
            quantity=body.quantity,
            recipient_name=body.recipient_name,
            recipient_phone=body.recipient_phone,
            postal_code=body.postal_code,
            address1=body.address1,
            address2=body.address2,
            memo=body.memo,
            db=db,
        )
    except OrderServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return CreateOrderResponse(
        success=True,
        message="주문이 완료되었습니다.",
        order_uid=data.orderUid,
        status=data.status,
        paid_amount=data.paidCreditAmount,
        shipping_amount=data.shippingAmount,
    )


# ---------------------------------------------------------------------------
# List orders
# ---------------------------------------------------------------------------


class OrderSummary(BaseModel):
    order_uid: str
    status: int
    paid_amount: Decimal
    shipping_amount: Decimal


class ListOrdersResponse(BaseModel):
    success: bool
    orders: list[OrderSummary]


@router.get("", response_model=ListOrdersResponse)
async def get_orders(
    status: int | None = None,
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
) -> ListOrdersResponse:
    """SweetBook 주문 목록을 조회합니다."""
    try:
        data = await list_orders(status=status, limit=limit, offset=offset)
    except OrderServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return ListOrdersResponse(
        success=True,
        orders=[
            OrderSummary(
                order_uid=o.orderUid,
                status=o.status,
                paid_amount=o.paidCreditAmount,
                shipping_amount=o.shippingAmount,
            )
            for o in data.orders
        ],
    )


# ---------------------------------------------------------------------------
# Get order detail
# ---------------------------------------------------------------------------


class OrderDetailResponse(BaseModel):
    success: bool
    order_uid: str
    status: int
    paid_amount: Decimal
    shipping_amount: Decimal
    external_ref: str | None


@router.get("/{order_uid}", response_model=OrderDetailResponse)
async def get_order_detail(
    order_uid: str,
    current_user: User = Depends(get_current_user),
) -> OrderDetailResponse:
    """특정 주문의 상세 정보를 조회합니다."""
    try:
        data = await get_order(order_uid=order_uid)
    except OrderServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return OrderDetailResponse(
        success=True,
        order_uid=data.orderUid,
        status=data.status,
        paid_amount=data.paidCreditAmount,
        shipping_amount=data.shippingAmount,
        external_ref=data.externalRef,
    )


# ---------------------------------------------------------------------------
# Cancel order
# ---------------------------------------------------------------------------


class CancelOrderResponse(BaseModel):
    success: bool
    message: str
    order_uid: str
    status: int
    cancel_reason: str | None


class CancelOrderRequest(BaseModel):
    cancel_reason: str = Field(..., description="취소 사유")


@router.post("/{order_uid}/cancel", response_model=CancelOrderResponse)
async def cancel(
    order_uid: str,
    body: CancelOrderRequest,
    current_user: User = Depends(get_current_user),
) -> CancelOrderResponse:
    """PAID 또는 PDF_READY 상태의 주문을 취소합니다."""
    try:
        data = await cancel_order(order_uid=order_uid, cancel_reason=body.cancel_reason)
    except OrderServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return CancelOrderResponse(
        success=True,
        message="주문이 취소되었습니다.",
        order_uid=data.orderUid,
        status=data.status,
        cancel_reason=data.cancelReason,
    )


# ---------------------------------------------------------------------------
# Update shipping
# ---------------------------------------------------------------------------


class UpdateShippingRequest(BaseModel):
    recipient_name: str = Field(..., max_length=100)
    recipient_phone: str = Field(..., max_length=20)
    postal_code: str = Field(..., max_length=10)
    address1: str = Field(..., max_length=200)
    address2: str | None = Field(None, max_length=200)
    memo: str | None = Field(None, max_length=200)


class UpdateShippingResponse(BaseModel):
    success: bool
    message: str
    order_uid: str


@router.patch("/{order_uid}/shipping", response_model=UpdateShippingResponse)
async def update_order_shipping(
    order_uid: str,
    body: UpdateShippingRequest,
    current_user: User = Depends(get_current_user),
) -> UpdateShippingResponse:
    """주문의 배송지를 수정합니다."""
    try:
        data = await update_shipping(
            order_uid=order_uid,
            recipient_name=body.recipient_name,
            recipient_phone=body.recipient_phone,
            postal_code=body.postal_code,
            address1=body.address1,
            address2=body.address2,
            memo=body.memo,
        )
    except OrderServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return UpdateShippingResponse(
        success=True,
        message="배송지가 수정되었습니다.",
        order_uid=data.orderUid,
    )
