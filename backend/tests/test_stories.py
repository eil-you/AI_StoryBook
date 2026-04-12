"""Integration tests for the /api/v1/stories endpoints.

OpenAI calls are replaced by a local mock so no tokens are consumed.
All tests run against an isolated SQLite test.db that is truncated between tests.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.services.ai_service import AIService

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------
_PROMPT = "A brave little rabbit discovers a hidden waterfall in the magic forest"

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

_GENERATE_URL = "/api/v1/stories/generate"
_LIST_URL = "/api/v1/stories"
_SEARCH_URL = "/api/v1/stories/search"


def _story_url(book_id: int) -> str:
    return f"/api/v1/stories/{book_id}"


# ---------------------------------------------------------------------------
# Fixture: mock out AIService.generate_story for every test that needs it
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_ai() -> AsyncMock:
    with patch.object(AIService, "generate_story", new_callable=AsyncMock) as m:
        m.return_value = _MOCK_STORY
        yield m


# ---------------------------------------------------------------------------
# Helper: POST /generate and return the parsed JSON body
# ---------------------------------------------------------------------------
def _create_story(client: TestClient, prompt: str = _PROMPT) -> dict:
    resp = client.post(_GENERATE_URL, json={"prompt_text": prompt, "user_id": 1})
    assert resp.status_code == 201, resp.text
    return resp.json()


# ===========================================================================
# POST /api/v1/stories/generate
# ===========================================================================


def test_create_story_returns_201_with_full_body(client, mock_ai):
    resp = client.post(_GENERATE_URL, json={"prompt_text": _PROMPT, "user_id": 1})

    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == _MOCK_STORY["title"]
    assert body["status"] == "completed"
    assert isinstance(body["book_id"], int)
    assert len(body["pages"]) == len(_MOCK_STORY["pages"])
    assert body["pages"][0]["page_number"] == 1
    assert body["pages"][0]["text_content"] == _MOCK_STORY["pages"][0]


def test_create_story_calls_ai_with_prompt(client, mock_ai):
    client.post(_GENERATE_URL, json={"prompt_text": _PROMPT, "user_id": 1})

    mock_ai.assert_called_once_with(_PROMPT)


def test_create_story_bad_request_when_prompt_too_short(client):
    resp = client.post(_GENERATE_URL, json={"prompt_text": "hi", "user_id": 1})

    assert resp.status_code == 422


def test_create_story_returns_502_when_ai_raises(client):
    from app.services.ai_service import StoryGenerationError

    with patch.object(
        AIService,
        "generate_story",
        new_callable=AsyncMock,
        side_effect=StoryGenerationError("timeout"),
    ):
        resp = client.post(_GENERATE_URL, json={"prompt_text": _PROMPT, "user_id": 1})

    assert resp.status_code == 502
    detail = resp.json()["detail"]
    assert detail["code"] == "ERR002"
    assert "timeout" in detail["message"]


# ===========================================================================
# GET /api/v1/stories  (list)
# ===========================================================================


def test_list_stories_empty_when_no_books_exist(client):
    resp = client.get(_LIST_URL)

    assert resp.status_code == 200
    assert resp.json() == []


def test_list_stories_returns_created_story(client, mock_ai):
    _create_story(client)

    resp = client.get(_LIST_URL)

    assert resp.status_code == 200
    stories = resp.json()
    assert len(stories) == 1
    assert stories[0]["title"] == _MOCK_STORY["title"]


def test_list_stories_excludes_soft_deleted(client, mock_ai):
    book_id = _create_story(client)["book_id"]
    client.delete(_story_url(book_id))

    resp = client.get(_LIST_URL)

    assert resp.json() == []


def test_list_stories_ordered_newest_first(client, mock_ai):
    mock_ai.return_value = {**_MOCK_STORY, "title": "First Story"}
    _create_story(client, "First story prompt about magic and wonder")

    mock_ai.return_value = {**_MOCK_STORY, "title": "Second Story"}
    _create_story(client, "Second story prompt about magic and wonder")

    stories = client.get(_LIST_URL).json()

    assert stories[0]["title"] == "Second Story"
    assert stories[1]["title"] == "First Story"


# ===========================================================================
# GET /api/v1/stories/{book_id}  (detail)
# ===========================================================================


def test_get_story_returns_full_detail(client, mock_ai):
    book_id = _create_story(client)["book_id"]

    resp = client.get(_story_url(book_id))

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == book_id
    assert body["title"] == _MOCK_STORY["title"]
    assert len(body["pages"]) == len(_MOCK_STORY["pages"])
    assert body["pages"][0]["page_number"] == 1


def test_get_story_not_found(client):
    resp = client.get(_story_url(99999))

    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "ERR001"


def test_get_story_returns_404_after_soft_delete(client, mock_ai):
    book_id = _create_story(client)["book_id"]
    client.delete(_story_url(book_id))

    resp = client.get(_story_url(book_id))

    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "ERR001"


# ===========================================================================
# DELETE /api/v1/stories/{book_id}  (soft-delete)
# ===========================================================================


def test_delete_story_returns_204(client, mock_ai):
    book_id = _create_story(client)["book_id"]

    resp = client.delete(_story_url(book_id))

    assert resp.status_code == 204


def test_delete_story_not_found(client):
    resp = client.delete(_story_url(99999))

    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "ERR001"


def test_delete_already_deleted_story_returns_404(client, mock_ai):
    book_id = _create_story(client)["book_id"]
    client.delete(_story_url(book_id))

    resp = client.delete(_story_url(book_id))

    assert resp.status_code == 404


# ===========================================================================
# GET /api/v1/stories/search
# ===========================================================================


def test_search_stories_returns_matching_title(client, mock_ai):
    _create_story(client)

    resp = client.get(_SEARCH_URL, params={"q": "Magic"})

    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert results[0]["title"] == _MOCK_STORY["title"]


def test_search_stories_is_case_insensitive(client, mock_ai):
    _create_story(client)

    resp = client.get(_SEARCH_URL, params={"q": "magic"})

    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_search_stories_no_match_returns_empty(client, mock_ai):
    _create_story(client)

    resp = client.get(_SEARCH_URL, params={"q": "dinosaur"})

    assert resp.status_code == 200
    assert resp.json() == []


def test_search_stories_excludes_soft_deleted(client, mock_ai):
    book_id = _create_story(client)["book_id"]
    client.delete(_story_url(book_id))

    resp = client.get(_SEARCH_URL, params={"q": "Magic"})

    assert resp.json() == []


def test_search_stories_requires_non_empty_query(client):
    resp = client.get(_SEARCH_URL, params={"q": ""})

    assert resp.status_code == 422
