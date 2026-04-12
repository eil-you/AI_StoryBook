import logging

from sqlalchemy.orm import Session

from app.models.book import Book
from app.models.enums import BookStatus
from app.models.page import Page
from app.services.ai_service import AIService, StoryGenerationError  # noqa: F401 – re-export

logger = logging.getLogger(__name__)


class StoryService:
    """Orchestrates AI story generation and DB persistence.

    Deliberately does NOT call db.commit(). The caller (API route)
    owns the transaction boundary via ``with db.begin():``.
    """

    def __init__(self, db: Session) -> None:
        self._db = db
        self._ai = AIService()

    async def create_story(self, user_id: int, prompt_text: str) -> Book:
        """Generate a story via AI and stage the Book + Page rows.

        Flushes to obtain PKs but never commits — the surrounding
        transaction context manager handles that.

        Args:
            user_id: Owner of the book being created.
            prompt_text: User-supplied story theme; stored as content_summary.

        Returns:
            The flushed and refreshed Book ORM instance (pages loaded).

        Raises:
            StoryGenerationError: Propagated from AIService on any AI failure.
        """
        story = await self._ai.generate_story(prompt_text)

        book = Book(
            user_id=user_id,
            title=story["title"],
            content_summary=prompt_text,
            status=BookStatus.completed,
        )
        self._db.add(book)
        self._db.flush()  # populate book.id before inserting pages

        for idx, paragraph in enumerate(story["pages"], start=1):
            self._db.add(
                Page(
                    book_id=book.id,
                    page_number=idx,
                    text_content=paragraph,
                )
            )

        self._db.flush()
        self._db.refresh(book)
        logger.info(
            "Staged book id=%s title=%r with %d pages for user_id=%s",
            book.id,
            book.title,
            len(story["pages"]),
            user_id,
        )
        return book
