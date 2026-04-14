from collections.abc import AsyncGenerator

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.providers.base import BookProvider
from app.providers.sweetbook import SweetBookProvider


async def get_book_provider(
    settings: Settings = Depends(get_settings),
) -> AsyncGenerator[BookProvider, None]:
    """
    FastAPI dependency that yields a BookProvider.

    Swap the concrete class here (e.g. replace SweetBookProvider with a
    future OpenAIBookProvider) without changing any router or service code.
    """
    provider = SweetBookProvider(api_key=settings.SWEETBOOK_API_KEY)
    try:
        yield provider
    finally:
        await provider.close()
