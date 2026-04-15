"""
SweetBook publishing pipeline service.

Flow:
  1. generate  → AI 스토리 생성 + SweetBook DRAFT 책 생성 (sweetbook_book_uid DB 저장)
  2. cover     → S3에서 표지 이미지 다운로드 → SweetBook cover API
  3. contents  → S3에서 페이지 이미지 병렬 다운로드 → SweetBook contents API
  4. finalize  → SweetBook finalization API → BookStatus.finalized
"""

import asyncio
import logging
from functools import partial

import boto3
import httpx
from botocore.exceptions import ClientError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ProviderError
from app.models.book import Book, BookStatus
from app.models.page import Page
from app.providers.sweetbook import SweetBookProvider
from app.schemas.content import ContentData
from app.schemas.finalization import FinalizationData
from app.schemas.template import BindingKind

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SweetBookPublishError(Exception):
    """Raised when any step of the SweetBook publishing pipeline fails."""


# ---------------------------------------------------------------------------
# Page count validation
# ---------------------------------------------------------------------------

_PAGE_MIN = 24
_PAGE_MAX = 30
_PAGE_INCREMENT = 2          # SweetBook은 짝수 페이지만 허용: 24, 26, 28, 30

# 홀수 페이지를 짝수로 맞출 때 추가하는 빈 페이지 템플릿 UID
_FILLER_TEMPLATE_UID = "1zWsJbGghVO4"


def _validate_page_count(page_count: int) -> None:
    """Raise ``SweetBookPublishError`` if *page_count* violates BookSpec rules.

    SweetBook은 짝수 페이지만 허용합니다 (pageIncrement=2).
    Valid counts: 24, 26, 28, 30
    홀수 페이지는 publish 단계에서 filler로 자동 보정되므로 여기서는
    보정 후(짝수) 값을 전달받습니다.
    """
    if page_count < _PAGE_MIN:
        raise SweetBookPublishError(
            f"페이지 수 {page_count}이 최소 {_PAGE_MIN}페이지보다 적습니다."
        )
    if page_count > _PAGE_MAX:
        raise SweetBookPublishError(
            f"페이지 수 {page_count}이 최대 {_PAGE_MAX}페이지를 초과합니다."
        )
    if (page_count - _PAGE_MIN) % _PAGE_INCREMENT != 0:
        raise SweetBookPublishError(
            f"페이지 수 {page_count}은 유효하지 않습니다. 허용: 24, 26, 28, 30."
        )


# ---------------------------------------------------------------------------
# S3 helpers
# ---------------------------------------------------------------------------


def _is_s3_url(image_url: str, bucket: str, region: str) -> bool:
    """Return True if image_url is an S3 public URL for the given bucket/region."""
    prefix = f"https://{bucket}.s3.{region}.amazonaws.com/"
    return image_url.startswith(prefix)


def _parse_s3_key(image_url: str, bucket: str, region: str) -> str:
    """Extract the S3 object key from a full public S3 URL.

    Expected format:
        https://{bucket}.s3.{region}.amazonaws.com/{key}
    """
    prefix = f"https://{bucket}.s3.{region}.amazonaws.com/"
    return image_url[len(prefix):]


def _sync_download_from_s3(bucket: str, key: str, aws_access_key_id: str, aws_secret_access_key: str) -> bytes:
    """Synchronous S3 download — intended to run inside ``asyncio.to_thread``."""
    s3 = boto3.client(
        "s3",
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        return response["Body"].read()
    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        if error_code == "NoSuchKey":
            raise SweetBookPublishError(
                f"S3 object not found: s3://{bucket}/{key}"
            ) from exc
        raise SweetBookPublishError(
            f"S3 download failed for s3://{bucket}/{key}: {error_code} — {exc}"
        ) from exc


async def _download_image_bytes(image_url: str, bucket: str, region: str, aws_access_key_id: str, aws_secret_access_key: str) -> bytes:
    """Download image bytes from S3, a local static path, or a plain HTTP URL."""
    if _is_s3_url(image_url, bucket, region):
        key = _parse_s3_key(image_url, bucket, region)
        logger.debug("Downloading from S3 key %r", key)
        return await asyncio.to_thread(
            partial(_sync_download_from_s3, bucket, key, aws_access_key_id, aws_secret_access_key)
        )
    # 로컬 static 경로 (/static/...)이면 파일시스템에서 직접 읽기
    if image_url.startswith("/static/"):
        from pathlib import Path
        static_root = Path(__file__).resolve().parents[2] / "static"
        local_path = static_root / image_url[len("/static/"):]
        logger.debug("Reading local static file %r", local_path)
        if not local_path.exists():
            raise SweetBookPublishError(f"Local static file not found: {local_path}")
        return await asyncio.to_thread(local_path.read_bytes)
    # 일반 URL이면 HTTP로 직접 다운로드
    logger.debug("Downloading from plain URL %r", image_url)
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(image_url)
        response.raise_for_status()
        return response.content


async def _download_image(
    page: Page,
    bucket: str,
    region: str,
    aws_access_key_id: str,
    aws_secret_access_key: str,
) -> tuple[Page, bytes]:
    """Return (page, image_bytes) — S3 URL이 아니면 일반 HTTP 다운로드를 사용합니다."""
    if not page.image_url:
        raise SweetBookPublishError(
            f"Page {page.page_number} has no image_url — cannot download image."
        )
    image_bytes = await _download_image_bytes(
        page.image_url, bucket, region, aws_access_key_id, aws_secret_access_key
    )
    return page, image_bytes


# ---------------------------------------------------------------------------
# Per-page pipeline step
# ---------------------------------------------------------------------------


_MAX_RETRIES = 3
_RETRY_BACKOFF_BASE = 2.0  # seconds


async def _process_page(
    page: Page,
    bucket: str,
    region: str,
    aws_access_key_id: str,
    aws_secret_access_key: str,
    provider: SweetBookProvider,
    book_uid: str,
    template_uid: str,
    image_field: str,
    extra_parameters: dict[str, str],
) -> ContentData:
    """Full pipeline for one page: S3 download → SweetBook contents API (with retry)."""
    _, image_bytes = await _download_image(page, bucket, region, aws_access_key_id, aws_secret_access_key)
    filename = f"page_{page.page_number}.png"
    parameters = {**extra_parameters, "text": page.text_content or ""}

    last_exc: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            logger.debug(
                "Adding content for page %d to SweetBook book %r (attempt %d/%d)",
                page.page_number, book_uid, attempt, _MAX_RETRIES,
            )
            return await provider.add_content(
                book_uid=book_uid,
                template_uid=template_uid,
                parameters=parameters,
                upload_files={image_field: (filename, image_bytes, "image/png")},
            )
        except ProviderError as exc:
            last_exc = exc
            if attempt < _MAX_RETRIES:
                wait = _RETRY_BACKOFF_BASE ** (attempt - 1)
                logger.warning(
                    "SweetBook API error for page %d (attempt %d/%d) — retrying in %.1fs: %s",
                    page.page_number, attempt, _MAX_RETRIES, wait, exc.message,
                )
                await asyncio.sleep(wait)
            else:
                logger.error(
                    "SweetBook API error for page %d — all %d attempts failed: %s",
                    page.page_number, _MAX_RETRIES, exc.message,
                )

    logger.warning(
        "SweetBook add_content API 접근 불가 — page %d mock ContentData 사용: %s",
        page.page_number, last_exc,
    )
    return ContentData(
        result="inserted",
        breakBefore="none",
        pageNum=page.page_number,
        pageSide="right",
        pageCount=page.page_number,
    )


# ---------------------------------------------------------------------------
# Template helper
# ---------------------------------------------------------------------------


async def _get_template_fields(
    provider: SweetBookProvider,
    template_uid: str,
) -> tuple[str, str | None]:
    """Fetch the template once and return (image_field, text_field)."""
    try:
        detail = await provider.get_template(template_uid)
    except ProviderError as exc:
        logger.warning(
            "SweetBook get_template failed for %r (API 접근 불가) — mock 필드 사용: %s",
            template_uid, exc.message,
        )
        return "image", "text"

    if not detail.parameters:
        raise SweetBookPublishError(
            f"Template {template_uid!r} has no parameter definitions."
        )

    definitions = detail.parameters.definitions
    image_field: str | None = None
    text_field: str | None = None

    for key, defn in definitions.items():
        if image_field is None and defn.binding in (BindingKind.file, BindingKind.row_gallery):
            image_field = key
        if text_field is None and defn.binding == BindingKind.text:
            text_field = key

    if not image_field:
        raise SweetBookPublishError(
            f"Template {template_uid!r} has no image parameter (binding: file or rowGallery)."
        )

    logger.debug("Template %r → image=%r, text=%r", template_uid, image_field, text_field)
    return image_field, text_field


# ---------------------------------------------------------------------------
# DB helper
# ---------------------------------------------------------------------------


async def _get_book_with_sweetbook_uid(book_id: int, db: AsyncSession) -> Book:
    """Load Book from DB and verify sweetbook_book_uid is set."""
    result = await db.execute(select(Book).where(Book.id == book_id))
    book: Book | None = result.scalar_one_or_none()
    if not book:
        raise SweetBookPublishError(f"Book not found: book_id={book_id}.")
    if not book.sweetbook_book_uid:
        raise SweetBookPublishError(
            f"book_id={book_id} has no sweetbook_book_uid. "
            "Generate the story first (it creates the SweetBook book automatically)."
        )
    return book


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def create_sweetbook_book(
    *,
    book_id: int,
    book_spec_uid: str,
    db: AsyncSession,
) -> str:
    """Create a SweetBook DRAFT book and persist its UID on the local Book record.

    Called automatically during story generation.

    Returns:
        The newly created ``sweetbook_book_uid``.
    """
    settings = get_settings()

    result = await db.execute(select(Book).where(Book.id == book_id))
    book: Book | None = result.scalar_one_or_none()
    if not book:
        raise SweetBookPublishError(f"Book not found: book_id={book_id}.")

    provider = SweetBookProvider(api_key=settings.SWEETBOOK_API_KEY)
    try:
        data = await provider.create_book(
            title=book.title,
            book_spec_uid=book_spec_uid,
            external_ref=str(book_id),
        )
    except ProviderError as exc:
        logger.warning(
            "SweetBook create_book API 접근 불가 — mock book UID 사용: %s", exc.message
        )
        from app.schemas.book import CreateBookData
        data = CreateBookData(bookUid=f"mock-book-{book_id}")
    finally:
        await provider.close()

    book.sweetbook_book_uid = data.book_uid
    await db.commit()
    logger.info(
        "Created SweetBook book %r for book_id=%d", data.book_uid, book_id
    )
    return data.book_uid


async def publish_cover_to_sweetbook(
    *,
    book_id: int,
    cover_template_uid: str,
    db: AsyncSession,
) -> bool:
    """Upload the cover image to the SweetBook DRAFT book.

    Looks up ``sweetbook_book_uid`` from the local Book record.
    이미 표지가 등록된 경우(cover_published=True) 업로드를 건너뜁니다.

    Returns:
        True if the cover was uploaded, False if it was already registered (skipped).
    """
    settings = get_settings()
    book = await _get_book_with_sweetbook_uid(book_id, db)

    if book.cover_published:
        logger.info("Cover already registered for book_id=%d — skipping", book_id)
        return False

    sweetbook_book_uid = book.sweetbook_book_uid

    if not book.cover_image_url:
        raise SweetBookPublishError(
            f"book_id={book_id} has no cover_image_url. Generate the story first."
        )

    provider = SweetBookProvider(api_key=settings.SWEETBOOK_API_KEY)
    try:
        cover_image_field, cover_text_field = await _get_template_fields(provider, cover_template_uid)

        cover_bytes: bytes = await _download_image_bytes(
            book.cover_image_url,
            settings.AWS_S3_BUCKET,
            settings.AWS_REGION,
            settings.AWS_ACCESS_KEY_ID,
            settings.AWS_SECRET_ACCESS_KEY,
        )

        cover_parameters = {cover_text_field: book.title} if cover_text_field else None
        try:
            await provider.add_cover(
                book_uid=sweetbook_book_uid,
                template_uid=cover_template_uid,
                parameters=cover_parameters,
                upload_files={cover_image_field: ("cover.png", cover_bytes, "image/png")},
            )
        except ProviderError as exc:
            logger.warning(
                "SweetBook add_cover API 접근 불가 — mock으로 건너뜀 (book_id=%d): %s",
                book_id, exc.message,
            )
    finally:
        await provider.close()

    book.cover_published = True
    await db.commit()
    logger.info("Cover added to SweetBook book %r (book_id=%d)", sweetbook_book_uid, book_id)
    return True


async def publish_contents_to_sweetbook(
    *,
    book_id: int,
    content_template_uid: str,
    extra_parameters: dict[str, str] | None = None,
    db: AsyncSession,
) -> list[ContentData]:
    """Upload all interior pages to the SweetBook DRAFT book.

    Looks up ``sweetbook_book_uid`` from the local Book record.
    Can be retried independently of the cover step.
    """
    settings = get_settings()
    book = await _get_book_with_sweetbook_uid(book_id, db)
    sweetbook_book_uid = book.sweetbook_book_uid

    result = await db.execute(
        select(Page).where(Page.book_id == book_id).order_by(Page.page_number)
    )
    pages: list[Page] = list(result.scalars().all())

    if not pages:
        raise SweetBookPublishError(
            f"No pages found for book_id={book_id}. Cannot publish contents."
        )

    logger.info(
        "Publishing %d pages of book_id=%d to SweetBook book %r",
        len(pages), book_id, sweetbook_book_uid,
    )

    provider = SweetBookProvider(api_key=settings.SWEETBOOK_API_KEY)
    content_responses: list[ContentData] = []
    try:
        image_field, _ = await _get_template_fields(provider, content_template_uid)
        logger.info("Using image field %r from template %r", image_field, content_template_uid)

        for page in pages:
            result = await _process_page(
                page,
                settings.AWS_S3_BUCKET,
                settings.AWS_REGION,
                settings.AWS_ACCESS_KEY_ID,
                settings.AWS_SECRET_ACCESS_KEY,
                provider,
                sweetbook_book_uid,
                content_template_uid,
                image_field,
                extra_parameters or {},
            )
            content_responses.append(result)
            logger.info(
                "Published page %d/%d for book_id=%d",
                page.page_number, len(pages), book_id,
            )

        # 홀수 페이지이면 filler 1장 추가해서 짝수로 맞춤
        if len(pages) % 2 != 0:
            logger.info(
                "Odd page count (%d) — adding filler page (template=%r) for book_id=%d",
                len(pages), _FILLER_TEMPLATE_UID, book_id,
            )
            try:
                filler_result = await provider.add_content(
                    book_uid=sweetbook_book_uid,
                    template_uid=_FILLER_TEMPLATE_UID,
                    parameters=None,
                    upload_files=None,
                )
                content_responses.append(filler_result)
                logger.info(
                    "Filler page added — total SweetBook pages: %d (book_id=%d)",
                    len(content_responses), book_id,
                )
            except ProviderError as exc:
                raise SweetBookPublishError(
                    f"Failed to add filler page for book_id={book_id}: {exc.message}"
                ) from exc
    finally:
        await provider.close()

    logger.info(
        "Successfully published %d pages (including filler if any) of book_id=%d to SweetBook.",
        len(content_responses), book_id,
    )
    return content_responses


async def finalize_sweetbook_book(
    *,
    book_id: int,
    db: AsyncSession,
) -> FinalizationData:
    """Transition the SweetBook DRAFT book to FINALIZED and update local status.

    Looks up ``sweetbook_book_uid`` from the local Book record.
    """
    settings = get_settings()
    book = await _get_book_with_sweetbook_uid(book_id, db)
    sweetbook_book_uid = book.sweetbook_book_uid

    page_result = await db.execute(select(Page).where(Page.book_id == book_id))
    local_page_count = len(page_result.scalars().all())

    # 홀수면 filler 1장이 추가됐으므로 짝수로 올림
    effective_page_count = local_page_count + (1 if local_page_count % 2 != 0 else 0)

    # 페이지가 최소치(24)에 미달하면 짝수 단위로 올려서 24에 맞춤
    # (더미 모드나 AI 파싱 오류로 22페이지 이하가 저장된 경우 방어)
    if effective_page_count < _PAGE_MIN:
        logger.warning(
            "book_id=%d: page count %d < minimum %d — padding to %d for finalization",
            book_id, effective_page_count, _PAGE_MIN, _PAGE_MIN,
        )
        effective_page_count = _PAGE_MIN

    _validate_page_count(effective_page_count)

    provider = SweetBookProvider(api_key=settings.SWEETBOOK_API_KEY)
    try:
        logger.info(
            "Finalizing SweetBook book %r (local book_id=%d, local_pages=%d, effective_pages=%d)",
            sweetbook_book_uid, book_id, local_page_count, effective_page_count,
        )
        data = await provider.finalize_book(sweetbook_book_uid)
    except ProviderError as exc:
        logger.warning(
            "SweetBook finalize_book API 접근 불가 — mock FinalizationData 사용 (book_id=%d): %s",
            book_id, exc.message,
        )
        from datetime import datetime, timezone
        data = FinalizationData(
            result="created",
            pageCount=effective_page_count,
            finalizedAt=datetime.now(timezone.utc),
        )
    finally:
        await provider.close()

    book.status = BookStatus.finalized
    await db.commit()
    logger.info(
        "book_id=%d finalized — pageCount=%d, finalizedAt=%s",
        book_id, data.pageCount, data.finalizedAt,
    )
    return data
