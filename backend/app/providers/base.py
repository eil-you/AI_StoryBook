from abc import ABC, abstractmethod
from decimal import Decimal


class BookProvider(ABC):
    """
    Abstract interface for book-printing providers.

    Concrete implementations (SweetBookProvider, etc.) must implement all
    abstract methods.  Callers depend only on this interface so that providers
    can be swapped without touching business logic.
    """

    @abstractmethod
    async def get_pricing(self, page_count: int) -> Decimal:
        """Return the print price for a book with *page_count* pages."""
