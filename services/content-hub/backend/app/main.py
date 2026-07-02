from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response

from .config import get_settings
from .database import ensure_upload_dir, init_database
from .i18n import parse_accept_language, translate
from .routes import articles, auth, certificates, dashboard, files, health, search, user
from .static_assets import get_asset, get_index_html, get_root_file, preload_static

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def _cached_response(content: bytes, media_type: str, *, immutable: bool = False) -> Response:
    headers = {"Content-Length": str(len(content))}
    if immutable:
        headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return Response(content=content, media_type=media_type, headers=headers)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_database(settings.effective_database_url)
    ensure_upload_dir(settings.upload_dir)
    if STATIC_DIR.exists():
        preload_static(STATIC_DIR)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.3.0", lifespan=lifespan)

    @app.middleware("http")
    async def attach_language(request: Request, call_next):
        session_language = None
        from .auth import get_session

        session = get_session(request)
        if session and session.get("user"):
            session_language = session["user"].get("language")

        request.state.language = session_language or parse_accept_language(
            request.headers.get("accept-language")
        )
        response = await call_next(request)
        response.headers["Content-Language"] = request.state.language
        return response

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        language = getattr(request.state, "language", settings.default_language)
        detail = exc.detail
        if isinstance(detail, str):
            message = translate(f"errors.{detail}", language)
            if message == f"errors.{detail}":
                message = translate("errors.generic", language)
            code = detail
        else:
            message = translate("errors.generic", language)
            code = "error"
        return JSONResponse(status_code=exc.status_code, content={"error": message, "code": code})

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        language = getattr(request.state, "language", settings.default_language)
        return JSONResponse(
            status_code=422,
            content={
                "error": translate("errors.validation", language),
                "code": "validation_error",
                "details": exc.errors(),
            },
        )

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(user.router)
    app.include_router(articles.router)
    app.include_router(files.router)
    app.include_router(certificates.router)
    app.include_router(search.router)
    app.include_router(dashboard.router)

    if STATIC_DIR.exists():

        @app.get("/assets/{asset_name}")
        async def serve_asset(asset_name: str):
            item = get_asset(asset_name)
            if not item:
                raise HTTPException(status_code=404, detail="not_found")
            content, media_type = item
            return _cached_response(content, media_type, immutable=True)

        @app.get("/{full_path:path}")
        async def spa_fallback(full_path: str):
            if full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="not_found")

            root_file = get_root_file(full_path)
            if root_file:
                content, media_type = root_file
                return _cached_response(content, media_type)

            static_file = STATIC_DIR / full_path
            if static_file.is_file():
                return FileResponse(static_file)

            index = get_index_html()
            if index:
                content, media_type = index
                return _cached_response(content, media_type)

            raise HTTPException(status_code=404, detail="not_found")

    return app


app = create_app()
