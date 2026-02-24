import cv2
import numpy as np
from typing import Dict, Optional, Tuple
import os
import logging

logger = logging.getLogger(__name__)


def analyze_osm_green_spaces(image_path: str, analysis_id: str) -> Optional[Dict]:
    try:
        image = cv2.imread(image_path)
        if image is None:
            logger.error(f"Failed to read image: {image_path}")
            return None

        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        green_masks = detect_osm_green_areas_fixed(image_rgb)
        combined_mask = combine_green_masks(green_masks)

        total_pixels = image.shape[0] * image.shape[1]
        green_pixels = np.sum(combined_mask > 0)
        green_percentage = (green_pixels / total_pixels) * 100

        breakdown = {}
        for green_type, mask in green_masks.items():
            type_pixels = np.sum(mask > 0)
            type_pct = (type_pixels / total_pixels) * 100
            breakdown[green_type] = round(type_pct, 2)

        visualization_path = create_osm_green_visualization(
            image_rgb, combined_mask, green_masks, green_percentage, analysis_id
        )

        return {
            "green_space_percentage": round(green_percentage, 2),
            "green_pixels": int(green_pixels),
            "total_pixels": int(total_pixels),
            "visualization_path": visualization_path,
            "breakdown": breakdown,
        }

    except Exception as e:
        logger.error(f"Error analyzing OSM green spaces: {e}", exc_info=True)
        return None


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def detect_osm_green_areas_fixed(image: np.ndarray) -> Dict[str, np.ndarray]:
    green_masks = {}

    hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
    rgb = image.copy()

    green_ranges = {
        "parks_grass": {
            "rgb_ranges": [
                ((180, 230, 180), (230, 255, 230)),
                ((190, 240, 190), (210, 255, 210)),
                ((195, 225, 155), (215, 245, 175)),
            ],
            "hsv_ranges": [
                ((30, 15, 150), (90, 100, 255)),
                ((35, 20, 180), (75, 80, 255)),
            ],
        },
        "forests_woods": {
            "rgb_ranges": [
                ((120, 180, 100), (180, 220, 180)),
                ((130, 190, 150), (180, 215, 170)),
                ((100, 170, 90), (160, 210, 140)),
            ],
            "hsv_ranges": [
                ((30, 25, 120), (90, 150, 230)),
                ((35, 30, 100), (80, 130, 220)),
            ],
        },
        "recreation": {
            "rgb_ranges": [
                ((165, 200, 150), (185, 220, 170)),
                ((150, 190, 140), (180, 215, 165)),
            ],
            "hsv_ranges": [
                ((32, 20, 150), (75, 90, 230)),
            ],
        },
        "natural_areas": {
            "rgb_ranges": [
                ((210, 235, 200), (230, 250, 225)),
                ((200, 230, 190), (225, 245, 220)),
            ],
            "hsv_ranges": [
                ((30, 10, 180), (85, 60, 255)),
            ],
        },
    }

    for green_type, ranges in green_ranges.items():
        type_mask = np.zeros((image.shape[0], image.shape[1]), dtype=np.uint8)

        for lower, upper in ranges.get("rgb_ranges", []):
            lower_rgb = np.array(lower, dtype=np.uint8)
            upper_rgb = np.array(upper, dtype=np.uint8)
            mask = cv2.inRange(rgb, lower_rgb, upper_rgb)
            type_mask = cv2.bitwise_or(type_mask, mask)

        for lower, upper in ranges.get("hsv_ranges", []):
            lower_hsv = np.array(lower, dtype=np.uint8)
            upper_hsv = np.array(upper, dtype=np.uint8)
            mask = cv2.inRange(hsv, lower_hsv, upper_hsv)
            type_mask = cv2.bitwise_or(type_mask, mask)

        kernel = np.ones((5, 5), np.uint8)
        type_mask = cv2.morphologyEx(type_mask, cv2.MORPH_CLOSE, kernel)
        type_mask = cv2.morphologyEx(type_mask, cv2.MORPH_OPEN, kernel)

        green_masks[green_type] = type_mask

    return green_masks


def combine_green_masks(green_masks: Dict[str, np.ndarray]) -> np.ndarray:
    combined = None
    for mask in green_masks.values():
        if combined is None:
            combined = mask.copy()
        else:
            combined = cv2.bitwise_or(combined, mask)
    return combined if combined is not None else np.zeros((100, 100), dtype=np.uint8)


def create_osm_green_visualization(
    image: np.ndarray,
    combined_mask: np.ndarray,
    green_masks: Dict[str, np.ndarray],
    green_percentage: float,
    analysis_id: str,
) -> str:
    try:
        output_dir = os.path.join(os.path.dirname(__file__), "..", "..", "results")
        os.makedirs(output_dir, exist_ok=True)

        overlay = image.copy()
        colored_overlay = np.zeros_like(image)

        pear_green = [34, 139, 34]

        colored_overlay[combined_mask > 0] = pear_green

        alpha = 0.5
        blended = cv2.addWeighted(overlay, 1 - alpha, colored_overlay, alpha, 0)

        contours, _ = cv2.findContours(
            combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        cv2.drawContours(blended, contours, -1, pear_green, 2)

        font = cv2.FONT_HERSHEY_SIMPLEX
        main_text = f"Green Space: {green_percentage:.2f}%"
        text_size = cv2.getTextSize(main_text, font, 1, 2)[0]

        cv2.rectangle(blended, (10, 10), (30 + text_size[0], 60), (0, 0, 0), -1)
        cv2.putText(blended, main_text, (20, 40), font, 1, (255, 255, 255), 2)

        output_filename = f"osm_green_space_{analysis_id}.png"
        output_path = os.path.join(output_dir, output_filename)

        height, width = blended.shape[:2]
        resized = cv2.resize(
            blended,
            (width // 2, height // 2),
            interpolation=cv2.INTER_AREA,
        )

        resized_bgr = cv2.cvtColor(resized, cv2.COLOR_RGB2BGR)
        cv2.imwrite(output_path, resized_bgr)

        return f"results/{output_filename}"

    except Exception as e:
        logger.error(f"Error creating visualization: {e}", exc_info=True)
        return None