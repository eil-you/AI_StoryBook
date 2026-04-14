from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def register(self, req: RegisterRequest) -> UserResponse:
        """이메일 중복 확인 후 신규 유저를 생성합니다."""
        existing = await self._db.scalar(select(User).where(User.email == req.email))
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="이미 사용 중인 이메일입니다.",
            )

        user = User(email=req.email, hashed_password=hash_password(req.password))
        self._db.add(user)
        await self._db.commit()
        await self._db.refresh(user)
        return UserResponse.model_validate(user)

    async def login(self, req: LoginRequest) -> TokenResponse:
        """이메일/비밀번호를 검증하고 JWT를 발급합니다."""
        user = await self._db.scalar(select(User).where(User.email == req.email))
        if not user or not verify_password(req.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="이메일 또는 비밀번호가 올바르지 않습니다.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = create_access_token(subject=user.email)
        return TokenResponse(access_token=token)
