# Phase 1 computer-vision prototypes

These two scripts are early experiments from Phase 1 (Nov 2025). They are **not used by the
production API**. They are the Phase 1 `src/cv/` scripts (first committed in `1ae3618` and `bc504fe`,
removed in "Clean Phase 2 branch"). The logic is the same; this version only adds command-line
arguments, drops the blocking `plt.show()`, and adds a diagnostic (see below).

| Script | What it does | Model |
|---|---|---|
| `green_space.py` | Estimates the green share of a satellite image | YOLOv8n-seg (COCO) + HSV colour mask |
| `detect_street.py` | Counts cars and people in a street-level photo | YOLOv8n (COCO) |

## Run

```bash
pip install -r experiments/requirements.txt   # run from the repo root
python experiments/phase1_cv/green_space.py path/to/satellite.jpg
python experiments/phase1_cv/detect_street.py path/to/street.jpg
```

Bring your own images. None are bundled, because map and satellite providers often restrict
redistribution of their imagery; check the licence of whatever you use. Model weights are
downloaded automatically on first run.

## What the green-space prototype showed

`green_space.py` prints two things:

1. **The reported number**, computed from an HSV colour mask.
2. **A YOLO diagnostic**: how many objects the model detected, which COCO classes they were, and how much of the image they cover.

The reported number comes from colour because the COCO-pretrained model has no tree, grass or
vegetation class (the closest of its 80 classes is "potted plant"). Its masks therefore cannot
represent green space on their own. Run the diagnostic on your own image to see which classes it
reports and how little of a satellite view the detected objects cover.

Production (`backend/app/tasks/computer_vision_tasks.py`) estimates *mapped* green space from
OpenStreetMap tile colours instead. Making a YOLO model contribute would require fine-tuning it on
tree-canopy data, for example the OAM-TCD dataset.
