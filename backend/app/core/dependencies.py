from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User
from app.providers.base import BookProvider
from app.providers.sweetbook import SweetBookProvider

_bearer = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Bearer 토큰을 검증하고 현재 로그인 유저를 반환합니다."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="인증 정보가 유효하지 않습니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        email = decode_access_token(credentials.credentials)
    except JWTError:
        raise credentials_exception

    user = await db.scalar(select(User).where(User.email == email))
    if user is None:
        raise credentials_exception
    return user


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
