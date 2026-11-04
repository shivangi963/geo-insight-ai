import os
import logging
import asyncio
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

# Config & Middleware
from .config import settings
from .middleware import (
    RequestValidationMiddleware,
    RequestLoggingMiddleware,
)
from .database import Database, initialize_database

try:
    from celery_config import celery_app
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False

try:
    from .supabase_client import vector_db
    VECTOR_DB_AVAILABLE = getattr(vector_db, 'enabled', False) if vector_db else False
except ImportError:
    VECTOR_DB_AVAILABLE = False

try:
    from .agents.local_expert import agent
    AI_AGENT_AVAILABLE = True
except ImportError:
    AI_AGENT_AVAILABLE = False

from .workflow_endpoints import router as workflow_router

# Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


async def _warmup_clip_model():
    await asyncio.sleep(5)
    try:
        from .supabase_client import CLIPEmbeddingService
        logger.info("Pre-loading CLIP model...")
        await CLIPEmbeddingService.get_instance()
        logger.info("CLIP model ready — vector search is fast")
    except Exception as e:
        logger.warning(f"CLIP warmup failed (non-fatal): {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Features: Celery={CELERY_AVAILABLE}, VectorDB={VECTOR_DB_AVAILABLE}, AI={AI_AGENT_AVAILABLE}")

    db_connected = False
    max_retries = 3
    for attempt in range(max_retries):
        try:
            await Database.connect()
            await initialize_database()  # Explicitly build database indexes on startup
            db_connected = True
            logger.info("Database connected & indexes initialized successfully")
            break
        except Exception as e:
            logger.error(f"Database connection attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)

    if not db_connected:
        logger.critical(
            "Could not connect to MongoDB after %d attempts. "
            "Check MONGODB_URL environment variable in Cloud Run. "
            "App is running in DEGRADED mode — data endpoints will return 503.",
            max_retries,
        )

    app.state.startup_time = datetime.now()
    app.state.total_requests = 0
    app.state.db_connected = db_connected

    if VECTOR_DB_AVAILABLE:
        asyncio.create_task(_warmup_clip_model())

    yield

    logger.info(f"Shutting down {settings.APP_NAME}")
    try:
        await Database.close()
        logger.info("Database closed")
    except Exception as e:
        logger.error(f"Error closing database: {e}")


app = FastAPI(
    title=settings.APP_NAME,
    description="Advanced Real Estate Intelligence & Geospatial Analysis Platform",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Middleware Setup using consolidated Settings
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:8501").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Application Middleware
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RequestValidationMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Register Routers
from .routers import (
    properties,
    neighborhood,
    ai_agent,
    vector_search,
    tasks,
    green_space,
    stats,
)

app.include_router(properties.router)
app.include_router(neighborhood.router)
app.include_router(ai_agent.router)
app.include_router(vector_search.router)
app.include_router(tasks.router)
app.include_router(green_space.router)
app.include_router(stats.router)
app.include_router(workflow_router, prefix="/api/workflow", tags=["workflow"])

logger.info("All routers registered")


@app.get("/")
async def root():
    startup_time = app.state.startup_time
    uptime = str(datetime.now() - startup_time)

    return {
        "application": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "operational",
        "uptime": uptime,
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
async def health_check():
    try:
        db_connected = await Database.is_connected()

        return {
            "status": "healthy" if db_connected else "degraded",
            "timestamp": datetime.now().isoformat(),
            "version": settings.APP_VERSION,
            "database": "connected" if db_connected else "disconnected",
            "hint": None if db_connected else "Set MONGODB_URL env var in Cloud Run",
        }
    except Exception as e:
        return {
            "status": "degraded",
            "timestamp": datetime.now().isoformat(),
            "version": settings.APP_VERSION,
            "database": "unknown",
            "error": str(e)
        }


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning(f"HTTP {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.now().isoformat(),
            "path": request.url.path
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "timestamp": datetime.now().isoformat(),
            "request_id": getattr(request.state, "request_id", "unknown")
        }
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info",
        access_log=True,
        timeout_keep_alive=30
    )