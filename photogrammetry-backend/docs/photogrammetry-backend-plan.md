# Photogrammetry Backend — Architecture Plan & Jira Tasks

> **Project:** Team Bath ROV — MATE 2026 Competition Task 1.2 (Coral Garden 3D Modeling)
> **Date:** 2026-02-11
> **Branch:** `feature/photogrammetry-page`

---

## 1. Architecture Overview

### System Context

The photogrammetry subsystem turns coral reef images (uploaded or captured live) into a scaled 3D model (GLB) and estimates coral height. It consists of:

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | React 19 + TypeScript + Vite | Upload images, trigger jobs, display 3D model |
| **Backend API** | FastAPI (Python 3.11) | REST endpoints for jobs, uploads, scaling, manual CAD |
| **Photogrammetry Engine** | OpenSfM (subprocess) | Structure-from-Motion → PLY point cloud |
| **Mesh Processor** | Open3D + trimesh | PLY → surface mesh → GLB |
| **Live Capture** | OpenCV | Threaded RTSP camera frame grabber |
| **Manual CAD** | trimesh | Generate placeholder 3-prism coral model (GLB) |
| **Container** | Docker + docker-compose | Reproducible build with OpenSfM compiled |

### Data Flow

```
                     ┌─────────────┐
                     │   Frontend   │
                     │  (React/TS)  │
                     └──────┬───────┘
                            │  HTTP (Vite proxy → :8100)
                            ▼
                     ┌─────────────┐
                     │  FastAPI API │
                     │   (:8100)   │
                     └──────┬───────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │  OpenSfM  │ │  Scaling │ │ ManualCAD│
        │ Pipeline  │ │ Service  │ │ Service  │
        └─────┬─────┘ └──────────┘ └──────────┘
              ▼
        ┌──────────┐
        │   Mesh   │
        │Processor │
        │(Open3D)  │
        └─────┬────┘
              ▼
         output.glb
```

### Key Design Decisions

1. **In-memory job store** — no database needed; jobs live for the duration of the container.
2. **Polling for progress** — frontend polls `GET /api/jobs/{id}` every 2 seconds; no WebSockets required.
3. **Subprocess isolation** — OpenSfM runs as a subprocess; the API remains responsive.
4. **GLB as universal output** — all pipelines (OpenSfM, manual CAD) produce GLB files for `<model-viewer>`.
5. **Vite dev proxy** — `/api/*` proxied to `localhost:8100` during development.

---

## 2. Directory Structure

### Backend (`photogrammetry-backend/`)

```
photogrammetry-backend/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app, CORS, router mounting
│   ├── config.py                  # Settings (ports, paths, CORS origins)
│   ├── models/
│   │   ├── __init__.py
│   │   ├── job.py                 # Job, JobStatus, JobCreate Pydantic models
│   │   └── scaling.py             # ScaleRequest, ScaleResponse models
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── health.py              # GET /api/health
│   │   ├── jobs.py                # GET/POST /api/jobs, GET /api/jobs/{id}
│   │   ├── upload.py              # POST /api/upload
│   │   ├── photogrammetry.py      # POST /api/photogrammetry/run
│   │   ├── scaling.py             # POST /api/scaling/estimate
│   │   └── manual_cad.py          # POST /api/manual-cad/generate
│   ├── services/
│   │   ├── __init__.py
│   │   ├── job_manager.py         # In-memory job store, CRUD, status updates
│   │   ├── opensfm_pipeline.py    # OpenSfM subprocess orchestration
│   │   ├── mesh_processor.py      # PLY → GLB conversion
│   │   ├── scaling_service.py     # Bounding box → scale factor → height
│   │   ├── manual_cad_service.py  # trimesh 3-prism coral → GLB
│   │   └── camera_capture.py      # OpenCV threaded RTSP capture
│   └── utils/
│       ├── __init__.py
│       └── file_utils.py          # Temp dir management, file cleanup
├── data/
│   ├── uploads/                   # Uploaded image sets (per-job subdirs)
│   └── outputs/                   # Generated GLB models (per-job subdirs)
├── tests/
│   ├── __init__.py
│   ├── test_health.py
│   ├── test_jobs.py
│   ├── test_upload.py
│   ├── test_scaling.py
│   └── test_manual_cad.py
├── Dockerfile
├── requirements.txt
├── pyproject.toml
└── README.md
```

### Frontend Changes (in existing `src/`)

```
src/
├── api/
│   └── photogrammetry.ts          # Fetch client (upload, runJob, getJob, scale, manualCad)
├── components/
│   └── Tiles/
│       └── ModelViewer.tsx         # @google/model-viewer wrapper (replaces placeholder)
├── pages/
│   └── Photogrammetry/
│       └── index.tsx               # Updated: wired to API, polling, progress bar
└── types/
    └── photogrammetry.types.ts     # Extended: JobResponse, ScaleResponse, etc.
```

### Docker (project root)

```
docker-compose.photogrammetry.yml  # photogrammetry-backend service definition
```

---

## 3. API Specification

**Base URL:** `http://localhost:8100/api`

### Health

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Returns `{ "status": "ok", "version": "1.0.0" }` |

### Jobs

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/jobs` | Create a new job → returns `{ id, status, created_at }` |
| `GET` | `/api/jobs` | List all jobs |
| `GET` | `/api/jobs/{id}` | Get job detail (status, progress %, stage, output_url, error) |

#### Job Status Enum

```
pending → uploading → reconstructing → meshing → scaling → complete
                                                          → error
```

#### `GET /api/jobs/{id}` Response

```json
{
  "id": "uuid",
  "status": "reconstructing",
  "progress": 45,
  "stage": "feature_matching",
  "created_at": "2026-02-11T12:00:00Z",
  "output_url": null,
  "estimated_height_cm": null,
  "error": null
}
```

### Upload

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/upload` | Upload images (multipart/form-data) → saves to `data/uploads/{job_id}/` |

**Request:** `multipart/form-data` with fields:
- `job_id`: string (UUID)
- `files`: multiple image files

**Response:**
```json
{
  "job_id": "uuid",
  "file_count": 24,
  "total_size_mb": 48.2
}
```

### Photogrammetry

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/photogrammetry/run` | Start reconstruction pipeline for a job |

**Request:**
```json
{
  "job_id": "uuid"
}
```

**Response:**
```json
{
  "job_id": "uuid",
  "status": "reconstructing",
  "message": "Pipeline started"
}
```

### Scaling

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/scaling/estimate` | Compute estimated coral height from model + true length |

**Request:**
```json
{
  "job_id": "uuid",
  "true_coral_length_cm": 15.0
}
```

**Response:**
```json
{
  "job_id": "uuid",
  "estimated_height_cm": 22.5,
  "scale_factor": 1.5,
  "bounding_box": {
    "width": 10.0,
    "height": 15.0,
    "depth": 8.0
  }
}
```

### Manual CAD

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/manual-cad/generate` | Generate a 3-prism placeholder coral model |

**Request:**
```json
{
  "job_id": "uuid",
  "estimated_height_cm": 22.5,
  "true_coral_length_cm": 15.0
}
```

**Response:**
```json
{
  "job_id": "uuid",
  "output_url": "/api/jobs/uuid/model",
  "message": "Manual CAD model generated"
}
```

### Static File Serving

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/jobs/{id}/model` | Serve the generated GLB file |

---

## 4. Jira Tasks

---

### PHOTO-01: Backend Skeleton (FastAPI App, Config, Health Endpoint)

**Priority:** Highest
**Story Points:** 3
**Dependencies:** None (first task — unblocks everything)

#### Description

Set up the foundational FastAPI application structure for the photogrammetry backend. This creates the project skeleton that all other backend tasks build upon. The backend runs on port 8100 and serves a REST API under the `/api` prefix.

#### Acceptance Criteria

- [ ] `photogrammetry-backend/` directory exists at project root with the full folder structure from Section 2
- [ ] `app/main.py` creates a FastAPI app with CORS middleware allowing `http://localhost:5173` (Vite dev server)
- [ ] `app/config.py` uses Pydantic `BaseSettings` with fields: `PORT=8100`, `UPLOAD_DIR=data/uploads`, `OUTPUT_DIR=data/outputs`, `CORS_ORIGINS=["http://localhost:5173"]`
- [ ] `GET /api/health` returns `{ "status": "ok", "version": "1.0.0" }` with 200
- [ ] `requirements.txt` includes: `fastapi`, `uvicorn[standard]`, `python-multipart`, `pydantic-settings`
- [ ] `pyproject.toml` with project metadata and Python 3.11 requirement
- [ ] Server starts with `uvicorn app.main:app --host 0.0.0.0 --port 8100`
- [ ] `data/uploads/` and `data/outputs/` directories are created on startup if missing
- [ ] All `__init__.py` files present in every package directory

#### Files to Create/Modify

| File | Action |
|------|--------|
| `photogrammetry-backend/app/__init__.py` | Create (empty) |
| `photogrammetry-backend/app/main.py` | Create |
| `photogrammetry-backend/app/config.py` | Create |
| `photogrammetry-backend/app/models/__init__.py` | Create (empty) |
| `photogrammetry-backend/app/routers/__init__.py` | Create (empty) |
| `photogrammetry-backend/app/routers/health.py` | Create |
| `photogrammetry-backend/app/services/__init__.py` | Create (empty) |
| `photogrammetry-backend/app/utils/__init__.py` | Create (empty) |
| `photogrammetry-backend/app/utils/file_utils.py` | Create |
| `photogrammetry-backend/requirements.txt` | Create |
| `photogrammetry-backend/pyproject.toml` | Create |

---

### PHOTO-02: Job Management Service

**Priority:** High
**Story Points:** 3
**Dependencies:** PHOTO-01

#### Description

Implement the in-memory job store and associated Pydantic models. Jobs track the lifecycle of a photogrammetry reconstruction from creation through upload, processing, and completion. The job manager is a singleton service used by all routers.

#### Acceptance Criteria

- [ ] `Job` Pydantic model with fields: `id` (UUID), `status` (enum), `progress` (int 0-100), `stage` (str | None), `created_at` (datetime), `output_url` (str | None), `estimated_height_cm` (float | None), `error` (str | None)
- [ ] `JobStatus` enum: `pending`, `uploading`, `reconstructing`, `meshing`, `scaling`, `complete`, `error`
- [ ] `JobManager` class with methods: `create_job() → Job`, `get_job(id) → Job | None`, `list_jobs() → list[Job]`, `update_job(id, **fields) → Job`
- [ ] `POST /api/jobs` creates a job and returns it with status `pending`
- [ ] `GET /api/jobs` returns list of all jobs
- [ ] `GET /api/jobs/{id}` returns single job or 404
- [ ] Job manager is instantiated once and injected via FastAPI dependency
- [ ] Thread-safe: uses `threading.Lock` around dict mutations (OpenSfM runs in background threads)

#### Files to Create/Modify

| File | Action |
|------|--------|
| `photogrammetry-backend/app/models/job.py` | Create |
| `photogrammetry-backend/app/models/__init__.py` | Update (re-export) |
| `photogrammetry-backend/app/services/job_manager.py` | Create |
| `photogrammetry-backend/app/services/__init__.py` | Update (re-export) |
| `photogrammetry-backend/app/routers/jobs.py` | Create |
| `photogrammetry-backend/app/main.py` | Update (mount jobs router) |

---

### PHOTO-03: Manual CAD Model Generation

**Priority:** High
**Story Points:** 3
**Dependencies:** PHOTO-01, PHOTO-02

#### Description

Implement a service that generates a placeholder 3D coral model using trimesh. The model consists of 3 triangular prisms arranged to approximate a coral structure. This is the fallback when photogrammetry reconstruction is not available or for quick demonstrations. The output is a GLB file saved to the job's output directory.

#### Acceptance Criteria

- [ ] `ManualCADService` class with method: `generate(job_id, height_cm, length_cm) → str` (returns output path)
- [ ] Model consists of 3 triangular prisms with varying heights and rotations to simulate coral branches
- [ ] Prism dimensions are parameterized by `height_cm` and `length_cm` inputs
- [ ] Output is a valid `.glb` file saved to `data/outputs/{job_id}/model.glb`
- [ ] `POST /api/manual-cad/generate` endpoint accepts `{ job_id, estimated_height_cm, true_coral_length_cm }`
- [ ] Endpoint updates the job status to `complete` and sets `output_url` to `/api/jobs/{job_id}/model`
- [ ] Returns 404 if `job_id` does not exist
- [ ] `trimesh` added to `requirements.txt`
- [ ] GLB file is viewable in any standard 3D viewer or `<model-viewer>`

#### Files to Create/Modify

| File | Action |
|------|--------|
| `photogrammetry-backend/app/services/manual_cad_service.py` | Create |
| `photogrammetry-backend/app/services/__init__.py` | Update (re-export) |
| `photogrammetry-backend/app/routers/manual_cad.py` | Create |
| `photogrammetry-backend/app/main.py` | Update (mount manual_cad router) |
| `photogrammetry-backend/requirements.txt` | Update (add `trimesh`, `numpy`) |

---

### PHOTO-04: Scaling Algorithm Service

**Priority:** High
**Story Points:** 3
**Dependencies:** PHOTO-01, PHOTO-02

#### Description

Implement the scaling service that computes estimated coral height from a generated 3D model. The algorithm loads the GLB model, computes its axis-aligned bounding box, uses the known true coral length to derive a scale factor, and applies it to the model's height axis to estimate real-world coral height in centimeters.

#### Acceptance Criteria

- [ ] `ScalingService` class with method: `estimate_height(job_id, true_length_cm) → ScaleResponse`
- [ ] Loads the GLB model from `data/outputs/{job_id}/model.glb` using trimesh
- [ ] Computes axis-aligned bounding box (AABB) → extracts width, height, depth in model units
- [ ] Scale factor = `true_length_cm / model_bounding_box_width` (longest horizontal axis)
- [ ] Estimated height = `model_bounding_box_height * scale_factor`
- [ ] `ScaleRequest` Pydantic model: `{ job_id: str, true_coral_length_cm: float }`
- [ ] `ScaleResponse` Pydantic model: `{ job_id: str, estimated_height_cm: float, scale_factor: float, bounding_box: { width, height, depth } }`
- [ ] `POST /api/scaling/estimate` returns `ScaleResponse` or 404 if job/model not found
- [ ] Updates the job's `estimated_height_cm` field

#### Files to Create/Modify

| File | Action |
|------|--------|
| `photogrammetry-backend/app/models/scaling.py` | Create |
| `photogrammetry-backend/app/models/__init__.py` | Update (re-export) |
| `photogrammetry-backend/app/services/scaling_service.py` | Create |
| `photogrammetry-backend/app/services/__init__.py` | Update (re-export) |
| `photogrammetry-backend/app/routers/scaling.py` | Create |
| `photogrammetry-backend/app/main.py` | Update (mount scaling router) |

---

### PHOTO-05: Image Upload Endpoint + Photogrammetry API Routes

**Priority:** High
**Story Points:** 3
**Dependencies:** PHOTO-01, PHOTO-02

#### Description

Implement the image upload endpoint that accepts multiple image files via multipart form data and saves them to the job's upload directory. Also implement the photogrammetry run trigger endpoint that kicks off the OpenSfM pipeline (initially a stub that updates job status, to be wired to the real pipeline in PHOTO-06).

#### Acceptance Criteria

- [ ] `POST /api/upload` accepts `multipart/form-data` with `job_id` field and `files` field (multiple files)
- [ ] Files are saved to `data/uploads/{job_id}/` with their original filenames
- [ ] Validates that files are image MIME types (`image/jpeg`, `image/png`, `image/tiff`, `image/webp`)
- [ ] Returns `{ job_id, file_count, total_size_mb }` on success
- [ ] Returns 400 if no files provided or if non-image files detected
- [ ] Returns 404 if `job_id` does not exist
- [ ] Updates job status to `uploading` during upload, then back to `pending` when complete
- [ ] `POST /api/photogrammetry/run` accepts `{ job_id }` and starts the reconstruction pipeline
- [ ] Run endpoint validates that upload directory has images before starting
- [ ] Returns 400 if no images found for the job
- [ ] `GET /api/jobs/{id}/model` serves the GLB file from `data/outputs/{job_id}/model.glb` with correct `Content-Type: model/gltf-binary`
- [ ] `python-multipart` already in requirements (from PHOTO-01)

#### Files to Create/Modify

| File | Action |
|------|--------|
| `photogrammetry-backend/app/routers/upload.py` | Create |
| `photogrammetry-backend/app/routers/photogrammetry.py` | Create |
| `photogrammetry-backend/app/main.py` | Update (mount upload + photogrammetry routers, add static file route) |

---

### PHOTO-06: OpenSfM Pipeline Orchestration

**Priority:** High
**Story Points:** 5
**Dependencies:** PHOTO-02, PHOTO-05

#### Description

Implement the OpenSfM pipeline orchestrator that runs the Structure-from-Motion reconstruction as a series of subprocess stages. Each stage updates the job's progress and stage name so the frontend can display granular progress. The pipeline runs in a background thread to avoid blocking the API.

OpenSfM stages (in order):
1. `extract_metadata` (0-10%)
2. `detect_features` (10-25%)
3. `match_features` (25-45%)
4. `create_tracks` (45-50%)
5. `reconstruct` (50-75%)
6. `export_ply` (75-85%)

After the PLY is exported, the mesh processor (PHOTO-07) converts it to GLB (85-100%).

#### Acceptance Criteria

- [ ] `OpenSfMPipeline` class with method: `run(job_id) → None` (runs in background thread)
- [ ] Creates an OpenSfM project structure in a temp directory: `config.yaml`, `images/` symlinked to uploads
- [ ] Runs each OpenSfM command via `subprocess.run()` with timeout (10 minutes per stage)
- [ ] Updates job progress and stage after each successful subprocess
- [ ] If any stage fails: sets job status to `error` with the stderr message, stops pipeline
- [ ] OpenSfM `config.yaml` generated with sensible defaults for underwater imagery (e.g., `feature_type: SIFT`, `matching_gps_distance: 0`)
- [ ] After PLY export, calls `MeshProcessor.convert(ply_path, output_glb_path)` (from PHOTO-07)
- [ ] On completion: sets job status to `complete`, sets `output_url`
- [ ] Pipeline method is called from the `POST /api/photogrammetry/run` endpoint in a `threading.Thread`
- [ ] Logs each stage start/end to stdout for debugging

#### Files to Create/Modify

| File | Action |
|------|--------|
| `photogrammetry-backend/app/services/opensfm_pipeline.py` | Create |
| `photogrammetry-backend/app/services/__init__.py` | Update (re-export) |
| `photogrammetry-backend/app/routers/photogrammetry.py` | Update (wire pipeline to run endpoint) |
| `photogrammetry-backend/requirements.txt` | Update (add `opensfm` if pip-installable, otherwise document Docker build) |

---

### PHOTO-07: Mesh Processor (PLY Point Cloud to GLB)

**Priority:** High
**Story Points:** 3
**Dependencies:** PHOTO-01

#### Description

Implement the mesh processor that converts a PLY point cloud (output of OpenSfM) into a GLB mesh suitable for browser viewing. Uses Open3D for point cloud processing and Poisson surface reconstruction, then trimesh for GLB export.

#### Acceptance Criteria

- [ ] `MeshProcessor` class with method: `convert(ply_path: str, output_glb_path: str) → str`
- [ ] Loads PLY point cloud using Open3D (`o3d.io.read_point_cloud`)
- [ ] Estimates normals if not present (`estimate_normals` with search_param KDTree)
- [ ] Runs Poisson surface reconstruction (`create_from_point_cloud_poisson`, depth=9)
- [ ] Removes low-density vertices (filters out noise)
- [ ] Converts Open3D mesh to trimesh mesh (vertices + faces + vertex colors)
- [ ] Exports as GLB via `trimesh.exchange.gltf.export_glb()` or `mesh.export(path, file_type='glb')`
- [ ] Output GLB is under 50 MB for typical coral scans (500-1000 images)
- [ ] Handles edge cases: empty point cloud raises descriptive error, very large clouds are downsampled first
- [ ] `open3d` and `trimesh` added to `requirements.txt`

#### Files to Create/Modify

| File | Action |
|------|--------|
| `photogrammetry-backend/app/services/mesh_processor.py` | Create |
| `photogrammetry-backend/app/services/__init__.py` | Update (re-export) |
| `photogrammetry-backend/requirements.txt` | Update (add `open3d`) |

---

### PHOTO-08: Camera Recording & Frame Extraction (Frontend)

**Priority:** Medium
**Story Points:** 5
**Dependencies:** Camera streams connected on CoPilot page
**Repository:** `team-bath-rov-secondary-ui` (frontend only — no backend component)

#### Description

Add recording functionality to the CoPilot camera tiles. The operator clicks "Start Recording" on a camera tile to begin capturing the video stream in the browser. When they click "Stop Recording", the browser extracts frames from the recorded video at a configurable interval and downloads them as a zip of JPEG images. The operator then navigates to the Photogrammetry page and uploads that folder of frames to run reconstruction.

This replaces the previous plan for a backend RTSP capture service. Recording in the browser means:
- No backend dependency — the operator can record while doing other tasks
- The camera feed stays available for live viewing during and after recording
- Frames are saved to the operator's laptop, ready for upload when needed

#### Architecture

```
Camera Canvas (JSMpeg) → canvas.captureStream() → MediaRecorder (WebM)
    → on stop → seek through video → draw frames to canvas → JPEG export
    → bundle as ZIP → trigger browser download
```

#### Acceptance Criteria

- [ ] **Recording controls on CameraTile:**
  - "Start Recording" button appears on each enabled camera tile
  - Uses `canvas.captureStream()` to get a `MediaStream` from the JSMpeg canvas
  - `MediaRecorder` API records the stream as WebM (or MP4 if supported)
  - Existing `RecordingStatus` pulsing indicator activates during recording
  - "Stop Recording" button replaces start button while recording
- [ ] **Frame extraction on stop:**
  - Recorded video blob is loaded into a hidden `<video>` element
  - Video is seeked through at a configurable interval (default: every 2 seconds)
  - At each seek position, the video frame is drawn to an offscreen `<canvas>` and exported as JPEG (quality 0.95)
  - Frames are named `frame_0001.jpg`, `frame_0002.jpg`, etc. (zero-padded 4 digits)
- [ ] **Download as ZIP:**
  - Frames are bundled into a ZIP file using `JSZip` (or similar library)
  - ZIP is named `{camera-name}_{timestamp}.zip` (e.g., `Front_Camera_2026-02-24T12-00-00.zip`)
  - Browser triggers automatic download of the ZIP
- [ ] **Configuration:**
  - Frame extraction interval configurable (default 2 seconds)
  - JPEG quality configurable (default 0.95)
  - Settings accessible via a small popover/menu on the camera tile
- [ ] **Error handling:**
  - Shows error toast if `MediaRecorder` is not supported
  - Shows error toast if canvas stream capture fails
  - Handles case where recording is stopped very quickly (< 1 second)
- [ ] **State management:**
  - Uses existing `isRecording` field in `CameraState`
  - Recording state persists correctly when toggling camera visibility
  - Only one camera can record at a time (or multiple — TBD)

#### Files to Create/Modify

| File | Action |
|------|--------|
| `src/hooks/useCanvasRecorder.ts` | Create — custom hook encapsulating MediaRecorder + frame extraction logic |
| `src/utils/frameExtractor.ts` | Create — seeks through video blob and extracts JPEG frames |
| `src/utils/zipDownload.ts` | Create — bundles frames into ZIP and triggers download |
| `src/components/Tiles/CameraTile.tsx` | Update — add record/stop buttons, wire to hook |
| `src/features/copilot/context/CoPilotContext.tsx` | Update — add recording actions if needed |
| `package.json` | Update — add `jszip` dependency |

---

### PHOTO-09: Frontend API Client + Vite Proxy

**Priority:** High
**Story Points:** 3
**Dependencies:** PHOTO-01, PHOTO-02, PHOTO-05

#### Description

Create the frontend API client module that wraps all fetch calls to the photogrammetry backend. Configure the Vite dev server to proxy `/api` requests to the backend at `localhost:8100`. Extend the existing TypeScript types to include API response shapes.

#### Acceptance Criteria

- [ ] `src/api/photogrammetry.ts` exports the following async functions:
  - `createJob() → Promise<JobResponse>`
  - `getJob(jobId: string) → Promise<JobResponse>`
  - `listJobs() → Promise<JobResponse[]>`
  - `uploadImages(jobId: string, files: File[]) → Promise<UploadResponse>`
  - `runPhotogrammetry(jobId: string) → Promise<RunResponse>`
  - `estimateScale(jobId: string, trueCoralLengthCm: number) → Promise<ScaleResponse>`
  - `generateManualCAD(jobId: string, heightCm: number, lengthCm: number) → Promise<ManualCADResponse>`
  - `getModelUrl(jobId: string) → string` (returns URL path, not a fetch)
- [ ] All fetch calls use relative URLs (`/api/...`) so the Vite proxy handles routing
- [ ] Error handling: functions throw a typed `ApiError` with `status` and `message` fields
- [ ] `vite.config.ts` updated with proxy: `'/api': { target: 'http://localhost:8100', changeOrigin: true }`
- [ ] `src/types/photogrammetry.types.ts` extended with: `JobResponse`, `UploadResponse`, `RunResponse`, `ScaleResponse`, `ManualCADResponse`, `ApiError`
- [ ] Barrel export in `src/api/index.ts`

#### Files to Create/Modify

| File | Action |
|------|--------|
| `src/api/photogrammetry.ts` | Create |
| `src/api/index.ts` | Create (barrel export) |
| `src/types/photogrammetry.types.ts` | Update (add API response types) |
| `src/types/index.ts` | Update (re-export new types) |
| `vite.config.ts` | Update (add proxy config) |

---

### PHOTO-10: Frontend 3D Model Viewer

**Priority:** High
**Story Points:** 3
**Dependencies:** PHOTO-09

#### Description

Replace the existing `ModelViewerPlaceholder` component with a real 3D model viewer using Google's `<model-viewer>` web component. The viewer displays the generated GLB model with orbit controls, auto-rotate, and AR-compatible rendering. It falls back to the placeholder UI when no model is available.

#### Acceptance Criteria

- [ ] `@google/model-viewer` package installed (`npm install @google/model-viewer`)
- [ ] `src/components/Tiles/ModelViewer.tsx` component created with props:
  - `modelUrl: string | null` — URL to the GLB file (or null for placeholder state)
  - `status: ReconstructionStatus` — current job status
  - `estimatedHeight: number | null` — displayed as overlay
- [ ] When `modelUrl` is null or status is not `complete`: renders existing placeholder UI (status messages, spinner)
- [ ] When `modelUrl` is set and status is `complete`: renders `<model-viewer>` with:
  - `src={modelUrl}`
  - `camera-controls` for orbit/zoom/pan
  - `auto-rotate` for idle animation
  - `shadow-intensity="1"` for ground shadow
  - `environment-image="neutral"` for neutral lighting
  - Styled to fill the parent container (100% width/height)
- [ ] Estimated height displayed as overlay chip in top-right corner (matching existing placeholder style)
- [ ] Type declaration for `<model-viewer>` JSX element added (extend `JSX.IntrinsicElements`)
- [ ] Barrel export updated in `src/components/Tiles/index.ts`
- [ ] Existing `ModelViewerPlaceholder.tsx` retained but no longer used by the Photogrammetry page

#### Files to Create/Modify

| File | Action |
|------|--------|
| `src/components/Tiles/ModelViewer.tsx` | Create |
| `src/components/Tiles/Index.tsx` | Update (add ModelViewer export) |
| `src/types/model-viewer.d.ts` | Create (JSX type declaration) |
| `package.json` | Update (add `@google/model-viewer`) |

---

### PHOTO-11: Frontend Page Integration (Wire Buttons to API)

**Priority:** High
**Story Points:** 5
**Dependencies:** PHOTO-09, PHOTO-10

#### Description

Wire the Photogrammetry page's UI controls to the backend API. Replace the current mock `setTimeout` reconstruction with real API calls. Implement job polling for progress updates, connect the Generate/Scale/Manual CAD buttons, and display the 3D model when reconstruction completes.

#### Acceptance Criteria

- [ ] **Generate Model button** flow:
  1. Calls `createJob()` to get a job ID
  2. Calls `uploadImages(jobId, uploadedImages)` to upload files
  3. Calls `runPhotogrammetry(jobId)` to start the pipeline
  4. Begins polling `getJob(jobId)` every 2 seconds
  5. Updates `reconstructionStatus` and progress based on job response
  6. On `complete`: stops polling, sets model URL, displays model
  7. On `error`: stops polling, shows error toast/snackbar
- [ ] **Scale Model** flow:
  1. Calls `estimateScale(jobId, trueCoralLength)` after model is complete
  2. Displays estimated height in the model viewer overlay
  3. Updates the `estimatedCoralHeight` state
- [ ] **Manual CAD button** (new):
  1. Added to the UI grid (below Generate, or as a secondary action)
  2. Calls `generateManualCAD(jobId, estimatedHeight, trueCoralLength)`
  3. On success: displays the manual model in the viewer
- [ ] Progress bar or percentage text shown during reconstruction (using `job.progress` and `job.stage`)
- [ ] Polling is cleaned up on component unmount (useEffect cleanup)
- [ ] Error states display MUI Snackbar with error message
- [ ] Loading states: buttons disabled during API calls, with CircularProgress indicator
- [ ] Uses the new `ModelViewer` component instead of `ModelViewerPlaceholder`

#### Files to Create/Modify

| File | Action |
|------|--------|
| `src/pages/Photogrammetry/index.tsx` | Update (major rewrite of handlers and state) |
| `src/types/photogrammetry.types.ts` | Update (if additional frontend-only types needed) |

---

### PHOTO-12: Docker Setup (Dockerfile + docker-compose)

**Priority:** Medium
**Story Points:** 5
**Dependencies:** PHOTO-01 through PHOTO-08 (all backend tasks)

#### Description

Create a Dockerfile for the photogrammetry backend that includes OpenSfM compiled from source, all Python dependencies, and a docker-compose service definition. OpenSfM requires building from source with CMake and has specific system dependencies (Ceres Solver, OpenCV, etc.).

#### Acceptance Criteria

- [ ] `photogrammetry-backend/Dockerfile` multi-stage build:
  - **Stage 1 (builder):** Ubuntu 22.04 base, installs build deps (cmake, gcc, libceres-dev, libeigen3-dev, etc.), clones OpenSfM from GitHub, builds with `python setup.py build`
  - **Stage 2 (runtime):** Python 3.11-slim, copies built OpenSfM and pip packages, minimal runtime dependencies only
- [ ] Final image size < 2.5 GB (multi-stage keeps it lean)
- [ ] `docker-compose.photogrammetry.yml` at project root with service:
  ```yaml
  services:
    photogrammetry-backend:
      build: ./photogrammetry-backend
      ports:
        - "8100:8100"
      volumes:
        - photogrammetry-data:/app/data
      environment:
        - PORT=8100
        - CORS_ORIGINS=["http://localhost:5173"]
      restart: unless-stopped
  volumes:
    photogrammetry-data:
  ```
- [ ] Health check configured: `HEALTHCHECK CMD curl -f http://localhost:8100/api/health || exit 1`
- [ ] `.dockerignore` excludes: `__pycache__`, `.git`, `data/`, `tests/`, `*.pyc`, `.env`
- [ ] Container starts and `GET /api/health` returns 200
- [ ] OpenSfM is importable inside the container (`python -c "import opensfm"`)
- [ ] Volume mount persists `data/` between container restarts

#### Files to Create/Modify

| File | Action |
|------|--------|
| `photogrammetry-backend/Dockerfile` | Create |
| `photogrammetry-backend/.dockerignore` | Create |
| `docker-compose.photogrammetry.yml` | Create (project root) |

---

## 5. Task Dependency Graph

```
Backend (team-bath-rov-software):

PHOTO-01 (Skeleton) ✅
    │
    ├──► PHOTO-02 (Job Manager) ✅
    │        │
    │        ├──► PHOTO-03 (Manual CAD) ✅
    │        ├──► PHOTO-04 (Scaling) ✅
    │        ├──► PHOTO-05 (Upload + Routes) ✅
    │        │        │
    │        │        └──► PHOTO-06 (OpenSfM)
    │        │
    │
    └──► PHOTO-07 (Mesh Processor)
              │
              └──► (used by PHOTO-06)

PHOTO-12 (Docker)
    depends on: PHOTO-01 through PHOTO-07

Frontend (team-bath-rov-secondary-ui):

PHOTO-08 (Camera Recording & Frame Extraction)
    │    depends on: camera streams connected on CoPilot page
    │    (independent of backend tasks)

PHOTO-09 (API Client + Proxy) ✅
    │    depends on: PHOTO-01, PHOTO-02, PHOTO-05
    │
    ├──► PHOTO-10 (Model Viewer) ✅
    │
    └──► PHOTO-11 (Page Integration) ✅
              depends on: PHOTO-09, PHOTO-10
```

## 6. Story Point Summary

| Task | Story Points | Status | Repo |
|------|-------------|--------|------|
| PHOTO-01 (Skeleton) | 3 | Done | software |
| PHOTO-02 (Job Manager) | 3 | Done | software |
| PHOTO-03 (Manual CAD) | 3 | Done | software |
| PHOTO-04 (Scaling) | 3 | Done | software |
| PHOTO-05 (Upload + Routes) | 3 | Done | software |
| PHOTO-06 (OpenSfM Pipeline) | 5 | TODO | software |
| PHOTO-07 (Mesh Processor) | 3 | TODO | software |
| PHOTO-08 (Camera Recording & Frame Extraction) | 5 | TODO | secondary-ui |
| PHOTO-09 (API Client + Proxy) | 3 | Done | secondary-ui |
| PHOTO-10 (Model Viewer) | 3 | Done | secondary-ui |
| PHOTO-11 (Page Integration) | 5 | Done | secondary-ui |
| PHOTO-12 (Docker) | 5 | TODO | software |
| **Total** | **44** | **8/12 Done** | |
