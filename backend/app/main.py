from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.stories import router as stories_router
from app.core.database import engine
from app.models import base  # noqa: F401 – registers all models with metadata
from app.models.book import Book  # noqa: F401
from app.models.order import Order  # noqa: F401
from app.models.page import Page  # noqa: F401
from app.models.user import User  # noqa: F401

app = FastAPI(
    title="AI-StoryWeaver API",
    description="Backend API for the AI-StoryWeaver application",
    version="0.1.0",
)

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


base.Base.metadata.create_all(bind=engine)

app.include_router(stories_router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    """Returns the current health status of the API."""
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
