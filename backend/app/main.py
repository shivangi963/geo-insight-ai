from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
import logging
import os
import asyncio
from datetime import datetime

from .config import Settings
from .security_config import CORSSettings
from .middleware import (
    RequestValidationMiddleware,
    RequestLoggingMiddleware,
    RateLimitHeaderMiddleware
)

settings = Settings()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

CELERY_AVAILABLE = False
try:
    from celery.result import AsyncResult
    from celery_config import celery_app
    CELERY_AVAILABLE = True
    logger.info("Celery available")
except ImportError:
    logger.info("Celery not available - using sync mode")

VECTOR_DB_AVAILABLE = False
try:
    from .supabase_client import vector_db
    if vector_db and getattr(vector_db, 'enabled', False):
        VECTOR_DB_AVAILABLE = True
        logger.info("Vector database available")
    else:
        logger.info("Vector database not enabled")
except ImportError:
    logger.info("Vector database not available")

AI_AGENT_AVAILABLE = False
try:
    from .agents.local_expert import agent
    AI_AGENT_AVAILABLE = True
    logger.info("AI Agent available")
except ImportError:
    logger.info("AI Agent not available")

WORKFLOW_ENABLED = False
try:
    from .workflow_endpoints import router as workflow_router
    WORKFLOW_ENABLED = True
    logger.info("Workflow endpoints available")
except ImportError:
    logger.info("Workflow endpoints not available")

RATE_LIMITING_AVAILABLE = False
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    
    limiter = Limiter(key_func=get_remote_address)
    RATE_LIMITING_AVAILABLE = True
    logger.info("Rate limiting available")
except ImportError:
    logger.info("Rate limiting not available")
    class DummyLimiter:
        def limit(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator
    limiter = DummyLimiter()

from .database import Database

async def periodic_cleanup():
    while True:
        await asyncio.sleep(3600)
        logger.info("Running periodic cleanup...")

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
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            await Database.connect()
            logger.info("Database connected")
            break
        except Exception as e:
            logger.error(f"Database connection attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                logger.critical("Failed to connect to database")
                raise
            await asyncio.sleep(2 ** attempt)
    
    app.state.startup_time = datetime.now()
    app.state.total_requests = 0
    
    cleanup_task = asyncio.create_task(periodic_cleanup())

    if VECTOR_DB_AVAILABLE:
        asyncio.create_task(_warmup_clip_model())
    
    yield
    
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    
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

cors_config = CORSSettings.get_cors_config(settings.ENVIRONMENT)
app.add_middleware(CORSMiddleware, **cors_config)


app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RequestValidationMiddleware)
app.add_middleware(RateLimitHeaderMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000)

results_dir = os.path.join(os.path.dirname(__file__), "..", "results")
os.makedirs(results_dir, exist_ok=True)
app.mount("/results", StaticFiles(directory=results_dir), name="results")
logger.info(f"Mounted static files: /results → {results_dir}")

if RATE_LIMITING_AVAILABLE:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

logger.info(f"Middleware initialized for ENVIRONMENT: {settings.ENVIRONMENT}")

from .routers import (
    properties,
    neighborhood,
    ai_agent,
    vector_search,
    tasks,
    debug_stats,
    green_space
)

app.include_router(properties.router)
app.include_router(neighborhood.router)
app.include_router(ai_agent.router)
app.include_router(vector_search.router)
app.include_router(tasks.router)
app.include_router(debug_stats.router)
app.include_router(green_space.router)

if WORKFLOW_ENABLED:
    app.include_router(workflow_router, prefix="/api/workflow", tags=["workflow"])

logger.info("All routers registered")

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
MAPS_DIR = os.path.join(os.path.dirname(BACKEND_DIR), "maps")
os.makedirs(MAPS_DIR, exist_ok=True)

app.mount("/static/maps", StaticFiles(directory=MAPS_DIR), name="maps")
logger.info(f"Static maps mounted: {MAPS_DIR}")

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
async def http_exception_handler(request, exc):
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
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "details": str(exc) if settings.DEBUG else "Contact administrator",
            "timestamp": datetime.now().isoformat(),
            "request_id": getattr(request.state, "request_id", "unknown")
        }
    )

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        HOST=settings.HOST,
        PORT=settings.PORT,
        reload=settings.DEBUG,
        log_level="DEBUG" if settings.DEBUG else "info",
        access_log=True,
        timeout_keep_alive=30
    )