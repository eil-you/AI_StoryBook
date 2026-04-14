from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import get_book_provider
from app.core.exceptions import ErrorCode, ProviderError
from app.providers.base import BookProvider
from app.schemas.book_spec import BookSpecDto, BookSpecListResponse, BookSpecResponse

router = APIRouter(prefix="/api/v1/book-specs", tags=["Book Specs"])


@router.get("", response_model=BookSpecListResponse)
async def list_book_specs(
    provider: BookProvider = Depends(get_book_provider),
) -> BookSpecListResponse:
    """Return all available book specifications from the SweetBook provider."""
    try:
        specs = await provider.list_book_specs()
    except ProviderError as exc:
        _raise_http(exc)
    return BookSpecListResponse(success=True, message="ok", data=specs)


@router.get("/{book_spec_uid}", response_model=BookSpecResponse)
async def get_book_spec(
    book_spec_uid: str,
    provider: BookProvider = Depends(get_book_provider),
) -> BookSpecResponse:
    """Return a single book specification by its UID."""
    try:
        spec = await provider.get_book_spec(book_spec_uid)
    except ProviderError as exc:
        _raise_http(exc)
    return BookSpecResponse(success=True, message="ok", data=spec)


def _raise_http(exc: ProviderError) -> NoReturn:
    if exc.code == ErrorCode.ERR001:
        raise HTTPException(status_code=400, detail=exc.message)
    if exc.status_code == 404:
        raise HTTPException(status_code=404, detail=exc.message)
    if exc.status_code == 422:
        raise HTTPException(status_code=422, detail=exc.message)
    raise HTTPException(status_code=502, detail=exc.message)
