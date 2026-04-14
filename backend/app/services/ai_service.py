import logging

from openai import APIStatusError, APITimeoutError, AsyncOpenAI, RateLimitError
from pydantic import BaseModel

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a creative children's book author.
When given story details, generate an engaging and age-appropriate story.
You MUST respond with valid JSON only, in this exact format:
{
  "title": "Story Title Here",
  "pages": [
    "Paragraph 1 text...",
    "Paragraph 2 text...",
    "Paragraph 3 text...",
    "Paragraph 4 text...",
    "Paragraph 5 text...",
    "Paragraph 6 text..."
  ]
}
The pages array must have exactly 5 or 6 paragraphs. Each paragraph becomes one page of the book.
Do not include any text outside the JSON object."""


class StoryData(BaseModel):
    title: str
    pages: list[str]


class StoryGenerationError(Exception):
    pass


class AIService:
    def __init__(self) -> None:
        settings = get_settings()
        self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self._model = settings.OPENAI_MODEL

    async def generate_story(
        self,
        character_name: str,
        character_age: int,
        genre: str,
        background: str,
        education: str,
    ) -> StoryData:
        """주어진 캐릭터 정보로 어린이 동화를 생성합니다.

        Raises:
            StoryGenerationError: AI 호출 또는 응답 파싱 실패 시.
        """
        prompt = self._build_prompt(character_name, character_age, genre, background, education)
        raw = await self._call_openai(prompt)
        return self._parse_response(raw)

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
                max_tokens=2000,
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

    def _parse_response(self, raw: str) -> StoryData:
        try:
            story = StoryData.model_validate_json(raw)
        except Exception as e:
            logger.error("Failed to parse AI response: %s", raw)
            raise StoryGenerationError("Received malformed response from AI service.") from e

        if not (5 <= len(story.pages) <= 6):
            raise StoryGenerationError(f"Expected 5-6 pages, got {len(story.pages)}.")

        return story
