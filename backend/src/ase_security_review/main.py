"""FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config.settings import AppConfig, load_config
from .controller import documents, misc, reviews
from .di import Container


def _frontend_dist() -> Path | None:
    dist = Path(__file__).resolve().parents[3] / "frontend" / "dist"
    return dist if dist.exists() else None


def create_app(
    config: AppConfig | None = None,
    container: Container | None = None,
    static_dir: str | None = None,
) -> FastAPI:
    if container is None:
        container = Container(config)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        container.start_background()
        yield
        container.shutdown()

    app = FastAPI(title="ASE Security Review Agent", version="0.1.0", lifespan=lifespan)
    app.state.container = container

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(misc.router)
    app.include_router(documents.router)
    app.include_router(reviews.router)

    dist = Path(static_dir) if static_dir else _frontend_dist()
    if dist and dist.exists():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="frontend")

    return app


app = create_app()
