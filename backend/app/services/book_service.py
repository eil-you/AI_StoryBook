import logging

from sqlalchemy.orm import Session

from app.models.book import Book, BookStatus
from app.models.page import Page
from app.services.ai_service import StoryData

logger = logging.getLogger(__name__)


class BookService:
    """Handles persistence of AI-generated stories into the database."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def save_story(self, user_id: int, prompt_text: str, story: StoryData) -> Book:
        """Persist a generated story as a Book with associated Pages.

        Creates the Book record first (flush to obtain its PK), then inserts
        one Page row per paragraph before committing the transaction.

        Args:
            user_id: ID of the user who requested the story.
            prompt_text: The original prompt, stored as content_summary.
            story: Structured story data returned by the AI service.

        Returns:
            The refreshed Book ORM instance with pages loaded.
        """
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

        self._db.commit()
        self._db.refresh(book)
        logger.info(
            "Saved book id=%s with %d pages for user_id=%s",
            book.id,
            len(story["pages"]),
            user_id,
        )
        return book
