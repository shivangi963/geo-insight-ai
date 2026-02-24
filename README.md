Geo Insight AI  

PHASE-0

 What I Did
- Created and set up GitHub repository geo-insight-ai.
- Wrote project_vision.md explaining how AI can help analyze rental/business locations.
- Learned Python fundamentals: data types, loops, functions, and OOP basics.
- Built a clean Location class to model geographical properties.
- Practiced data analysis using Pandas and NumPy.
- Analyzed a Mumbai housing dataset — cleaned missing values, converted price units (Cr/L), computed ₹ per sqft, and exported the      cleaned file.

What I Learned
- How to use Git & GitHub for version control.
- How to handle and clean messy real-world data.
- How to write Python classes and methods.
- How to calculate derived features like price_per_sqft.
- Basics of reading/writing CSV files using Pandas.


PHASE-1

What I Did
-Set up a clean Python virtual environment.
-Installed CV libraries (OpenCV, Ultralytics) and NLP libraries (Transformers, Torch).
-Implemented green space detection using HSV thresholding.
-Saved binary masks + overlay images to visualize vegetation areas.
-Added YOLO-based street object detection for traffic, vehicles, and urban features.
-Built an LLM-based property summarizer using HuggingFace Transformers.
-Organized code into src/cv and src/llm with modular structure.

What I Learned
-Basics of image processing: masking, color spaces, morphological ops.
-How YOLO object detection works and how to run inference.
-How to build an LLM pipeline using HuggingFace models.
-How to structure a real project (folders, modules, virtual env, requirements).
-How CV + NLP can combine to analyze locations intelligently.


PHASE 2 — Building Backend Services

What I Did
- Built a full FastAPI backend with proper project structure (`app/`, `routers/`, `models/`, `crud/`)
- Set up async MongoDB connection using Motor (async driver) with connection pooling
- Implemented complete CRUD endpoints for properties (`/api/properties`)
- Added proper Pydantic models for request validation and response serialization
- Built the `/health` endpoint and `/api/stats` for system monitoring
- Added middleware for logging, security headers, rate limiting (slowapi), and CORS
- Loaded the Mumbai housing dataset (1000+ properties) into MongoDB using a custom loader script

What I Learned
- How FastAPI's async/await pattern works and why it matters for performance
- The difference between sync and async database drivers (pymongo vs motor)
- How Pydantic models enforce data validation at the API boundary
- How to structure a backend with routers, models, and CRUD separation
- How middleware works in ASGI applications
