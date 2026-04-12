"""Tests for the story generation API.

Covers:
  1. Success (201)  — valid prompt returns the created book object.
  2. Validation (422) — prompt shorter than 10 characters is rejected.
  3. AI error (502)  — StoryGenerationError propagates as 502 ERR002.
  4. Soft-delete (404) — fetching a soft-deleted story returns 404 ERR001.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.services.ai_service import AIService, StoryGenerationError

_GENERATE_URL = "/api/v1/stories/generate"

_PROMPT = "A brave little rabbit discovers a hidden waterfall in the magic forest"


def _story_url(book_id: int) -> str:
    return f"/api/v1/stories/{book_id}"

_MOCK_STORY = {
    "title": "The Magic Forest",
    "pages": [
        "Once upon a time in a magical forest, there lived a brave rabbit named Pip.",
        "One morning, Pip decided to explore the part of the forest no one dared to enter.",
        "After hopping through tall ferns, Pip heard the sound of rushing water.",
        "Hidden behind a curtain of ivy was the most beautiful waterfall Pip had ever seen.",
        "Pip raced back to tell the other animals, and together they made it their secret place.",
    ],
}


@pytest.fixture
def mock_ai() -> AsyncMock:
    with patch.object(AIService, "generate_story", new_callable=AsyncMock) as m:
        m.return_value = _MOCK_STORY
        yield m


# ===========================================================================
# Success — 201
# ===========================================================================


def test_generate_story_returns_201_with_full_body(client: TestClient, mock_ai: AsyncMock):
    """Valid title and prompt (≥10 chars) → 201 with the created book object."""
    resp = client.post(_GENERATE_URL, json={"prompt_text": _PROMPT, "user_id": 1})

    assert resp.status_code == 201

    body = resp.json()
    # Top-level book fields
    assert isinstance(body["book_id"], int)
    assert body["title"] == _MOCK_STORY["title"]
    assert body["status"] == "completed"
    assert "created_at" in body
    assert "updated_at" in body

    # Pages match the mocked AI output
    assert len(body["pages"]) == len(_MOCK_STORY["pages"])
    first_page = body["pages"][0]
    assert first_page["page_number"] == 1
    assert first_page["text_content"] == _MOCK_STORY["pages"][0]
    assert "created_at" in first_page
    assert "updated_at" in first_page


# ===========================================================================
# Validation — 422
# ===========================================================================


def test_generate_story_422_when_prompt_too_short(client: TestClient):
    """Prompt shorter than 10 characters must be rejected with 422.

    StoryRequest enforces min_length=10 on prompt_text via Pydantic.
    No AI call should be made — FastAPI rejects the request before the handler runs.
    """
    resp = client.post(_GENERATE_URL, json={"prompt_text": "short", "user_id": 1})

    assert resp.status_code == 422
    errors = resp.json()["detail"]
    # Pydantic v2 returns a list of validation error objects.
    assert any("prompt_text" in str(e.get("loc", "")) for e in errors)


# ===========================================================================
# AI service error — 502 ERR002
# ===========================================================================


def test_generate_story_502_when_ai_raises(client: TestClient):
    """StoryGenerationError from the AI layer must surface as 502 with ERR002.

    The router catches StoryGenerationError and converts it to HTTPException(502).
    The response detail must carry code='ERR002' and include the original message.
    """
    with patch.object(
        AIService,
        "generate_story",
        new_callable=AsyncMock,
        side_effect=StoryGenerationError("OpenAI timed out"),
    ):
        resp = client.post(_GENERATE_URL, json={"prompt_text": _PROMPT, "user_id": 1})

    assert resp.status_code == 502
    detail = resp.json()["detail"]
    assert detail["code"] == "ERR002"
    assert "OpenAI timed out" in detail["message"]


# ===========================================================================
# Soft-delete — 404 ERR001
# ===========================================================================


def test_get_story_404_when_soft_deleted(client: TestClient, mock_ai: AsyncMock):
    """Fetching a story whose is_deleted flag is True must return 404 ERR001.

    Steps:
      1. Create a story (POST /generate).
      2. Soft-delete it (DELETE /{book_id}).
      3. Fetch it (GET /{book_id}) → expect 404 with code='ERR001'.
    """
    # 1. Create
    create_resp = client.post(_GENERATE_URL, json={"prompt_text": _PROMPT, "user_id": 1})
    assert create_resp.status_code == 201
    book_id = create_resp.json()["book_id"]

    # 2. Soft-delete
    delete_resp = client.delete(_story_url(book_id))
    assert delete_resp.status_code == 204

    # 3. Fetch — must be invisible now
    get_resp = client.get(_story_url(book_id))
    assert get_resp.status_code == 404
    detail = get_resp.json()["detail"]
    assert detail["code"] == "ERR001"
