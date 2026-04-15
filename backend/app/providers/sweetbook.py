import json

import httpx
from pydantic import BaseModel, ValidationError
from decimal import Decimal
from app.core.exceptions import ErrorCode, ProviderError
from app.providers.base import BookProvider
from app.schemas.book import CreateBookData, CreateBookResponse
from app.schemas.content import ContentData, ContentResponse
from app.schemas.cover import CoverData, CoverResponse
from app.schemas.finalization import FinalizationData, FinalizationResponse
from app.schemas.order import (
    CreateEstimatePayload,
    CreateOrderPayload,
    CreateOrderResponse,
    EstimateDto,
    EstimateItemPayload,
    EstimateResponse,
    OrderDto,
    OrderDetailResponse,
    OrderItemPayload,
    ShippingPayload,
)
from app.schemas.image import PhotoListData, PhotoListResponse, UploadPhotoData, UploadPhotoResponse
from app.schemas.template import (
    TemplateDetailDto,
    TemplateDetailResponse,
    TemplateListData,
    TemplateListResponse,
)

_BASE_URL = "https://api-sandbox.sweetbook.com/v1"


class _PricingData(BaseModel):
    total_price: Decimal


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class SweetBookProvider(BookProvider):
    """
    Adapter that translates the generic BookProvider interface into
    Sweet Book API calls.

    All HTTP communication is isolated here.  Business logic must
    interact only with BookProvider — never with this class directly.
    """

    def __init__(
        self,
        api_key: str,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._client = client or httpx.AsyncClient(
            base_url=_BASE_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
        )

    async def create_book(
        self,
        title: str,
        book_spec_uid: str,
        spec_profile_uid: str | None = None,
        external_ref: str | None = None,
        idempotency_key: str | None = None,
    ) -> CreateBookData:
        """Create a new book object in DRAFT status."""
        body: dict[str, str | None] = {
            "title": title,
            "bookSpecUid": book_spec_uid,
        }
        if spec_profile_uid is not None:
            body["specProfileUid"] = spec_profile_uid
        if external_ref is not None:
            body["externalRef"] = external_ref

        extra_headers = {}
        if idempotency_key is not None:
            extra_headers["Idempotency-Key"] = idempotency_key

        raw = await self._post("/books", body, extra_headers=extra_headers)
        try:
            return CreateBookResponse.model_validate(raw).data
        except ValidationError as exc:
            raise ProviderError(
                code=ErrorCode.ERR002,
                message=f"Unexpected create-book response: {exc}",
            ) from exc

    async def list_templates(
        self,
        scope: str | None = None,
        book_spec_uid: str | None = None,
        spec_profile_uid: str | None = None,
        template_kind: str | None = None,
        category: str | None = None,
        template_name: str | None = None,
        theme: str | None = None,
        sort: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> TemplateListData:
        """Fetch a paginated list of templates with optional filters."""
        params: dict[str, str | int] = {"limit": limit, "offset": offset}
        if scope is not None:
            params["scope"] = scope
        if book_spec_uid is not None:
            params["bookSpecUid"] = book_spec_uid
        if spec_profile_uid is not None:
            params["specProfileUid"] = spec_profile_uid
        if template_kind is not None:
            params["templateKind"] = template_kind
        if category is not None:
            params["category"] = category
        if template_name is not None:
            params["templateName"] = template_name
        if theme is not None:
            params["theme"] = theme
        if sort is not None:
            params["sort"] = sort

        raw = await self._get("/templates", params=params)
        try:
            return TemplateListResponse.model_validate(raw).data
        except ValidationError as exc:
            raise ProviderError(
                code=ErrorCode.ERR002,
                message=f"Unexpected templates list response: {exc}",
            ) from exc

    async def get_template(self, template_uid: str) -> TemplateDetailDto:
        """Fetch the full detail of a single template by its UID.

        If the detail endpoint does not return a thumbnail URL, fall back to
        the list endpoint to find the thumbnail for this template.
        """
        import logging
        _log = logging.getLogger(__name__)

        raw = await self._get(f"/templates/{template_uid}")
        try:
            detail = TemplateDetailResponse.model_validate(raw).data
        except ValidationError as exc:
            raise ProviderError(
                code=ErrorCode.ERR002,
                message=f"Unexpected template detail response for '{template_uid}': {exc}",
            ) from exc

        _log.info(
            "Template detail fetched uid=%s thumbnails=%s",
            template_uid,
            detail.thumbnails,
        )

        # If the detail endpoint didn't return a thumbnail URL, search the list.
        if detail.thumbnails is None or detail.thumbnails.layout is None:
            _log.info(
                "Thumbnail missing in detail for uid=%s — searching list endpoint",
                template_uid,
            )
            try:
                list_data = await self.list_templates(limit=100)
                for tmpl in list_data.templates:
                    if tmpl.template_uid == template_uid:
                        detail = TemplateDetailDto(
                            parameters=detail.parameters,
                            layout=detail.layout,
                            layout_rules=detail.layout_rules,
                            base_layer=detail.base_layer,
                            thumbnails=tmpl.thumbnails,
                        )
                        _log.info(
                            "Found thumbnail via list for uid=%s url=%s",
                            template_uid,
                            tmpl.thumbnails.layout if tmpl.thumbnails else None,
                        )
                        break
            except Exception as exc:
                _log.warning(
                    "List-fallback for thumbnail failed uid=%s: %s", template_uid, exc
                )

        return detail

    async def add_cover(
        self,
        book_uid: str,
        template_uid: str,
        parameters: dict | None = None,
        upload_files: dict[str, tuple[str, bytes, str]] | None = None,
        idempotency_key: str | None = None,
    ) -> CoverData:
        """Bind a cover template (with images/text) to a DRAFT book."""
        form_data: dict[str, str] = {"templateUid": template_uid}
        if parameters is not None:
            form_data["parameters"] = json.dumps(parameters, ensure_ascii=False)

        extra_headers: dict[str, str] = {}
        if idempotency_key is not None:
            extra_headers["Idempotency-Key"] = idempotency_key

        raw = await self._post_multipart(
            f"/books/{book_uid}/cover",
            data=form_data,
            files=upload_files,
            extra_headers=extra_headers or None,
        )
        try:
            return CoverResponse.model_validate(raw).data
        except ValidationError as exc:
            raise ProviderError(
                code=ErrorCode.ERR002,
                message=f"Unexpected cover response for book '{book_uid}': {exc}",
            ) from exc

    async def add_content(
        self,
        book_uid: str,
        template_uid: str,
        parameters: dict | None = None,
        upload_files: dict[str, tuple[str, bytes, str]] | None = None,
        break_before: str | None = None,
        from_: str | None = None,
        idempotency_key: str | None = None,
    ) -> ContentData:
        """Append an interior page to a DRAFT book using a content template."""
        form_data: dict[str, str] = {"templateUid": template_uid}
        if parameters is not None:
            form_data["parameters"] = json.dumps(parameters, ensure_ascii=False)
        if from_ is not None:
            form_data["from"] = from_

        query_params: dict[str, str] = {}
        if break_before is not None:
            query_params["breakBefore"] = break_before

        extra_headers: dict[str, str] = {}
        if idempotency_key is not None:
            extra_headers["Idempotency-Key"] = idempotency_key

        # /contents 엔드포인트는 항상 multipart/form-data를 요구함.
        # httpx는 files 파라미터에 실제 파일이 있어야만 multipart를 사용하므로,
        # 파일이 없는 경우(filler 등)에는 multipart body를 직접 조립해서 전송함.
        if upload_files:
            raw = await self._post_multipart(
                f"/books/{book_uid}/contents",
                data=form_data,
                files=upload_files,
                params=query_params or None,
                extra_headers=extra_headers or None,
            )
        else:
            raw = await self._post_multipart_fields_only(
                f"/books/{book_uid}/contents",
                data=form_data,
                params=query_params or None,
                extra_headers=extra_headers or None,
            )
        try:
            return ContentResponse.model_validate(raw).data
        except ValidationError as exc:
            raise ProviderError(
                code=ErrorCode.ERR002,
                message=f"Unexpected contents response for book '{book_uid}': {exc}",
            ) from exc

    async def upload_photo(
        self,
        book_uid: str,
        filename: str,
        content: bytes,
        content_type: str,
    ) -> UploadPhotoData:
        """Upload a single photo to a DRAFT book."""
        raw = await self._post_multipart(
            f"/books/{book_uid}/photos",
            data={},
            files={"file": (filename, content, content_type)},
        )
        try:
            return UploadPhotoResponse.model_validate(raw).data
        except ValidationError as exc:
            raise ProviderError(
                code=ErrorCode.ERR002,
                message=f"Unexpected photo upload response for book '{book_uid}': {exc}",
            ) from exc

    async def finalize_book(self, book_uid: str) -> FinalizationData:
        """Transition a DRAFT book to FINALIZED status.

        POST /v1/books/{bookUid}/finalization — no request body needed.
        Returns 201 on first finalization, 200 if already finalized (idempotent).
        """
        raw = await self._post(f"/books/{book_uid}/finalization", {})
        try:
            return FinalizationResponse.model_validate(raw).data
        except ValidationError as exc:
            raise ProviderError(
                code=ErrorCode.ERR002,
                message=f"Unexpected finalization response for book '{book_uid}': {exc}",
            ) from exc

    async def list_photos(self, book_uid: str) -> PhotoListData:
        """Return all photos uploaded to a book."""
        raw = await self._get(f"/books/{book_uid}/photos")
        try:
            return PhotoListResponse.model_validate(raw).data
        except ValidationError as exc:
            raise ProviderError(
                code=ErrorCode.ERR002,
                message=f"Unexpected photo list response for book '{book_uid}': {exc}",
            ) from exc

    async def create_order(
        self,
        book_uid: str,
        quantity: int,
        recipient_name: str,
        recipient_phone: str,
        postal_code: str,
        address1: str,
        address2: str | None = None,
        memo: str | None = None,
        external_ref: str | None = None,
    ) -> OrderDto:
        """Create an order for a FINALIZED book (credits deducted immediately)."""
        try:
            payload = CreateOrderPayload(
                items=[OrderItemPayload(bookUid=book_uid, quantity=quantity)],
                shipping=ShippingPayload(
                    recipientName=recipient_name,
                    recipientPhone=recipient_phone,
                    postalCode=postal_code,
                    address1=address1,
                    address2=address2,
                    memo=memo,
                ),
                externalRef=external_ref,
            )
        except ValidationError as exc:
            raise ProviderError(
                code=ErrorCode.ERR001,
                message=f"Order payload validation failed: {exc}",
            ) from exc

        raw = await self._post("/orders", payload.model_dump(exclude_none=True))
        try:
            return CreateOrderResponse.model_validate(raw).data
        except ValidationError as exc:
            raise ProviderError(
                code=ErrorCode.ERR002,
                message=f"Unexpected create-order response: {exc}",
            ) from exc

    async def get_order(self, order_uid: str) -> OrderDto:
        """Fetch a single order by its UID."""
        raw = await self._get(f"/orders/{order_uid}")
        try:
            return OrderDetailResponse.model_validate(raw).data
        except ValidationError as exc:
            raise ProviderError(
                code=ErrorCode.ERR002,
                message=f"Unexpected order detail response for '{order_uid}': {exc}",
            ) from exc

    async def cancel_order(self, order_uid: str, *, cancel_reason: str) -> OrderDto:
        """Cancel a PAID or PDF_READY order."""
        raw = await self._post(f"/orders/{order_uid}/cancel", {"cancelReason": cancel_reason})
        try:
            return OrderDetailResponse.model_validate(raw).data
        except ValidationError as exc:
            raise ProviderError(
                code=ErrorCode.ERR002,
                message=f"Unexpected cancel-order response for '{order_uid}': {exc}",
            ) from exc

    async def update_shipping(
        self,
        order_uid: str,
        recipient_name: str,
        recipient_phone: str,
        postal_code: str,
        address1: str,
        address2: str | None = None,
        memo: str | None = None,
    ) -> OrderDto:
        """Update the shipping address of an order (PATCH /v1/orders/{orderUid}/shipping)."""
        body: dict = {
            "recipientName": recipient_name,
            "recipientPhone": recipient_phone,
            "postalCode": postal_code,
            "address1": address1,
        }
        if address2 is not None:
            body["address2"] = address2
        if memo is not None:
            body["memo"] = memo

        raw = await self._request("PATCH", f"/orders/{order_uid}/shipping", json=body)
        try:
            return OrderDetailResponse.model_validate(raw).data
        except ValidationError as exc:
            raise ProviderError(
                code=ErrorCode.ERR002,
                message=f"Unexpected update-shipping response for '{order_uid}': {exc}",
            ) from exc

    async def estimate_order(
        self,
        book_uid: str,
        quantity: int,
    ) -> EstimateDto:
        """Preview the total cost before placing an order."""
        try:
            payload = CreateEstimatePayload(
                items=[EstimateItemPayload(bookUid=book_uid, quantity=quantity)]
            )
        except ValidationError as exc:
            raise ProviderError(
                code=ErrorCode.ERR001,
                message=f"Estimate payload validation failed: {exc}",
            ) from exc

        raw = await self._post("/orders/estimate", payload.model_dump())
        try:
            return EstimateResponse.model_validate(raw).data  # type: ignore[return-value]
        except ValidationError as exc:
            raise ProviderError(
                code=ErrorCode.ERR002,
                message=f"Unexpected estimate response: {exc}",
            ) from exc

    async def get_pricing(self, page_count: int) -> Decimal:
        if page_count < 1:
            raise ProviderError(
                code=ErrorCode.ERR001,
                message=f"page_count must be ≥ 1, got {page_count}",
            )

        raw = await self._get("/pricing", params={"pages": page_count})

        try:
            data = _PricingData.model_validate(raw)
        except ValidationError as exc:
            raise ProviderError(
                code=ErrorCode.ERR002,
                message=f"Unexpected pricing response from Sweet Book API: {exc}",
            ) from exc

        return data.total_price

    # ------------------------------------------------------------------
    # Shared HTTP helpers
    # ------------------------------------------------------------------

    async def _post(self, path: str, body: dict, extra_headers: dict | None = None) -> dict:
        return await self._request("POST", path, json=body, headers=extra_headers or {})

    async def _post_multipart_fields_only(
        self,
        path: str,
        data: dict[str, str],
        params: dict[str, str] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict:
        """파일 없이 multipart/form-data로 POST 전송.

        httpx는 files 파라미터에 실제 파일이 있어야 multipart를 사용하므로,
        데이터 필드만 있는 경우 multipart body를 직접 조립해서 전송한다.
        """
        import secrets
        boundary = secrets.token_hex(16)
        body_parts: list[bytes] = []
        for key, value in data.items():
            body_parts.append(
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{key}"\r\n'
                f"\r\n"
                f"{value}\r\n"
            )
        raw_body = "".join(body_parts) + f"--{boundary}--\r\n"
        headers = {**(extra_headers or {}), "Content-Type": f"multipart/form-data; boundary={boundary}"}
        return await self._request(
            "POST",
            path,
            content=raw_body.encode(),
            headers=headers,
            params=params or {},
        )

    async def _post_multipart(
        self,
        path: str,
        data: dict[str, str],
        files: dict[str, tuple[str, bytes, str]] | None = None,
        params: dict[str, str] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict:
        # Passing files={} forces httpx to use multipart/form-data encoding
        # even when no file is uploaded (URL/server-filename methods).
        return await self._request(
            "POST",
            path,
            data=data,
            files=files or {},
            params=params or {},
            headers=extra_headers or {},
        )

    async def _get(self, path: str, params: dict | None = None) -> dict:
        return await self._request("GET", path, params=params)

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        try:
            response = await self._client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()

        except httpx.ConnectTimeout as exc:
            raise ProviderError(
                code=ErrorCode.ERR003,
                message=f"Connection to Sweet Book API timed out ({method} {path})",
            ) from exc

        except httpx.HTTPStatusError as exc:
            raise ProviderError(
                code=ErrorCode.ERR002,
                message=(
                    f"Sweet Book API returned {exc.response.status_code} "
                    f"for {method} {path}: {exc.response.text}"
                ),
                status_code=exc.response.status_code,
            ) from exc

        except httpx.RequestError as exc:
            raise ProviderError(
                code=ErrorCode.ERR004,
                message=f"Network error calling Sweet Book API ({method} {path}): {exc}",
            ) from exc

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Release the underlying HTTP client. Call on application shutdown."""
        await self._client.aclose()
