import logging
import time
import uuid
from typing import Callable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RequestValidationMiddleware(BaseHTTPMiddleware):
    
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB
    
    async def dispatch(self, request: Request, call_next: Callable) -> Callable:
        try:
            request_id = str(uuid.uuid4())
            request.state.request_id = request_id
            
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > self.MAX_CONTENT_LENGTH:
                return JSONResponse(
                    status_code=413,
                    content={
                        "error": "Request too large",
                        "max_size": f"{self.MAX_CONTENT_LENGTH / 1_000_000}MB",
                        "request_id": request_id
                    }
                )
            
            if request.method in ["POST", "PUT", "PATCH"]:
                content_type = request.headers.get("content-type", "")
                if not content_type or not any(
                    ct in content_type for ct in ["application/json", "multipart/form-data", "application/x-www-form-urlencoded"]
                ):
                    return JSONResponse(
                        status_code=415,
                        content={
                            "error": "Unsupported media type",
                            "received": content_type,
                            "supported": ["application/json", "multipart/form-data"],
                            "request_id": request_id
                        }
                    )
            
            response = await call_next(request)
            
            # Security and tracing headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            
            return response
            
        except Exception as e:
            logger.error(f"Request validation error: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "request_id": getattr(request.state, "request_id", "unknown")
                }
            )


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    
    async def dispatch(self, request: Request, call_next: Callable) -> Callable:
        start_time = time.time()
        request_id = getattr(request.state, "request_id", "unknown")
        
        logger.info(
            f"REQUEST [ID: {request_id}] {request.method} {request.url.path} | "
            f"Client: {request.client.host if request.client else 'unknown'}"
        )
        
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            
            status_indicator = (
                "OK" if 200 <= response.status_code < 300 else
                "REDIRECT" if 300 <= response.status_code < 400 else
                "ERROR"
            )
            
            logger.info(
                f"{status_indicator} RESPONSE [ID: {request_id}] "
                f"Status: {response.status_code} | Time: {process_time:.3f}s"
            )
            
            response.headers["X-Process-Time"] = f"{process_time:.6f}"
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                f"ERROR [ID: {request_id}] {request.method} {request.url.path} | "
                f"Error: {str(e)} | Time: {process_time:.3f}s"
            )
            raise