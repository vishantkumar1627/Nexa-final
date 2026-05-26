# AI Text-to-2D Floor Plan & 3D Architecture Generation System
## Production-Grade Asynchronous CAD Generation Engine

Welcome to the **AI Text-to-3D Architecture Generation System**. This production-ready backend is designed to parse natural language architectural commands (e.g., *"Design a modern 3-bedroom house with garage and balcony"*), map spatial relationships dynamically, pack layouts procedurally, generate beautiful vectorized plans (SVG, DXF), and construct high-fidelity 3D meshes along with photorealistic renders using background-driven **Blender** software instances.

---

## 1. Architectural Deep-Dive

The backend is built around a **Modular Monolith** architecture patterns, containerized with **Docker** and proxy-controlled with **NGINX**. By utilizing a shared database layer but separating service execution bounds, we achieve high scalability and horizontal expandability.

### Topological Service Layout
*   **NGINX Ingress (Port 80)**: Intercepts all traffic. Routes HTTP request pools to the API Gateway and maps WebSocket connections directly to the WebSocket Service, performing standard protocol upgrade handshakes.
*   **API Gateway (FastAPI, Port 8000)**: Serves standard REST operations, authenticates sessions via high-entropy JWT, and tracks background job transactions in PostgreSQL.
*   **WebSocket Progress Service (FastAPI, Port 8001)**: Dedicated async thread running a high-concurrency event listener, subscribing to Redis channels and streaming progress updates back to connected web clients.
*   **Celery Queue & Redis Broker**: Decouples long-running neural operations and heavy 3D rendering tasks from client HTTP threads, distributing jobs cleanly.
*   **Celery task Worker (Blender Embedded)**: The rendering and generation engine. Executes the 5-stage pipeline, spins up headless Blender CLI operations, and writes files directly to a shared static volume `/outputs/` for immediate access.
*   **Database Persistent Layer (PostgreSQL 15)**: Persists schemas with relational integrity.

```
+-----------------------------------------------------------------------------------+
|                                  NGINX Proxy                                      |
+-----------------------------------------------------------------------------------+
             |                                             |
             v (HTTP API)                                  v (WebSockets /ws/*)
+----------------------------+               +--------------------------------------+
|        API Gateway         |               |          WebSocket Service           |
|       (FastAPI:8000)       |               |            (FastAPI:8001)            |
+----------------------------+               +--------------------------------------+
             |                                             |
             +-------------+                   +-----------+
                           |                   |
                           v                   v
                   +-----------------------------------+
                   |           Redis Broker            |
                   +-----------------------------------+
                                   |
                                   v (Celery Job Dispatch)
                   +-----------------------------------+
                   |           Celery Worker           |
                   |      (Blender Headless Engine)    |
                   +-----------------------------------+
```

---

## 2. 5-Stage Generation Workflow

Every text generation request enqueues a background job that moves sequentially through our ML-inspired layout engine:

1.  **NLP Service Parsing (Stage 1)**: Reads prompts, maps semantic intents, tokenizes terms with HuggingFace, and extracts rooms, area dimensions, visual styles, and relational adjacencies.
2.  **Spatial Graph Processing (Stage 2)**: Builds an algebraic graph model using `NetworkX`, verifies planarity (checking if the layout is physically constructible without intersecting paths), and generates spring-embedding continuous layouts.
3.  **Layout Generation & Grid snap (Stage 3)**: Packs continuous spring coordinates into snapped room rectangles, resolving spacing overlaps and snapping joint walls, then generates a gorgeous labeled raster image of the plan.
4.  **Vectorization Pipeline (Stage 4)**: Executes contour detection and polygon simplifications in `OpenCV`, generating CAD-compliant standard AutoCAD `DXF` files, scalable layered web `SVG` drawings, and coordinate `JSON` arrays.
5.  **Blender 3D Modeling & Rendering (Stage 5)**: The worker launches a background instance of Blender, passing layout coordinates. A custom script procedurally extrudes walls, lays wood flooring, inserts assets, configures interior lighting, and renders isometric and topdown visualizations, exporting files to `.gltf`, `.obj`, and `.blend`.

---

## 3. Directory File Map

```
backend/
├── docker-compose.yml              # Multi-container orchestration topology
├── .env                            # Active environment variables config
├── requirements.txt                # System dependencies list
├── nginx/
│   └── nginx.conf                  # Proxy router mappings & websocket handshakes
├── docker/
│   ├── Dockerfile.api              # FastAPI Gateway container build
│   ├── Dockerfile.websocket        # WebSocket service container build
│   └── Dockerfile.worker           # Celery worker with Blender & OpenGL setup
├── shared/
│   ├── config.py                   # Central settings provider
│   ├── database.py                 # SQLAlchemy connection pools (sync/async)
│   ├── security.py                 # Password hashing & JWT operations
│   ├── models.py                   # Relational Postgres models definitions
│   └── schemas.py                  # Pydantic v2 data validations
├── services/
│   ├── storage_service.py          # Unified file persistence (local or AWS S3)
│   ├── nlp_service.py              # Text processor & intent extractor
│   ├── graph_service.py            # Planar validator & NetworkX layouts
│   ├── layout_service.py           # Room grid snapper & raster plan drawer
│   ├── floorplan_service.py        # Vectorizer generating SVG, DXF, and JSON
│   ├── websocket_service/
│   │   └── main.py                 # WebSocket progress stream microservice
│   └── api_gateway/
│       ├── main.py                 # Master REST entrypoint
│       └── routers/
│           ├── auth.py             # Authentications controller
│           ├── projects.py         # Project CRUD controller
│           ├── generate.py         # AI generators controller
│           └── files.py            # File downloader & traversal protection
├── scripts/
│   └── blender_generator.py        # Blender Python automation script
├── workers/
│   ├── celery_app.py               # Celery app initialization
│   └── tasks.py                    # Pipeline pipeline worker tasks
└── tests/
    └── test_api.py                 # Pytest integration validations
```

---

## 4. Environment Variables Setup

Create a `.env` file in the `backend/` root folder (a fully configured `.env` has already been generated for your immediate development ease):

```ini
# Project Settings
PROJECT_NAME="AI Text-to-3D Floor Plan System"
DEBUG=True

# Database Settings
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=architecture_db
POSTGRES_HOST=db
POSTGRES_PORT=5432
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/architecture_db
SYNC_DATABASE_URL=postgresql://postgres:postgres@db:5432/architecture_db

# Broker Settings
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Security Secrets (Must be secure hashes in production)
JWT_SECRET_KEY=9a3dfbe48f95c1d683719485bb29e0018f2f9c8da9e06180a0684f88427fbf02
JWT_REFRESH_SECRET_KEY=e83a992a7e7b5abfa34ff6c6a47ea1e389d020fb143c1ab2f20c4ef18671607a
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# File Storage
STORAGE_DIR=/app/outputs
USE_S3=False
```

---

## 5. Local Setup & Execution Guide

The entire system is configured to launch with a single command. 

### Prerequisites
*   [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running.
*   Port `80` and `5432` available.

### Booting the System
Open your terminal in the `backend/` directory and run:
```bash
docker-compose up --build
```

Docker will:
1.  Spin up the PostgreSQL database (`db`) and run automated health checks.
2.  Spin up the Redis broker (`redis`).
3.  Compile and launch the API Gateway (`api`) on port 8000 internally. (It automatically connects to PostgreSQL and bootstraps all tables immediately on startup!).
4.  Compile and launch the WebSocket progress service (`websocket`) on port 8001 internally.
5.  Compile and install Blender, virtual framebuffers (Mesa/GLX), PyTorch, and tokenizers on the Celery Worker (`worker`).
6.  Launch NGINX (`nginx`) on port `80` to act as our gateway proxy.

You can verify the services are active by opening:
[http://localhost/health](http://localhost/health)

Swagger Interactive OpenAPI Docs can be viewed directly at:
[http://localhost/docs](http://localhost/docs)

---

## 6. End-to-End API Documentation & Testing Steps

You can easily test the entire generation pipeline using Swagger or standard `curl`:

### Step 1: User Registration
Submit credentials to create an active account:
```bash
curl -X POST "http://localhost/auth/register" \
     -H "Content-Type: application/json" \
     -d '{"email": "architect@nex.ai", "password": "securepassword123"}'
```
*Response returns active access and refresh JWT tokens.*

### Step 2: Login and Save Access Token
```bash
curl -X POST "http://localhost/auth/login" \
     -d "username=architect@nex.ai&password=securepassword123"
```
*Extract the `access_token` string from this response to authorize subsequent API requests.*

### Step 3: Create an Architectural Project
Submit your text descriptions and architectural layouts requests:
```bash
curl -X POST "http://localhost/projects/create" \
     -H "Authorization: Bearer <YOUR_ACCESS_TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "Sleek Modernist Villa",
       "prompt": "Design a modern 3-bedroom house with garage, spacious living room, open kitchen, and classic front balcony",
       "style": "minimalist"
     }'
```
*Extract the `id` of the created project from the response JSON.*

### Step 4: Open WebSocket Connection for Progress Tracking
Using any WebSocket client (or in browser JS console), subscribe to progress events:
```javascript
const socket = new WebSocket("ws://localhost/ws/progress/<GENERATED_JOB_ID>");
socket.onmessage = (event) => {
    const progress = JSON.parse(event.data);
    console.log(`[${progress.current_stage}] -> ${progress.progress_percent}%`);
};
```

### Step 5: Trigger Asynchronous Pipeline
Start the generation pipeline:
```bash
curl -X POST "http://localhost/generate/floorplan" \
     -H "Authorization: Bearer <YOUR_ACCESS_TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{"project_id": "<YOUR_PROJECT_ID>"}'
```
*Response immediately returns a `job_id` and transitions to `PENDING` status. The WebSocket stream will start printing logs from `NLP Parsing`, `Graph Generation`, `Vectorization` up to `Completed`.*

### Step 6: Fetch Generated Files
Once progress hits 100%, you can fetch the structural project details:
```bash
curl -X GET "http://localhost/projects/<YOUR_PROJECT_ID>" \
     -H "Authorization: Bearer <YOUR_ACCESS_TOKEN>"
```
This returns complete asset locations:
*   **Floor Plan SVG Layout**: `/download/floorplans/floorplan_<JOB_ID>.svg`
*   **Floor Plan CAD DXF**: `/download/floorplans/floorplan_<JOB_ID>.dxf`
*   **Isometric Renders**: `/download/renders/render_ext_<JOB_ID>.png`
*   **Headless 3D Mesh GLTF**: `/download/models3d/model_<JOB_ID>.gltf`
*   **CAD Mesh OBJ**: `/download/models3d/model_<JOB_ID>.obj`
*   **Native Blender Archive**: `/download/models3d/model_<JOB_ID>.blend`

To download an asset, simply call:
```bash
curl -O -L "http://localhost/download/floorplans/floorplan_<JOB_ID>.svg" \
     -H "Authorization: Bearer <YOUR_ACCESS_TOKEN>"
```

---

## 7. Testing Suite

To execute the automated unit tests, navigate to the `backend/` folder and run:
```bash
pytest -v
```
This will automatically execute the gateway validations, mock JWT register/logins, and confirm healthy execution boundaries.

---

### Architectural Design and Development by Antigravity (Google DeepMind Team)
