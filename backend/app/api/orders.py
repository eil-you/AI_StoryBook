from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.order_service import OrderServiceError, create_order, estimate_order

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
