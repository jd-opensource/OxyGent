from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.config import load_config
from app.routers import annotation, banks, documents, retrieval, samples, settings, templates
from app.storage.es_client import ESClient
from app.storage.vearch_client import VearchClient
from app.services.event_bus import EventBus

logger = logging.getLogger("oxybank")

def _resolve_frontend_dir() -> Path:
    """Locate the directory with the static frontend files.

    Historically the repo was laid out as OxyBank/{backend/app, frontend}. The
    project has since flattened to OxyBank/{app, web} (backend files pulled up
    to the repo root, and frontend renamed to web). In Docker builds the layout
    is /export/App/{app, web}. Try the new locations first, keep the old ones
    as fallbacks so older deployment scripts don't break.
    """
    here = Path(__file__).resolve().parent
    for candidate in (
        here.parent / "web",              # current repo layout: OxyBank/{app, web}
        here.parent / "frontend",         # legacy docker layout: /export/App/{app,frontend}
        here.parent.parent / "frontend",  # legacy repo layout:   OxyBank/{backend/app, frontend}
    ):
        if candidate.exists():
            return candidate
    return here.parent / "web"


FRONTEND_DIR = _resolve_frontend_dir()


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = load_config()

    es = ESClient(
        hosts=cfg.es.hosts,
        user=cfg.es.user,
        password=cfg.es.password,
        prefix=cfg.es.index_prefix,
        timeout=cfg.es.timeout,
    )
    es.init_system_indices()
    app.state.es = es

    vearch = VearchClient(
        master_url=cfg.vearch.master_url,
        router_url=cfg.vearch.router_url,
        db_name=cfg.vearch.db_name,
    )
    app.state.vearch = vearch

    event_bus = EventBus(queue_size=cfg.annotation.event_queue_size)
    app.state.event_bus = event_bus

    from app.services.annotation_service import AnnotationDispatcher
    dispatcher = AnnotationDispatcher(
        max_concurrency=cfg.annotation.max_concurrency,
        max_cascade_depth=cfg.annotation.max_cascade_depth,
        agent_timeout=cfg.annotation.agent_timeout,
        es_client=es,
    )
    event_bus.subscribe(dispatcher.handle_status_change)
    await dispatcher.load_agents()
    await event_bus.start()
    app.state.dispatcher = dispatcher

    from app.auth.service import init_admin_user
    init_admin_user(es)

    from app.services.bank_service import init_builtin_templates
    init_builtin_templates(es)

    logger.info("OxyBank started")
    yield

    await event_bus.stop()
    logger.info("OxyBank stopped")


def create_app() -> FastAPI:
    app = FastAPI(title="OxyBank", version="1.0.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from app.routers import users
    from app.auth.dependencies import auth_router

    app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
    app.include_router(banks.router, prefix="/api/banks", tags=["banks"])
    app.include_router(documents.router, prefix="/api/banks/{bank_name}/documents", tags=["documents"])
    app.include_router(samples.router, prefix="/api/banks/{bank_name}/samples", tags=["samples"])
    app.include_router(retrieval.router, prefix="/api/banks/{bank_name}/retrieval-apis", tags=["retrieval"])
    app.include_router(annotation.router, prefix="/api/banks/{bank_name}/agents", tags=["annotation"])
    app.include_router(templates.router, prefix="/api/banks/{bank_name}/templates", tags=["templates"])
    app.include_router(settings.router, prefix="/api/config", tags=["config"])
    app.include_router(users.router, prefix="/api/users", tags=["users"])

    # Static assets (css/js) served under /css, /js paths
    app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
    app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")
    # `/assets` was mounted historically for a directory that no longer exists in
    # the flattened repo. Nothing under web/ references it — mount only if the
    # directory is actually present, so startup doesn't crash on a missing dir.
    if (FRONTEND_DIR / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets")

    # HTML pages — catch-all at the end so API routes take priority
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        # Never serve HTML for API paths
        if full_path.startswith("api/") or full_path.startswith("api"):
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        # Serve specific .html file if it exists
        if full_path and not full_path.endswith(".html"):
            candidate = full_path + ".html"
            if (FRONTEND_DIR / candidate).exists():
                full_path = candidate
        file_path = FRONTEND_DIR / (full_path or "index.html")
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        # Default to index.html
        return FileResponse(FRONTEND_DIR / "index.html")

    return app


app = create_app()
