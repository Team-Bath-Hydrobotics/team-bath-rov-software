# Team Bath ROV Software

Monorepo for **Team Bath Hydrobotics** — competing in MATE ROV 2026. Contains all backend services, ML pipelines, and tooling that run on or alongside the ROV.

The pilot-facing UI lives in a separate repo: [`team-bath-rov-secondary-ui`](https://github.com/Team-Bath-Hydrobotics/team-bath-rov-secondary-ui).

## Services

| Folder | Description |
|---|---|
| `common/` | Shared Python utilities and schemas |
| `docs-site/` | MkDocs documentation site |
| `machine-learning/` | ML models (crab detection, etc.) |
| `packet-simulator/` | Simulates ROV telemetry packets for testing |
| `photogrammetry-backend/` | FastAPI service for 3D coral reconstruction |
| `telemetry-processor/` | Processes and routes telemetry data |
| `video-processor/` | Video ingest, encoding, and streaming |

## Quick Start

### Prerequisites

- Python 3.11+
- [Poetry](https://python-poetry.org/docs/#installing-with-pipx) (dependency management)
- [Node.js 20+](https://nodejs.org/) & npm (for the secondary UI)
- [FFmpeg](https://ffmpeg.org/) (for video processing)

### 1. Clone both repos

```bash
git clone https://github.com/Team-Bath-Hydrobotics/team-bath-rov-software.git
git clone https://github.com/Team-Bath-Hydrobotics/team-bath-rov-secondary-ui.git
```

### 2. Run the photogrammetry backend

```bash
cd team-bath-rov-software/photogrammetry-backend
pip install -e .
uvicorn app.main:app --reload --port 8100
```

The API will be available at `http://localhost:8100`. Interactive docs at `http://localhost:8100/docs`.

### 3. Run the secondary UI

```bash
cd team-bath-rov-secondary-ui
npm install
npm run dev
```

The UI dev server starts at `http://localhost:5173` and proxies `/api` requests to the backend via its Vite config.

### How the repos connect

```
┌─────────────────────────────┐       ┌──────────────────────────┐
│  team-bath-rov-secondary-ui │       │ team-bath-rov-software   │
│  (Vite + React)             │       │                          │
│                             │  /api │  photogrammetry-backend  │
│  localhost:5173  ───────────┼──────>│  localhost:8100          │
│                             │ proxy │                          │
└─────────────────────────────┘       └──────────────────────────┘
```

The secondary UI's Vite dev server proxies all `/api/*` requests to `localhost:8100`, so the frontend and backend can run on different ports without CORS issues during development.

## Documentation

Full guides, architecture docs, and contribution info live on our docs site:

**[https://team-bath-hydrobotics-f1fbb4.netlify.app/](https://team-bath-hydrobotics-f1fbb4.netlify.app/)**

To run the docs site locally:

```bash
cd docs-site
poetry install --no-root
poetry run mkdocs serve
```
