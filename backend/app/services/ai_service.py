import json
import logging
from typing import TypedDict

import httpx
from openai import APIStatusError, APITimeoutError, AsyncOpenAI, RateLimitError

from app.core.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a creative children's book author.
When given a story prompt, generate an engaging and age-appropriate story.
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


class StoryData(TypedDict):
    title: str
    pages: list[str]


class StoryGenerationError(Exception):
    pass


class AIService:
    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=httpx.Timeout(60.0, connect=10.0),
        )

    async def generate_story(self, prompt_text: str) -> StoryData:
        """Call the OpenAI API and return structured story data.

        Args:
            prompt_text: User-supplied theme or story idea.

        Returns:
            StoryData with a title and a list of 5–6 page paragraphs.

        Raises:
            StoryGenerationError: For any AI service or parsing failure.
        """
        user_message = f"Write a children's story about: {prompt_text}"

        try:
            response = await self._client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                response_format={"type": "json_object"},
                temperature=0.8,
                max_tokens=2000,
            )
        except APITimeoutError as e:
            logger.error("OpenAI request timed out: %s", e)
            raise StoryGenerationError(
                "Story generation timed out. Please try again."
            ) from e
        except RateLimitError as e:
            logger.error("OpenAI rate limit exceeded: %s", e)
            raise StoryGenerationError(
                "Service is temporarily busy. Please try again in a moment."
            ) from e
        except APIStatusError as e:
            logger.error("OpenAI API error (status=%s): %s", e.status_code, e)
            raise StoryGenerationError(
                f"Story generation failed with API error: {e.message}"
            ) from e

        raw_content = response.choices[0].message.content
        if not raw_content:
            raise StoryGenerationError("Received empty response from AI service.")

        try:
            data = json.loads(raw_content)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse AI response as JSON: %s", raw_content)
            raise StoryGenerationError(
                "Received malformed response from AI service."
            ) from e

        if "title" not in data or "pages" not in data:
            raise StoryGenerationError(
                "AI response missing required 'title' or 'pages' fields."
            )

        if not isinstance(data["pages"], list) or not (5 <= len(data["pages"]) <= 6):
            raise StoryGenerationError(
                f"Expected 5-6 pages, got {len(data.get('pages', []))}."
            )

        return StoryData(title=data["title"], pages=data["pages"])
