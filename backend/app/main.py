"""FastAPI application factory and ASGI entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.audit import AuditLogMiddleware
from app.core.config import get_settings
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    """Build and configure the FastAPI application.

    Using a factory (rather than a module-level app only) keeps construction
    testable and lets each test build an isolated instance.
    """
    settings = get_settings()
    configure_logging()

    app = FastAPI(title=settings.app_name, version=settings.version)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Outermost — added after CORS so Starlette's reverse-add order puts it
    # last to run, seeing (and recording) the final status code the client gets.
    app.add_middleware(AuditLogMiddleware)
    app.include_router(api_router)
    return app


app = create_app()
