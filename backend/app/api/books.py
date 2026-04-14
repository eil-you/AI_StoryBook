from typing import NoReturn

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.core.dependencies import get_book_provider
from app.core.exceptions import ErrorCode, ProviderError
from app.providers.base import BookProvider
from app.schemas.book import (
    BookListResponse,
    BookStatus,
    CreateBookBody,
    CreateBookResponse,
)

router = APIRouter(prefix="/api/v1/books", tags=["Books"])


@router.post("", response_model=CreateBookResponse, status_code=201)
async def create_book(
    body: CreateBookBody,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    provider: BookProvider = Depends(get_book_provider),
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


@router.get("", response_model=BookListResponse)
async def list_books(
    book_uid: str | None = Query(None),
    status: BookStatus | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    provider: BookProvider = Depends(get_book_provider),
) -> BookListResponse:
    """Return a paginated list of books, or a single book when book_uid is provided."""
    try:
        data = await provider.list_books(
            book_uid=book_uid,
            status=status.value if status else None,
            limit=limit,
            offset=offset,
        )
    except ProviderError as exc:
        _raise_http(exc)
    return BookListResponse(success=True, message="ok", data=data)


def _raise_http(exc: ProviderError) -> NoReturn:
    if exc.code == ErrorCode.ERR001:
        raise HTTPException(status_code=400, detail=exc.message)
    if exc.status_code == 404:
        raise HTTPException(status_code=404, detail=exc.message)
    if exc.status_code == 422:
        raise HTTPException(status_code=422, detail=exc.message)
    raise HTTPException(status_code=502, detail=exc.message)
