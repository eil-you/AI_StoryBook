from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.book import Book, BookStatus
from app.models.page import Page
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
    book_id: int
    data: StoryData


@router.post("/generate", response_model=GenerateStoryResponse, status_code=201)
async def generate_story(
    body: GenerateStoryRequest,
    db: AsyncSession = Depends(get_db),
) -> GenerateStoryResponse:
    """주인공 정보와 장르, 배경, 교육 가치를 바탕으로 어린이 동화를 자동 생성하고 저장합니다."""
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

    book = Book(
        user_id=1,  # TODO: replace with authenticated user id
        title=story.title,
        content_summary=f"주인공: {body.character_name}({body.character_age}세) / 장르: {body.genre} / 배경: {body.background} / 교육: {body.education}",
        status=BookStatus.draft,
    )
    db.add(book)
    await db.flush()  # book.id 확보

    for idx, page in enumerate(story.pages, start=1):
        db.add(Page(
            book_id=book.id,
            page_number=idx,
            text_content=page.text,
            image_url=page.image_url,
        ))

    await db.commit()
    await db.refresh(book)

    return GenerateStoryResponse(success=True, message="스토리 생성 완료", book_id=book.id, data=story)
