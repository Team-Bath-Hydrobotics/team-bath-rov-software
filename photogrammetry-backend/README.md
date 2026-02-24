# Photogrammetry Backend

FastAPI service for 3D coral reef reconstruction. Part of the Team Bath ROV MATE 2026 project. Takes uploaded images of coral gardens and produces 3D `.glb` models.

## Prerequisites

- Python 3.11+

## Install & Run

```bash
cd photogrammetry-backend
pip install -e .
uvicorn app.main:app --reload --port 8100
```

- API: `http://localhost:8100`
- Interactive docs (Swagger): `http://localhost:8100/docs`

### Configuration

The server is configured via environment variables (defaults shown):

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8100` | Server port |
| `UPLOAD_DIR` | `data/uploads` | Where uploaded images are stored |
| `OUTPUT_DIR` | `data/outputs` | Where generated models are saved |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | Allowed CORS origins |

## API Endpoints

All endpoints are prefixed with `/api`.

| Route | Description |
|---|---|
| `GET /api/health` | Health check |
| `POST /api/upload` | Upload images for a job |
| `POST /api/photogrammetry` | Start photogrammetry processing |
| `GET /api/jobs` | List all jobs |
| `GET /api/jobs/{job_id}` | Get job status |
| `GET /api/jobs/{job_id}/model` | Download the generated `.glb` model |
| `POST /api/scaling` | Set scale reference for a job |
| `POST /api/manual-cad` | Upload a manual CAD model |

## Architecture

The service is consumed by the [`team-bath-rov-secondary-ui`](https://github.com/Team-Bath-Hydrobotics/team-bath-rov-secondary-ui) React app, which proxies `/api` requests to this backend via Vite's dev server.

## Further Reading

See the detailed plan document: [`docs/photogrammetry-backend-plan.md`](docs/photogrammetry-backend-plan.md)
