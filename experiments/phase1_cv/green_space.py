"""Phase 1 prototype: green-space estimate from a satellite image (YOLOv8-seg + HSV).

Status: EXPERIMENT. Not used by the production API.

Restored from commit bc504fe (Nov 2025). Changes since the original: command-line
arguments, no blocking ``plt.show()``, and a diagnostic for the YOLO stage (the
original computed YOLO masks but never used them). The HSV thresholds are unchanged.

What it does
------------
1. Runs the COCO-pretrained YOLOv8n-seg model on the image.
2. Reports how much of the image the detected objects cover (diagnostic only).
3. Computes the green-space percentage from an HSV colour mask. This is the
   reported number.

Why the number comes from colour and not from YOLO
--------------------------------------------------
COCO's 80 classes contain no tree, grass or other vegetation class (the closest is
"potted plant"), so the model's masks cannot represent green space by themselves.
The diagnostic makes that measurable on your own images. The production pipeline
(backend/app/tasks/computer_vision_tasks.py) later moved to colour segmentation of
OpenStreetMap tiles. To make a detector contribute, it would have to be fine-tuned
on tree-canopy data.

Usage
-----
    python green_space.py path/to/satellite.jpg [--output results/green_space.jpg]
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

# HSV ranges in OpenCV scale (H 0-179, S and V 0-255). Unchanged from the original.
GREEN_RANGES = (
    (np.array([35, 40, 40]), np.array([85, 255, 255])),
    (np.array([25, 40, 40]), np.array([35, 255, 255])),
)
MIN_CONFIDENCE = 0.5  # YOLO detections below this are ignored
MIN_GREEN_IN_OBJECT = 0.3  # an object counts as "green" if >30% of its pixels are green
KERNEL = np.ones((5, 5), np.uint8)


def hsv_green_mask(image_bgr: np.ndarray) -> np.ndarray:
    """Binary mask (0/255) of green pixels, cleaned with a close then open."""
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
    for lower, upper in GREEN_RANGES:
        mask = cv2.bitwise_or(mask, cv2.inRange(hsv, lower, upper))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, KERNEL)
    return cv2.morphologyEx(mask, cv2.MORPH_OPEN, KERNEL)


def yolo_diagnostic(model: YOLO, image_bgr: np.ndarray) -> dict:
    """Measure how much of the image YOLO's detected objects cover.

    Mirrors the original prototype: a detection counts only if its confidence is above
    0.5, and it is "green" if more than 30% of its pixels fall in the first HSV green
    range (raw range, no morphology). ``retina_masks=True`` returns masks at the
    original image size, so no resizing or letterbox correction is needed.
    """
    height, width = image_bgr.shape[:2]
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    object_green = cv2.inRange(hsv, *GREEN_RANGES[0])
    result = model(image_bgr, retina_masks=True, verbose=False)[0]

    objects = np.zeros((height, width), dtype=bool)
    green_objects = np.zeros((height, width), dtype=bool)
    n_objects = n_green_objects = 0
    classes: Counter = Counter()

    if result.masks is not None:
        for mask, box in zip(result.masks.data, result.boxes):
            if float(box.conf[0]) <= MIN_CONFIDENCE:
                continue
            obj = mask.cpu().numpy() > 0.5
            if not obj.any():
                continue
            n_objects += 1
            classes[result.names[int(box.cls[0])]] += 1
            objects |= obj
            if (object_green[obj] > 0).mean() > MIN_GREEN_IN_OBJECT:
                n_green_objects += 1
                green_objects |= obj

    total = height * width
    return {
        "yolo_objects": n_objects,
        "yolo_classes": dict(classes),
        "yolo_object_coverage_pct": round(100 * objects.sum() / total, 2),
        "yolo_green_objects": n_green_objects,
        "yolo_green_object_coverage_pct": round(100 * green_objects.sum() / total, 2),
    }


def estimate_green_space(
    image_path: str,
    output_path: str = "results/green_space_analysis.jpg",
    weights: str = "yolov8n-seg.pt",
) -> dict:
    """Return the colour-based green percentage plus the YOLO diagnostic."""
    image = cv2.imread(image_path)
    if image is None:
        raise SystemExit(f"Could not read image: {image_path}")

    green_mask = hsv_green_mask(image)
    green_pct = 100 * np.count_nonzero(green_mask) / green_mask.size

    metrics = {"green_space_pct_hsv": round(green_pct, 2)}
    metrics.update(yolo_diagnostic(YOLO(weights), image))

    overlay = image.copy()
    overlay[green_mask > 0] = (0, 255, 0)
    blended = cv2.addWeighted(image, 0.4, overlay, 0.6, 0)
    label = f"Green space (HSV): {green_pct:.2f}%"
    (text_w, _), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 1, 2)
    cv2.rectangle(blended, (10, 10), (30 + text_w, 55), (0, 0, 0), -1)
    cv2.putText(
        blended, label, (20, 42), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2
    )

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), blended)
    metrics["output_image"] = str(out)
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("image", help="path to a satellite or aerial image")
    parser.add_argument("--output", default="results/green_space_analysis.jpg")
    args = parser.parse_args()

    metrics = estimate_green_space(args.image, args.output)
    green_pct = metrics["green_space_pct_hsv"]
    print(f"Green space (HSV colour mask, reported number): {green_pct}%")
    print(
        f"YOLOv8-seg diagnostic: {metrics['yolo_objects']} object(s) covering "
        f"{metrics['yolo_object_coverage_pct']}% of the image; "
        f"{metrics['yolo_green_objects']} of them green, covering "
        f"{metrics['yolo_green_object_coverage_pct']}%"
    )
    print(f"COCO classes detected: {metrics['yolo_classes'] or 'none'}")
    print(f"Saved overlay to {metrics['output_image']}")


if __name__ == "__main__":
    main()
