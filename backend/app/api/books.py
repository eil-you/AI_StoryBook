from typing import NoReturn

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_book_provider, get_current_user
from app.core.exceptions import ErrorCode, ProviderError
from app.models.book import Book
from app.models.user import User
from app.providers.base import BookProvider
from app.schemas.book import (
    CreateBookBody,
    CreateBookResponse,
)

router = APIRouter(prefix="/api/v1/books", tags=["Books"])


@router.post("", response_model=CreateBookResponse, status_code=201)
async def create_book(
    body: CreateBookBody,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    provider: BookProvider = Depends(get_book_provider),
    current_user: User = Depends(get_current_user),
) -> CreateBookResponse:
    """Create a new book in DRAFT status."""
    try:
        data = await provider.create_book(
            title=body.title,
            book_spec_uid=body.book_spec_uid,
            spec_profile_uid=body.spec_profile_uid,
            external_ref=body.external_ref,
            idempotency_key=idempotency_key,
        )
    except ProviderError as exc:
        _raise_http(exc)
    return CreateBookResponse(success=True, message="책 생성 완료", data=data)


class LocalBookItem(BaseModel):
    id: int
    title: str
    cover_image_url: str | None
    status: str
    content_summary: str | None


class LocalBookListResponse(BaseModel):
    success: bool
    message: str
    data: list[LocalBookItem]


@router.get("", response_model=LocalBookListResponse)
async def list_books(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LocalBookListResponse:
    """현재 사용자의 로컬 DB 책 목록을 최신순으로 반환합니다."""
    result = await db.execute(
        select(Book)
        .where(Book.user_id == current_user.id, Book.is_deleted.is_(False))
        .order_by(Book.id.desc())
        .limit(limit)
        .offset(offset)
    )
    books = result.scalars().all()
    return LocalBookListResponse(
        success=True,
        message="ok",
        data=[
            LocalBookItem(
                id=b.id,
                title=b.title,
                cover_image_url=b.cover_image_url,
                status=b.status.value,
                content_summary=b.content_summary,
            )
            for b in books
        ],
    )


class PageDetail(BaseModel):
    page_number: int
    text: str | None
    image_url: str | None


class BookDetailResponse(BaseModel):
    success: bool
    book_id: int
    title: str
    cover_image_url: str | None
    status: str
    pages: list[PageDetail]


class DeleteBookResponse(BaseModel):
    success: bool
    message: str
    book_id: int


@router.post("/{book_id}/delete", response_model=DeleteBookResponse)
async def delete_book(
    book_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DeleteBookResponse:
    """책을 소프트 삭제합니다 (is_deleted = True). 주문된 책은 삭제할 수 없습니다."""
    result = await db.execute(
        select(Book).where(Book.id == book_id, Book.is_deleted.is_(False))
    )
    book = result.scalar_one_or_none()
    if book is None:
        raise HTTPException(status_code=404, detail="책을 찾을 수 없습니다.")
    if book.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다.")

    book.is_deleted = True
    await db.commit()
    return DeleteBookResponse(success=True, message="책이 삭제되었습니다.", book_id=book_id)


@router.get("/{book_id}", response_model=BookDetailResponse)
async def get_book_detail(
    book_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BookDetailResponse:
    """로컬 DB에서 책과 페이지 목록을 조회합니다."""
    result = await db.execute(
        select(Book)
        .options(selectinload(Book.pages))
        .where(Book.id == book_id, Book.is_deleted.is_(False))
    )
    book = result.scalar_one_or_none()
    if book is None:
        raise HTTPException(status_code=404, detail="책을 찾을 수 없습니다.")
    if book.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다.")

    return BookDetailResponse(
        success=True,
        book_id=book.id,
        title=book.title,
        cover_image_url=book.cover_image_url,
        status=book.status.value,
        pages=[
            PageDetail(
                page_number=p.page_number,
                text=p.text_content,
                image_url=p.image_url,
            )
            for p in book.pages
        ],
    )


def _raise_http(exc: ProviderError) -> NoReturn:
    if exc.code == ErrorCode.ERR001:
        raise HTTPException(status_code=400, detail=exc.message)
    if exc.status_code == 404:
        raise HTTPException(status_code=404, detail=exc.message)
    if exc.status_code == 422:
        raise HTTPException(status_code=422, detail=exc.message)
    raise HTTPException(status_code=502, detail=exc.message)
