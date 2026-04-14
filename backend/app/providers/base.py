from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class PageData:
    page_number: int
    text_content: str | None = None
    image_url: str | None = None


@dataclass
class BookOrderRequest:
    """Provider-agnostic representation of a book print order."""
    book_id: int
    title: str
    pages: list[PageData] = field(default_factory=list)


@dataclass
class BookOrderResponse:
    """Result returned after successfully submitting a print order."""
    provider_order_id: str   # the ID assigned by the external provider
    status: str               # e.g. "pending", "processing"
    total_price: Decimal


@dataclass
class OrderStatusResponse:
    """Current status of a previously submitted print order."""
    provider_order_id: str
    status: str               # mirrors the provider's own status vocabulary


class BookProvider(ABC):
    """
    Abstract interface for book-printing providers.

    Concrete implementations (SweetBookProvider, etc.) must implement all
    three methods.  Callers depend only on this interface so that providers
    can be swapped without touching business logic.
    """

    @abstractmethod
    async def create_order(self, request: BookOrderRequest) -> BookOrderResponse:
        """Submit a book for printing and return the provider's order details."""

    @abstractmethod
    async def get_order_status(self, provider_order_id: str) -> OrderStatusResponse:
        """Fetch the current status of an existing print order."""

    @abstractmethod
    async def get_pricing(self, page_count: int) -> Decimal:
        """Return the print price for a book with *page_count* pages."""
