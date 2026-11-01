"""Phase 1 prototype: count cars and people in a street-level photo with YOLOv8n.

Status: EXPERIMENT. Not used by the production API.

Restored from commit bc504fe (Nov 2025). Changes since the original: command-line
arguments, no blocking ``plt.show()``, and the counts are returned and printed.

This is a legitimate use of a COCO-pretrained detector, because "person" and "car"
are COCO classes. (Contrast with green_space.py, where COCO has no vegetation class.)

Usage
-----
    python detect_street.py path/to/street.jpg [--output results/annotated_street.jpg]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
from ultralytics import YOLO

PERSON, CAR = 0, 2  # COCO class ids
CLASSES = {
    PERSON: ("person", (0, 255, 0)),  # green box (BGR)
    CAR: ("car", (0, 0, 255)),  # red box (BGR)
}


def analyse_street(
    image_path: str,
    output_path: str = "results/annotated_street.jpg",
    min_confidence: float = 0.5,
    weights: str = "yolov8n.pt",
) -> dict:
    """Annotate detections of cars and people; return counts per class."""
    image = cv2.imread(image_path)
    if image is None:
        raise SystemExit(f"Could not read image: {image_path}")

    result = YOLO(weights)(image, verbose=False)[0]
    counts = {"car": 0, "person": 0}

    for box in result.boxes:
        class_id, score = int(box.cls[0]), float(box.conf[0])
        if class_id not in CLASSES or score <= min_confidence:
            continue
        name, colour = CLASSES[class_id]
        counts[name] += 1

        x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
        cv2.rectangle(image, (x1, y1), (x2, y2), colour, 2)
        label = f"{name}: {score:.2f}"
        (text_w, text_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
        cv2.rectangle(image, (x1, y1 - text_h - 10), (x1 + text_w, y1), colour, -1)
        cv2.putText(
            image,
            label,
            (x1, y1 - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            2,
        )

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), image)
    return {**counts, "output_image": str(out)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("image", help="path to a street-level photo")
    parser.add_argument("--output", default="results/annotated_street.jpg")
    parser.add_argument("--min-confidence", type=float, default=0.5)
    args = parser.parse_args()

    summary = analyse_street(args.image, args.output, args.min_confidence)
    print(f"Cars: {summary['car']}   People: {summary['person']}")
    print(f"Saved annotated image to {summary['output_image']}")


if __name__ == "__main__":
    main()
