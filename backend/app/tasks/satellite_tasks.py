from celery import shared_task
from datetime import datetime
from bson import ObjectId
import traceback
import os
import logging

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@shared_task(bind=True, name="analyze_satellite")
def analyze_satellite_task(self, analysis_id: str, request_data: dict) -> dict:

    temp_path = None
    mongo_client = None

    try:
        from app.database import get_sync_database
        from app.tasks.computer_vision_tasks import analyze_osm_green_spaces
        from app.geospatial import get_geocoder, get_osm_map_area

        mongo_client, db = get_sync_database()

        self.update_state(state='PROGRESS', meta={
            'status': 'Geocoding address...',
            'progress': 10
        })

        update_analysis_status_sync(db, analysis_id, 'processing', {'progress': 10})

        address = request_data.get('address')
        radius_m = request_data.get('radius_m', 500)

        geocoder = get_geocoder()
        coordinates = geocoder.address_to_coordinates(address)

        if not coordinates:
            raise Exception("Could not geocode address")

        lat, lon = coordinates

        self.update_state(state='PROGRESS', meta={
            'status': 'Fetching OpenStreetMap tiles...',
            'progress': 30
        })

        update_analysis_status_sync(db, analysis_id, 'processing', {
            'progress': 30,
            'coordinates': {'latitude': lat, 'longitude': lon}
        })

        temp_path = get_osm_map_area(lat, lon, radius_m)

        if not temp_path:
            raise Exception("Failed to fetch OpenStreetMap tiles")

        if not os.path.exists(temp_path):
            raise Exception(f"Map file not found: {temp_path}")

        logger.info(f" OSM map saved to: {temp_path}")

        self.update_state(state='PROGRESS', meta={
            'status': 'Analyzing green spaces...',
            'progress': 60
        })

        update_analysis_status_sync(db, analysis_id, 'processing', {'progress': 60})

        result = analyze_osm_green_spaces(temp_path, analysis_id)

        if result:
            green_space_pct = result.get('green_space_percentage', 0)
            green_pixels = result.get('green_pixels', 0)
            total_pixels = result.get('total_pixels', 0)
            visualization_path = result.get('visualization_path')
            breakdown = result.get('breakdown', {})

            result_data = {
                'address': address,
                'coordinates': {'latitude': lat, 'longitude': lon},
                'search_radius_m': radius_m,
                'green_space_percentage': green_space_pct,
                'green_pixels': green_pixels,
                'total_pixels': total_pixels,
                'visualization_path': visualization_path,
                'breakdown': breakdown,
                'map_source': 'OpenStreetMap',
                'status': 'completed',
                'progress': 100,
                'completed_at': datetime.now().isoformat()
            }

            update_analysis_status_sync(db, analysis_id, 'completed', result_data)

            logger.info(f" Satellite analysis {analysis_id} completed")
            logger.info(f"   Green Space: {green_space_pct:.1f}%")

            return result_data
        else:
            raise Exception("Green space calculation failed")

    except Exception as e:
        error_msg = str(e)
        error_trace = traceback.format_exc()

        logger.error(f" Satellite analysis failed: {error_msg}")
        logger.error(f"Traceback:\n{error_trace}")

        try:
            from app.database import get_sync_database
            _client, _db = get_sync_database()  
            update_analysis_status_sync(_db, analysis_id, 'failed', {
                'error': error_msg,
                'progress': 100
            })
            _client.close()
        except Exception:
            pass

        return {
            'analysis_id': analysis_id,
            'status': 'failed',
            'error': error_msg,
            'timestamp': datetime.now().isoformat()
        }

    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
                logger.info(f" Cleaned up temp file: {temp_path}")
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup temp file: {cleanup_error}")

        if mongo_client is not None:
            try:
                mongo_client.close()
            except Exception:
                pass


def update_analysis_status_sync(db, analysis_id: str, status: str, updates: dict = None):
    try:
        update_data = {
            'status': status,
            'updated_at': datetime.now()
        }
        if updates:
            update_data.update(updates)

        try:
            obj_id = ObjectId(analysis_id)
            result = db.satellite_analyses.update_one(
                {"_id": obj_id},
                {"$set": update_data}
            )
        except Exception:
            result = db.satellite_analyses.update_one(
                {"_id": analysis_id},
                {"$set": update_data}
            )

        if result.modified_count > 0:
            logger.info(f" Updated analysis {analysis_id} to status: {status}")
        else:
            logger.warning(f" No documents updated for analysis ID: {analysis_id}")

    except Exception as e:
        logger.error(f" Error updating analysis status: {e}")