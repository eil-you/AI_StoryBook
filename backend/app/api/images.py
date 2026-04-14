from typing import NoReturn

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.dependencies import get_book_provider, get_current_user
from app.core.exceptions import ErrorCode, ProviderError
from app.models.user import User
from app.providers.base import BookProvider
from app.schemas.image import PhotoListResponse, UploadPhotoResponse

router = APIRouter(prefix="/api/v1/books", tags=["Images"])

_ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/bmp",
    "image/heic",
    "image/heif",
}
_MAX_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB


@router.post("/{book_uid}/photos", response_model=UploadPhotoResponse, status_code=201)
async def upload_photo(
    book_uid: str,
    file: UploadFile = File(...),
    provider: BookProvider = Depends(get_book_provider),
    current_user: User = Depends(get_current_user),
) -> UploadPhotoResponse:
    """
    Upload a single photo to a DRAFT book (max 50 MB, up to 200 photos per book).

    Supported formats: JPEG, PNG, GIF, WebP, BMP, HEIC, HEIF.

    The returned `fileName` (server filename) can be used in subsequent
    cover/content `parameters` fields instead of re-uploading the file.
    """
    if file.content_type not in _ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type '{file.content_type}'. "
                   f"Allowed: {', '.join(sorted(_ALLOWED_MIME_TYPES))}",
        )

    content = await file.read()

    if len(content) > _MAX_SIZE_BYTES:
        raise HTTPException(
            status_code=422,
            detail=f"File exceeds the 50 MB limit ({len(content)} bytes)",
        )

    try:
        data = await provider.upload_photo(
            book_uid=book_uid,
            filename=file.filename or file.content_type.replace("/", "."),
            content=content,
            content_type=file.content_type,
        )
    except ProviderError as exc:
        _raise_http(exc)
    return UploadPhotoResponse(success=True, data=data)


@router.get("/{book_uid}/photos", response_model=PhotoListResponse)
async def list_photos(
    book_uid: str,
    provider: BookProvider = Depends(get_book_provider),
    current_user: User = Depends(get_current_user),
) -> PhotoListResponse:
    """Return all photos uploaded to a book."""
    try:
        data = await provider.list_photos(book_uid=book_uid)
    except ProviderError as exc:
        _raise_http(exc)
    return PhotoListResponse(success=True, data=data)


def _raise_http(exc: ProviderError) -> NoReturn:
    if exc.code == ErrorCode.ERR001:
        raise HTTPException(status_code=400, detail=exc.message)
    if exc.status_code == 404:
        raise HTTPException(status_code=404, detail=exc.message)
    if exc.status_code == 422:
        raise HTTPException(status_code=422, detail=exc.message)
    raise HTTPException(status_code=502, detail=exc.message)
