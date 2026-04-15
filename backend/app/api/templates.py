import json
import logging
from pathlib import Path
from typing import Any, NoReturn

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

# app/assets/ 디렉터리 내 로컬 템플릿 JSON 파일 매핑 (UID → 파일명)
_ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"
_LOCAL_TEMPLATES: dict[str, str] = {
    "7jOxkBjj6VGe": "my_template_cover.json",
    "8DGGFyjtOu0E": "my_template_contents.json",
}

_GENERIC_MOCK = TemplateDetailDto(
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


def _load_local_template(template_uid: str) -> TemplateDetailDto | None:
    """app/assets/ 에서 로컬 JSON 파일을 읽어 TemplateDetailDto 로 변환합니다.
    파일이 없거나 알 수 없는 UID면 None 반환.
    """
    filename = _LOCAL_TEMPLATES.get(template_uid)
    if not filename:
        return None

    path = _ASSETS_DIR / filename
    if not path.exists():
        _log.warning("Local template file not found: %s", path)
        return None

    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))

    # parameters: SweetBook JSON은 list 형태 → definitions dict 로 변환
    parameters: ParametersDto | None = None
    raw_params = raw.get("parameters")
    if isinstance(raw_params, list):
        defs: dict[str, ParameterDefinition] = {}
        for item in raw_params:
            name = item.get("name", "")
            binding_val = item.get("binding", "text")
            try:
                binding = BindingKind(binding_val)
            except ValueError:
                binding = BindingKind.text
            defs[name] = ParameterDefinition(
                binding=binding,
                type=item.get("type", "string"),
                required=item.get("required", False),
                description=item.get("description", ""),
            )
        parameters = ParametersDto(definitions=defs)
    elif isinstance(raw_params, dict) and "definitions" in raw_params:
        parameters = ParametersDto(**raw_params)

    return TemplateDetailDto(
        parameters=parameters,
        layout=raw.get("layout"),
        layoutRules=raw.get("layoutRules"),
        baseLayer=raw.get("baseLayer"),
        thumbnails=ThumbnailsDto(layout=None),
    )


router = APIRouter(prefix="/api/v1/templates", tags=["Templates"])


@router.get("/{template_uid}", response_model=TemplateDetailResponse)
async def get_template(
    template_uid: str,
    provider: BookProvider = Depends(get_book_provider),
) -> TemplateDetailResponse:
    """Return the full detail of a single template by its UID.
    SweetBook API 접근 불가 시 app/assets/ 의 로컬 JSON 파일로 fallback합니다.
    """
    try:
        detail = await provider.get_template(template_uid)
    except ProviderError as exc:
        _log.warning(
            "SweetBook get_template API 접근 불가 — 로컬 fallback 시도 (uid=%s): %s",
            template_uid, exc.message,
        )
        detail = _load_local_template(template_uid) or _GENERIC_MOCK
    return TemplateDetailResponse(success=True, message="ok", data=detail)


def _raise_http(exc: ProviderError) -> NoReturn:
    if exc.code == ErrorCode.ERR001:
        raise HTTPException(status_code=400, detail=exc.message)
    if exc.status_code == 404:
        raise HTTPException(status_code=404, detail=exc.message)
    if exc.status_code == 422:
        raise HTTPException(status_code=422, detail=exc.message)
    raise HTTPException(status_code=502, detail=exc.message)
