"""
Book page preview endpoints.

Returns server-rendered PNG images of book pages with template applied.
Template thumbnail is used as the background; story image and text are composited on top.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.book import Book
from app.models.page import Page
from app.models.user import User
from app.services.preview_service import render_content_page, render_cover_page

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/stories", tags=["Preview"])

# These are passed as query params so the frontend can swap templates freely
_DEFAULT_COVER_THUMBNAIL = None
_DEFAULT_CONTENT_THUMBNAIL = None


@router.get("/{book_id}/preview/cover")
async def preview_cover(
    book_id: int,
    template_thumbnail: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Render the cover page as a PNG with template applied."""
    result = await db.execute(
        select(Book).where(Book.id == book_id, Book.is_deleted.is_(False))
    )
    book = result.scalar_one_or_none()
    if book is None or book.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="책을 찾을 수 없습니다.")

    logger.info(
        "preview_cover book_id=%d cover_url=%s template_thumbnail=%s",
        book_id,
        book.cover_image_url,
        template_thumbnail,
    )
    try:
        png = await render_cover_page(
            cover_image_url=book.cover_image_url or "",
            title=book.title,
            template_thumbnail_url=template_thumbnail,
        )
    except Exception as exc:
        logger.error("Cover preview render failed for book_id=%d: %s", book_id, exc)
        raise HTTPException(status_code=500, detail="미리보기 생성에 실패했습니다.")

    return Response(content=png, media_type="image/png")


@router.get("/{book_id}/preview/page/{page_number}")
async def preview_page(
    book_id: int,
    page_number: int,
    template_thumbnail: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Render a content page as a PNG with template applied."""
    result = await db.execute(
        select(Book).where(Book.id == book_id, Book.is_deleted.is_(False))
    )
    book = result.scalar_one_or_none()
    if book is None or book.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="책을 찾을 수 없습니다.")

    page_result = await db.execute(
        select(Page).where(Page.book_id == book_id, Page.page_number == page_number)
    )
    page = page_result.scalar_one_or_none()
    if page is None:
        raise HTTPException(status_code=404, detail="페이지를 찾을 수 없습니다.")

    logger.info(
        "preview_page book_id=%d page=%d image_url=%s template_thumbnail=%s",
        book_id,
        page_number,
        page.image_url,
        template_thumbnail,
    )
    try:
        png = await render_content_page(
            story_image_url=page.image_url or "",
            text=page.text_content or "",
            template_thumbnail_url=template_thumbnail,
        )
    except Exception as exc:
        logger.error(
            "Page preview render failed for book_id=%d page=%d: %s", book_id, page_number, exc
        )
        raise HTTPException(status_code=500, detail="미리보기 생성에 실패했습니다.")

    return Response(content=png, media_type="image/png")
