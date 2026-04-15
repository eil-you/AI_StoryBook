from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import auth, books, contents, covers, images, orders, preview, stories, templates
from app.core.config import get_settings
from app.core.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_settings()
    await init_db()
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


_static_dir = Path(__file__).resolve().parents[1] / "static"
_static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=_static_dir), name="static")

app.include_router(auth.router)
app.include_router(books.router)
app.include_router(images.router)
app.include_router(covers.router)
app.include_router(contents.router)
app.include_router(templates.router)
app.include_router(stories.router)
app.include_router(preview.router)
app.include_router(orders.router)


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    """Returns the current health status of the API."""
    return {"status": "ok"}
