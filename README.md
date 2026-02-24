GeoInsight AI

An AI-powered real estate and neighborhood analysis platform. Enter any address and get a comprehensive report covering nearby amenities, walkability, green space coverage, investment metrics, and visual property similarity.

Built as part of an AI/ML engineering internship — progressing from Python fundamentals all the way to a fully deployed, cloud-native application.

---

 PHASE 0 — Data Science Foundations

What I Did
- Created and set up the GitHub repository `geo-insight-ai` with proper branching
- Wrote `project_vision.md` explaining how AI can help analyze rental and business locations
- Learned Python fundamentals: data types, loops, functions, and OOP basics
- Built a clean `Location` class to model geographical properties with address, latitude, and longitude
- Practiced data analysis using Pandas and NumPy on a real Mumbai housing dataset
- Cleaned messy data — handled missing values, converted price units (Cr/L to raw INR), computed ₹ per sqft, and exported the cleaned file

What I Learned
- How to use Git and GitHub for version control with meaningful commit messages
- How to handle and clean messy real-world data (missing values, unit inconsistencies)
- How to write Python classes and methods using OOP principles
- How to calculate derived features like `price_per_sqft`
- Basics of reading/writing CSV files using Pandas

---

 PHASE 1 — AI & ML Fundamentals

What I Did
- Set up a clean Python virtual environment and organized the project into `src/cv` and `src/llm` modules
- Installed computer vision libraries (OpenCV, Ultralytics) and NLP libraries (Transformers, PyTorch)
- Implemented green space detection using HSV color thresholding on satellite images
- Saved binary masks and overlay images to visualize vegetation areas
- Added YOLO-based street object detection for cars, pedestrians, and urban features
- Built an LLM-based property description summarizer using HuggingFace Transformers (BART)
- Also integrated the Gemini API for higher-quality summaries and tested both side by side

What I Learned
- Basics of image processing: color spaces (RGB vs HSV), masking, and morphological operations
- How YOLO object detection works and how to run inference with pre-trained models
- How to build an NLP pipeline using HuggingFace models
- How to structure a real project (folders, modules, virtual environment, requirements.txt)
- How computer vision and NLP can combine to analyze locations intelligently



---

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


---

 PHASE 3 — Building AI-Powered Tools & UIs

What I Did
- Built a multi-tab Streamlit dashboard (`frontend/`) that communicates entirely with the FastAPI backend
- Created the Properties tab with filtering, comparison, and a form to add new properties
- Built the Neighborhood Intelligence tab with an interactive analysis form and real-time progress polling
- Built the AI Real Estate Assistant tab — full investment analysis with IRR, DSCR, CoC ROI, break-even occupancy
- Built the Vector Search (Similar Homes) tab — upload a photo, find visually similar properties
- The AI agent (`local_expert.py`) uses the Gemini API with a custom investment calculator that handles Indian number formats (Cr/L/K) and produces detailed financial reports
- Connected Streamlit to FastAPI via a clean `APIClient` class with error handling and retries

What I Learned
- How to build multi-page Streamlit apps with tabs, forms, session state, and real-time polling
- How LLM function/tool calling works — defining tools and letting the model decide when to use them
- How to build a financial calculator from scratch (IRR via Newton-Raphson, DSCR, cash-on-cash ROI)
- How to parse Indian number formats (Rs. 80L, 1.2 Cr) from natural language queries using regex
- The importance of separating API logic from UI logic



---

 PHASE 4 — Integrating Real-World Data & Systems

What I Did
- Integrated OpenStreetMap via `osmnx` to fetch real nearby amenities (restaurants, schools, hospitals, parks, etc.)
- Built a walk score calculator based on amenity proximity and type weights
- Added green space analysis using OSM map tiles + OpenCV color detection — calculates actual percentage of vegetation coverage
- Implemented async neighborhood analysis with background tasks (FastAPI BackgroundTasks + Celery)
- Set up Redis as the message broker and result backend for Celery workers
- Integrated Supabase with pgvector for image embedding storage and cosine similarity search
- Used CLIP (openai/clip-vit-base-patch32) via HuggingFace Transformers to generate 512-dimensional image embeddings
- Built the n8n workflow (`n8n_workflow.json`) — webhook trigger → FastAPI analysis → task polling → email notification on completion
- Built the vector search pipeline: upload image → CLIP embedding → Supabase RPC → ranked results with similarity scores

What I Learned
- How to work with OpenStreetMap data using osmnx and handle timeouts gracefully
- How Celery's task queue architecture works — workers, brokers, result backends, task routing
- How vector databases work — embeddings, cosine similarity, IVFFlat indexing
- How CLIP generates image embeddings that capture visual meaning, not just pixel values
- How n8n workflows chain API calls together and handle async completion polling
- How to build a proper retry/fallback system when external APIs fail

---

 PHASE 5 — DevOps & Cloud Deployment

What I Did

- Wrote multi-stage Dockerfile files for both the FastAPI backend and Streamlit frontend — builder stage installs dependencies, runtime stage is a lean image
- Wrote a docker-compose.yml orchestrating all six services: MongoDB, Redis, FastAPI backend, Celery worker, n8n, and Streamlit frontend with health checks and named volumes
- Tagged and pushed Docker images to Google Artifact Registry using gcloud
- Deployed the FastAPI backend as a serverless Cloud Run service with auto-scaling, a public HTTPS URL, and environment variable injection via Secret Manager
- Deployed the Streamlit frontend as a second Cloud Run service pointing to the backend's public URL
- Configured Cloud Run concurrency, memory limits, and min-instances so cold starts stay under 3 seconds
- Explored Vertex AI — uploaded the Mumbai housing dataset as a managed dataset, ran an AutoML tabular training job to predict property price and inspected the resulting feature importance chart
- Configured a Cloud Run service account with least-privilege IAM roles (Artifact Registry Reader, Secret Manager Accessor, Cloud Run Invoker)

What I Learned

- The difference between a builder and a runtime Docker stage and why it matters for image size
- How docker buildx enables multi-platform builds (amd64 for Cloud Run when developing on Apple Silicon)
- How Google Artifact Registry differs from Docker Hub and why it integrates better with Cloud Run
- How Cloud Run achieves serverless scaling — instances spin up per request, billing is per 100ms of CPU time
- How Secret Manager lets you inject API keys at deploy time without hardcoding them in images
- How Vertex AI AutoML handles feature engineering and model selection automatically, and when to use it vs. a custom training job
- Why container-first deployment makes the app genuinely reproducible across local, staging, and production



---

 Running the Project

 Prerequisites
- Docker Desktop
- Python 3.11+
- MongoDB (local or Atlas)
- Redis

 Load Sample Data
```bash
# Load Mumbai housing dataset into MongoDB
python load_kaggle_data.py --csv-path data/Mumbai\ House\ Prices.csv --max-rows 50    

# Add images to properties (for vector search)
python add_property_images.py
```

 Clone and install

bashgit clone https://github.com/YOUR_USERNAME/geo-insight-ai.git
cd geo-insight-ai

python -m venv venv
source venv/bin/activate      

pip install -r requirements.txt



 Get a Gemini API key

Go to https://aistudio.google.com/app/apikey
Sign in with Google
Click Create API Key
Paste it into GOOGLE_API_KEY in .env



 Set up Supabase (for vector/visual search)

This powers the "Find Similar Properties" feature. Skip if you don't need it — the rest of the app works fine without it.

Create a free account at https://supabase.com
Create a new project, choose a region near you
Go to Settings → API and copy:

Project URL → SUPABASE_URL
anon public key → SUPABASE_KEY


Open the SQL Editor in your Supabase dashboard and run:

sqlcreate extension if not exists vector;

create table if not exists property_embeddings (
  id uuid primary key default gen_random_uuid(),
  property_id text unique not null,
  address text,
  embedding vector(512),
  image_url text,
  metadata jsonb default '{}',
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now()
);

create index on property_embeddings
  using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

create or replace function match_property_embeddings(
  query_embedding vector(512),
  match_threshold float,
  match_count int
)
returns table (
  property_id text,
  address text,
  image_url text,
  metadata jsonb,
  similarity float
)
language sql stable
as $$
  select
    property_id,
    address,
    image_url,
    metadata,
    1 - (embedding <=> query_embedding) as similarity
  from property_embeddings
  where 1 - (embedding <=> query_embedding) > match_threshold
  order by embedding <=> query_embedding
  limit match_count;
$$;



 n8n Workflow (optional)

n8n is a workflow automation tool. The workflow in this project does: receive webhook → call FastAPI to start analysis → poll until task completes → send email with results.
Run n8n:
 In bash : npx n8n
Downloads and starts n8n at http://localhost:5678. Create a local account when it asks.
Import the workflow:

Go to http://localhost:5678
Workflows → Import from File
Upload backend/n8n_workflow.json (do not forget to edit your email id in n8n_workflow.json )
The full workflow will appear, pre-wired

Set up email (Gmail SMTP):
You need an App Password, not your regular Gmail password.
Go to: Google Account → Security → 2-Step Verification → App Passwords → generate one for "Mail"
In n8n:

Click the Send Success Email node
Credentials → Create New → SMTP
Fill in:

Host: smtp.gmail.com
Port: 587
SSL/TLS: STARTTLS
Username: your Gmail
Password: the App Password you just generated

Add to .env:
envN8N_WEBHOOK_URL=http://localhost:5678/webhook/geoinsight-analysis
EMAIL_USER=your@gmail.com
EMAIL_PASS=your_app_password
Activate and test:
bash# Activate the workflow in the n8n UI first, then:
curl -X POST http://localhost:5678/webhook/geoinsight-analysis \
  -H "Content-Type: application/json" \
  -d '{
    "address": "Koramangala, Bengaluru, Karnataka, India",
    "email": "your@email.com",
    "radius_m": 1000
  }'



 Quick Start with Docker
 
bashdocker-compose up --build

This starts:

  FastAPI backend on http://localhost:8000
  Streamlit frontend on http://localhost:8501
  MongoDB on port 27017
  Redis on port 6379
  Celery worker
  n8n on http://localhost:5678

Deploying to Google Cloud Run 

1. Install & authenticate gcloud
    bash# Install the Google Cloud CLI: https://cloud.google.com/sdk/docs/install
    gcloud auth login
    gcloud config set project YOUR_PROJECT_ID
2. Enable required APIs
  bashgcloud services enable \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    secretmanager.googleapis.com

3. Create an Artifact Registry repository
  bashgcloud artifacts repositories create geoinsight-repo \
    --repository-format=docker \
    --location=asia-south1 \
    --description="GeoInsight AI container images"

4. Build and push images
  bash# Authenticate Docker with Artifact Registry
  gcloud auth configure-docker asia-south1-docker.pkg.dev

# Build for Cloud Run (linux/amd64 — required on Apple Silicon)
  docker buildx build \
    --platform linux/amd64 \
    -f docker/Dockerfile.backend \
    -t asia-south1-docker.pkg.dev/YOUR_PROJECT_ID/geoinsight-repo/backend:latest \
    --push .

docker buildx build \
  --platform linux/amd64 \
  -f docker/Dockerfile.frontend \
  -t asia-south1-docker.pkg.dev/YOUR_PROJECT_ID/geoinsight-repo/frontend:latest \
  --push .

5. Store secrets in Secret Manager
bashecho -n "your_gemini_key" | gcloud secrets create GOOGLE_API_KEY --data-file=-
echo -n "your_mongo_atlas_url" | gcloud secrets create MONGODB_URL --data-file=-
echo -n "your_supabase_url" | gcloud secrets create SUPABASE_URL --data-file=-
echo -n "your_supabase_key" | gcloud secrets create SUPABASE_KEY --data-file=-

6. Deploy the backend
  bashgcloud run deploy geoinsight-backend \
    --image asia-south1-docker.pkg.dev/YOUR_PROJECT_ID/geoinsight-repo/backend:latest \
    --region asia-south1 \
    --platform managed \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 2 \
    --concurrency 80 \
    --min-instances 0 \
    --max-instances 5 \
    --set-secrets "GOOGLE_API_KEY=GOOGLE_API_KEY:latest,MONGODB_URL=MONGODB_URL:latest,SUPABASE_URL=SUPABASE_URL:latest,SUPABASE_KEY=SUPABASE_KEY:latest" \
    --set-env-vars "DATABASE_NAME=geoinsight_ai,ENVIRONMENT=production"
  Note the public URL printed at the end — it looks like https://geoinsight-backend-xxxx-el.a.run.app.


7. Deploy the frontend
  bashgcloud run deploy geoinsight-frontend \
    --image asia-south1-docker.pkg.dev/YOUR_PROJECT_ID/geoinsight-repo/frontend:latest \
    --region asia-south1 \
    --platform managed \
    --allow-unauthenticated \
    --memory 512Mi \
    --set-env-vars "BACKEND_URL=https://geoinsight-backend-xxxx-el.a.run.app"


8. Vertex AI (optional exploration)
  bash# Upload your cleaned Mumbai housing CSV as a managed dataset
  gcloud ai datasets create \
    --display-name="Mumbai Housing Prices" \
    --metadata-schema-uri=gs://google-cloud-aiplatform/schema/dataset/metadata/tabular_1.0.0.yaml \
    --region=asia-south1

  # Then in the Cloud Console:
  # Vertex AI → Datasets → your dataset → Train new model
  # Choose AutoML → Tabular → Regression → target column: price_inr
  # Let it run (takes ~1-2 hours), then check Feature Importance under Model Evaluation


  Local Development

bash# Backend
cd backend
pip install -r requirements.txt
cp ../.env.example .env   # fill in your API keys
uvicorn app.main:app --reload

# Frontend (new terminal)
cd frontend
streamlit run app.py

# Celery worker (new terminal)
cd backend
celery -A celery_config.celery_app worker --loglevel=info

API Documentation
Interactive docs available at http://localhost:8000/docs when backend is running.
Key endpoints:

GET /health — System health check
GET /api/properties — List all properties
POST /api/neighborhood/analyze — Start neighborhood analysis
GET /api/tasks/{task_id} — Poll task status
POST /api/agent/query — AI investment analysis
POST /api/vector/search — Find visually similar properties


  Tech Stack

Layer	                Technology
Backend API	          FastAPI + Uvicorn
Database	            MongoDB (Motor async)
Task Queue	          Celery + Redis
Vector DB	            Supabase (pgvector)
Computer Vision	      YOLOv8 (Ultralytics), OpenCV, CLIP
LLM / AI	            Gemini API, HuggingFace Transformers
Geospatial	          osmnx, Folium, Geopy
Frontend	            Streamlit
Workflow	            n8n
Deployment	          Docker, Google Cloud Run 