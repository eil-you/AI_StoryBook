from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


def _get_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    req: RegisterRequest,
    service: AuthService = Depends(_get_service),
) -> UserResponse:
    """신규 유저를 등록합니다."""
    return await service.register(req)


@router.post("/login", response_model=TokenResponse)
async def login(
    req: LoginRequest,
    service: AuthService = Depends(_get_service),
) -> TokenResponse:
    """이메일/비밀번호로 로그인하여 JWT access token을 발급받습니다."""
    return await service.login(req)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout() -> None:
    """로그아웃 — 클라이언트에서 토큰을 폐기합니다.

    JWT는 stateless이므로 서버에서 별도의 처리 없이 204를 반환합니다.
    클라이언트는 저장된 토큰을 삭제해야 합니다.
    """
