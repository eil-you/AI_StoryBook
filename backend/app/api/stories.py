from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.ai_service import AIService, PageData, StoryData, StoryGenerationError

router = APIRouter(prefix="/api/v1/stories", tags=["Stories"])

_ai_service = AIService()


class GenerateStoryRequest(BaseModel):
    character_name: str = Field(..., min_length=1, max_length=50, description="주인공 이름")
    character_age: int = Field(..., ge=1, le=20, description="주인공 나이")
    genre: str = Field(..., min_length=1, max_length=50, description="장르 (예: 모험, 판타지, 일상)")
    background: str = Field(..., min_length=1, max_length=100, description="배경/장소 (예: 숲속, 우주, 바닷속)")
    education: str = Field(..., min_length=1, max_length=100, description="교육적 가치 (예: 용기, 친절, 우정)")


class GenerateStoryResponse(BaseModel):
    success: bool
    message: str
    data: StoryData


@router.post("/generate", response_model=GenerateStoryResponse, status_code=201)
async def generate_story(body: GenerateStoryRequest) -> GenerateStoryResponse:
    """주인공 정보와 장르, 배경, 교육 가치를 바탕으로 어린이 동화를 자동 생성합니다."""
    try:
        story = await _ai_service.generate_story(
            character_name=body.character_name,
            character_age=body.character_age,
            genre=body.genre,
            background=body.background,
            education=body.education,
        )
    except StoryGenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return GenerateStoryResponse(success=True, message="스토리 생성 완료", data=story)
