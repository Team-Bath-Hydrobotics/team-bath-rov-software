# Getting Started

This guide walks you through setting up the full Team Bath ROV development environment from scratch.

## Prerequisites

Install the following before proceeding:

| Tool | Version | Install link |
|---|---|---|
| **Python** | 3.11+ | [python.org/downloads](https://www.python.org/downloads/) |
| **Poetry** | latest | [python-poetry.org](https://python-poetry.org/docs/#installing-with-pipx) (install via [pipx](https://pipx.pypa.io/stable/installation/)) |
| **Node.js** | 20+ | [nodejs.org](https://nodejs.org/) |
| **FFmpeg** | latest | [ffmpeg.org](https://ffmpeg.org/download.html) |
| **Git** | latest | [git-scm.com](https://git-scm.com/) |

Verify your installs:

```bash
python3 --version   # 3.11+
poetry --version
node --version       # v20+
ffmpeg -version
```

## Clone Both Repos

The project is split across two repositories:

```bash
git clone https://github.com/Team-Bath-Hydrobotics/team-bath-rov-software.git
git clone https://github.com/Team-Bath-Hydrobotics/team-bath-rov-secondary-ui.git
```

## Architecture Overview

```
┌──────────────────────────────────────┐
│     team-bath-rov-secondary-ui       │
│     (React + Vite)                   │
│     http://localhost:5173            │
│                                      │
│   Vite dev server proxies /api/*     │
│   requests to the backend ──────────────┐
└──────────────────────────────────────┘  │
                                          │
┌──────────────────────────────────────┐  │
│     team-bath-rov-software           │  │
│                                      │  │
│  ┌────────────────────────────────┐  │  │
│  │ photogrammetry-backend         │<────┘
│  │ FastAPI — http://localhost:8100│  │
│  └────────────────────────────────┘  │
│                                      │
│  ┌────────────────────────────────┐  │
│  │ telemetry-processor            │  │
│  │ video-processor                │  │
│  │ packet-simulator               │  │
│  │ machine-learning               │  │
│  │ ...                            │  │
│  └────────────────────────────────┘  │
└──────────────────────────────────────┘
```

The **secondary UI** is a React app served by Vite's dev server on port `5173`. Its Vite config includes a proxy rule that forwards any `/api/*` request to `http://localhost:8100`, where the **photogrammetry backend** runs. This means during development both servers run independently, but the browser only talks to `:5173` — Vite handles routing API calls to the backend, avoiding CORS issues.

Other services in the monorepo (telemetry processor, video processor, etc.) communicate via MQTT and are designed to run on or near the ROV hardware.

## Per-Service Setup

### Photogrammetry Backend

```bash
cd team-bath-rov-software/photogrammetry-backend
pip install -e .
uvicorn app.main:app --reload --port 8100
```

- API: [http://localhost:8100](http://localhost:8100)
- Swagger docs: [http://localhost:8100/docs](http://localhost:8100/docs)

The backend stores uploads in `data/uploads/` and outputs in `data/outputs/` (created automatically on first run).

### Secondary UI

```bash
cd team-bath-rov-secondary-ui
npm install
npm run dev
```

- UI: [http://localhost:5173](http://localhost:5173)

The UI should now be able to talk to the photogrammetry backend through the Vite proxy.

### Other Python Services

Most Python services in the monorepo follow the same pattern:

```bash
cd team-bath-rov-software/<service-folder>
poetry install
poetry run python3 <entrypoint>.py
```

Check each service's `README.md` for the specific entrypoint.

### Docs Site

```bash
cd team-bath-rov-software/docs-site
poetry install --no-root
poetry run mkdocs serve
```

Docs will be served at [http://localhost:8000](http://localhost:8000).

## Running Photogrammetry Backend + Secondary UI Together

1. **Terminal 1** — start the backend:
    ```bash
    cd team-bath-rov-software/photogrammetry-backend
    uvicorn app.main:app --reload --port 8100
    ```

2. **Terminal 2** — start the UI:
    ```bash
    cd team-bath-rov-secondary-ui
    npm run dev
    ```

3. Open [http://localhost:5173](http://localhost:5173) in your browser. The UI will proxy API requests to the backend automatically.

## Ports Reference

| Service | Port |
|---|---|
| Photogrammetry backend | `8100` |
| Secondary UI (Vite) | `5173` |
| Docs site (MkDocs) | `8000` |

## Troubleshooting

### Python version mismatch

If you see errors about unsupported syntax or missing features, check your Python version:

```bash
python3 --version
```

The project requires Python 3.11+. If you have multiple versions installed, you may need to use `python3.12` explicitly or manage versions with [pyenv](https://github.com/pyenv/pyenv).

### Missing FFmpeg

The video processor requires FFmpeg. If you get `ffmpeg: command not found`:

- **macOS**: `brew install ffmpeg`
- **Ubuntu/Debian**: `sudo apt install ffmpeg`
- **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to your PATH

### Poetry not found

Install Poetry via pipx (recommended):

```bash
pipx install poetry
```

Or via the official installer:

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

### CORS errors in the browser

If you see CORS errors, make sure both servers are running and you're accessing the UI through `http://localhost:5173` (not directly hitting the backend at `:8100` from a browser page).

### Port already in use

If a port is occupied, find and kill the process:

```bash
lsof -i :8100  # or :5173
kill <PID>
```
