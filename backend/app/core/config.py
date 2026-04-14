from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    OPENAI_API_KEY: str
    SWEETBOOK_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o-mini"
    DATABASE_URL: str = "sqlite:///./storybook.db"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
