import random
import uuid
from pathlib import Path

import httpx

from app.core.config import get_settings

# backend/static/story-images/ 에 저장 (생성된 이미지)
_STATIC_DIR = Path(__file__).resolve().parents[2] / "static" / "story-images"
_STATIC_DIR.mkdir(parents=True, exist_ok=True)

# 테스트용 샘플 이미지 폴더
_TEST_IMAGES_DIR = Path(__file__).resolve().parents[2] / "static" / "images"


def _get_test_image_url() -> str:
    """테스트 모드: static/images/ 폴더의 PNG 파일 중 랜덤으로 하나를 반환합니다."""
    images = list(_TEST_IMAGES_DIR.glob("*.png")) + list(_TEST_IMAGES_DIR.glob("*.jpg"))
    if not images:
        return "https://placehold.co/1024x1024/FFF9C4/A0522D?text=No+Image"
    chosen = random.choice(images)
    return f"/static/images/{chosen.name}"


async def download_and_save(url: str) -> str:
    """이미지를 다운로드하여 로컬 static 폴더에 저장하고 서빙 경로를 반환합니다.

    IMAGE_TEST_MODE=True 이면 DALL-E 호출 없이 더미 이미지 URL을 즉시 반환합니다.

    Returns:
        - 테스트 모드: Unsplash 더미 이미지 URL (랜덤)
        - 프로덕션: /static/story-images/<uuid>.png
    """
    settings = get_settings()

    if settings.IMAGE_TEST_MODE:
        return _get_test_image_url()

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        image_bytes = response.content

    filename = f"{uuid.uuid4().hex}.png"
    (_STATIC_DIR / filename).write_bytes(image_bytes)

    return f"/static/story-images/{filename}"
