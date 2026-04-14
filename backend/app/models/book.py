from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import BookStatus

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.page import Page
    from app.models.order import Order


class Book(TimestampMixin, Base):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_image_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    sweetbook_book_uid: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    status: Mapped[BookStatus] = mapped_column(
        Enum(BookStatus), default=BookStatus.draft, nullable=False
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="books")
    pages: Mapped[list["Page"]] = relationship(
        "Page", back_populates="book", cascade="all, delete-orphan", order_by="Page.page_number"
    )
    order: Mapped["Order | None"] = relationship(
        "Order", back_populates="book", uselist=False, cascade="all, delete-orphan"
    )
