import json
from typing import NoReturn

from fastapi import APIRouter, Depends, Form, Header, HTTPException, Query, Request, UploadFile

from app.core.dependencies import get_book_provider
from app.core.exceptions import ErrorCode, ProviderError
from app.providers.base import BookProvider
from app.schemas.content import BreakBefore, ContentResponse

router = APIRouter(prefix="/api/v1/books", tags=["Contents"])


@router.post("/{book_uid}/contents", response_model=ContentResponse, status_code=201)
async def add_content(
    book_uid: str,
    request: Request,
    template_uid: str = Form(..., alias="templateUid"),
    parameters_raw: str | None = Form(None, alias="parameters"),
    from_: str | None = Form(None, alias="from"),
    break_before: BreakBefore | None = Query(None),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    provider: BookProvider = Depends(get_book_provider),
) -> ContentResponse:
    """
    Append an interior page to a DRAFT book by binding a content template.

    Call repeatedly to build pages sequentially (each call adds the next spread).
    Returns `result: "updated"` with HTTP 201 when an existing page slot is overwritten.

    Image provision methods supported:
    - **File upload**: named form field matching the template parameter key
    - **URL**: `"fieldName": "https://..."` inside the `parameters` JSON
    - **Gallery array**: `"galleryPhotos": ["url1", "url2", ...]` inside `parameters`
    - **Mixed**: `"fieldName": "$upload"` in `parameters` + file in form field
    """
    # --- Parse parameters JSON ---
    parameters: dict | None = None
    if parameters_raw:
        try:
            parameters = json.loads(parameters_raw)
        except json.JSONDecodeError:
            raise HTTPException(status_code=422, detail="parameters must be valid JSON")

    # --- Dynamic image file fields (names come from the template definition) ---
    # FastAPI caches the parsed form, so request.form() reuses the same result.
    form = await request.form()
    upload_files: dict[str, tuple[str, bytes, str]] = {}
    for key, value in form.multi_items():
        if isinstance(value, UploadFile):
            content = await value.read()
            upload_files[key] = (
                value.filename or key,
                content,
                value.content_type or "application/octet-stream",
            )

    try:
        data = await provider.add_content(
            book_uid=book_uid,
            template_uid=template_uid,
            parameters=parameters,
            upload_files=upload_files or None,
            break_before=break_before.value if break_before else None,
            from_=from_,
            idempotency_key=idempotency_key,
        )
    except ProviderError as exc:
        _raise_http(exc)
    return ContentResponse(success=True, message="Content created successfully", data=data)


def _raise_http(exc: ProviderError) -> NoReturn:
    if exc.code == ErrorCode.ERR001:
        raise HTTPException(status_code=400, detail=exc.message)
    if exc.status_code == 404:
        raise HTTPException(status_code=404, detail=exc.message)
    if exc.status_code == 422:
        raise HTTPException(status_code=422, detail=exc.message)
    raise HTTPException(status_code=502, detail=exc.message)
