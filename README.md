# GeoInsight AI

**An AI-powered real estate and neighbourhood analysis platform.**  
Enter any address and get a comprehensive report covering nearby amenities, walkability, green space coverage, investment metrics, and visual property similarity.

Built as part of an AI/ML engineering internship — progressing from Python fundamentals all the way to a fully deployed, cloud-native application.

---

## Table of Contents

- [Project Overview](#project-overview)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Phases](#phases)
- [Running Locally](#running-locally)
- [Deployment](#deployment)
- [API Reference](#api-reference)

---

## Project Overview

Finding the right place to rent, invest, or open a business is hard. Information is scattered across rental websites, government data, maps, and satellite imagery — none of it connected. GeoInsight AI brings everything together.

Type in an address, ask a question like *"Is this a good area to open a cafe?"* — and the system fetches real amenity data from OpenStreetMap, calculates a walk score, analyses green space coverage from map tiles, runs an investment model, and lets you find visually similar properties by uploading a photo.

---

## Tech Stack

| Layer |             Technology |
| Backend API |        FastAPI + Uvicorn |
| Database |           MongoDB Atlas (Motor async driver) |
| Task Queue |         Celery + Redis |
| Vector DB |          Supabase (pgvector) |
| Computer Vision |    YOLOv8, OpenCV, CLIP (openai/clip-vit-base-patch32) |
| LLM / AI |           Gemini API, HuggingFace Transformers |
| Geospatial |         osmnx, Folium, Geopy |
| Frontend |           Streamlit |
| Workflow Automation |n8n |
| Deployment |         Docker, Google Cloud Run |
| CI/CD |              Google Cloud Build (triggered on push to `main`) |

---

## Phases

### Phase 0 — Data Science Foundations

**What I Did**
- Set up the GitHub repository with proper branching strategy
- Wrote `project_vision.md` explaining how AI can help analyse rental and business locations
- Learned Python fundamentals: data types, loops, functions, and OOP
- Built a `Location` class to model geographical properties with address, latitude, and longitude
- Practised data analysis using Pandas and NumPy on a real Mumbai housing dataset
- Cleaned messy data — handled missing values, converted price units (Cr/L to INR), computed ₹/sqft, and exported the cleaned file

**What I Learned**
- Git and GitHub for version control with meaningful commit messages
- Handling and cleaning messy real-world data (missing values, unit inconsistencies)
- Writing Python classes using OOP principles
- Calculating derived features like `price_per_sqft`
- Reading/writing CSV files using Pandas

---

### Phase 1 — AI & ML Fundamentals

**What I Did**
- Set up a clean Python virtual environment and organised the project into `src/cv` and `src/llm` modules
- Implemented green space detection using HSV colour thresholding on satellite images
- Saved binary masks and overlay images to visualise vegetation areas
- Added YOLO-based street object detection for cars, pedestrians, and urban features
- Built a property description summariser using HuggingFace Transformers (BART)
- Integrated the Gemini API for higher-quality summaries and tested both side by side

**What I Learned**
- Image processing basics: colour spaces (RGB vs HSV), masking, and morphological operations
- How YOLO object detection works and how to run inference with pre-trained models
- Building an NLP pipeline using HuggingFace models
- Structuring a real project with folders, modules, virtual environments, and requirements.txt
- How computer vision and NLP can combine to analyse locations intelligently

---

### Phase 2 — Building Backend Services

**What I Did**
- Built a full FastAPI backend with proper project structure (`app/`, `routers/`, `models/`, `crud/`)
- Set up async MongoDB connection using Motor with connection pooling
- Implemented complete CRUD endpoints for properties (`/api/properties`)
- Added Pydantic models for request validation and response serialisation
- Built `/health` and `/api/stats` endpoints for system monitoring
- Added middleware for logging, security headers, rate limiting (slowapi), and CORS
- Loaded the Mumbai housing dataset (1,000+ properties) into MongoDB using a custom loader script

**What I Learned**
- How FastAPI's async/await pattern works and why it matters for performance
- The difference between sync and async database drivers (pymongo vs motor)
- How Pydantic models enforce data validation at the API boundary
- How to structure a backend with routers, models, and CRUD separation
- How middleware works in ASGI applications

---

### Phase 3 — Building AI-Powered Tools & UIs

**What I Did**
- Built a multi-tab Streamlit dashboard that communicates entirely with the FastAPI backend
- Created the Properties tab with filtering, comparison, and a form to add new properties
- Built the Neighbourhood Intelligence tab with an interactive analysis form and real-time progress polling
- Built the AI Real Estate Assistant tab — full investment analysis with IRR, DSCR, CoC ROI, and break-even occupancy
- Built the Vector Search (Similar Homes) tab — upload a photo, find visually similar properties
- The AI agent (`local_expert.py`) uses the Gemini API with a custom investment calculator that handles Indian number formats (Cr/L/K)
- Connected Streamlit to FastAPI via a clean `APIClient` class with error handling and retries

**What I Learned**
- Building multi-page Streamlit apps with tabs, forms, session state, and real-time polling
- How LLM function/tool calling works — defining tools and letting the model decide when to use them
- Building a financial calculator from scratch (IRR via Newton-Raphson, DSCR, cash-on-cash ROI)
- Parsing Indian number formats (Rs. 80L, 1.2 Cr) from natural language queries using regex
- The importance of separating API logic from UI logic

---

### Phase 4 — Integrating Real-World Data & Systems

**What I Did**
- Integrated OpenStreetMap via `osmnx` to fetch real nearby amenities (restaurants, schools, hospitals, parks, etc.)
- Built a walk score calculator based on amenity proximity and type weights
- Added green space analysis using OSM map tiles + OpenCV colour detection — calculates actual vegetation coverage percentage
- Implemented async neighbourhood analysis with background tasks (FastAPI BackgroundTasks + Celery)
- Set up Redis as the message broker and result backend for Celery workers
- Integrated Supabase with pgvector for image embedding storage and cosine similarity search
- Used CLIP (openai/clip-vit-base-patch32) via HuggingFace to generate 512-dimensional image embeddings
- Built the n8n workflow (`n8n_workflow.json`) — webhook trigger → FastAPI analysis → task polling → email notification on completion
- Built the vector search pipeline: upload image → CLIP embedding → Supabase RPC → ranked results with similarity scores

**What I Learned**
- Working with OpenStreetMap data using osmnx and handling timeouts gracefully
- How Celery's task queue architecture works — workers, brokers, result backends, task routing
- How vector databases work — embeddings, cosine similarity, IVFFlat indexing
- How CLIP generates image embeddings that capture visual meaning, not just pixel values
- How n8n workflows chain API calls together and handle async completion polling
- Building a proper retry/fallback system when external APIs fail

---

### Phase 5 — DevOps & Cloud Deployment

**What I Did**
- Containerised the backend and frontend using multi-stage Dockerfiles — a builder stage installs heavy dependencies, the runtime stage is a lean copy with no build tools
- Deployed both services to **Google Cloud Run** — fully managed, serverless, auto-scaling to zero when idle
- Migrated the database from local MongoDB to **MongoDB Atlas** (cloud-hosted free tier, Mumbai region)
- Configured **Google Cloud Build** as the CI/CD pipeline, connected directly to the GitHub repository — every push to `main` triggers an automatic rebuild and redeploy with zero-downtime rolling revisions
- Stored all secrets (API keys, database URLs) as Cloud Run environment variables — nothing sensitive is baked into Docker images or committed to source control
- Deployed backend and frontend as independent Cloud Run services — a frontend change does not trigger a rebuild of the 2 GiB ML backend image

**Infrastructure**

| Component | Service | Config |
|---|---|---|
| Backend API | Cloud Run (`geoinsight-backend`) | 2 GiB RAM · 2 vCPU · 0–3 instances |
| Frontend | Cloud Run (`geoinsight-frontend`) | 512 MiB RAM · 1 vCPU · 0–3 instances |
| Database | MongoDB Atlas M0 | Free tier · Mumbai (ap-south-1) |
| CI/CD | Google Cloud Build | Auto-deploy on push to `main` |
| Container Registry | Google Artifact Registry | Stores versioned Docker images |

**What I Learned**
- How Cloud Run's serverless model works — containers scale to zero when idle, spin up on demand in seconds
- Why `mongodb+srv://` Atlas connection strings are required (Cloud Run cannot reach `localhost`)
- How Cloud Build connects to GitHub and triggers deployments automatically on every commit
- Multi-stage Docker builds keep production images lean by separating build-time and runtime dependencies
- Environment variable injection at deploy time keeps secrets out of source control entirely
- Independent service deployments reduce build times and prevent unrelated changes from causing downtime
- Rolling revisions in Cloud Run enable zero-downtime deploys with automatic rollback on failure

---

## Running Locally

### Prerequisites

- Docker Desktop
- Python 3.11+
- MongoDB (local or Atlas)
- Redis

### Clone and Install

```bash
git clone https://github.com/shivangi963/geo-insight-ai.git
cd geo-insight-ai

python -m venv venv
Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### Environment Setup

```bash
cp .env.example .env
# Fill in your API keys in .env
```

| Variable | Where to get it |
|---|---|
| `GOOGLE_API_KEY` | [Google AI Studio](https://aistudio.google.com/app/apikey) |
| `MONGODB_URL` | MongoDB Atlas → Connect → Drivers |
| `SUPABASE_URL` | Supabase → Settings → API |
| `SUPABASE_KEY` | Supabase → Settings → API (anon public key) |

### Load Sample Data

```bash
# Load Mumbai housing dataset into MongoDB
python load_kaggle_data.py --csv-path "data/Mumbai House Prices.csv" --max-rows 500

# Add images to properties (enables vector search)
python add_property_images.py
```

### Quick Start with Docker

```bash
docker-compose up --build
```

| Service | URL |
|---|---|
| FastAPI backend | http://localhost:8000 |
| Streamlit frontend | http://localhost:8501 |
| MongoDB | localhost:27017 |
| Redis | localhost:6379 |
| n8n | http://localhost:5678 |

### Local Development (without Docker)

```bash
# Terminal 1 — Backend
cd backend && uvicorn app.main:app --reload

# Terminal 2 — Frontend
cd frontend && streamlit run app.py

# Terminal 3 — Celery worker
cd backend && celery -A celery_config.celery_app worker --loglevel=info
```

---

## Supabase Setup (Vector Search)

This powers the **"Find Similar Properties"** feature. The rest of the app works without it.

1. Create a free project at [supabase.com](https://supabase.com)
2. Copy your **Project URL** and **anon public key** into `.env`
3. Run the following SQL in the Supabase SQL Editor:

```sql
create extension if not exists vector;

create table if not exists property_embeddings (
  id uuid primary key default gen_random_uuid(),
  property_id text unique not null,
  address text,
  embedding vector(512),
  image_url text,
  metadata jsonb default '{}',
  created_at timestamp with time zone default now()
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
language sql stable as $$
  select property_id, address, image_url, metadata,
         1 - (embedding <=> query_embedding) as similarity
  from property_embeddings
  where 1 - (embedding <=> query_embedding) > match_threshold
  order by embedding <=> query_embedding
  limit match_count;
$$;
```

---

## n8n Workflow (Optional)

n8n automates the full analysis pipeline: receive webhook → call FastAPI → poll until complete → send email with results.

```bash
npx n8n   # starts n8n at http://localhost:5678
```

1. **Workflows → Import from File** → upload `backend/n8n_workflow.json`
2. Edit the **Send Success Email** node — add Gmail SMTP credentials using a [Gmail App Password](https://myaccount.google.com/apppasswords)
3. Activate the workflow, then test:

```bash
curl -X POST http://localhost:5678/webhook/geoinsight-analysis \
  -H "Content-Type: application/json" \
  -d '{"address": "Koramangala, Bengaluru, Karnataka, India", "email": "your@email.com", "radius_m": 1000}'
```

---

## Deployment

The application is deployed on **Google Cloud Run** with **Google Cloud Build** handling CI/CD.

**Live Services**

| Service | URL |
|---|---|
| Backend API | `https://geoinsight-ai-530105254435.europe-west1.run.app` |
| Frontend | `https://geoinsight-frontend-530105254435.europe-west1.run.app` |
| API Docs | `https://geoinsight-backend-xxxx-el.a.run.app/docs` |

**How It Works**

Every push to `main` triggers Cloud Build automatically. Cloud Build pulls the code, builds the Docker image, pushes it to Artifact Registry, and deploys a new Cloud Run revision — all without manual intervention. The previous revision stays live until the new one passes its health check, ensuring zero downtime.

**Production Environment Variables**

All secrets are configured as Cloud Run environment variables at deploy time. The codebase reads `MONGODB_URL`, `GOOGLE_API_KEY`, `SUPABASE_URL`, and `SUPABASE_KEY` from the environment — the same code runs identically in local Docker and in production Cloud Run with no changes.

---

## API Reference

Interactive docs available at `/docs` when the backend is running.

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | System health check |
| `GET` | `/api/stats` | Database statistics |
| `GET` | `/api/properties` | List all properties |
| `POST` | `/api/properties` | Create a property |
| `POST` | `/api/neighborhood/analyze` | Start neighbourhood analysis |
| `GET` | `/api/neighborhood/{id}` | Get analysis result |
| `GET` | `/api/neighborhood/{id}/map` | Get interactive HTML map |
| `GET` | `/api/tasks/{task_id}` | Poll background task status |
| `POST` | `/api/agent/query` | AI investment analysis |
| `POST` | `/api/vector/search` | Find visually similar properties |
| `POST` | `/api/vector/store` | Store a property image embedding |
| `GET` | `/api/analysis/green-space/{id}` | Get green space analysis |

