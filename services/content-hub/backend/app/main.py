from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse

from .config import get_settings
from .database import ensure_upload_dir, init_database
from .i18n import parse_accept_language, translate
from .routes import articles, audit, auth, certificates, dashboard, departments, files, health, integrations, monitor, publish, search, sync, user, versions, workflow
from .static_assets import media_type_for, resolve_asset_path, resolve_root_file

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
IMMUTABLE_CACHE = "public, max-age=31536000, immutable"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_database(settings.effective_database_url)
    ensure_upload_dir(settings.upload_dir)

    async def scheduled_publish_loop():
        from .database import _SessionLocal
        from .workflow_service import process_due_scheduled_articles

        while True:
            await asyncio.sleep(60)
            if _SessionLocal is None:
                continue
            db = _SessionLocal()
            try:
                process_due_scheduled_articles(db)
            except Exception:  # noqa: BLE001
                logger.exception("Scheduled publish loop failed")
            finally:
                db.close()

    task = asyncio.create_task(scheduled_publish_loop())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.7.0", lifespan=lifespan)

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
    app.include_router(departments.router)
    app.include_router(articles.router)
    app.include_router(files.router)
    app.include_router(certificates.router)
    app.include_router(search.router)
    app.include_router(dashboard.router)
    app.include_router(publish.router)
    app.include_router(integrations.router)
    app.include_router(versions.router)
    app.include_router(sync.router)
    app.include_router(workflow.router)
    app.include_router(audit.router)
    app.include_router(monitor.router)

    if STATIC_DIR.exists() and os.getenv("SERVE_STATIC", "true").lower() != "false":

        @app.get("/assets/{asset_name}")
        async def serve_asset(asset_name: str):
            path = resolve_asset_path(STATIC_DIR, asset_name)
            if not path:
                raise HTTPException(status_code=404, detail="not_found")
            return FileResponse(
                path,
                media_type=media_type_for(path),
                headers={"Cache-Control": IMMUTABLE_CACHE},
            )

        @app.get("/{full_path:path}")
        async def spa_fallback(full_path: str):
            if full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="not_found")

            root_file = resolve_root_file(STATIC_DIR, full_path)
            if root_file:
                return FileResponse(root_file, media_type=media_type_for(root_file))

            index = STATIC_DIR / "index.html"
            if index.is_file():
                return FileResponse(index, media_type="text/html; charset=utf-8")

            raise HTTPException(status_code=404, detail="not_found")

    return app


app = create_app()
