import asyncio
import logging

from openai import APIStatusError, APITimeoutError, AsyncOpenAI, RateLimitError
from pydantic import BaseModel

from app.core.config import get_settings
from app.services.image_storage import download_and_save

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a creative children's book author specializing in age-appropriate storytelling.
When given story details, generate an engaging story carefully calibrated to the child's age level.

AGE-APPROPRIATE WRITING GUIDELINES:
- Ages 1-3 (Toddler): Very simple sentences (3-5 words each). Repetitive patterns. Basic concepts only. Onomatopoeia and sound words. Familiar objects and animals.
- Ages 4-6 (Preschool): Simple sentences (5-8 words). Gentle adventures. Emotions and friendships. Easy vocabulary. Rhymes welcome.
- Ages 7-9 (Early reader): Moderate complexity. Short paragraphs. Light problem-solving. Expanding vocabulary with context clues.
- Ages 10-13 (Middle grade): Richer descriptions. Character development. Moral dilemmas. More sophisticated vocabulary.
- Ages 14+ (Young adult): Complex narratives. Nuanced emotions. Challenging vocabulary. Deeper themes.

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
The title and all page text MUST be written in Korean.
Do not include any text outside the JSON object."""

_IMAGE_STYLE = (
    "children's picture book illustration, soft watercolor style, "
    "warm and cozy atmosphere, pastel colors, gentle brushstrokes, "
    "age-appropriate for toddlers, no text, no words, wholesome and cheerful"
)

_DUMMY_IMAGE_URL = "https://placehold.co/1024x1024/FFF9C4/A0522D?text=Story+Page"

_PROMPT_TRANSLATOR_SYSTEM = """You are a DALL-E 3 prompt engineer specializing in children's picture books.
Your job is to convert story scene descriptions into safe, policy-compliant English image prompts.

Rules:
- Output ONLY the image prompt in English, nothing else.
- NEVER include character names, real names, or any proper nouns.
- Describe the scene visually and generically: use "a cheerful young child" not a name.
- Keep it wholesome, warm, and age-appropriate (target audience: toddlers/preschoolers).
- Focus on visual elements: setting, mood, colors, actions.
- Avoid any ambiguous, violent, or scary content.
- Keep the prompt under 150 words.
- Start with: "A warm and cheerful children's book illustration of"
"""


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
        # DALL-E rate limit: 동시 이미지 생성을 3개로 제한
        self._image_semaphore = asyncio.Semaphore(3)

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
        # 나이대별 독서 수준 설명 추가
        if character_age <= 3:
            age_guidance = "toddler level (ages 1-3): extremely simple words, very short sentences, lots of repetition"
        elif character_age <= 6:
            age_guidance = "preschool level (ages 4-6): simple sentences, gentle story, easy vocabulary"
        elif character_age <= 9:
            age_guidance = "early reader level (ages 7-9): moderate sentences, light adventure, growing vocabulary"
        elif character_age <= 13:
            age_guidance = "middle grade level (ages 10-13): richer descriptions, character growth, varied vocabulary"
        else:
            age_guidance = "young adult level (ages 14+): complex narrative, nuanced emotions, sophisticated vocabulary"

        return (
            f"Write a children's story in Korean with the following details:\n"
            f"- Main character name: {character_name}\n"
            f"- Main character age: {character_age} years old\n"
            f"- Reading level: {age_guidance}\n"
            f"- Genre: {genre}\n"
            f"- Background/Setting: {background}\n"
            f"- Educational value to convey: {education}\n\n"
            f"IMPORTANT: Adjust ALL vocabulary, sentence length, and story complexity to exactly match the {character_age}-year-old reading level described above."
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

    async def _translate_to_image_prompt(
        self,
        scene_description: str,
        background: str,
        genre: str,
    ) -> str:
        """한글 장면 묘사를 DALL-E 안전 정책을 준수하는 영문 프롬프트로 변환합니다.

        GPT에게 번역을 맡겨 한글 텍스트가 DALL-E에 직접 전달되지 않도록 합니다.
        변환 실패 시 기본 안전 프롬프트를 반환합니다.
        """
        user_message = (
            f"Scene (Korean): {scene_description}\n"
            f"Setting: {background}\n"
            f"Genre: {genre}\n"
            "Convert this into a safe DALL-E 3 image prompt."
        )
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": _PROMPT_TRANSLATOR_SYSTEM},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.5,
                max_tokens=200,
            )
            translated = response.choices[0].message.content or ""
            return translated.strip()
        except Exception as exc:
            logger.warning("Prompt translation failed, using fallback prompt: %s", exc)
            return (
                f"A warm and cheerful children's book illustration of "
                f"a happy young child on an adventure in a {background} setting, "
                f"{genre} style, bright and colorful"
            )

    async def _call_dalle(self, prompt: str) -> str:
        """DALL-E 이미지를 생성하고 URL을 반환합니다.

        IMAGE_TEST_MODE=True 이면 DALL-E를 호출하지 않고 즉시 더미 URL을 반환합니다.
        세마포어로 동시 호출을 3개로 제한해 ConnectTimeout을 방지합니다.
        400 (content_policy_violation) 또는 500 (server error) 발생 시
        시스템이 멈추지 않도록 더미 이미지 URL을 반환합니다.
        """
        from app.core.config import get_settings
        from app.services.image_storage import _get_test_image_url

        if get_settings().IMAGE_TEST_MODE:
            logger.debug("IMAGE_TEST_MODE enabled — skipping DALL-E call")
            return _get_test_image_url()

        full_prompt = f"{_IMAGE_STYLE}. {prompt}"
        async with self._image_semaphore:
            try:
                response = await self._client.images.generate(
                    model=self._image_model,
                    prompt=full_prompt,
                    size="1024x1024",
                    quality="standard",
                    n=1,
                )
                dalle_url = response.data[0].url
                if not dalle_url:
                    logger.error("DALL-E returned no URL in response — using dummy image")
                    return _DUMMY_IMAGE_URL
                return await download_and_save(dalle_url)
            except APIStatusError as e:
                if e.status_code == 400:
                    logger.warning(
                        "DALL-E content policy violation (400) — using dummy image. prompt=%r",
                        prompt[:100],
                    )
                else:
                    logger.error(
                        "DALL-E API error (status=%s) — using dummy image: %s",
                        e.status_code,
                        e,
                    )
                return _DUMMY_IMAGE_URL
            except (APITimeoutError, RateLimitError) as e:
                logger.error("DALL-E unavailable (%s) — using dummy image: %s", type(e).__name__, e)
                return _DUMMY_IMAGE_URL

    async def _generate_cover_image(
        self,
        title: str,
        character_name: str,
        background: str,
        genre: str,
    ) -> str:
        # test mode 면 번역 GPT 호출도 스킵
        return await self._call_dalle(
            f"Book cover for a {genre} story, {background} setting, title: {title}"
        )

    async def _generate_image(
        self,
        page_text: str,
        character_name: str,
        background: str,
        genre: str,
    ) -> str:
        # test mode 면 번역 GPT 호출도 스킵
        from app.core.config import get_settings

        if not get_settings().IMAGE_TEST_MODE:
            page_text = await self._translate_to_image_prompt(page_text, background, genre)

        return await self._call_dalle(page_text)
