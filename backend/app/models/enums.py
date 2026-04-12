import enum


class BookStatus(str, enum.Enum):
    draft = "draft"
    processing = "processing"
    completed = "completed"


class OrderStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    failed = "failed"


class ErrorCode(enum.Enum):
    """Application-level error codes.

    Each member holds a short machine-readable ``code`` (e.g. ``ERR001``) and a
    default human-readable ``message``.  Use :meth:`to_detail` to build the
    ``detail`` dict passed to :class:`fastapi.HTTPException`.
    """

    STORY_NOT_FOUND = ("ERR001", "Story not found.")
    AI_SERVICE_UNAVAILABLE = ("ERR002", "AI story generation failed. Please try again.")

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message

    def to_detail(self, message: str | None = None) -> dict[str, str]:
        """Return a detail dict suitable for ``HTTPException(detail=...)``.

        Args:
            message: Override the default message when a more specific
                description is available (e.g. from a caught exception).
        """
        return {"code": self.code, "message": message or self.message}
