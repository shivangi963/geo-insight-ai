from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
import logging
from datetime import datetime
import math

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def sanitize_floats(obj: Any) -> Any:
   
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    elif isinstance(obj, dict):
        return {k: sanitize_floats(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [sanitize_floats(i) for i in obj]
    return obj


def _extract_message(info: Any, state: str) -> str:
   
    if info is None:
        return f"Task {state.lower()}"
    if isinstance(info, dict):
     
        return (
            info.get("status")
            or info.get("message")
            or info.get("detail")
            or f"Task {state.lower()}"
        )
    if isinstance(info, Exception):
        return str(info)
    return str(info)


CELERY_AVAILABLE = False
try:
    from celery.result import AsyncResult
    from celery_config import celery_app
    CELERY_AVAILABLE = True
    logger.info(" Celery available for task tracking")
except ImportError:
    logger.info(" Celery not available – using in-memory task store")

try:
    from ..crud import get_neighborhood_analysis
except ImportError:
    async def get_neighborhood_analysis(analysis_id: str):
        return None

try:
    from ..crud import get_satellite_analysis
except ImportError:
    async def get_satellite_analysis(analysis_id: str):
        return None


def _nbr_response(task_id: str, analysis_id: str, analysis: dict) -> dict:
    status   = analysis.get("status", "unknown")
    progress = analysis.get("progress", 0)
    return {
        "task_id":        task_id,
        "analysis_id":    analysis_id,
        "status":         status,
        "progress":       progress,
        "message":        analysis.get("message", f"Analysis {status}"),
        "result":         sanitize_floats(analysis) if status == "completed" else None,
        "error":          analysis.get("error"),
        "address":        analysis.get("address"),
        "walk_score":     sanitize_floats(analysis.get("walk_score")),
        "total_amenities": analysis.get("total_amenities", 0),
    }



def _sat_response(task_id: str, analysis_id: str, analysis: dict) -> dict:
    status   = analysis.get("status", "unknown")
    progress = analysis.get("progress", 0)
    return {
        "task_id":     task_id,
        "analysis_id": analysis_id,
        "status":      status,
        "progress":    progress,
        "message":     analysis.get("message", f"Green space analysis {status}"),
        "result":      sanitize_floats(analysis) if status == "completed" else None,
        "error":       analysis.get("error"),
        "address":     analysis.get("address"),
        "green_space_percentage": sanitize_floats(
            analysis.get("green_space_percentage")
        ),
    }


@router.get("/{task_id}")
async def get_task_status(task_id: str):
   
    logger.info(f"Checking status for task: {task_id}")


    if task_id.startswith("analysis_"):
        analysis_id = task_id[len("analysis_"):]
        logger.info(f"Background task — checking analysis_id: {analysis_id}")

        try:
            analysis = await get_neighborhood_analysis(analysis_id)
            if analysis:
                return _nbr_response(task_id, analysis_id, analysis)
        except Exception as e:
            logger.error(f"Neighbourhood lookup failed for {analysis_id}: {e}")

        try:
            analysis = await get_satellite_analysis(analysis_id)
            if analysis:
                logger.info(f"Found satellite analysis for {analysis_id}")
                return _sat_response(task_id, analysis_id, analysis)
        except Exception as e:
            logger.error(f"Satellite lookup failed for {analysis_id}: {e}")


    if CELERY_AVAILABLE:
        try:
            celery_task = AsyncResult(task_id, app=celery_app)
            state       = celery_task.state

            logger.info(f"Celery task state: {state}")

            status_map = {
                "PENDING":  "pending",
                "STARTED":  "processing",
                "PROGRESS": "processing",
                "SUCCESS":  "completed",
                "FAILURE":  "failed",
                "RETRY":    "processing",
                "REVOKED":  "failed",
            }
            task_status = status_map.get(state, state.lower())

            progress = 0
            if state == "PROGRESS" and celery_task.info:
                info = celery_task.info
                progress = info.get("progress", 50) if isinstance(info, dict) else 50
            elif state == "SUCCESS":
                progress = 100

            result_data = None
            error_msg   = None
            if state == "SUCCESS":
                result_data = sanitize_floats(celery_task.result)
            elif state == "FAILURE":
                error_msg = _extract_message(celery_task.info, state)

          
            message = _extract_message(celery_task.info, state)

            return {
                "task_id":  task_id,
                "status":   task_status,
                "progress": progress,
                "message":  message,
                "result":   result_data,
                "error":    error_msg,
            }
        except Exception as e:
            logger.error(f"Celery lookup failed for {task_id}: {e}")

    try:
        analysis = await get_neighborhood_analysis(task_id)
        if analysis:
            logger.info("Found neighbourhood analysis using task_id as analysis_id")
            return _nbr_response(task_id, task_id, analysis)
    except Exception as e:
        logger.error(f"Bare neighbourhood lookup failed for {task_id}: {e}")

    try:
        analysis = await get_satellite_analysis(task_id)
        if analysis:
            logger.info("Found satellite analysis using task_id as analysis_id")
            return _sat_response(task_id, task_id, analysis)
    except Exception as e:
        logger.error(f"Bare satellite lookup failed for {task_id}: {e}")


    logger.warning(f"Task {task_id} not found in any system")
    raise HTTPException(
        status_code=404,
        detail={
            "error":   "Task not found",
            "task_id": task_id,
            "message": "Task may have expired or never existed",
            "troubleshooting": {
                "celery_available": CELERY_AVAILABLE,
                "suggestions": [
                    "Check if the task was created successfully",
                    "Task results expire after 1 hour",
                    "Check backend logs for errors",
                ],
            },
        },
    )