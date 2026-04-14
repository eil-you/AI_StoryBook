import json
from typing import NoReturn

from fastapi import APIRouter, Depends, Header, HTTPException, Request, UploadFile

from app.core.dependencies import get_book_provider
from app.core.exceptions import ErrorCode, ProviderError
from app.providers.base import BookProvider
from app.schemas.cover import CoverResponse

router = APIRouter(prefix="/api/v1/books", tags=["Cover"])


@router.post("/{book_uid}/cover", response_model=CoverResponse, status_code=201)
async def add_cover(
    book_uid: str,
    request: Request,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    provider: BookProvider = Depends(get_book_provider),
) -> CoverResponse:
    """
    Add a cover to a DRAFT book by binding a cover template with images and text.

    Accepts multipart/form-data. Image fields are dynamic and match the template's
    parameter definitions. Three image provision methods are supported:

    - **File upload**: send the image file directly in a named form field
    - **URL**: include `"fieldName": "https://..."` in the `parameters` JSON
    - **Server filename**: include `"fieldName": "photo250105.JPG"` in `parameters`
    - **Mixed**: use `"fieldName": "$upload"` in `parameters` and also upload the file
    """
    form = await request.form()

    # --- Required field ---
    template_uid = form.get("templateUid")
    if not template_uid or not isinstance(template_uid, str):
        raise HTTPException(status_code=422, detail="templateUid is required")

    # --- Optional parameters JSON ---
    parameters: dict | None = None
    parameters_raw = form.get("parameters")
    if parameters_raw and isinstance(parameters_raw, str):
        try:
            parameters = json.loads(parameters_raw)
        except json.JSONDecodeError:
            raise HTTPException(status_code=422, detail="parameters must be valid JSON")

    # --- Dynamic image file fields (field names come from the template definition) ---
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
        data = await provider.add_cover(
            book_uid=book_uid,
            template_uid=template_uid,
            parameters=parameters,
            upload_files=upload_files or None,
            idempotency_key=idempotency_key,
        )
    except ProviderError as exc:
        _raise_http(exc)
    return CoverResponse(success=True, message="Cover created successfully", data=data)


def _raise_http(exc: ProviderError) -> NoReturn:
    if exc.code == ErrorCode.ERR001:
        raise HTTPException(status_code=400, detail=exc.message)
    if exc.status_code == 404:
        raise HTTPException(status_code=404, detail=exc.message)
    if exc.status_code == 422:
        raise HTTPException(status_code=422, detail=exc.message)
    raise HTTPException(status_code=502, detail=exc.message)
