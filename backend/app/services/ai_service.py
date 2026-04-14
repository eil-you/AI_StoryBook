import asyncio
import logging

from openai import APIStatusError, APITimeoutError, AsyncOpenAI, RateLimitError
from pydantic import BaseModel

from app.core.config import get_settings
from app.services.image_storage import download_and_save

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a creative children's book author.
When given story details, generate an engaging and age-appropriate story.
You MUST respond with valid JSON only, in this exact format:
{
  "title": "Story Title Here",
  "pages": [
    "Paragraph 1 text...",
    "Paragraph 2 text...",
    ...
  ]
}
The pages array MUST have between 24 and 30 paragraphs. This is a hard requirement — do NOT return fewer than 24 paragraphs under any circumstances.
Keep each paragraph short (2-4 sentences) so the story flows naturally page by page.
Do not include any text outside the JSON object."""

_IMAGE_STYLE = (
    "anime-style children's book illustration, vibrant and colorful, "
    "cute anime art style, expressive characters, detailed background, "
    "warm lighting, soft cel shading, age-appropriate, no text"
)


class PageData(BaseModel):
    text: str
    image_url: str


class StoryData(BaseModel):
    title: str
    cover_image_url: str
    pages: list[PageData]


class StoryGenerationError(Exception):
    pass


class AIService:
    def __init__(self) -> None:
        settings = get_settings()
        self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self._model = settings.OPENAI_MODEL
        self._image_model = settings.OPENAI_IMAGE_MODEL

    async def generate_story(
        self,
        character_name: str,
        character_age: int,
        genre: str,
        background: str,
        education: str,
    ) -> StoryData:
        """캐릭터 정보로 어린이 동화와 각 페이지 이미지를 생성합니다.

        Raises:
            StoryGenerationError: AI 호출 또는 응답 파싱 실패 시.
        """
        prompt = self._build_prompt(character_name, character_age, genre, background, education)

        title, page_texts = None, None
        for attempt in range(3):
            raw = await self._call_openai(prompt)
            try:
                title, page_texts = self._parse_story(raw)
                break
            except StoryGenerationError as exc:
                if attempt == 2:
                    raise
                logger.warning("Story parse failed (attempt %d/3): %s — retrying", attempt + 1, exc)

        all_urls = await asyncio.gather(
            self._generate_cover_image(
                title=title,
                character_name=character_name,
                background=background,
                genre=genre,
            ),
            *[
                self._generate_image(
                    page_text=text,
                    character_name=character_name,
                    background=background,
                    genre=genre,
                )
                for text in page_texts
            ]
        )

        cover_image_url = all_urls[0]
        page_image_urls = all_urls[1:]

        return StoryData(
            title=title,
            cover_image_url=cover_image_url,
            pages=[
                PageData(text=text, image_url=url)
                for text, url in zip(page_texts, page_image_urls)
            ],
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_prompt(
        self,
        character_name: str,
        character_age: int,
        genre: str,
        background: str,
        education: str,
    ) -> str:
        return (
            f"Write a children's story with the following details:\n"
            f"- Main character name: {character_name}\n"
            f"- Main character age: {character_age}\n"
            f"- Genre: {genre}\n"
            f"- Background/Setting: {background}\n"
            f"- Educational value to convey: {education}"
        )

    async def _call_openai(self, user_message: str) -> str:
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                response_format={"type": "json_object"},
                temperature=0.8,
                max_tokens=4000,
            )
        except APITimeoutError as e:
            logger.error("OpenAI request timed out: %s", e)
            raise StoryGenerationError("Story generation timed out. Please try again.") from e
        except RateLimitError as e:
            logger.error("OpenAI rate limit exceeded: %s", e)
            raise StoryGenerationError("Service is temporarily busy. Please try again in a moment.") from e
        except APIStatusError as e:
            logger.error("OpenAI API error (status=%s): %s", e.status_code, e)
            raise StoryGenerationError(f"Story generation failed with API error: {e.message}") from e

        content = response.choices[0].message.content
        if not content:
            raise StoryGenerationError("Received empty response from AI service.")
        return content

    def _parse_story(self, raw: str) -> tuple[str, list[str]]:
        try:
            class _RawStory(BaseModel):
                title: str
                pages: list[str]

            story = _RawStory.model_validate_json(raw)
        except Exception as e:
            logger.error("Failed to parse AI story response: %s", raw)
            raise StoryGenerationError("Received malformed response from AI service.") from e

        if not (24 <= len(story.pages) <= 30):
            raise StoryGenerationError(f"Expected 24–30 pages, got {len(story.pages)}.")

        return story.title, story.pages

    async def _generate_cover_image(
        self,
        title: str,
        character_name: str,
        background: str,
        genre: str,
    ) -> str:
        image_prompt = (
            f"{_IMAGE_STYLE}, {genre} children's book cover, "
            f"{background} setting, main character named {character_name}, "
            f"book title theme: {title}, dramatic and eye-catching composition"
        )
        try:
            response = await self._client.images.generate(
                model=self._image_model,
                prompt=image_prompt,
                size="1024x1024",
                quality="standard",
                n=1,
            )
        except APITimeoutError as e:
            logger.error("Cover image generation timed out: %s", e)
            raise StoryGenerationError("Cover image generation timed out. Please try again.") from e
        except RateLimitError as e:
            logger.error("Cover image generation rate limit exceeded: %s", e)
            raise StoryGenerationError("Service is temporarily busy. Please try again in a moment.") from e
        except APIStatusError as e:
            logger.error("Cover image generation API error (status=%s): %s", e.status_code, e)
            raise StoryGenerationError(f"Cover image generation failed: {e.message}") from e

        dalle_url = response.data[0].url
        return await download_and_save(dalle_url)

    async def _generate_image(
        self,
        page_text: str,
        character_name: str,
        background: str,
        genre: str,
    ) -> str:
        image_prompt = (
            f"{_IMAGE_STYLE}, {genre} story set in {background}, "
            f"main character named {character_name}, scene: {page_text[:200]}"
        )
        await asyncio.sleep(13)
        try:
            response = await self._client.images.generate(
                model=self._image_model,
                prompt=image_prompt,
                size="1024x1024",
                quality="standard",
                n=1,
            )
        except APITimeoutError as e:
            logger.error("Image generation timed out: %s", e)
            raise StoryGenerationError("Image generation timed out. Please try again.") from e
        except RateLimitError as e:
            logger.error("Image generation rate limit exceeded: %s", e)
            raise StoryGenerationError("Service is temporarily busy. Please try again in a moment.") from e
        except APIStatusError as e:
            logger.error("Image generation API error (status=%s): %s", e.status_code, e)
            raise StoryGenerationError(f"Image generation failed: {e.message}") from e

        dalle_url = response.data[0].url
        return await download_and_save(dalle_url)
