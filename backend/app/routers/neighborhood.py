from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from typing import List, Optional, Dict
from fastapi.responses import FileResponse
import logging
from datetime import datetime
import asyncio
import os


from ..models import NeighborhoodAnalysisRequest, NeighborhoodAnalysisResponse, NeighborhoodAnalysis
from ..crud import (
    create_neighborhood_analysis,
    get_neighborhood_analysis,
    get_recent_analyses,
    update_analysis_status
)
from ..geospatial import OpenStreetMapClient, calculate_walk_score

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/neighborhood", tags=["neighborhood"])

osm_client = OpenStreetMapClient()

PROGRESS_START = 10
PROGRESS_AMENITIES = 40
PROGRESS_WALK_SCORE = 55
PROGRESS_GREEN_SPACE = 75
PROGRESS_MAP = 85
PROGRESS_COMPLETE = 100

AMENITY_TYPES = ['restaurant', 'cafe', 'school', 'hospital', 'park', 'supermarket']


async def update_analysis_progress(analysis_id: str, progress: int,
                                   message: str = "", data: dict = None):
    try:
        update_data = {"progress": progress}
        if message:
            update_data["message"] = message
        if data:
            update_data.update(data)
        await update_analysis_status(analysis_id, "processing", update_data)
    except Exception as e:
        logger.error(f"Failed to update progress for {analysis_id}: {e}")


async def _analyze_green_space(
    coordinates,
    radius_m: int,
    analysis_id: str
) -> Dict:
    from ..geospatial import get_osm_map_area
    from ..tasks.computer_vision_tasks import analyze_osm_green_spaces

    lat, lon = coordinates
    tile_radius = min(radius_m, 1000)
    map_path = None

    try:
        map_path = await asyncio.to_thread(get_osm_map_area, lat, lon, tile_radius)

        if not map_path or not os.path.exists(map_path):
            logger.warning("Green-space tile fetch returned nothing – skipping")
            return {}

        gs_id = f"nbr_{analysis_id}"
        result = await asyncio.to_thread(analyze_osm_green_spaces, map_path, gs_id)
        return result or {}

    except Exception as exc:
        logger.warning(f"Green-space sub-analysis failed (non-critical): {exc}")
        return {}

    finally:
        if map_path and os.path.exists(map_path):
            try:
                os.unlink(map_path)
            except Exception:
                pass


async def process_neighborhood_sync(
    analysis_id: str,
    address: str,
    radius_m: int,
    amenity_types: List[str],
    include_buildings: bool = False,
    generate_map: bool = True,
):
    try:
        amenities_data = await asyncio.to_thread(
            osm_client.get_nearby_amenities,
            address=address,
            radius=radius_m,
            amenity_types=amenity_types
        )

        if "error" in amenities_data:
            await update_analysis_status(analysis_id, "failed", {
                "error": amenities_data["error"], "progress": 100
            })
            return

        await update_analysis_progress(
            analysis_id, PROGRESS_AMENITIES, "Calculating walk score…"
        )

        coordinates = amenities_data.get("coordinates")
        walk_score = None
        if coordinates:
            walk_score = await asyncio.to_thread(
                calculate_walk_score, coordinates, amenities_data
            )

        await update_analysis_progress(
            analysis_id, PROGRESS_WALK_SCORE, "Analysing green spaces…",
            {"walk_score": walk_score}
        )

        green_space_data: Dict = {}
        if coordinates:
            try:
                await update_analysis_progress(
                    analysis_id, PROGRESS_WALK_SCORE + 5,
                    "Fetching OpenStreetMap tiles for green-space analysis…"
                )
                green_space_data = await _analyze_green_space(
                    coordinates, radius_m, analysis_id
                )
                gs_pct = green_space_data.get("green_space_percentage", 0)
                logger.info(
                    f"[{analysis_id}] Green space: {gs_pct:.1f}%"
                )
            except Exception as exc:
                logger.warning(f"Green space failed (non-critical): {exc}")

        await update_analysis_progress(
            analysis_id, PROGRESS_GREEN_SPACE,
            "Generating interactive map…" if generate_map else "Finalising…",
            {
                "green_space_percentage": green_space_data.get("green_space_percentage"),
                "green_space_breakdown": green_space_data.get("breakdown"),
                "green_space_visualization": green_space_data.get("visualization_path"),
                "green_pixels": green_space_data.get("green_pixels"),
                "total_pixels": green_space_data.get("total_pixels"),
            }
        )

        map_path = None
        if generate_map and coordinates:
            await update_analysis_progress(analysis_id, PROGRESS_MAP,
                                           "Generating map…")
            try:
                map_filename = f"neighborhood_{analysis_id.replace('-', '_')}.html"
                map_path = os.path.join("maps", map_filename)

                result = await asyncio.to_thread(
                    osm_client.create_map_visualization,
                    address=address,
                    amenities_data=amenities_data,
                    save_path=map_path
                )
                map_path = result if result and os.path.exists(result) else None
            except Exception as exc:
                logger.error(f"Map generation failed: {exc}")

        amenities = amenities_data.get("amenities", {})
        total_amenities = sum(len(v) for v in amenities.values())

        result_data = {
            "walk_score": walk_score,
            "map_path": map_path,
            "amenities": amenities,
            "total_amenities": total_amenities,
            "coordinates": coordinates,
            "green_space_percentage": green_space_data.get("green_space_percentage"),
            "green_space_breakdown": green_space_data.get("breakdown"),
            "green_space_visualization": green_space_data.get("visualization_path"),
            "green_pixels": green_space_data.get("green_pixels"),
            "total_pixels": green_space_data.get("total_pixels"),
            "progress": PROGRESS_COMPLETE,
            "completed_at": datetime.now().isoformat(),
        }

        await update_analysis_status(analysis_id, "completed", result_data)
        logger.info(
            f"Analysis {analysis_id} completed — "
            f"amenities={total_amenities}, walk={walk_score}, "
            f"green={green_space_data.get('green_space_percentage', 'n/a')}%"
        )

    except Exception as exc:
        logger.error(f"Analysis failed: {exc}", exc_info=True)
        await update_analysis_status(analysis_id, "failed", {
            "error": str(exc), "progress": 100
        })


@router.post("/analyze", status_code=202, response_model=NeighborhoodAnalysisResponse)
async def analyze_neighborhood(
    analysis_request: NeighborhoodAnalysisRequest,
    background_tasks: BackgroundTasks,
):
    try:
        analysis_doc = {
            "address": analysis_request.address,
            "search_radius_m": analysis_request.radius_m,
            "amenity_types": analysis_request.amenity_types,
            "include_buildings": analysis_request.include_buildings,
            "generate_map": analysis_request.generate_map,
            "status": "pending",
            "progress": 0,
            "created_at": datetime.now().isoformat(),
        }

        analysis_id = await create_neighborhood_analysis(analysis_doc)
        logger.info(f"Created analysis: {analysis_id}")

        CELERY_AVAILABLE = False
        try:
            from celery.result import AsyncResult
            from celery_config import celery_app
            CELERY_AVAILABLE = True
        except ImportError:
            pass

        use_celery = CELERY_AVAILABLE
        task_id: str = ""

        if use_celery:
            try:
                from ..tasks.geospatial_tasks import analyze_neighborhood_task
                task = analyze_neighborhood_task.delay(
                    analysis_id=analysis_id,
                    request_data=analysis_request.dict()
                )
                task_id = task.id
                logger.info(f"Celery task created: {task_id}")
            except ImportError:
                logger.warning("Celery task import failed – using background task")
                use_celery = False

        if not use_celery:
            task_id = f"analysis_{analysis_id}"
            background_tasks.add_task(
                process_neighborhood_sync,
                analysis_id,
                analysis_request.address,
                analysis_request.radius_m,
                analysis_request.amenity_types or AMENITY_TYPES[:8],
                analysis_request.include_buildings,
                analysis_request.generate_map,
            )
            logger.info(f"Background task scheduled: {task_id}")

        return NeighborhoodAnalysisResponse(
            analysis_id=analysis_id,
            task_id=task_id,
            address=analysis_request.address,
            status="queued",
            message="Analysis includes amenities, walk score, green space coverage, and map",
        )
    except Exception as exc:
        logger.error(f"Failed to create analysis: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/recent")
async def get_recent(limit: int = Query(10)):
    try:
        analyses = await get_recent_analyses(limit)
        if not analyses:
            return {"analyses": []}

        formatted = []
        for a in analyses:
            amenities = a.get("amenities", {})
            total = sum(len(v) for v in amenities.values())
            formatted.append({
                "analysis_id": str(a.get("id", a.get("_id", ""))),
                "address": a.get("address", "Unknown"),
                "status": a.get("status", "unknown"),
                "walk_score": a.get("walk_score"),
                "total_amenities": total,
                "created_at": a.get("created_at"),
                "map_available": bool(a.get("map_path")),
                "amenity_categories": len(amenities),
                "green_space_percentage": a.get("green_space_percentage"),
            })

        return {"analyses": formatted}

    except Exception as exc:
        logger.error(f"Failed to get recent analyses: {exc}")
        return {"analyses": []}


@router.get("/{analysis_id}", response_model=NeighborhoodAnalysis)
async def get_analysis(analysis_id: str):
    try:
        analysis = await get_neighborhood_analysis(analysis_id)
        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not found")

        coordinates = analysis.get("coordinates")
        if isinstance(coordinates, (list, tuple)) and len(coordinates) == 2:
            analysis["coordinates"] = {
                "latitude": coordinates[0],
                "longitude": coordinates[1],
            }
        elif not isinstance(coordinates, dict):
            analysis["coordinates"] = None

        amenities = analysis.get("amenities", {})
        analysis["total_amenities"] = sum(len(v) for v in amenities.values())
        analysis["amenity_categories"] = len(amenities)

        return analysis

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to get analysis {analysis_id}: {exc}")
        raise HTTPException(status_code=500, detail="Failed to retrieve analysis")


@router.get("/{analysis_id}/map")
async def get_analysis_map(analysis_id: str):
    try:
        analysis = await get_neighborhood_analysis(analysis_id)
        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not found")
        if analysis.get("status") != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Analysis not completed. Status: {analysis.get('status')}"
            )

        map_path = analysis.get("map_path")
        if not map_path:
            raise HTTPException(status_code=404, detail="Map not generated")

        if not os.path.isabs(map_path):
            backend_root = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            map_path = os.path.join(backend_root, map_path)

        if not os.path.exists(map_path):
            raise HTTPException(
                status_code=404,
                detail=f"Map file not found: {os.path.basename(map_path)}"
            )

        return FileResponse(
            map_path,
            media_type="text/html",
            headers={
                "Content-Type": "text/html; charset=utf-8",
                "Content-Disposition": "inline",
                "Cache-Control": "no-cache",
            },
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to get map for {analysis_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{analysis_id}/generate-image")
async def generate_location_image(analysis_id: str):
    try:
        from ..image_generator import image_generator

        analysis = await get_neighborhood_analysis(analysis_id)
        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not found")

        coordinates = analysis.get("coordinates")
        if not coordinates:
            raise HTTPException(status_code=400, detail="No coordinates available")

        if isinstance(coordinates, (list, tuple)):
            lat, lon = coordinates
        else:
            lat = coordinates.get("latitude")
            lon = coordinates.get("longitude")

        image_path = image_generator.generate_osm_static_map(
            latitude=lat, longitude=lon, zoom=15, width=800, height=600, add_marker=True
        )
        if not image_path or not os.path.exists(image_path):
            raise HTTPException(status_code=500, detail="Failed to generate image")

        return FileResponse(
            image_path,
            media_type="image/png",
            headers={
                "Content-Disposition": f'inline; filename="location_{analysis_id}.png"'
            },
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error generating image: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
    