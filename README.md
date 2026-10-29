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
- [Poetry](https://python-poetry.org/docs/#installing-with-pipx) - dependency management
- [FFmpeg](https://ffmpeg.org/) - for video processing
- [Docker](https://docs.docker.com/desktop/#:~:text=Next%20steps-,Install%20Docker%20Desktop,-Install%20Docker%20Desktop) - for managing containers
  
## 1. Clone both repos:
```bash
git clone https://github.com/Team-Bath-Hydrobotics/team-bath-rov-software.git
git clone https://github.com/Team-Bath-Hydrobotics/team-bath-rov-secondary-ui.git
```
## 2. Install dependencies 
Navigate to team-bath-rov-software/telemetry-processor and run
```bash
poetry install
```
Repeat this step for video-processor and packet-processor

## Running

For two lightweight simulated camera feeds on your laptop, see the
[local video preset](config/local-video/README.md). It provides matching simulator
and processor configurations with generated 640×480 video at 30 fps and small
frame queues. From the repository root, start it with the secondary UI using:

```bash
python scripts/run-all.py --local-video --exclude telemetry-processor
```

Omit `--exclude telemetry-processor` to include telemetry and its Docker broker.
Without `--local-video`, run-all uses the existing video configs in each service
directory.

## Option 1 (recommended)

Navigate to the team-bath-rov-software/scripts and run:
```bash
python run-all.py --help
```
Review the output to learn more about the flags. 

By default (with no flags provided), it runs everything and starts the web server as usual. 

## Option 2 (more involved)

#### 1. Run the Telemetry Processor

Instructions can be found in telemetry-processor/README.md

#### 2. Run the Video Processor

Instructions can be found in video-processor/README.md

#### 3. Run the Packet Simulator

Instructions can be found in packet-simulator/README.md

#### 4. Run the secondary UI

```bash
cd team-bath-rov-secondary-ui
npm install
npm run dev
```

The UI dev server starts at `http://localhost:5173` and proxies `/api` requests to the backend via its Vite config.

### To run the photogrammetry backend

This isn't being used for the 2027 MATE ROV competition AFAIK so we don't need to worry about this for now

```bash
cd team-bath-rov-software/photogrammetry-backend
pip install -e .
uvicorn app.main:app --reload --port 8100
```

The API will be available at `http://localhost:8100`. Interactive docs at `http://localhost:8100/docs`.

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
