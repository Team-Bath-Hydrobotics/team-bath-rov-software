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

The repository includes setup scripts for macOS and Windows. The secondary UI
is a separate repository and should be cloned beside this one:

```text
parent-directory/
├── team-bath-rov-software/
└── team-bath-rov-secondary-ui/
```

### Automated setup: macOS

From the software repository, run:

```bash
./scripts/mac_setup.sh
```

This installs Homebrew packages, Python 3.11, Poetry, Node.js, FFmpeg, Docker
Desktop, and `mkcert`. It installs the three Python services and creates the
MQTT TLS keystore after prompting for its password.

### Automated setup: Windows

The Windows setup script checks for `winget` and attempts to install
Microsoft's signed App Installer package automatically if it is missing. If
that download or package installation is blocked, install or update **App
Installer** from the Microsoft Store instead, then open a new PowerShell
window.

Then open PowerShell in the software repository and run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\windows_setup.ps1
```

The Windows script uses `winget` to install Git, Docker Desktop, Python 3.11,
Node.js, FFmpeg, and `mkcert`. It installs the UI dependencies and Poetry,
installs the Python services, waits for Docker, creates the MQTT keystore, and
starts `scripts/run-all.py`.

Windows setup installs Git for Windows, which includes Git Bash for running the
MQTT keystore script. A new PowerShell window may be needed after installing
tools if they are not immediately available on `PATH`.

Docker Desktop may require a Windows restart, WSL 2, and hardware
virtualization to be enabled. The script attempts to start Docker and waits for
it to become ready; if that fails, complete Docker Desktop's setup and rerun
the script.

## Manual setup guide

Use these steps if you prefer not to use an automated script or need to recover
from a partially completed setup.

### 1. Clone both repositories

```bash
git clone https://github.com/Team-Bath-Hydrobotics/team-bath-rov-software.git
git clone https://github.com/Team-Bath-Hydrobotics/team-bath-rov-secondary-ui.git
cd team-bath-rov-software
```

Keep the repositories as sibling directories because `run-all.py` looks for the
UI at `../team-bath-rov-secondary-ui` by default.

### 2. Install prerequisites

Install Python 3.11+, Poetry, Node.js/npm, FFmpeg, Docker Desktop, `mkcert`,
and Git for Windows. Git for Windows includes Git Bash, which is needed for the
MQTT keystore script.

Verify the tools:

```bash
python3 --version
poetry --version
node --version
npm --version
ffmpeg -version
docker --version
mkcert --version
```

### 3. Install Python dependencies

Use Python 3.11 for each service:

```bash
cd telemetry-processor
poetry env use python3.11
poetry install

cd ../video-processor
poetry env use python3.11
poetry install

cd ../packet-simulator
poetry env use python3.11
poetry install

cd ..
```

The shared `common` package is installed automatically as a path dependency.

### 4. Install the UI

```bash
cd ../team-bath-rov-secondary-ui
npm install
cd ../team-bath-rov-software
```

### 5. Configure MQTT

Start Docker Desktop, then create the local password file:

```bash
cd mqtt
cp PASSWORD.example PASSWORD
```

Edit `PASSWORD` and set a non-empty value:

```text
HIVEMQ_KEYSTORE_PASSWORD=your-local-password
```

Generate the certificates and keystore:

```bash
./create_keystore.sh
cd ..
```

On Windows, run this command from Git Bash. Do not commit `PASSWORD` or
generated private key material.

### 6. Start the complete stack

```bash
python3 scripts/run-all.py
```

The launcher starts MQTT, the three Python services, and the UI. Logs are
written to `logs/`. Press `Ctrl+C` to shut everything down.

Useful options:

```bash
python3 scripts/run-all.py --help
python3 scripts/run-all.py --verbose
python3 scripts/run-all.py --run telemetry-processor
python3 scripts/run-all.py --exclude packet-simulator
```

### 7. Run services manually

Start MQTT first:

```bash
cd mqtt
docker compose up -d
```

Then run each service in a separate terminal:

```bash
cd telemetry-processor
poetry run python src/telemetry_processor.py --config src/config.json
```

```bash
cd video-processor
poetry run python src/video_processor.py --config processor_config.json
```

```bash
cd packet-simulator
poetry run python src/packet_simulator.py --config src/video_config.json
```

```bash
cd ../team-bath-rov-secondary-ui
npm run dev
```

The UI is available at `http://localhost:5173`. For two lightweight simulated
camera feeds, see the [local video preset](config/local-video/README.md).

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
