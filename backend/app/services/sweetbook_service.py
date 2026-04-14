"""
SweetBook publishing pipeline service.

Flow:
  1. Load Page rows from DB (ordered by page_number).
  2. Download each page's image from AWS S3 (parallel, boto3 in thread pool).
  3. POST /v1/books/{book_uid}/contents for every page in parallel,
     uploading the image as multipart/form-data via SweetBookProvider.
"""

import asyncio
import logging
from functools import partial

import boto3
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
_PAGE_MAX = 24
_PAGE_INCREMENT = 2


def _validate_page_count(page_count: int) -> None:
    """Raise ``SweetBookPublishError`` if *page_count* violates BookSpec rules.

    Rules (pageMin=24, pageMax=24, pageIncrement=2):
      - page_count >= _PAGE_MIN
      - page_count <= _PAGE_MAX
      - (page_count - _PAGE_MIN) % _PAGE_INCREMENT == 0
    """
    if page_count < _PAGE_MIN:
        raise SweetBookPublishError(
            f"Page count {page_count} is below the minimum of {_PAGE_MIN}."
        )
    if page_count > _PAGE_MAX:
        raise SweetBookPublishError(
            f"Page count {page_count} exceeds the maximum of {_PAGE_MAX}."
        )
    if (page_count - _PAGE_MIN) % _PAGE_INCREMENT != 0:
        raise SweetBookPublishError(
            f"Page count {page_count} is not a valid increment "
            f"(must be a multiple of {_PAGE_INCREMENT} from {_PAGE_MIN})."
        )


# ---------------------------------------------------------------------------
# S3 helpers
# ---------------------------------------------------------------------------


def _parse_s3_key(image_url: str, bucket: str, region: str) -> str:
    """Extract the S3 object key from a full public S3 URL.

    Expected format:
        https://{bucket}.s3.{region}.amazonaws.com/{key}
    """
    prefix = f"https://{bucket}.s3.{region}.amazonaws.com/"
    if not image_url.startswith(prefix):
        raise SweetBookPublishError(
            f"Unexpected S3 URL format (cannot extract key): {image_url!r}"
        )
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


async def _download_image(
    page: Page,
    bucket: str,
    region: str,
    aws_access_key_id: str,
    aws_secret_access_key: str,
) -> tuple[Page, bytes]:
    """Return (page, image_bytes) after downloading from S3."""
    if not page.image_url:
        raise SweetBookPublishError(
            f"Page {page.page_number} has no image_url — cannot download from S3."
        )
    key = _parse_s3_key(page.image_url, bucket, region)
    logger.debug("Downloading S3 key %r for page %d", key, page.page_number)
    image_bytes: bytes = await asyncio.to_thread(
        partial(_sync_download_from_s3, bucket, key, aws_access_key_id, aws_secret_access_key)
    )
    return page, image_bytes


# ---------------------------------------------------------------------------
# Combined per-page pipeline step
# ---------------------------------------------------------------------------


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
    """Full pipeline for one page: S3 download → SweetBook contents API.

    The image is sent as a multipart file upload alongside the text so that
    no separate /images pre-upload step is required.
    """
    _, image_bytes = await _download_image(page, bucket, region, aws_access_key_id, aws_secret_access_key)
    filename = f"page_{page.page_number}.png"
    logger.debug("Adding content for page %d to SweetBook book %r", page.page_number, book_uid)

    # extra_parameters 먼저 깔고, 페이지 텍스트로 덮어씀
    parameters = {**extra_parameters, "text": page.text_content or ""}

    try:
        return await provider.add_content(
            book_uid=book_uid,
            template_uid=template_uid,
            parameters=parameters,
            upload_files={image_field: (filename, image_bytes, "image/png")},
        )
    except ProviderError as exc:
        raise SweetBookPublishError(
            f"SweetBook API error for page {page.page_number}: {exc.message}"
        ) from exc


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def _get_template_fields(
    provider: SweetBookProvider,
    template_uid: str,
) -> tuple[str, str | None]:
    """Fetch the template once and return (image_field, text_field).

    *image_field* is required — raises ``SweetBookPublishError`` if absent.
    *text_field* is optional — returns ``None`` if the template has no text parameter.
    """
    try:
        detail = await provider.get_template(template_uid)
    except ProviderError as exc:
        raise SweetBookPublishError(
            f"Failed to fetch template {template_uid!r}: {exc.message}"
        ) from exc

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


async def finalize_sweetbook_book(
    *,
    book_id: int,
    sweetbook_book_uid: str,
    db: AsyncSession,
) -> FinalizationData:
    """Call the SweetBook finalization endpoint and update the local book status.

    Transitions the SweetBook DRAFT book to FINALIZED, then marks the local
    ``Book`` record as ``finalized``.  The call is idempotent — calling it on
    an already-finalized book succeeds without error.

    Args:
        book_id: Primary key of the local ``Book`` record.
        sweetbook_book_uid: UID of the corresponding SweetBook book.
        db: Active async database session.

    Returns:
        ``FinalizationData`` from the SweetBook API.

    Raises:
        SweetBookPublishError: If the book is not found or the API call fails.
    """
    settings = get_settings()

    book_result = await db.execute(select(Book).where(Book.id == book_id))
    book: Book | None = book_result.scalar_one_or_none()
    if not book:
        raise SweetBookPublishError(f"Book not found: book_id={book_id}.")

    page_result = await db.execute(
        select(Page).where(Page.book_id == book_id)
    )
    page_count = len(page_result.scalars().all())
    _validate_page_count(page_count)

    provider = SweetBookProvider(api_key=settings.SWEETBOOK_API_KEY)
    try:
        logger.info(
            "Finalizing SweetBook book %r (local book_id=%d, pages=%d)",
            sweetbook_book_uid,
            book_id,
            page_count,
        )
        data = await provider.finalize_book(sweetbook_book_uid)
    except ProviderError as exc:
        raise SweetBookPublishError(
            f"SweetBook finalization API error: {exc.message}"
        ) from exc
    finally:
        await provider.close()

    book.status = BookStatus.finalized
    await db.commit()
    logger.info(
        "book_id=%d finalized — pageCount=%d, finalizedAt=%s",
        book_id,
        data.pageCount,
        data.finalizedAt,
    )
    return data


async def publish_book_to_sweetbook(
    *,
    book_id: int,
    sweetbook_book_uid: str,
    cover_template_uid: str,
    content_template_uid: str,
    extra_parameters: dict[str, str] | None = None,
    db: AsyncSession,
) -> list[ContentData]:
    """Publish all pages of *book_id* to an existing SweetBook DRAFT book.

    Steps performed:
      1. Fetch ``Book`` and ``Page`` rows from the database for *book_id*.
      2. Add the cover (POST /v1/books/{uid}/cover) using the book's cover_image_url.
      3. Fetch templates to resolve image field names automatically.
      4. Download each page image from AWS S3 and POST /v1/books/{uid}/contents in parallel.

    Args:
        book_id: Primary key of the local ``Book`` record.
        sweetbook_book_uid: UID of the corresponding DRAFT book in SweetBook.
        cover_template_uid: Cover template UID.
        content_template_uid: Content template UID for every interior page.
        extra_parameters: Extra template parameters applied to every page (e.g. childName).
        db: Active async database session.

    Returns:
        List of ``ContentData`` objects from the SweetBook contents API,
        one entry per page (sorted by page_number).

    Raises:
        SweetBookPublishError: On any S3, network, or API error.
    """
    settings = get_settings()

    # 1. Load book + pages from DB
    book_result = await db.execute(select(Book).where(Book.id == book_id))
    book: Book | None = book_result.scalar_one_or_none()
    if not book:
        raise SweetBookPublishError(f"Book not found: book_id={book_id}.")

    result = await db.execute(
        select(Page)
        .where(Page.book_id == book_id)
        .order_by(Page.page_number)
    )
    pages: list[Page] = list(result.scalars().all())

    if not pages:
        raise SweetBookPublishError(
            f"No pages found for book_id={book_id}. Cannot publish."
        )

    logger.info(
        "Publishing book_id=%d (%d pages) to SweetBook book %r",
        book_id,
        len(pages),
        sweetbook_book_uid,
    )

    provider = SweetBookProvider(api_key=settings.SWEETBOOK_API_KEY)
    try:
        # 2. Add cover
        if not book.cover_image_url:
            raise SweetBookPublishError(
                f"book_id={book_id} has no cover_image_url. Generate the story first."
            )

        (cover_image_field, cover_text_field), (image_field, _) = await asyncio.gather(
            _get_template_fields(provider, cover_template_uid),
            _get_template_fields(provider, content_template_uid),
        )
        logger.info("Downloading cover image from S3 for book_id=%d", book_id)
        cover_key = _parse_s3_key(book.cover_image_url, settings.AWS_S3_BUCKET, settings.AWS_REGION)
        cover_bytes: bytes = await asyncio.to_thread(
            partial(
                _sync_download_from_s3,
                settings.AWS_S3_BUCKET,
                cover_key,
                settings.AWS_ACCESS_KEY_ID,
                settings.AWS_SECRET_ACCESS_KEY,
            )
        )

        cover_parameters = {cover_text_field: book.title} if cover_text_field else None
        try:
            await provider.add_cover(
                book_uid=sweetbook_book_uid,
                template_uid=cover_template_uid,
                parameters=cover_parameters,
                upload_files={cover_image_field: ("cover.png", cover_bytes, "image/png")},
            )
            logger.info("Cover added to SweetBook book %r with title %r", sweetbook_book_uid, book.title)
        except ProviderError as exc:
            raise SweetBookPublishError(
                f"SweetBook cover API error: {exc.message}"
            ) from exc

        # 3–4. Upload pages concurrently
        logger.info("Using image field %r from template %r", image_field, content_template_uid)

        tasks = [
            _process_page(
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
            for page in pages
        ]
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        await provider.close()

    # Collect all failed pages, then report them together
    failures = [
        (page, outcome)
        for page, outcome in zip(pages, outcomes)
        if isinstance(outcome, BaseException)
    ]
    if failures:
        detail = "; ".join(
            f"page {page.page_number}: {outcome}"
            for page, outcome in failures
        )
        raise SweetBookPublishError(
            f"{len(failures)}/{len(pages)} page(s) failed — {detail}"
        )

    content_responses: list[ContentData] = list(outcomes)
    logger.info(
        "Successfully published %d pages of book_id=%d to SweetBook.",
        len(content_responses),
        book_id,
    )
    return content_responses
