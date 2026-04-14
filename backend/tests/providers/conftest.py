from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.providers.base import BookOrderRequest, PageData
from app.providers.sweetbook import SweetBookProvider, _BASE_URL


# ---------------------------------------------------------------------------
# Provider fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_client() -> MagicMock:
    """
    A MagicMock shaped like httpx.AsyncClient.

    Injecting this avoids constructing a real AsyncClient (which sets up SSL
    and httpcore at import time) during tests.  Each test replaces
    mock_client.request via mocker.patch.object to control responses.
    """
    client = MagicMock(spec=httpx.AsyncClient)
    client.request = AsyncMock()
    client.aclose = AsyncMock()
    return client


@pytest.fixture
def provider(mock_client: MagicMock) -> SweetBookProvider:
    """A SweetBookProvider backed by a mock HTTP client — no real network calls."""
    return SweetBookProvider(api_key="test-api-key", client=mock_client)


# ---------------------------------------------------------------------------
# Domain fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def valid_order_request() -> BookOrderRequest:
    return BookOrderRequest(
        book_id=42,
        title="My Little Story",
        pages=[
            PageData(
                page_number=1,
                text_content="Once upon a time...",
                image_url="https://cdn.example.com/cover.png",
            )
        ],
    )


# ---------------------------------------------------------------------------
# httpx response builders
# ---------------------------------------------------------------------------


def make_response(
    status_code: int,
    *,
    json: dict | None = None,
    text: str = "",
    method: str = "POST",
    path: str = "/orders",
) -> httpx.Response:
    """
    Build a real httpx.Response so that raise_for_status() behaves exactly as
    it would in production (raises httpx.HTTPStatusError for 4xx/5xx).
    """
    request = httpx.Request(method, f"{_BASE_URL}{path}")
    if json is not None:
        return httpx.Response(status_code, json=json, request=request)
    return httpx.Response(status_code, text=text, request=request)
