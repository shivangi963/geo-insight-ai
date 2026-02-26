import os
import traceback
from celery import shared_task
from app.geospatial import OpenStreetMapClient, calculate_walk_score
from app.database import get_sync_database
from typing import Dict
from datetime import datetime
from bson import ObjectId

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MAPS_DIR = os.path.join(PROJECT_ROOT, "maps")


def update_analysis_status_sync(db, analysis_id: str, status: str, updates: Dict = None):
    try:
        update_data = {
            "status": status,
            "updated_at": datetime.now()
        }
        if updates:
            update_data.update(updates)

        try:
            obj_id = ObjectId(analysis_id)
            result = db.neighborhood_analyses.update_one(
                {"_id": obj_id},
                {"$set": update_data}
            )
        except Exception:
            result = db.neighborhood_analyses.update_one(
                {"_id": analysis_id},
                {"$set": update_data}
            )

        if result.modified_count > 0:
            print(f" Updated analysis {analysis_id} to status: {status}")
        else:
            print(f" No documents updated for analysis ID: {analysis_id}")

    except Exception as e:
        print(f" Error updating analysis status: {e}")


def _run_green_space_sync(coordinates, radius_m: int, analysis_id: str) -> Dict:
    from app.geospatial import get_osm_map_area
    from app.tasks.computer_vision_tasks import analyze_osm_green_spaces

    lat, lon = coordinates
    tile_radius = min(radius_m, 1000)
    map_path = None
    try:
        map_path = get_osm_map_area(lat, lon, tile_radius)
        if not map_path or not os.path.exists(map_path):
            print(" Green-space tile fetch returned nothing – skipping")
            return {}

        gs_id = f"nbr_{analysis_id}"
        result = analyze_osm_green_spaces(map_path, gs_id)
        return result or {}
    except Exception as exc:
        print(f" Green-space analysis failed (non-critical): {exc}")
        return {}
    finally:
        if map_path and os.path.exists(map_path):
            try:
                os.unlink(map_path)
            except Exception:
                pass


@shared_task(bind=True, name="analyze_neighborhood")
def analyze_neighborhood_task(self, analysis_id: str, request_data: Dict) -> Dict:

    mongo_client = None  
    db = None
    map_path = None

    try:
        
        mongo_client, db = get_sync_database()

        self.update_state(state='PROGRESS', meta={
            'status': 'Geocoding address...',
            'progress': 5
        })
        update_analysis_status_sync(db, analysis_id, 'processing', {'progress': 5})

        osm_client = OpenStreetMapClient()

        address = request_data.get('address')
        radius_m = request_data.get('radius_m', 1000)
        amenity_types = request_data.get('amenity_types')
        include_buildings = request_data.get('include_buildings', True)
        generate_map = request_data.get('generate_map', True)

        self.update_state(state='PROGRESS', meta={
            'status': 'Fetching amenities from OpenStreetMap...',
            'progress': 20
        })
        update_analysis_status_sync(db, analysis_id, 'processing', {'progress': 20})

        amenities_data = osm_client.get_nearby_amenities(
            address=address,
            radius=radius_m,
            amenity_types=amenity_types
        )

        if "error" in amenities_data:
            raise Exception(amenities_data["error"])

        self.update_state(state='PROGRESS', meta={
            'status': 'Calculating walk score...',
            'progress': 50
        })
        update_analysis_status_sync(db, analysis_id, 'processing', {'progress': 50})

        coordinates = amenities_data.get("coordinates")
        walk_score = None
        if coordinates:
            walk_score = calculate_walk_score(coordinates, amenities_data)

        green_space_data: Dict = {}
        if coordinates:
            self.update_state(state='PROGRESS', meta={
                'status': 'Analysing green spaces…',
                'progress': 55
            })
            update_analysis_status_sync(db, analysis_id, 'processing', {'progress': 55})
            green_space_data = _run_green_space_sync(coordinates, radius_m, analysis_id)
            gs_pct = green_space_data.get("green_space_percentage", "n/a")
            print(f" Green space: {gs_pct}%")

        building_footprints = []
        if include_buildings:
            self.update_state(state='PROGRESS', meta={
                'status': 'Analyzing building footprints...',
                'progress': 65
            })
            update_analysis_status_sync(db, analysis_id, 'processing', {'progress': 65})

            try:
                buildings_data = osm_client.get_building_footprints(
                    address=address,
                    radius=min(radius_m, 500)
                )
                if "error" not in buildings_data:
                    building_footprints = buildings_data.get("buildings", [])
            except Exception as e:
                print(f" Building footprints failed: {e}")

        if generate_map and coordinates:
            self.update_state(state='PROGRESS', meta={
                'status': 'Generating interactive map...',
                'progress': 80
            })
            update_analysis_status_sync(db, analysis_id, 'processing', {'progress': 80})

            try:
                os.makedirs(MAPS_DIR, exist_ok=True)

                map_filename = f"neighborhood_{analysis_id.replace('-', '_')}.html"
                map_absolute_path = os.path.join(MAPS_DIR, map_filename)

                print(f"Generating map at: {map_absolute_path}")

                result_path = osm_client.create_map_visualization(
                    address=address,
                    amenities_data=amenities_data,
                    save_path=map_absolute_path
                )

                if result_path and os.path.exists(result_path):
                    map_path = f"maps/{map_filename}"
                    print(f"  Map created successfully: {map_path}")
                    print(f"   Absolute path: {result_path}")
                    print(f"   Size: {os.path.getsize(result_path):,} bytes")
                else:
                    print(f" Map generation returned no valid path")
                    map_path = None

            except Exception as map_error:
                print(f"Map generation failed: {map_error}")
                traceback.print_exc()
                map_path = None

        amenities = amenities_data.get("amenities", {})
        total_amenities = sum(len(items) for items in amenities.values())

        results = {
            'analysis_id': analysis_id,
            'status': 'completed',
            'address': address,
            'walk_score': walk_score,
            'total_amenities': total_amenities,
            'building_count': len(building_footprints),
            'map_path': map_path,
            'coordinates': coordinates,
            'amenities': amenities,
            'green_space_percentage':    green_space_data.get('green_space_percentage'),
            'green_space_breakdown':     green_space_data.get('breakdown'),
            'green_space_visualization': green_space_data.get('visualization_path'),
            'green_pixels':              green_space_data.get('green_pixels'),
            'total_pixels':              green_space_data.get('total_pixels'),
            'timestamp': datetime.now().isoformat()
        }

        update_data = {
            'status': 'completed',
            'walk_score': walk_score,
            'map_path': map_path,
            'amenities': amenities,
            'building_footprints': building_footprints,
            'total_amenities': total_amenities,
            'coordinates': coordinates,
            'green_space_percentage':    green_space_data.get('green_space_percentage'),
            'green_space_breakdown':     green_space_data.get('breakdown'),
            'green_space_visualization': green_space_data.get('visualization_path'),
            'green_pixels':              green_space_data.get('green_pixels'),
            'total_pixels':              green_space_data.get('total_pixels'),
            'completed_at': datetime.now(),
            'progress': 100
        }

        update_analysis_status_sync(db, analysis_id, 'completed', update_data)

        print(f"Analysis {analysis_id} completed successfully")
        print(f"Address: {address}")
        print(f"Amenities: {total_amenities}")
        print(f"Walk Score: {walk_score}")
        print(f"Map: {' Created' if map_path else ' Not created'}")

        return results

    except Exception as e:
        error_msg = str(e)
        error_trace = traceback.format_exc()

        print(f" Analysis failed: {error_msg}")
        print(f"Traceback:\n{error_trace}")

        if db is not None:
            update_analysis_status_sync(db, analysis_id, 'failed', {
                'error': error_msg,
                'progress': 100
            })

        return {
            'analysis_id': analysis_id,
            'status': 'failed',
            'error': error_msg,
            'timestamp': datetime.now().isoformat()
        }

    finally:
       
        if mongo_client is not None:
            try:
                mongo_client.close()
            except Exception:
                pass