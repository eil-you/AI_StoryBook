from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    OPENAI_API_KEY: str
    SWEETBOOK_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_IMAGE_MODEL: str = "dall-e-3"
    DATABASE_URL: str = "sqlite:///./storybook.db"

    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "ap-northeast-2"
    AWS_S3_BUCKET: str = ""

    IMAGE_TEST_MODE: bool = True

    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24시간

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
