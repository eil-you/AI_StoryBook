"""
Unit tests for SweetBookProvider.

Strategy
--------
- httpx.AsyncClient.request is patched with an AsyncMock so no network
  traffic is produced.
- Responses are real httpx.Response objects so that raise_for_status()
  fires exactly as it would in production.
- Each test asserts the public surface: return type / field values for
  success paths, and ProviderError.code + ProviderError.status_code for
  error paths.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, call

import httpx
import pytest

from app.core.exceptions import ErrorCode, ProviderError
from app.providers.base import BookOrderRequest, PageData
from app.providers.sweetbook import SweetBookProvider

from .conftest import make_response


# ===========================================================================
# create_order
# ===========================================================================


class TestCreateOrder:
    # -----------------------------------------------------------------------
    # Happy path
    # -----------------------------------------------------------------------

    async def test_200_ok_returns_book_order_response(
        self, provider: SweetBookProvider, valid_order_request: BookOrderRequest, mocker
    ):
        """Sweet Book API returns 200 with a valid body → BookOrderResponse populated."""
        mock_request = AsyncMock(
            return_value=make_response(
                200,
                json={"order_id": "SBO-001", "status": "pending", "total_price": "19.99"},
            )
        )
        mocker.patch.object(provider._client, "request", mock_request)

        result = await provider.create_order(valid_order_request)

        assert result.provider_order_id == "SBO-001"
        assert result.status == "pending"
        assert result.total_price == Decimal("19.99")

    async def test_200_ok_sends_correct_payload(
        self, provider: SweetBookProvider, valid_order_request: BookOrderRequest, mocker
    ):
        """Verifies the outbound JSON body matches the BookOrderRequest fields."""
        mock_request = AsyncMock(
            return_value=make_response(
                200,
                json={"order_id": "SBO-002", "status": "pending", "total_price": "9.99"},
            )
        )
        mocker.patch.object(provider._client, "request", mock_request)

        await provider.create_order(valid_order_request)

        _, call_kwargs = mock_request.call_args
        sent_body = call_kwargs["json"]

        assert sent_body["reference_id"] == "42"
        assert sent_body["title"] == "My Little Story"
        assert sent_body["pages"][0]["page_number"] == 1
        assert sent_body["pages"][0]["text"] == "Once upon a time..."

    # -----------------------------------------------------------------------
    # Sweet Book HTTP errors  →  ERR002
    # -----------------------------------------------------------------------

    async def test_422_from_api_raises_err002(
        self, provider: SweetBookProvider, valid_order_request: BookOrderRequest, mocker
    ):
        """Sweet Book rejects our request (422) → ProviderError with ERR002."""
        mock_request = AsyncMock(
            return_value=make_response(
                422, text='{"detail": "Invalid page content"}'
            )
        )
        mocker.patch.object(provider._client, "request", mock_request)

        with pytest.raises(ProviderError) as exc_info:
            await provider.create_order(valid_order_request)

        err = exc_info.value
        assert err.code == ErrorCode.ERR002
        assert err.status_code == 422

    async def test_500_from_api_raises_err002(
        self, provider: SweetBookProvider, valid_order_request: BookOrderRequest, mocker
    ):
        """Sweet Book has an internal error (500) → ProviderError with ERR002."""
        mock_request = AsyncMock(
            return_value=make_response(500, text="Internal Server Error")
        )
        mocker.patch.object(provider._client, "request", mock_request)

        with pytest.raises(ProviderError) as exc_info:
            await provider.create_order(valid_order_request)

        err = exc_info.value
        assert err.code == ErrorCode.ERR002
        assert err.status_code == 500

    # -----------------------------------------------------------------------
    # Outbound Pydantic validation  →  ERR001  (no HTTP call made)
    # -----------------------------------------------------------------------

    async def test_blank_title_raises_err001(
        self, provider: SweetBookProvider, mocker
    ):
        """A blank title is caught by _CreateOrderPayload before any HTTP call."""
        mock_request = AsyncMock()
        mocker.patch.object(provider._client, "request", mock_request)

        bad_request = BookOrderRequest(
            book_id=1,
            title="   ",
            pages=[PageData(page_number=1, text_content="text")],
        )

        with pytest.raises(ProviderError) as exc_info:
            await provider.create_order(bad_request)

        assert exc_info.value.code == ErrorCode.ERR001
        mock_request.assert_not_called()

    async def test_empty_pages_raises_err001(
        self, provider: SweetBookProvider, mocker
    ):
        """An order with no pages is caught before any HTTP call."""
        mock_request = AsyncMock()
        mocker.patch.object(provider._client, "request", mock_request)

        bad_request = BookOrderRequest(book_id=1, title="Valid Title", pages=[])

        with pytest.raises(ProviderError) as exc_info:
            await provider.create_order(bad_request)

        assert exc_info.value.code == ErrorCode.ERR001
        mock_request.assert_not_called()

    async def test_invalid_page_number_raises_err001(
        self, provider: SweetBookProvider, mocker
    ):
        """page_number=0 violates the ≥1 constraint → ERR001, no HTTP call."""
        mock_request = AsyncMock()
        mocker.patch.object(provider._client, "request", mock_request)

        bad_request = BookOrderRequest(
            book_id=1,
            title="Valid Title",
            pages=[PageData(page_number=0, text_content="text")],
        )

        with pytest.raises(ProviderError) as exc_info:
            await provider.create_order(bad_request)

        assert exc_info.value.code == ErrorCode.ERR001
        mock_request.assert_not_called()

    # -----------------------------------------------------------------------
    # Inbound response validation  →  ERR002
    # -----------------------------------------------------------------------

    async def test_malformed_response_raises_err002(
        self, provider: SweetBookProvider, valid_order_request: BookOrderRequest, mocker
    ):
        """200 OK but unexpected JSON shape → ERR002 (gateway contract violated)."""
        mock_request = AsyncMock(
            return_value=make_response(
                200,
                json={"unexpected_key": "unexpected_value"},
            )
        )
        mocker.patch.object(provider._client, "request", mock_request)

        with pytest.raises(ProviderError) as exc_info:
            await provider.create_order(valid_order_request)

        assert exc_info.value.code == ErrorCode.ERR002

    # -----------------------------------------------------------------------
    # Transport-level errors
    # -----------------------------------------------------------------------

    async def test_connect_timeout_raises_err003(
        self, provider: SweetBookProvider, valid_order_request: BookOrderRequest, mocker
    ):
        mock_request = AsyncMock(side_effect=httpx.ConnectTimeout("timed out"))
        mocker.patch.object(provider._client, "request", mock_request)

        with pytest.raises(ProviderError) as exc_info:
            await provider.create_order(valid_order_request)

        assert exc_info.value.code == ErrorCode.ERR003
        assert exc_info.value.status_code is None

    async def test_network_error_raises_err004(
        self, provider: SweetBookProvider, valid_order_request: BookOrderRequest, mocker
    ):
        mock_request = AsyncMock(
            side_effect=httpx.RequestError("DNS resolution failed")
        )
        mocker.patch.object(provider._client, "request", mock_request)

        with pytest.raises(ProviderError) as exc_info:
            await provider.create_order(valid_order_request)

        assert exc_info.value.code == ErrorCode.ERR004
        assert exc_info.value.status_code is None


# ===========================================================================
# get_order_status
# ===========================================================================


class TestGetOrderStatus:

    async def test_200_ok_returns_order_status_response(
        self, provider: SweetBookProvider, mocker
    ):
        mock_request = AsyncMock(
            return_value=make_response(
                200,
                method="GET",
                path="/orders/SBO-001",
                json={"order_id": "SBO-001", "status": "processing"},
            )
        )
        mocker.patch.object(provider._client, "request", mock_request)

        result = await provider.get_order_status("SBO-001")

        assert result.provider_order_id == "SBO-001"
        assert result.status == "processing"

    async def test_500_from_api_raises_err002(
        self, provider: SweetBookProvider, mocker
    ):
        mock_request = AsyncMock(
            return_value=make_response(
                500,
                method="GET",
                path="/orders/SBO-001",
                text="Internal Server Error",
            )
        )
        mocker.patch.object(provider._client, "request", mock_request)

        with pytest.raises(ProviderError) as exc_info:
            await provider.get_order_status("SBO-001")

        err = exc_info.value
        assert err.code == ErrorCode.ERR002
        assert err.status_code == 500

    async def test_malformed_response_raises_err002(
        self, provider: SweetBookProvider, mocker
    ):
        mock_request = AsyncMock(
            return_value=make_response(
                200,
                method="GET",
                path="/orders/SBO-001",
                json={"wrong_field": "value"},
            )
        )
        mocker.patch.object(provider._client, "request", mock_request)

        with pytest.raises(ProviderError) as exc_info:
            await provider.get_order_status("SBO-001")

        assert exc_info.value.code == ErrorCode.ERR002


# ===========================================================================
# get_pricing
# ===========================================================================


class TestGetPricing:

    async def test_200_ok_returns_decimal_price(
        self, provider: SweetBookProvider, mocker
    ):
        mock_request = AsyncMock(
            return_value=make_response(
                200,
                method="GET",
                path="/pricing",
                json={"total_price": "14.99"},
            )
        )
        mocker.patch.object(provider._client, "request", mock_request)

        price = await provider.get_pricing(page_count=20)

        assert price == Decimal("14.99")
        _, call_kwargs = mock_request.call_args
        assert call_kwargs["params"] == {"pages": 20}

    async def test_zero_page_count_raises_err001_without_http_call(
        self, provider: SweetBookProvider, mocker
    ):
        """page_count < 1 is caught locally before any HTTP call is made."""
        mock_request = AsyncMock()
        mocker.patch.object(provider._client, "request", mock_request)

        with pytest.raises(ProviderError) as exc_info:
            await provider.get_pricing(page_count=0)

        assert exc_info.value.code == ErrorCode.ERR001
        mock_request.assert_not_called()

    async def test_422_from_api_raises_err002(
        self, provider: SweetBookProvider, mocker
    ):
        mock_request = AsyncMock(
            return_value=make_response(
                422,
                method="GET",
                path="/pricing",
                text='{"detail": "pages out of range"}',
            )
        )
        mocker.patch.object(provider._client, "request", mock_request)

        with pytest.raises(ProviderError) as exc_info:
            await provider.get_pricing(page_count=5)

        err = exc_info.value
        assert err.code == ErrorCode.ERR002
        assert err.status_code == 422
