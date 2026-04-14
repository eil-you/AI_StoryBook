from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import book_specs, books, contents, covers, images, stories, templates
from app.core.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Validate that all required env vars are present at startup.
    get_settings()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="AI-test API",
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


app.include_router(book_specs.router)
app.include_router(books.router)
app.include_router(images.router)
app.include_router(covers.router)
app.include_router(contents.router)
app.include_router(templates.router)
app.include_router(stories.router)


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    """Returns the current health status of the API."""
    return {"status": "ok"}
