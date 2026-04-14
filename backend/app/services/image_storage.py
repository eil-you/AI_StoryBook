import asyncio
import uuid
from functools import partial

import boto3
import httpx

from app.core.config import get_settings


def _get_s3_client():
    settings = get_settings()
    return boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )


async def download_and_save(url: str) -> str:
    """DALL-E URL에서 이미지를 다운로드하여 S3에 저장하고 퍼블릭 URL을 반환합니다.

    Returns:
        S3 퍼블릭 URL (예: https://bucket.s3.ap-northeast-2.amazonaws.com/story-images/abc123.png)
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        image_bytes = response.content

    settings = get_settings()
    key = f"story-images/{uuid.uuid4().hex}.png"

    s3 = _get_s3_client()
    upload = partial(
        s3.put_object,
        Bucket=settings.AWS_S3_BUCKET,
        Key=key,
        Body=image_bytes,
        ContentType="image/png",
    )
    await asyncio.to_thread(upload)

    return f"https://{settings.AWS_S3_BUCKET}.s3.{settings.AWS_REGION}.amazonaws.com/{key}"
