
import os
from dataclasses import dataclass
from typing import List

@dataclass
class APIConfig:
    base_url: str = os.getenv("BACKEND_URL")
    timeout: int = 90
    max_retries: int = 3
    
@dataclass
class UIConfig:
    page_title: str = "GeoInsight AI - Real Estate Intelligence"
    layout: str = "wide"
    initial_sidebar_state: str = "expanded"
    
    # Theme colors
    primary_color: str = "#667eea"
    secondary_color: str = "#764ba2"
    success_color: str = "#28a745"
    warning_color: str = "#ffc107"
    error_color: str = "#dc3545"
    
@dataclass
class FeatureConfig:
    enable_vector_search: bool = True
    enable_image_analysis: bool = True
    enable_ai_agent: bool = True
    enable_maps: bool = True
    max_file_size_mb: int = 10
    
@dataclass
class MapConfig:
    default_zoom: int = 15
    default_radius: int = 1000
    min_radius: int = 100
    max_radius: int = 5000
    
    amenity_types: List[str] = None
    
    def __post_init__(self):
        if self.amenity_types is None:
            self.amenity_types = [
                'restaurant', 'cafe', 'school', 'hospital',
                'park', 'supermarket', 'bank', 'pharmacy',
                'gym', 'library', 'transit_station'
            ]

@dataclass
class PaginationConfig:
    default_page_size: int = 20
    max_page_size: int = 100
    
api_config = APIConfig()
ui_config = UIConfig()
feature_config = FeatureConfig()
map_config = MapConfig()
pagination_config = PaginationConfig()

TASK_POLL_INTERVAL = 3  
TASK_MAX_WAIT = 300 
TASK_PROGRESS_BAR_ENABLED = True
