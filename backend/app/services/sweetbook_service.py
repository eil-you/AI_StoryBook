"""
SweetBook publishing pipeline service.

Flow:
  1. Load Page rows from DB (ordered by page_number).
  2. Download each page's image from AWS S3 (parallel, boto3 in thread pool).
  3. Upload each image binary to POST /v1/images (parallel, httpx multipart).
  4. POST /v1/books/{book_uid}/contents for every page (parallel, form-urlencoded).
"""

import asyncio
import json
import logging
import os
from functools import partial

import boto3
import httpx
from botocore.exceptions import ClientError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.page import Page

logger = logging.getLogger(__name__)

_SWEETBOOK_BASE_URL = "https://api-sandbox.sweetbook.com/v1"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SweetBookPublishError(Exception):
    """Raised when any step of the SweetBook publishing pipeline fails."""


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


def _sync_download_from_s3(bucket: str, key: str) -> bytes:
    """Synchronous S3 download — intended to run inside ``asyncio.to_thread``."""
    s3 = boto3.client(
        "s3",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
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


async def _download_image(page: Page, bucket: str, region: str) -> tuple["Page", bytes]:
    """Return (page, image_bytes) after downloading from S3."""
    if not page.image_url:
        raise SweetBookPublishError(
            f"Page {page.page_number} has no image_url — cannot download from S3."
        )
    key = _parse_s3_key(page.image_url, bucket, region)
    logger.debug("Downloading S3 key %r for page %d", key, page.page_number)
    image_bytes: bytes = await asyncio.to_thread(
        partial(_sync_download_from_s3, bucket, key)
    )
    return page, image_bytes


# ---------------------------------------------------------------------------
# SweetBook image-upload helper  (POST /v1/images)
# ---------------------------------------------------------------------------


async def _upload_image_to_sweetbook(
    client: httpx.AsyncClient,
    page: "Page",
    image_bytes: bytes,
) -> tuple["Page", str]:
    """Upload *image_bytes* to ``POST /v1/images``.

    Returns ``(page, image_id)`` where *image_id* is the identifier
    returned by the SweetBook API.
    """
    filename = f"page_{page.page_number}.png"
    logger.debug("Uploading image for page %d (%d bytes)", page.page_number, len(image_bytes))
    try:
        response = await client.post(
            "/images",
            files={"file": (filename, image_bytes, "image/png")},
        )
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise SweetBookPublishError(
            f"Timeout uploading image for page {page.page_number} to SweetBook."
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise SweetBookPublishError(
            f"SweetBook image upload failed for page {page.page_number}: "
            f"HTTP {exc.response.status_code} — {exc.response.text}"
        ) from exc
    except httpx.RequestError as exc:
        raise SweetBookPublishError(
            f"Network error uploading image for page {page.page_number}: {exc}"
        ) from exc

    body = response.json()
    # Accepts either {"data": {"imageId": "..."}} or a flat {"imageId": "..."}
    image_id: str | None = (
        body.get("data", {}).get("imageId")
        or body.get("imageId")
    )
    if not image_id:
        raise SweetBookPublishError(
            f"SweetBook /v1/images returned no imageId for page {page.page_number}. "
            f"Response: {body}"
        )
    return page, image_id


# ---------------------------------------------------------------------------
# SweetBook content helper  (POST /v1/books/{book_uid}/contents)
# ---------------------------------------------------------------------------


async def _add_page_content(
    client: httpx.AsyncClient,
    book_uid: str,
    template_uid: str,
    page: "Page",
    image_id: str,
) -> dict:
    """Submit one page's content to ``POST /v1/books/{book_uid}/contents``.

    The *parameters* value is serialised as a JSON string and the entire
    request is sent as ``application/x-www-form-urlencoded``.
    """
    parameters = json.dumps(
        {"imageId": image_id, "text": page.text_content or ""},
        ensure_ascii=False,
    )
    logger.debug(
        "Adding content for page %d to SweetBook book %r", page.page_number, book_uid
    )
    try:
        response = await client.post(
            f"/books/{book_uid}/contents",
            data={"templateUid": template_uid, "parameters": parameters},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise SweetBookPublishError(
            f"Timeout adding content for page {page.page_number} to SweetBook book {book_uid!r}."
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise SweetBookPublishError(
            f"SweetBook /contents failed for page {page.page_number}: "
            f"HTTP {exc.response.status_code} — {exc.response.text}"
        ) from exc
    except httpx.RequestError as exc:
        raise SweetBookPublishError(
            f"Network error adding content for page {page.page_number}: {exc}"
        ) from exc

    return response.json()


# ---------------------------------------------------------------------------
# Combined per-page pipeline step
# ---------------------------------------------------------------------------


async def _process_page(
    page: "Page",
    bucket: str,
    region: str,
    client: httpx.AsyncClient,
    book_uid: str,
    template_uid: str,
) -> dict:
    """Full pipeline for one page: S3 download → SweetBook upload → content API."""
    _, image_bytes = await _download_image(page, bucket, region)
    _, image_id = await _upload_image_to_sweetbook(client, page, image_bytes)
    return await _add_page_content(client, book_uid, template_uid, page, image_id)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def publish_book_to_sweetbook(
    *,
    book_id: int,
    sweetbook_book_uid: str,
    template_uid: str,
    db: AsyncSession,
) -> list[dict]:
    """Publish all pages of *book_id* to an existing SweetBook DRAFT book.

    Steps performed (pages processed in parallel):
      1. Fetch ``Page`` rows from the database for *book_id*.
      2. Download each page image from AWS S3.
      3. Upload each image to ``POST /v1/images`` and collect the ``imageId``.
      4. Call ``POST /v1/books/{sweetbook_book_uid}/contents`` for every page
         with ``parameters`` as a JSON string in a form-urlencoded body.

    Args:
        book_id: Primary key of the local ``Book`` record.
        sweetbook_book_uid: UID of the corresponding DRAFT book in SweetBook.
        template_uid: Content template UID to use for every interior page.
        db: Active async database session.

    Returns:
        List of raw JSON response dicts from the SweetBook contents API,
        one entry per page (sorted by page_number).

    Raises:
        SweetBookPublishError: On any S3, network, or API error.
    """
    settings = get_settings()

    # 1. Load pages
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

    async with httpx.AsyncClient(
        base_url=_SWEETBOOK_BASE_URL,
        headers={"Authorization": f"Bearer {settings.SWEETBOOK_API_KEY}"},
        timeout=60.0,
    ) as client:
        # 2–4. Run all pages concurrently
        tasks = [
            _process_page(
                page,
                settings.AWS_S3_BUCKET,
                settings.AWS_REGION,
                client,
                sweetbook_book_uid,
                template_uid,
            )
            for page in pages
        ]
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)

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

    content_responses: list[dict] = [o for o in outcomes if isinstance(o, dict)]
    logger.info(
        "Successfully published %d pages of book_id=%d to SweetBook.",
        len(content_responses),
        book_id,
    )
    return content_responses
