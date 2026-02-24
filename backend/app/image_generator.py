
import os
import requests
from typing import Optional, Tuple
from PIL import Image, ImageDraw, ImageFont
import io
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class LocationImageGenerator:

    
    def __init__(self):
        self.mapbox_token = os.getenv('MAPBOX_TOKEN', '')
        self.use_mapbox = bool(self.mapbox_token and self.mapbox_token != 'your_token_here')
        self.cache_dir = "property_images"
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def generate_osm_static_map(
        self,
        latitude: float,
        longitude: float,
        zoom: int = 15,
        width: int = 600,
        height: int = 400,
        add_marker: bool = True
    ) -> Optional[str]:
        
        try:
            if self.use_mapbox:
                return self._generate_mapbox_image(latitude, longitude, zoom, width, height, add_marker)
            else:
                return self._generate_osm_tiles_image(latitude, longitude, zoom, width, height, add_marker)
        
        except Exception as e:
            logger.error(f"Error generating map image: {e}")
            return None
    
    def _generate_mapbox_image(
        self,
        lat: float,
        lon: float,
        zoom: int,
        width: int,
        height: int,
        marker: bool
    ) -> Optional[str]:
       
        overlay = f"pin-s+ff0000({lon},{lat})" if marker else ""
        
        url = f"https://api.mapbox.com/styles/v1/mapbox/streets-v11/static/{overlay}/{lon},{lat},{zoom}/{width}x{height}"
        url += f"?access_token={self.mapbox_token}"
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            
            filename = f"map_{lat:.4f}_{lon:.4f}_{int(datetime.now().timestamp())}.png"
            filepath = os.path.join(self.cache_dir, filename)
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"Generated Mapbox image: {filepath}")
            return filepath
        else:
            logger.error(f"Mapbox API error: {response.status_code}")
            return None
    
    def _generate_osm_tiles_image(
        self,
        lat: float,
        lon: float,
        zoom: int,
        width: int,
        height: int,
        marker: bool
    ) -> Optional[str]:
    
        from .geospatial import lat_lon_to_tile, download_osm_tile
        
        try:

            tile_x, tile_y = lat_lon_to_tile(lat, lon, zoom)

            center_tile = download_osm_tile(tile_x, tile_y, zoom, timeout=10)
            
            if not center_tile:
                logger.error("Failed to download OSM tile")
                return None
            
            canvas_width = width
            canvas_height = height
            canvas = Image.new('RGB', (canvas_width, canvas_height), color=(240, 240, 240))
            
            tile_width, tile_height = center_tile.size
            x_offset = (canvas_width - tile_width) // 2
            y_offset = (canvas_height - tile_height) // 2
            canvas.paste(center_tile, (x_offset, y_offset))
            
            if marker:
                draw = ImageDraw.Draw(canvas)
                marker_x = canvas_width // 2
                marker_y = canvas_height // 2
                
                draw.ellipse(
                    [marker_x - 10, marker_y - 10, marker_x + 10, marker_y + 10],
                    fill='red',
                    outline='darkred',
                    width=2
                )
            
            filename = f"osm_{lat:.4f}_{lon:.4f}_{int(datetime.now().timestamp())}.png"
            filepath = os.path.join(self.cache_dir, filename)
            canvas.save(filepath)
            
            logger.info(f"Generated OSM tile image: {filepath}")
            return filepath
        
        except Exception as e:
            logger.error(f"Error generating OSM tile image: {e}")
            return None
    
    def generate_comparison_image(
        self,
        neighborhoods: list,
        title: str = "Neighborhood Comparison"
    ) -> Optional[str]:
       
        try:
            cols = min(len(neighborhoods), 3)
            rows = (len(neighborhoods) + cols - 1) // cols
            
            cell_width = 400
            cell_height = 300
            margin = 20
            
            canvas_width = cols * cell_width + (cols + 1) * margin
            canvas_height = rows * cell_height + (rows + 1) * margin + 60 
            
            canvas = Image.new('RGB', (canvas_width, canvas_height), color='white')
            draw = ImageDraw.Draw(canvas)
            
            try:
                font = ImageFont.truetype("arial.ttf", 24)
            except:
                font = ImageFont.load_default()
            
            draw.text((margin, 20), title, fill='black', font=font)
            
            for idx, neighborhood in enumerate(neighborhoods[:9]):  
                row = idx // cols
                col = idx % cols
                
                x = col * cell_width + (col + 1) * margin
                y = row * cell_height + (row + 1) * margin + 60
    
                coords = neighborhood.get('coordinates')
                if coords:
                    if isinstance(coords, (list, tuple)):
                        lat, lon = coords
                    else:
                        lat = coords.get('latitude')
                        lon = coords.get('longitude')
                    
           
                    mini_map_path = self.generate_osm_static_map(
                        lat, lon, zoom=14, 
                        width=cell_width - 20, 
                        height=cell_height - 60
                    )
                    
                    if mini_map_path and os.path.exists(mini_map_path):
                        mini_map = Image.open(mini_map_path)
                        canvas.paste(mini_map, (x + 10, y + 10))

                        try:
                            os.unlink(mini_map_path)
                        except:
                            pass
                

                address = neighborhood.get('address', 'Unknown')[:40]
                similarity = neighborhood.get('similarity_score', 0) * 100
                
                label_y = y + cell_height - 40
                draw.rectangle([x, label_y, x + cell_width, y + cell_height], fill='rgba(0,0,0,0.7)')
                
                try:
                    label_font = ImageFont.truetype("arial.ttf", 12)
                except:
                    label_font = ImageFont.load_default()
                
                draw.text((x + 10, label_y + 5), f"{address}", fill='white', font=label_font)
                draw.text((x + 10, label_y + 20), f"Match: {similarity:.0f}%", fill='lightgreen', font=label_font)
            
            filename = f"comparison_{int(datetime.now().timestamp())}.png"
            filepath = os.path.join(self.cache_dir, filename)
            canvas.save(filepath)
            
            logger.info(f"Generated comparison image: {filepath}")
            return filepath
        
        except Exception as e:
            logger.error(f"Error generating comparison image: {e}")
            return None

image_generator = LocationImageGenerator()