from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.book import Book, BookStatus
from app.models.page import Page
from app.services.ai_service import AIService, PageData, StoryData, StoryGenerationError
from app.services.sweetbook_service import (
    SweetBookPublishError,
    create_sweetbook_book,
    finalize_sweetbook_book,
    publish_contents_to_sweetbook,
    publish_cover_to_sweetbook,
)

router = APIRouter(prefix="/api/v1/stories", tags=["Stories"])

_ai_service = AIService()


class GenerateStoryRequest(BaseModel):
    character_name: str = Field(..., min_length=1, max_length=50, description="주인공 이름")
    character_age: int = Field(..., ge=1, le=20, description="주인공 나이")
    genre: str = Field(..., min_length=1, max_length=50, description="장르 (예: 모험, 판타지, 일상)")
    background: str = Field(..., min_length=1, max_length=100, description="배경/장소 (예: 숲속, 우주, 바닷속)")
    education: str = Field(..., min_length=1, max_length=100, description="교육적 가치 (예: 용기, 친절, 우정)")
    book_spec_uid: str = Field(..., description="SweetBook 사양 UID")


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
        cover_image_url=story.cover_image_url,
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

    try:
        await create_sweetbook_book(
            book_id=book.id,
            book_spec_uid=body.book_spec_uid,
            db=db,
        )
    except SweetBookPublishError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return GenerateStoryResponse(success=True, message="스토리 생성 완료", book_id=book.id, data=story)


class PublishCoverRequest(BaseModel):
    cover_template_uid: str = Field(..., description="표지 템플릿 UID")


class PublishCoverResponse(BaseModel):
    success: bool
    message: str
    book_id: int


@router.post("/{book_id}/publish/cover", response_model=PublishCoverResponse, status_code=201)
async def publish_cover(
    book_id: int,
    body: PublishCoverRequest,
    db: AsyncSession = Depends(get_db),
) -> PublishCoverResponse:
    """DB에 저장된 스토리의 표지 이미지를 SweetBook DRAFT 책에 추가합니다."""
    try:
        await publish_cover_to_sweetbook(
            book_id=book_id,
            cover_template_uid=body.cover_template_uid,
            db=db,
        )
    except SweetBookPublishError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return PublishCoverResponse(
        success=True,
        message="SweetBook 표지 퍼블리시 완료",
        book_id=book_id,
    )


class PublishContentsRequest(BaseModel):
    content_template_uid: str = Field(..., description="내지 콘텐츠 템플릿 UID")
    extra_parameters: dict[str, str] = Field(
        default_factory=dict,
        description="템플릿 필수 파라미터 추가 입력 (예: {\"childName\": \"민준\"})",
    )


class PublishContentsResponse(BaseModel):
    success: bool
    message: str
    book_id: int
    page_count: int


@router.post("/{book_id}/publish/contents", response_model=PublishContentsResponse, status_code=201)
async def publish_contents(
    book_id: int,
    body: PublishContentsRequest,
    db: AsyncSession = Depends(get_db),
) -> PublishContentsResponse:
    """DB에 저장된 스토리 페이지(텍스트 + 이미지)를 SweetBook DRAFT 책에 내지로 추가합니다."""
    try:
        pages = await publish_contents_to_sweetbook(
            book_id=book_id,
            content_template_uid=body.content_template_uid,
            extra_parameters=body.extra_parameters,
            db=db,
        )
    except SweetBookPublishError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return PublishContentsResponse(
        success=True,
        message="SweetBook 내지 퍼블리시 완료",
        book_id=book_id,
        page_count=len(pages),
    )


class FinalizeStoryResponse(BaseModel):
    success: bool
    message: str
    book_id: int
    page_count: int
    finalized_at: str


@router.post("/{book_id}/finalize", response_model=FinalizeStoryResponse, status_code=201)
async def finalize_story(
    book_id: int,
    db: AsyncSession = Depends(get_db),
) -> FinalizeStoryResponse:
    """SweetBook DRAFT 책을 FINALIZED 상태로 전환합니다. 주문 생성이 가능해집니다."""
    try:
        data = await finalize_sweetbook_book(
            book_id=book_id,
            db=db,
        )
    except SweetBookPublishError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return FinalizeStoryResponse(
        success=True,
        message="SweetBook 파이널라이즈 완료",
        book_id=book_id,
        page_count=data.pageCount,
        finalized_at=data.finalizedAt.isoformat(),
    )
