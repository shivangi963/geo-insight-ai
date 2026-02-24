from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/vector", tags=["vector-search"])


def _require_vector_db():
    from ..supabase_client import vector_db
    if not vector_db.enabled:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Vector database not configured",
                "hint": "Set SUPABASE_URL and SUPABASE_KEY in backend/.env",
                "setup": "Run the SQL in backend/supabase_setup.sql",
            },
        )
    return vector_db


async def _require_embed_service():
    try:
        from ..supabase_client import get_embedding_service
        svc = await get_embedding_service()
        if not svc.is_ready:
            raise RuntimeError("CLIP model not loaded")
        return svc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Embedding service unavailable",
                "hint": "Install transformers & torch, then restart the backend",
                "cause": str(exc),
            },
        )


class SimilarProperty(BaseModel):
    property_id: str
    address: str
    similarity: float = Field(..., ge=0.0, le=1.0, description="Cosine similarity (0–1)")
    image_url: Optional[str] = None
    metadata: Dict[str, Any] = {}


class SearchResponse(BaseModel):
    status: str = "success"
    query_image_hash: str = Field(..., description="First 16 chars of SHA-256 for dedup")
    results: List[SimilarProperty]
    total_results: int
    threshold_used: float
    timestamp: str


class StoreResponse(BaseModel):
    success: bool
    property_id: str
    message: str
    timestamp: str


class PropertyRecord(BaseModel):
    property_id: str
    address: str
    image_url: Optional[str] = None
    metadata: Dict[str, Any] = {}
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    has_embedding: bool = True


class StatsResponse(BaseModel):
    enabled: bool
    total_embeddings: int = 0
    table: str = ""
    embedding_dimension: int = 512
    timestamp: str


@router.post(
    "/search",
    response_model=SearchResponse,
    summary="Find visually similar properties",
    description=(
        "Upload a property image → CLIP embedding → pgvector cosine search "
        "→ ranked list of similar properties."
    ),
)
async def search_similar_properties(
    file: UploadFile = File(..., description="Query image (JPEG/PNG/WEBP, max 10 MB)"),
    limit: int = Query(5, ge=1, le=20, description="Max results"),
    threshold: float = Query(0.70, ge=0.0, le=1.0, description="Min similarity"),
    db=Depends(_require_vector_db),
    svc=Depends(_require_embed_service),
):
    ct = file.content_type or ""
    if not ct.startswith("image/"):
        raise HTTPException(
            400,
            detail=f"Expected an image file, got content-type '{ct}'",
        )

    raw = await file.read()

    try:
        embedding = await svc.embed_bytes(raw)
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc))

    if embedding is None:
        raise HTTPException(500, detail="Embedding model returned None — check backend logs")

    loop = asyncio.get_event_loop()
    raw_results: List[Dict] = await loop.run_in_executor(
        None, db.similarity_search, embedding, limit, threshold
    )

    results = [SimilarProperty(**r) for r in raw_results]

    return SearchResponse(
        query_image_hash=svc.content_hash(raw)[:16],
        results=results,
        total_results=len(results),
        threshold_used=threshold,
        timestamp=datetime.now().isoformat(),
    )


@router.post(
    "/store",
    response_model=StoreResponse,
    summary="Store a property image embedding",
    description=(
        "Upload a property image, generate a CLIP embedding, "
        "and upsert it into Supabase. Safe to call multiple times."
    ),
)
async def store_property(
    file: UploadFile = File(..., description="Property image"),
    property_id: str = Query(..., description="Unique property identifier"),
    address: str = Query(..., description="Human-readable address"),
    image_url: Optional[str] = Query(None, description="Public URL of the image (optional)"),
    db=Depends(_require_vector_db),
    svc=Depends(_require_embed_service),
):
    ct = file.content_type or ""
    if not ct.startswith("image/"):
        raise HTTPException(400, detail=f"Expected an image file, got '{ct}'")

    raw = await file.read()

    try:
        embedding = await svc.embed_bytes(raw)
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc))

    if embedding is None:
        raise HTTPException(500, detail="Embedding generation returned None")

    loop = asyncio.get_event_loop()
    ok: bool = await loop.run_in_executor(
        None,
        lambda: db.upsert_property(
            property_id=property_id,
            address=address,
            embedding=embedding,
            image_url=image_url or "",
            metadata={},
        ),
    )

    if not ok:
        raise HTTPException(500, detail="Failed to store embedding — check Supabase logs")

    return StoreResponse(
        success=True,
        property_id=property_id,
        message="Embedding stored (upsert — safe to call again)",
        timestamp=datetime.now().isoformat(),
    )


@router.get(
    "/property/{property_id}",
    response_model=PropertyRecord,
    summary="Get property record by ID",
)
async def get_property(
    property_id: str,
    db=Depends(_require_vector_db),
):
    loop = asyncio.get_event_loop()
    row = await loop.run_in_executor(None, db.get_by_property_id, property_id)
    if not row:
        raise HTTPException(404, detail=f"Property '{property_id}' not found in vector DB")
    return PropertyRecord(**row)


@router.delete(
    "/property/{property_id}",
    summary="Remove a property embedding",
)
async def delete_property(
    property_id: str,
    db=Depends(_require_vector_db),
):
    loop = asyncio.get_event_loop()
    row = await loop.run_in_executor(None, db.get_by_property_id, property_id)
    if not row:
        raise HTTPException(404, detail=f"Property '{property_id}' not found in vector DB")

    await loop.run_in_executor(None, db.delete_property, property_id)
    return {
        "deleted": True,
        "property_id": property_id,
        "timestamp": datetime.now().isoformat(),
    }


@router.get(
    "/stats",
    response_model=StatsResponse,
    summary="Vector database statistics",
)
async def vector_stats(db=Depends(_require_vector_db)):
    loop = asyncio.get_event_loop()
    stats = await loop.run_in_executor(None, db.get_stats)
    return StatsResponse(
        **{k: v for k, v in stats.items() if k in StatsResponse.model_fields},
        timestamp=datetime.now().isoformat(),
    )


@router.post(
    "/batch-store",
    summary="Batch-embed all properties",
    description=(
        "Queues all properties (up to `limit`) for CLIP embedding via Celery. "
        "Falls back to a direct response list when Celery is unavailable."
    ),
)
async def batch_store(
    limit: int = Query(50, ge=1, le=500, description="Max properties to embed"),
    db=Depends(_require_vector_db),
):
    from ..crud import property_crud
    props = await property_crud.get_all_properties(limit=limit)
    if not props:
        return {"queued": 0, "message": "No properties found in database"}

    try:
        from ..tasks.vector_tasks import batch_embed_task
        task = batch_embed_task.delay([p["id"] for p in props])
        return {
            "queued": len(props),
            "task_id": task.id,
            "status": "processing",
            "message": "Batch embedding started — poll /api/tasks/{task_id}",
        }
    except Exception:
        pass

    return {
        "queued": len(props),
        "task_id": None,
        "message": (
            "Celery not available. "
            "Use POST /api/vector/store for individual properties."
        ),
    }