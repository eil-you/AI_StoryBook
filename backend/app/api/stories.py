import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.models.book import Book
from app.models.enums import ErrorCode
from app.schemas.story import BookCreatedResponse, PageOut, StoryDetail, StorySummary, StoryRequest
from app.services.ai_service import StoryGenerationError
from app.services.story_service import StoryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stories", tags=["Stories"])


@router.post(
    "/generate",
    response_model=BookCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate and save an AI story",
    description=(
        "Generates a children's story from the given prompt, "
        "saves it to the Book and Page tables, and returns the book ID with content."
    ),
)
async def generate_story(
    request: StoryRequest, db: Session = Depends(get_db)
) -> BookCreatedResponse:
    """Generate a story via OpenAI, persist it, and return the saved book.

    Transaction ownership: ``with db.begin()`` commits on success and
    auto-rolls back on any exception, keeping the service layer free of
    transaction concerns.
    """
    story_service = StoryService(db)
    try:
        with db.begin():
            book = await story_service.create_story(
                user_id=request.user_id,
                prompt_text=request.prompt_text,
            )
            # Access relationship inside the transaction so expire_on_commit
            # does not trigger a lazy-load after the session is committed.
            pages = sorted(book.pages, key=lambda p: p.page_number)
    except StoryGenerationError as e:
        logger.warning("Story generation failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=ErrorCode.AI_SERVICE_UNAVAILABLE.to_detail(str(e)),
        )

    return BookCreatedResponse(
        book_id=book.id,
        title=book.title,
        status=book.status,
        created_at=book.created_at,
        updated_at=book.updated_at,
        pages=[
            PageOut(
                page_number=p.page_number,
                text_content=p.text_content or "",
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in pages
        ],
    )


@router.get(
    "",
    response_model=list[StorySummary],
    summary="List all stories",
    description="Returns a lightweight list of all stories (id, title, created_at).",
)
async def list_stories(db: Session = Depends(get_db)) -> list[StorySummary]:
    """Return id, title, and created_at for every book in the database."""
    books = db.query(Book).filter(Book.is_deleted.is_(False)).order_by(Book.created_at.desc()).all()
    return [StorySummary.model_validate(b) for b in books]


@router.get(
    "/search",
    response_model=list[StorySummary],
    summary="Search stories by title",
    description="Returns stories whose title contains the given keyword (case-insensitive LIKE search).",
)
async def search_stories(
    q: str = Query(..., min_length=1, description="Title keyword to search for"),
    db: Session = Depends(get_db),
) -> list[StorySummary]:
    """Search active books by title using a SQL LIKE pattern."""
    books = (
        db.query(Book)
        .filter(Book.is_deleted.is_(False), Book.title.ilike(f"%{q}%"))
        .order_by(Book.created_at.desc())
        .all()
    )
    return [StorySummary.model_validate(b) for b in books]


@router.get(
    "/{book_id}",
    response_model=StoryDetail,
    summary="Get full story detail",
    description="Returns the full detail of a story, including all its pages, fetched in one query via joinedload.",
)
async def get_story(book_id: int, db: Session = Depends(get_db)) -> StoryDetail:
    """Fetch a single book with all its pages eagerly loaded."""
    book = (
        db.query(Book)
        .options(joinedload(Book.pages))
        .filter(Book.id == book_id, Book.is_deleted.is_(False))
        .first()
    )
    if book is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorCode.STORY_NOT_FOUND.to_detail(),
        )
    pages = sorted(book.pages, key=lambda p: p.page_number)
    return StoryDetail(
        id=book.id,
        title=book.title,
        status=book.status,
        content_summary=book.content_summary,
        created_at=book.created_at,
        updated_at=book.updated_at,
        pages=[
            PageOut(
                page_number=p.page_number,
                text_content=p.text_content or "",
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in pages
        ],
    )


@router.delete(
    "/{book_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a story",
    description="Marks the story as deleted by setting is_deleted=True. The record is retained in the database.",
)
async def delete_story(book_id: int, db: Session = Depends(get_db)) -> None:
    """Soft-delete a book by flipping its is_deleted flag."""
    book = db.query(Book).filter(Book.id == book_id, Book.is_deleted.is_(False)).first()
    if book is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorCode.STORY_NOT_FOUND.to_detail(),
        )
    book.is_deleted = True
    db.commit()
