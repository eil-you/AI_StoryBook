"""
Order service — wraps SweetBookProvider order calls and persists results to DB.
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ProviderError
from app.models.book import Book, BookStatus
from app.models.order import Order, OrderStatus
from app.providers.sweetbook import SweetBookProvider
from app.schemas.order import EstimateDto, OrderDto, OrderListData

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


async def list_orders(
    *,
    status: int | None = None,
    limit: int = 20,
    offset: int = 0,
) -> OrderListData:
    """Fetch a paginated list of orders from SweetBook."""
    settings = get_settings()
    provider = SweetBookProvider(api_key=settings.SWEETBOOK_API_KEY)
    try:
        return await provider.list_orders(status=status, limit=limit, offset=offset)
    except ProviderError as exc:
        raise OrderServiceError(f"Failed to list orders: {exc.message}") from exc
    finally:
        await provider.close()


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


async def cancel_order(*, order_uid: str, cancel_reason: str) -> OrderDto:
    """Cancel a PAID or PDF_READY order."""
    settings = get_settings()
    provider = SweetBookProvider(api_key=settings.SWEETBOOK_API_KEY)
    try:
        return await provider.cancel_order(order_uid, cancel_reason=cancel_reason)
    except ProviderError as exc:
        raise OrderServiceError(f"Failed to cancel order '{order_uid}': {exc.message}") from exc
    finally:
        await provider.close()


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
