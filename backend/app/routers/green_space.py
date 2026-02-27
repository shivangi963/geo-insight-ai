from fastapi.responses import StreamingResponse
import io
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Depends
from typing import Any, Optional
import logging
from datetime import datetime
import os
import traceback

from ..database import get_database
from ..geospatial import get_osm_map_area, download_osm_tile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analysis", tags=["green-space-analysis"])


@router.get("/tile/{zoom}/{tile_x}/{tile_y}")
async def get_tile(zoom: int, tile_x: int, tile_y: int):
    try:
        tile_img = download_osm_tile(tile_x, tile_y, zoom)
        if not tile_img:
            raise HTTPException(status_code=404, detail="Tile not found")

        buf = io.BytesIO()
        tile_img.save(buf, format="PNG")
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching tile: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/map")
async def get_map_image(
    latitude: float = Query(..., ge=-90, le=90, description="Latitude"),
    longitude: float = Query(..., ge=-180, le=180, description="Longitude"),
    radius_m: int = Query(500, ge=100, le=5000, description="Radius in metres"),
):
    try:
        map_path = get_osm_map_area(latitude, longitude, radius_m)
        if not map_path:
            raise HTTPException(status_code=500, detail="Failed to generate map")

        with open(map_path, "rb") as f:
            img_data = f.read()

        try:
            os.unlink(map_path)
        except Exception:
            pass

        return StreamingResponse(io.BytesIO(img_data), media_type="image/png")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating map: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/info")
async def get_osm_info():
    return {
        "service": "OpenStreetMap Tile Service",
        "tile_size": 256,
        "max_zoom": 19,
        "attribution": "© OpenStreetMap contributors",
        "license": "ODbL",
        "usage_policy": "https://operations.osmfoundation.org/policies/tiles/",
        "note": "Please respect OSM tile usage policy – avoid bulk downloads",
    }


@router.post("/green-space", status_code=202)
async def analyze_green_space(
    address: str = Query(..., description="Address to analyse"),
    radius_m: int = Query(500, ge=100, le=4000, description="Search radius in metres"),
    background_tasks: BackgroundTasks = None,
):
    try:
        from ..crud import create_satellite_analysis

        logger.info(f"Green space analysis request: {address}, radius={radius_m}m")

        analysis_doc = {
            "address": address,
            "search_radius_m": radius_m,
            "calculate_green_space": True,
            "map_source": "OpenStreetMap",
            "status": "pending",
            "progress": 0,
            "created_at": datetime.now().isoformat(),
        }

        analysis_id = await create_satellite_analysis(analysis_doc)
        logger.info(f"Created green space analysis: {analysis_id}")

        CELERY_AVAILABLE = False
        try:
            from celery.result import AsyncResult
            from celery_config import celery_app
            CELERY_AVAILABLE = True
        except ImportError:
            pass

        task_id = None
        use_celery = CELERY_AVAILABLE

        if use_celery:
            try:
                from ..tasks.satellite_tasks import analyze_satellite_task
                task = analyze_satellite_task.delay(
                    analysis_id=analysis_id,
                    request_data={
                        "address": address,
                        "radius_m": radius_m,
                        "calculate_green_space": True,
                    },
                )
                task_id = task.id
            except Exception:
                use_celery = False

        if not use_celery:
            task_id = f"analysis_{analysis_id}"
            background_tasks.add_task(
                _process_green_space_analysis, analysis_id, address, radius_m
            )

        return {
            "analysis_id": analysis_id,
            "task_id": task_id,
            "address": address,
            "status": "queued",
            "message": "Green space analysis started",
            "created_at": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start green space analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def _process_green_space_analysis(
    analysis_id: str, address: str, radius_m: int
) -> None:
    try:
        from ..crud import update_satellite_analysis_status
        from ..geospatial import get_geocoder, get_osm_map_area
        from ..tasks.computer_vision_tasks import analyze_osm_green_spaces
        import asyncio

        await update_satellite_analysis_status(
            analysis_id,
            "processing",
            {"progress": 10, "message": "Geocoding address…"},
        )

        geocoder = get_geocoder()
        coordinates = await asyncio.to_thread(
            geocoder.address_to_coordinates, address
        )

        if not coordinates:
            await update_satellite_analysis_status(
                analysis_id,
                "failed",
                {"error": "Could not geocode address", "progress": 100},
            )
            return

        lat, lon = coordinates
        await update_satellite_analysis_status(
            analysis_id,
            "processing",
            {
                "progress": 30,
                "message": "Fetching OpenStreetMap tiles…",
                "coordinates": {"latitude": lat, "longitude": lon},
            },
        )

        map_path = await asyncio.to_thread(
            get_osm_map_area, lat, lon, radius_m
        )
        if not map_path or not os.path.exists(map_path):
            await update_satellite_analysis_status(
                analysis_id,
                "failed",
                {"error": "Failed to fetch OSM tiles", "progress": 100},
            )
            return

        try:
            await update_satellite_analysis_status(
                analysis_id,
                "processing",
                {"progress": 60, "message": "Analysing green spaces…"},
            )
            result = await asyncio.to_thread(
                analyze_osm_green_spaces, map_path, analysis_id
            )
            if result:
                await update_satellite_analysis_status(
                    analysis_id,
                    "completed",
                    {
                        "address": address,
                        "coordinates": {"latitude": lat, "longitude": lon},
                        "search_radius_m": radius_m,
                        "green_space_percentage": result.get("green_space_percentage"),
                        "green_pixels": result.get("green_pixels"),
                        "total_pixels": result.get("total_pixels"),
                        "visualization_path": result.get("visualization_path"),
                        "breakdown": result.get("breakdown"),
                        "map_source": "OpenStreetMap",
                        "progress": 100,
                        "completed_at": datetime.now().isoformat(),
                    },
                )
            else:
                await update_satellite_analysis_status(
                    analysis_id,
                    "failed",
                    {"error": "Green space calculation failed", "progress": 100},
                )
        finally:
            try:
                os.unlink(map_path)
            except Exception:
                pass

    except Exception as e:
        logger.error(f"Green space analysis failed: {e}", exc_info=True)
        try:
            from ..crud import update_satellite_analysis_status
            await update_satellite_analysis_status(
                analysis_id,
                "failed",
                {"error": str(e), "progress": 100},
            )
        except Exception:
            pass


@router.get("/green-space/recent")
async def get_recent_green_space_analyses(
    limit: int = Query(default=5, ge=1, le=50),
    db: Any = Depends(get_database),
):
    try:
        analyses = await (
            db["satellite_analyses"]
            .find(
                {"status": "completed"},
                {
                    "_id": 1,
                    "address": 1,
                    "coordinates": 1,
                    "search_radius_m": 1,
                    "green_space_percentage": 1,
                    "breakdown": 1,
                    "visualization_path": 1,
                    "map_source": 1,
                    "created_at": 1,
                    "completed_at": 1,
                },
            )
            .sort("completed_at", -1)
            .limit(limit)
            .to_list(length=limit)
        )

        if not analyses:
            return {"count": 0, "analyses": []}

        for a in analyses:
            a["_id"] = str(a["_id"])
            for field in ("created_at", "completed_at"):
                if field in a and a[field]:
                    a[field] = (
                        a[field].isoformat()
                        if hasattr(a[field], "isoformat")
                        else str(a[field])
                    )

        return {"count": len(analyses), "analyses": analyses}

    except Exception as e:
        logger.error(f"Error fetching recent analyses: {e}\n{traceback.format_exc()}")
        return {"count": 0, "analyses": [], "error": str(e)}


@router.get("/green-space/{analysis_id}")
async def get_green_space_analysis(analysis_id: str):
    try:
        from ..crud import get_satellite_analysis

        analysis = await get_satellite_analysis(analysis_id)
        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not found")
        return analysis

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get analysis {analysis_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve analysis")