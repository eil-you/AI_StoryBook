import enum


class ErrorCode(str, enum.Enum):
    """
    Canonical error codes used across the application.

    Providers and services raise ProviderError with one of these codes so
    that routers can map them to consistent HTTP responses without knowing
    which concrete provider is in use.
    """

    ERR001 = "ERR001"  # Request payload failed validation before reaching the provider
    ERR002 = "ERR002"  # Provider returned a non-2xx HTTP response (gateway error)
    ERR003 = "ERR003"  # Connection or read timeout while calling the provider
    ERR004 = "ERR004"  # Generic network / transport error


class ProviderError(Exception):
    """
    Raised by BookProvider implementations when an external call fails.

    Attributes
    ----------
    code:
        One of the ErrorCode values — lets routers handle errors uniformly.
    message:
        Human-readable description (safe to surface in logs, not user responses).
    status_code:
        The upstream HTTP status code, if available (None for network-level errors).
    """

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code

    def __repr__(self) -> str:
        return (
            f"ProviderError(code={self.code!r}, "
            f"status_code={self.status_code!r}, "
            f"message={self.message!r})"
        )
