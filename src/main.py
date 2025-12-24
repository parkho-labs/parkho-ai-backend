import logging
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.v1 import api_router
from .config import get_settings
from .core.database import create_tables


class WebSocketAccessFilter(logging.Filter):
    """
    Filters uvicorn websocket access logs that include query params/tokens.
    """

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        if record.levelno > logging.INFO:
            return True

        try:
            message = record.getMessage()
        except Exception:
            message = str(record.msg)

        if not message:
            return True

        if '"WebSocket ' in message and ('[accepted]' in message or message.strip().endswith("403")):
            return False

        return True


def apply_logging_preferences(settings):
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.protocols.websockets").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)

    if settings.suppress_websocket_logs:
        uvicorn_error_logger = logging.getLogger("uvicorn.error")
        already_installed = any(isinstance(f, WebSocketAccessFilter) for f in uvicorn_error_logger.filters)
        if not already_installed:
            uvicorn_error_logger.addFilter(WebSocketAccessFilter())


settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(message)s"
)

apply_logging_preferences(settings)

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer() if settings.log_format == "json" else structlog.dev.ConsoleRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    apply_logging_preferences(settings)
    logger.info("Starting Parkho AI API", version="0.1.0")
    try:
        create_tables()
        logger.info("Database tables created/verified")
    except Exception as e:
        logger.error("Failed to initialize database", error=str(e))
        raise
    
    yield
    
    logger.info("Shutting down Parkho AI API")


def create_application() -> FastAPI:
    app = FastAPI(
        title="Parkho AI",
        description="AI-powered legal education platform with RAG-based legal assistant, document analysis, and intelligent question generation",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/api/v1/openapi.json",
        lifespan=lifespan,
    )
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def handle_common_requests(request: Request, call_next):
        # Handle common requests that cause warnings
        common_paths = ["/favicon.ico", "/robots.txt", "/sitemap.xml", "/apple-touch-icon.png"]
        if request.url.path in common_paths:
            return JSONResponse(status_code=404, content={"detail": "Not found"})

        response = await call_next(request)
        return response
    
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        logger.error(
            "Unhandled exception occurred",
            path=request.url.path,
            method=request.method,
            error=str(exc),
            exc_info=exc,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "message": "An unexpected error occurred. Please try again later.",
                "request_id": getattr(request.state, "request_id", None),
            }
        )
    
    # Health check at root
    from .api.v1.endpoints import health
    app.include_router(health.router, tags=["health"])

    # Mount Static Files for Uploads
    from fastapi.staticfiles import StaticFiles
    import os
    os.makedirs(settings.file_storage_dir, exist_ok=True)
    app.mount("/uploaded_files", StaticFiles(directory=settings.file_storage_dir), name="uploads")


    # Include API router
    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_application()


if __name__ == "__main__":
    import uvicorn
    import logging

    # Disable websocket logs to prevent token exposure and reduce noise
    logging.getLogger("uvicorn.protocols.websockets").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.WARNING)

    uvicorn.run(
        "src.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level="info",
        access_log=False,
    )