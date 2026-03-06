import os
import random
import time
import math
import requests
import io
import tempfile
import logging

import osmnx as ox
import networkx as nx
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from typing import Dict, List, Optional, Tuple
import folium
from datetime import datetime
from PIL import Image

logger = logging.getLogger(__name__)

ox.settings.log_console = True
ox.settings.use_cache = True
ox.settings.cache_folder = "./.osmnx_cache"
ox.settings.timeout = 30
ox.settings.max_query_area_size = 50000000

_OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.fr/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

def _configure_overpass():
    endpoint = random.choice(_OVERPASS_ENDPOINTS)
    try:
        ox.settings.overpass_url = endpoint
    except AttributeError:
        try:
            ox.settings.overpass_endpoint = endpoint
        except AttributeError:
            pass
    print(f"Using Overpass endpoint: {endpoint}")
    return endpoint

_configure_overpass()

KNOWN_COORDINATES = {
    'indiranagar, bengaluru, karnataka, india': (12.9716, 77.6412),
    'indiranagar, bangalore, karnataka, india': (12.9716, 77.6412),
    'koramangala, bengaluru, karnataka, india': (12.9352, 77.6245),
    'koramangala, bangalore, karnataka, india': (12.9352, 77.6245),
    'whitefield, bengaluru, karnataka, india': (12.9698, 77.7499),
    'hsr layout, bengaluru, karnataka, india': (12.9116, 77.6389),
    'jayanagar, bengaluru, karnataka, india': (12.9308, 77.5838),
    'jp nagar, bengaluru, karnataka, india': (12.9063, 77.5857),
    'electronic city, bengaluru, karnataka, india': (12.8399, 77.6770),
    'marathahalli, bengaluru, karnataka, india': (12.9591, 77.6974),
    'btm layout, bengaluru, karnataka, india': (12.9166, 77.6101),
    'malleshwaram, bengaluru, karnataka, india': (13.0035, 77.5710),
}


def _normalise(addr: str) -> str:
    """Lower-case, collapse whitespace/punctuation for cache lookups."""
    import re
    s = addr.strip().lower()
    s = re.sub(r'\s+', ' ', s)
    return s


class LocationGeocoder:
    def __init__(self, user_agent: str = "geo_insight_ai"):
        self.geolocator = Nominatim(user_agent=user_agent, timeout=10)
        self.last_request_time = 0.0
        self.min_request_interval = 1.5         
        self._google_key = os.getenv("GOOGLE_API_KEY", "").strip()
        self._google_ok = bool(
            self._google_key and self._google_key not in ("your_key_here", "")
        )
        if self._google_ok:
            logger.info("Google Geocoding API available")
        else:
            logger.warning("GOOGLE_API_KEY not set – falling back to Nominatim only")

   
    def _rate_limit(self):
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()

   
    def _geocode_google(self, address: str) -> Optional[Tuple[float, float]]:
        if not self._google_ok:
            return None
        try:
            url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {"address": address, "key": self._google_key}
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()
            if data.get("status") == "OK" and data.get("results"):
                loc = data["results"][0]["geometry"]["location"]
                coords = (loc["lat"], loc["lng"])
                logger.info(f"Google geocoded '{address}': {coords}")
                return coords
            logger.warning(f"Google geocoding status: {data.get('status')} for '{address}'")
        except Exception as exc:
            logger.warning(f"Google geocoding error for '{address}': {exc}")
        return None

    
    def _geocode_nominatim(self, address: str) -> Optional[Tuple[float, float]]:
        parts = [p.strip() for p in address.split(",") if p.strip()]
        for skip in range(len(parts)):
            query = ", ".join(parts[skip:])
            try:
                self._rate_limit()
                location = self.geolocator.geocode(query)
                if location:
                    coords = (location.latitude, location.longitude)
                    if skip:
                        logger.info(
                            f"Nominatim geocoded via fallback (skipped {skip}): '{query}' → {coords}"
                        )
                    else:
                        logger.info(f"Nominatim geocoded '{address}': {coords}")
                    return coords
            except Exception as exc:
                logger.warning(f"Nominatim error for '{query}': {exc}")
        return None

    
    def address_to_coordinates(self, address: str) -> Optional[Tuple[float, float]]:
        if not address or not isinstance(address, str):
            logger.warning(f"Invalid address: {address!r}")
            return None

        normalised = _normalise(address)

        if normalised in KNOWN_COORDINATES:
            logger.info(f"Cache hit for '{address}'")
            return KNOWN_COORDINATES[normalised]

        for key, coords in KNOWN_COORDINATES.items():
            if normalised.startswith(key) or key.startswith(normalised):
                logger.info(f"Fuzzy cache hit: '{normalised}' ~ '{key}'")
                return coords

        coords = self._geocode_google(address)
        if coords:
            KNOWN_COORDINATES[normalised] = coords
            return coords

        coords = self._geocode_nominatim(address)
        if coords:
            KNOWN_COORDINATES[normalised] = coords
            return coords

        logger.error(f"All geocoding attempts failed for '{address}'")
        return None

    def coordinates_to_address(self, lat: float, lon: float) -> Optional[str]:
        try:
            self._rate_limit()
            location = self.geolocator.reverse(f"{lat}, {lon}")
            return location.address if location else None
        except Exception as e:
            logger.error(f"Reverse geocoding error: {e}")
            return None


_geocoder_instance: Optional[LocationGeocoder] = None

def get_geocoder() -> LocationGeocoder:
    global _geocoder_instance
    if _geocoder_instance is None:
        _geocoder_instance = LocationGeocoder()
    return _geocoder_instance


class OpenStreetMapClient:

    def get_nearby_amenities(
        self,
        address: str,
        radius: float = 1000,
        amenity_types: Optional[List[str]] = None,
        max_results_per_type: int = None
    ) -> Dict:

        if amenity_types is None:
            amenity_types = [
                'restaurant', 'cafe', 'school', 'hospital',
                'park', 'supermarket', 'bank', 'pharmacy'
            ]

        if max_results_per_type is None:
            if radius >= 5000:
                max_results_per_type = 50
            elif radius >= 2000:
                max_results_per_type = 30
            else:
                max_results_per_type = 20

        max_amenity_types = 6
        if radius >= 5000:
            max_amenity_types = 3
        elif radius >= 2000:
            max_amenity_types = 4

        if len(amenity_types) > max_amenity_types:
            print(f"Limiting {len(amenity_types)} amenity types to {max_amenity_types}")
            amenity_types = amenity_types[:max_amenity_types]

        try:
            geocoder = get_geocoder()
            coordinates = geocoder.address_to_coordinates(address)

            if not coordinates:
                return {
                    "error": (
                        f"Could not geocode address: '{address}'. "
                        "Try a more specific address, e.g. 'Koramangala, Bengaluru, Karnataka, India'."
                    ),
                    "address": address,
                }

            lat, lon = coordinates
            _configure_overpass()

            lat_rad = math.radians(lat)
            delta_lat = radius / 111320
            delta_lon = radius / (111320 * math.cos(lat_rad))
            north = lat + delta_lat
            south = lat - delta_lat
            east  = lon + delta_lon
            west  = lon - delta_lon

            amenities_data: Dict[str, List] = {}
            errors: List[str] = []
            timeout_count = 0

            for amenity in amenity_types:
                try:
                    print(f"Fetching {amenity}…")
                    query_timeout = 15 if radius >= 5000 else 12 if radius >= 2000 else 10

                    amenities = ox.features.features_from_bbox(
                        north, south, east, west,
                        tags={'amenity': amenity}
                    )

                    if not amenities.empty:
                        amenities_list = []
                        for idx, row in amenities.iterrows():
                            try:
                                centroid = row.geometry.centroid
                                a_lat = centroid.y
                                a_lon = centroid.x
                            except Exception:
                                continue
                            distance = geodesic(coordinates, (a_lat, a_lon)).km
                            amenities_list.append({
                                'name': row.get('name', f'Unknown {amenity}'),
                                'type': amenity,
                                'coordinates': {'latitude': float(a_lat), 'longitude': float(a_lon)},
                                'distance_km': round(distance, 2),
                            })
                        amenities_list.sort(key=lambda x: x['distance_km'])
                        amenities_data[amenity] = amenities_list[:max_results_per_type]
                    else:
                        amenities_data[amenity] = []

                except TimeoutError:
                    timeout_count += 1
                    msg = f"Timeout fetching {amenity}"
                    print(msg)
                    errors.append(msg)
                    amenities_data[amenity] = []
                    if timeout_count >= 3:
                        print("Too many timeouts, stopping early")
                        break
                except Exception as e:
                    msg = f"Error fetching {amenity}: {e}"
                    print(msg)
                    errors.append(msg)
                    amenities_data[amenity] = []

            return {
                "address":         address,
                "coordinates":     coordinates,
                "search_radius_m": radius,
                "amenities":       amenities_data,
                "errors":          errors or None,
                "timestamp":       datetime.now().isoformat(),
                "timeout_count":   timeout_count,
            }

        except Exception as e:
            return {"error": f"Failed to get amenities: {e}", "address": address}

    def get_building_footprints(self, address: str, radius: float = 500) -> Dict:
        try:
            geocoder = get_geocoder()
            coordinates = geocoder.address_to_coordinates(address)
            if not coordinates:
                return {"error": "Could not geocode address"}

            lat, lon = coordinates
            try:
                buildings = ox.features.features_from_point(
                    (lat, lon), dist=radius, tags={'building': True}
                )
            except TimeoutError:
                return {"error": "Timeout fetching buildings", "address": address, "coordinates": coordinates}

            building_data = []
            if not buildings.empty:
                for idx, row in buildings.iterrows():
                    try:
                        centroid = row.geometry.centroid
                        area = row.geometry.area if hasattr(row.geometry, 'area') else None
                        building_data.append({
                            'building_id':   str(idx),
                            'building_type': row.get('building', 'unknown'),
                            'geometry_type': row.geometry.geom_type,
                            'area_sq_m':     round(area, 2) if area else None,
                            'centroid': {
                                'latitude':  float(centroid.y),
                                'longitude': float(centroid.x),
                            },
                        })
                    except Exception:
                        continue

            return {
                "address":         address,
                "coordinates":     coordinates,
                "total_buildings": len(building_data),
                "buildings":       building_data,
            }
        except Exception as e:
            return {"error": f"Failed to get buildings: {e}", "address": address}

    def create_map_visualization(
        self,
        address: str,
        amenities_data: Dict,
        save_path: str = "map.html"
    ) -> Optional[str]:
        try:
            coordinates = amenities_data.get("coordinates")
            if not coordinates:
                print("No coordinates in amenities_data")
                return None

            lat, lon = coordinates

            if not os.path.isabs(save_path):
                backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                save_path = os.path.join(backend_root, save_path)

            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            m = folium.Map(
                location=[lat, lon],
                zoom_start=15,
                tiles='OpenStreetMap',
                control_scale=True,
                prefer_canvas=True,
            )

            folium.Marker(
                [lat, lon],
                popup=folium.Popup(f"<b>Target Location</b><br>{address}", max_width=300),
                tooltip="Target Location",
                icon=folium.Icon(color="red", icon="star", prefix='fa'),
            ).add_to(m)

            colors = {
                'restaurant': 'blue', 'cafe': 'green', 'school': 'orange',
                'hospital': 'red', 'park': 'darkgreen', 'supermarket': 'purple',
                'bank': 'darkblue', 'pharmacy': 'pink', 'gym': 'cadetblue',
                'library': 'lightblue', 'transit_station': 'gray',
            }

            marker_count = 0
            for amenity_type, items in amenities_data.get("amenities", {}).items():
                color = colors.get(amenity_type, 'gray')
                for item in items:
                    try:
                        c = item.get('coordinates', {})
                        a_lat, a_lon = c.get('latitude'), c.get('longitude')
                        if a_lat and a_lon:
                            popup_html = (
                                f"<div style='font-family:Arial;min-width:150px'>"
                                f"<h4 style='margin:0 0 5px 0'>{item.get('name','Unknown')}</h4>"
                                f"<p style='margin:0'><b>Type:</b> {amenity_type.title()}</p>"
                                f"<p style='margin:0'><b>Distance:</b> {item.get('distance_km',0):.2f} km</p>"
                                f"</div>"
                            )
                            folium.Marker(
                                [a_lat, a_lon],
                                popup=folium.Popup(popup_html, max_width=300),
                                tooltip=item.get('name', 'Unknown'),
                                icon=folium.Icon(color=color, icon="info-sign"),
                            ).add_to(m)
                            marker_count += 1
                    except Exception:
                        continue

            folium.Circle(
                radius=amenities_data.get("search_radius_m", 1000),
                location=[lat, lon],
                color='crimson', fill=True,
                fill_color='crimson', fill_opacity=0.1, weight=2,
            ).add_to(m)

            folium.LayerControl().add_to(m)
            m.save(save_path)

            if os.path.exists(save_path) and os.path.getsize(save_path) > 1000:
                return save_path
            return None

        except Exception as e:
            logger.error(f"Error creating map: {e}", exc_info=True)
            return None


def calculate_walk_score(coordinates: Tuple[float, float], amenities_data: Dict) -> float:
    try:
        amenities = amenities_data.get("amenities", {})
        if not amenities:
            return 0.0

        score = 0
        max_points = 0
        weights = {
            'restaurant': 10, 'cafe': 8, 'supermarket': 15, 'pharmacy': 12,
            'school': 8, 'hospital': 5, 'park': 10, 'bank': 5,
            'gym': 7, 'library': 6, 'transit_station': 12,
        }

        for amenity_type, items in amenities.items():
            weight = weights.get(amenity_type, 5)
            max_points += weight * 5
            for item in items[:5]:
                distance_km = item.get('distance_km', 10)
                if not isinstance(distance_km, (int, float)) or math.isnan(distance_km):
                    distance_km = 10
                distance_m = distance_km * 1000
                if distance_m <= 500:
                    score += weight
                elif distance_m <= 1000:
                    score += weight * 0.7
                elif distance_m <= 2000:
                    score += weight * 0.3

        if max_points > 0:
            val = round(min((score / max_points) * 100, 100), 1)
            return 0.0 if math.isnan(val) else val
        return 0.0

    except Exception as e:
        logger.error(f"Error calculating walk score: {e}")
        return 0.0


def lat_lon_to_tile(latitude: float, longitude: float, zoom: int) -> Tuple[int, int]:
    lat_rad = math.radians(latitude)
    n = 2.0 ** zoom
    tile_x = int((longitude + 180.0) / 360.0 * n)
    tile_y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return tile_x, tile_y


def download_osm_tile(tile_x: int, tile_y: int, zoom: int, timeout: int = 5) -> Optional[Image.Image]:
    try:
        url = f"https://tile.openstreetmap.org/{zoom}/{tile_x}/{tile_y}.png"
        headers = {'User-Agent': 'GeoInsightAI/1.0 (Educational Project)'}
        response = requests.get(url, headers=headers, timeout=timeout)
        if response.status_code == 200:
            return Image.open(io.BytesIO(response.content))
        logger.warning(f"OSM tile ({tile_x},{tile_y}) returned {response.status_code}")
    except requests.exceptions.Timeout:
        logger.warning(f"OSM tile ({tile_x},{tile_y}) timeout")
    except Exception as e:
        logger.warning(f"OSM tile ({tile_x},{tile_y}) error: {e}")
    return None


def get_osm_map_area(latitude: float, longitude: float, radius_meters: int = 500) -> Optional[str]:
    logger.info(f"Fetching OSM map for ({latitude:.4f}, {longitude:.4f}), radius={radius_meters}m")

    zoom = 17 if radius_meters <= 500 else 16 if radius_meters <= 1000 else 15
    center_x, center_y = lat_lon_to_tile(latitude, longitude, zoom)

    if radius_meters <= 600:
        tile = download_osm_tile(center_x, center_y, zoom)
        if not tile:
            return None
        try:
            fd, temp_path = tempfile.mkstemp(suffix='.png', prefix='osm_map_')
            os.close(fd)
            tile.save(temp_path, format='PNG')
            return temp_path
        except Exception as e:
            logger.error(f"Failed to save tile: {e}")
            return None
    else:
        tiles = {}
        for dx in [0, 1]:
            for dy in [0, 1]:
                tile = download_osm_tile(center_x + dx, center_y + dy, zoom)
                if tile:
                    tiles[(center_x + dx, center_y + dy)] = tile

        if not tiles:
            return None

        if len(tiles) == 1:
            tile = list(tiles.values())[0]
        else:
            tile_size = 256
            stitched = Image.new('RGB', (tile_size * 2, tile_size * 2), color=(240, 240, 240))
            for (tx, ty), t in tiles.items():
                stitched.paste(t, ((tx - center_x) * tile_size, (ty - center_y) * tile_size))
            tile = stitched

        try:
            fd, temp_path = tempfile.mkstemp(suffix='.png', prefix='osm_map_')
            os.close(fd)
            tile.save(temp_path, format='PNG')
            return temp_path
        except Exception as e:
            logger.error(f"Failed to save stitched image: {e}")
            return None