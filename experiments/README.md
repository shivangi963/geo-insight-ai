# Experiments

Early prototypes from Phase 1 (Nov 2025). **None of this code is used by the production API.**
It is kept to show how the project evolved. The scripts were written in a local `src/` folder and
first committed in Nov 2025 (commits `1ae3618`, `bc504fe`, `aa7cece`); they were removed from the
repo in "Clean Phase 2 branch" and `src/` has been git-ignored since. The logic here is the same as
those commits; the differences are listed in each file's docstring.

| Folder | What it contains | Models |
|---|---|---|
| [`phase1_cv/`](phase1_cv/) | Green-space estimate from a satellite image; car and pedestrian counting in a street photo | YOLOv8n-seg, YOLOv8n (COCO) + OpenCV |
| [`phase1_llm/`](phase1_llm/) | Property-description summariser comparing two approaches; small Hugging Face demos | BART (`facebook/bart-large-cnn`), Gemini 2.5 Flash |

```bash
pip install -r experiments/requirements.txt
```

Secrets are never stored in these files. The Gemini key is read from the `GEMINI_API_KEY`
environment variable.
