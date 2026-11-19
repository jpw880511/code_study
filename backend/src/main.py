import re
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from src.api.debug import debug_router
from src.api.exceptions import UnhandledErrorMiddleware, register_exception_handlers
from src.api.router import api_router, health
from src.config import AppSettings
from src.db.session import dispose_engine

SAFE_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await dispose_engine()


def create_app(settings: AppSettings | None = None) -> FastAPI:
    settings = settings or AppSettings()
    app = FastAPI(title="AI Code Learning Platform API", debug=settings.debug, lifespan=lifespan)

    app.state.settings = settings
    register_exception_handlers(app)
    # Added first so it ends up innermost: 500 responses still pass through CORS and metadata.
    app.add_middleware(UnhandledErrorMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID", "X-Process-Time"],
    )

    @app.middleware("http")
    async def add_request_metadata(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming = request.headers.get("X-Request-ID", "")
        request_id = incoming if SAFE_REQUEST_ID.fullmatch(incoming) else uuid.uuid4().hex
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{time.perf_counter() - started:.6f}"
        return response

    app.add_api_route("/health", health, tags=["health"])
    app.include_router(api_router)
    if settings.environment != "production":
        app.include_router(debug_router)

    return app


app = create_app()
