from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.dependencies import get_book_provider
from app.core.exceptions import ErrorCode, ProviderError
from app.providers.base import BookProvider
from app.schemas.template import (
    TemplateDetailResponse,
    TemplateKind,
    TemplateListResponse,
    TemplateScope,
)

router = APIRouter(prefix="/api/v1/templates", tags=["Templates"])


@router.get("", response_model=TemplateListResponse)
async def list_templates(
    scope: TemplateScope = Query(TemplateScope.all),
    book_spec_uid: str | None = Query(None),
    spec_profile_uid: str | None = Query(None),
    template_kind: TemplateKind | None = Query(None),
    category: str | None = Query(None),
    template_name: str | None = Query(None),
    theme: str | None = Query(None),
    sort: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    provider: BookProvider = Depends(get_book_provider),
) -> TemplateListResponse:
    """Return a paginated list of templates with optional filters."""
    try:
        data = await provider.list_templates(
            scope=scope.value,
            book_spec_uid=book_spec_uid,
            spec_profile_uid=spec_profile_uid,
            template_kind=template_kind.value if template_kind else None,
            category=category,
            template_name=template_name,
            theme=theme,
            sort=sort,
            limit=limit,
            offset=offset,
        )
    except ProviderError as exc:
        _raise_http(exc)
    return TemplateListResponse(success=True, message="ok", data=data)


@router.get("/{template_uid}", response_model=TemplateDetailResponse)
async def get_template(
    template_uid: str,
    provider: BookProvider = Depends(get_book_provider),
) -> TemplateDetailResponse:
    """Return the full detail of a single template by its UID."""
    try:
        detail = await provider.get_template(template_uid)
    except ProviderError as exc:
        _raise_http(exc)
    return TemplateDetailResponse(success=True, message="ok", data=detail)


def _raise_http(exc: ProviderError) -> NoReturn:
    if exc.code == ErrorCode.ERR001:
        raise HTTPException(status_code=400, detail=exc.message)
    if exc.status_code == 404:
        raise HTTPException(status_code=404, detail=exc.message)
    if exc.status_code == 422:
        raise HTTPException(status_code=422, detail=exc.message)
    raise HTTPException(status_code=502, detail=exc.message)
