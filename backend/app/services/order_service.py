"""
Order service — wraps SweetBookProvider order calls and persists results to DB.
"""

import logging

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ProviderError
from app.models.book import Book, BookStatus
from app.models.order import Order, OrderStatus
from app.providers.sweetbook import SweetBookProvider
from app.schemas.order import EstimateDto, OrderDto, OrderListData


@dataclass
class LocalOrderItem:
    """로컬 DB에서 조합한 주문 요약 데이터."""
    order_uid: str | None
    status: int            # SweetBook 상태 코드 (20 = PAID 기본값)
    paid_amount: float
    book_title: str | None
    created_at: datetime

logger = logging.getLogger(__name__)


class OrderServiceError(Exception):
    """Raised when any step of the order pipeline fails."""


async def estimate_order(
    *,
    book_id: int,
    quantity: int,
    db: AsyncSession,
) -> EstimateDto:
    """Preview the cost of ordering a book without placing the order."""
    settings = get_settings()

    book = await _get_finalized_book(book_id, db)

    provider = SweetBookProvider(api_key=settings.SWEETBOOK_API_KEY)
    try:
        return await provider.estimate_order(
            book_uid=book.sweetbook_book_uid,
            quantity=quantity,
        )
    except ProviderError as exc:
        raise OrderServiceError(f"Estimate failed: {exc.message}") from exc
    finally:
        await provider.close()


async def create_order(
    *,
    book_id: int,
    quantity: int,
    recipient_name: str,
    recipient_phone: str,
    postal_code: str,
    address1: str,
    address2: str | None = None,
    memo: str | None = None,
    db: AsyncSession,
) -> OrderDto:
    """Place an order for a FINALIZED book and persist the result to DB.

    Credits are deducted immediately upon success.

    Raises:
        OrderServiceError: If the book is not found, not finalized, or the API call fails.
    """
    settings = get_settings()

    book = await _get_finalized_book(book_id, db)

    provider = SweetBookProvider(api_key=settings.SWEETBOOK_API_KEY)
    try:
        logger.info(
            "Creating order for book_id=%d (sweetbook_uid=%r, qty=%d)",
            book_id, book.sweetbook_book_uid, quantity,
        )
        data = await provider.create_order(
            book_uid=book.sweetbook_book_uid,
            quantity=quantity,
            recipient_name=recipient_name,
            recipient_phone=recipient_phone,
            postal_code=postal_code,
            address1=address1,
            address2=address2,
            memo=memo,
            external_ref=str(book_id),
        )
    except ProviderError as exc:
        raise OrderServiceError(f"SweetBook order API error: {exc.message}") from exc
    finally:
        await provider.close()

    order = Order(
        book_id=book_id,
        user_id=book.user_id,
        sweetbook_order_uid=data.orderUid,
        status=OrderStatus.paid,
        total_price=float(data.paidCreditAmount),
    )
    db.add(order)
    await db.commit()
    logger.info(
        "Order created: orderUid=%r, book_id=%d, amount=%s",
        data.orderUid, book_id, data.paidCreditAmount,
    )
    return data


_LOCAL_STATUS_MAP: dict[OrderStatus, int] = {
    OrderStatus.pending: 20,   # pending → PAID(20) as default
    OrderStatus.paid: 20,
    OrderStatus.failed: -1,
    OrderStatus.cancelled: -1,
}


async def list_user_orders(
    *,
    user_id: int,
    db: AsyncSession,
    limit: int = 50,
    offset: int = 0,
) -> list[LocalOrderItem]:
    """로컬 DB에서 현재 사용자의 주문 목록을 반환합니다.

    SweetBook API를 호출하지 않아 빠르며, 반드시 현재 사용자의 주문만 반환합니다.
    상태 코드가 없거나 기본값인 경우 PAID(20)으로 처리합니다.
    """
    rows = await db.execute(
        select(Order, Book.title)
        .join(Book, Order.book_id == Book.id)
        .where(Order.user_id == user_id)
        .order_by(Order.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = []
    for order, book_title in rows:
        # 로컬 OrderStatus → SweetBook 숫자 코드 변환
        # 값이 없으면 PAID(20) 기본값
        sweetbook_status = _LOCAL_STATUS_MAP.get(order.status, 20)
        result.append(
            LocalOrderItem(
                order_uid=order.sweetbook_order_uid,
                status=sweetbook_status,
                paid_amount=float(order.total_price),
                book_title=book_title,
                created_at=order.created_at,
            )
        )
    return result


async def get_order(*, order_uid: str) -> OrderDto:
    """Fetch a single order by its SweetBook UID."""
    settings = get_settings()
    provider = SweetBookProvider(api_key=settings.SWEETBOOK_API_KEY)
    try:
        return await provider.get_order(order_uid)
    except ProviderError as exc:
        raise OrderServiceError(f"Failed to get order '{order_uid}': {exc.message}") from exc
    finally:
        await provider.close()


async def cancel_order(*, order_uid: str, cancel_reason: str, db: AsyncSession) -> OrderDto:
    """Cancel a PAID or PDF_READY order and update the local DB status to cancelled."""
    settings = get_settings()
    provider = SweetBookProvider(api_key=settings.SWEETBOOK_API_KEY)
    try:
        result = await provider.cancel_order(order_uid, cancel_reason=cancel_reason)
    except ProviderError as exc:
        raise OrderServiceError(f"Failed to cancel order '{order_uid}': {exc.message}") from exc
    finally:
        await provider.close()

    # 로컬 DB 상태를 cancelled로 업데이트
    local_order = await db.execute(
        select(Order).where(Order.sweetbook_order_uid == order_uid)
    )
    order = local_order.scalar_one_or_none()
    if order:
        order.status = OrderStatus.cancelled
        await db.commit()
        logger.info("Order %s marked as cancelled in local DB.", order_uid)

    return result


async def update_shipping(
    *,
    order_uid: str,
    recipient_name: str,
    recipient_phone: str,
    postal_code: str,
    address1: str,
    address2: str | None = None,
    memo: str | None = None,
) -> OrderDto:
    """Update the shipping address of an order."""
    settings = get_settings()
    provider = SweetBookProvider(api_key=settings.SWEETBOOK_API_KEY)
    try:
        return await provider.update_shipping(
            order_uid=order_uid,
            recipient_name=recipient_name,
            recipient_phone=recipient_phone,
            postal_code=postal_code,
            address1=address1,
            address2=address2,
            memo=memo,
        )
    except ProviderError as exc:
        raise OrderServiceError(
            f"Failed to update shipping for order '{order_uid}': {exc.message}"
        ) from exc
    finally:
        await provider.close()


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------


async def _get_finalized_book(book_id: int, db: AsyncSession) -> Book:
    result = await db.execute(select(Book).where(Book.id == book_id))
    book: Book | None = result.scalar_one_or_none()
    if not book:
        raise OrderServiceError(f"Book not found: book_id={book_id}.")
    if not book.sweetbook_book_uid:
        raise OrderServiceError(
            f"book_id={book_id} has no sweetbook_book_uid. Generate the story first."
        )
    if book.status != BookStatus.finalized:
        raise OrderServiceError(
            f"book_id={book_id} is not finalized (status={book.status}). "
            "Finalize the book before ordering."
        )
    return book
