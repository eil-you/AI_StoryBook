import logging
from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import get_book_provider
from app.core.exceptions import ErrorCode, ProviderError
from app.providers.base import BookProvider
from app.schemas.template import (
    BindingKind,
    ParameterDefinition,
    ParametersDto,
    TemplateDetailDto,
    TemplateDetailResponse,
    ThumbnailsDto,
)

_log = logging.getLogger(__name__)

_MOCK_TEMPLATE_DETAIL = TemplateDetailDto(
    parameters=ParametersDto(
        definitions={
            "image": ParameterDefinition(
                binding=BindingKind.file,
                type="file",
                required=True,
                description="페이지 이미지",
            ),
            "text": ParameterDefinition(
                binding=BindingKind.text,
                type="string",
                required=False,
                description="페이지 텍스트",
            ),
        }
    ),
    layout={"width": 210, "height": 297, "elements": []},
    thumbnails=ThumbnailsDto(layout=None),
)

router = APIRouter(prefix="/api/v1/templates", tags=["Templates"])


@router.get("/{template_uid}", response_model=TemplateDetailResponse)
async def get_template(
    template_uid: str,
    provider: BookProvider = Depends(get_book_provider),
) -> TemplateDetailResponse:
    """Return the full detail of a single template by its UID."""
    try:
        detail = await provider.get_template(template_uid)
    except ProviderError as exc:
        _log.warning(
            "SweetBook get_template API 접근 불가 — mock template 반환 (uid=%s): %s",
            template_uid, exc.message,
        )
        detail = _MOCK_TEMPLATE_DETAIL
    return TemplateDetailResponse(success=True, message="ok", data=detail)


def _raise_http(exc: ProviderError) -> NoReturn:
    if exc.code == ErrorCode.ERR001:
        raise HTTPException(status_code=400, detail=exc.message)
    if exc.status_code == 404:
        raise HTTPException(status_code=404, detail=exc.message)
    if exc.status_code == 422:
        raise HTTPException(status_code=422, detail=exc.message)
    raise HTTPException(status_code=502, detail=exc.message)
