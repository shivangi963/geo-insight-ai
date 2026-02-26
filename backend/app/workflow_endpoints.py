from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any, Optional
import httpx
from datetime import datetime
import asyncio
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

SELF_BASE_URL = os.getenv("SELF_BASE_URL", "http://localhost:8000")

DEFAULT_AMENITY_TYPES = ["restaurant", "cafe", "school", "hospital", "park", "supermarket"]


@router.post("/trigger")
async def trigger_analysis(payload: Dict[str, Any]):

    address = payload.get("address")
    if not address:
        raise HTTPException(status_code=400, detail="address is required")

    radius_m = payload.get("radius_m", 1000)
    if not isinstance(radius_m, int) or not (100 <= radius_m <= 5000):
        radius_m = 1000

    amenity_types = payload.get("amenity_types") or DEFAULT_AMENITY_TYPES

    logger.info(f"[Workflow] Triggering analysis for: {address}, amenities: {amenity_types}")

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(
                f"{SELF_BASE_URL}/api/neighborhood/analyze",
                json={
                    "address":           address,
                    "radius_m":          radius_m,
                    "amenity_types":     amenity_types,   
                    "include_buildings": False,
                    "generate_map":      True,
                },
            )
            resp.raise_for_status()
        except httpx.RequestError as exc:
            raise HTTPException(status_code=503, detail=f"Backend unreachable: {exc}")
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=exc.response.status_code,
                                detail=exc.response.text)

    data = resp.json()
    logger.info(f"[Workflow] Started: analysis_id={data.get('analysis_id')}, "
                f"task_id={data.get('task_id')}")

    return {
        "analysis_id":  data.get("analysis_id"),
        "task_id":      data.get("task_id"),
        "address":      address,
        "status":       "queued",
        "triggered_at": datetime.now().isoformat(),
        "poll_url":     f"{SELF_BASE_URL}/api/workflow/status/{data.get('task_id')}",
    }


@router.get("/status/{task_id}")
async def get_workflow_status(task_id: str):

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{SELF_BASE_URL}/api/tasks/{task_id}")
            resp.raise_for_status()
        except httpx.RequestError as exc:
            raise HTTPException(status_code=503, detail=f"Task service unreachable: {exc}")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise HTTPException(status_code=404, detail="Task not found")
            raise HTTPException(status_code=exc.response.status_code,
                                detail=exc.response.text)
    return resp.json()


@router.post("/webhook/analysis")
async def n8n_webhook(payload: Dict[str, Any]):
    
    address = payload.get("address")
    if not address:
        raise HTTPException(status_code=400, detail="address is required")

    n8n_webhook_url = os.getenv(
        "N8N_WEBHOOK_URL",
        "http://localhost:5678/webhook/geoinsight-analysis"
    )

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(n8n_webhook_url, json=payload)
            resp.raise_for_status()
            logger.info(f"[Workflow] n8n accepted request for: {address}")
            return resp.json()

        except httpx.RequestError as exc:
            logger.warning(f"n8n unreachable ({exc}), triggering analysis directly")

        except httpx.HTTPStatusError as exc:
            logger.warning(
                f"n8n returned HTTP {exc.response.status_code} "
                f"({exc.response.text[:120]}), triggering analysis directly"
            )
    return await trigger_analysis(payload)


@router.post("/batch")
async def batch_workflow(payload: Dict[str, Any]):

    addresses = payload.get("addresses", [])
    if not addresses:
        raise HTTPException(status_code=400, detail="addresses list is required")
    if len(addresses) > 10:
        raise HTTPException(status_code=400, detail="Max 10 addresses per batch")

    radius_m     = payload.get("radius_m", 1000)
    amenity_types = payload.get("amenity_types") or DEFAULT_AMENITY_TYPES  

    async def _trigger_one(addr: str) -> Dict:
        try:
            return await trigger_analysis({
                "address":      addr,
                "radius_m":     radius_m,
                "amenity_types": amenity_types,
            })
        except Exception as exc:
            return {"address": addr, "status": "failed", "error": str(exc)}

    results = await asyncio.gather(*[_trigger_one(a) for a in addresses])

    return {
        "batch_id":  f"batch_{int(datetime.now().timestamp())}",
        "total":     len(addresses),
        "triggered": [r for r in results if r.get("status") != "failed"],
        "failed":    [r for r in results if r.get("status") == "failed"],
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/health")
async def workflow_health():

    n8n_url  = os.getenv("N8N_WEBHOOK_URL", "http://localhost:5678/webhook/geoinsight-analysis")
    n8n_base = n8n_url.split("/webhook")[0]

    n8n_status = "unknown"
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            r = await client.get(f"{n8n_base}/healthz")
            n8n_status = "reachable" if r.status_code == 200 else f"HTTP {r.status_code}"
        except Exception as exc:
            n8n_status = f"unreachable ({exc})"

    return {
        "status":    "ok",
        "service":   "GeoInsight Workflow Endpoints",
        "n8n":       n8n_status,
        "n8n_url":   n8n_url,
        "timestamp": datetime.now().isoformat(),
    }