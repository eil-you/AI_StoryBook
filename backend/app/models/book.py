import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.page import Page
    from app.models.order import Order


class BookStatus(str, enum.Enum):
    draft = "draft"
    processing = "processing"
    completed = "completed"


class Book(Base):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[BookStatus] = mapped_column(
        Enum(BookStatus), default=BookStatus.draft, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="books")
    pages: Mapped[list["Page"]] = relationship(
        "Page", back_populates="book", cascade="all, delete-orphan"
    )
    order: Mapped["Order | None"] = relationship(
        "Order", back_populates="book", uselist=False, cascade="all, delete-orphan"
    )
