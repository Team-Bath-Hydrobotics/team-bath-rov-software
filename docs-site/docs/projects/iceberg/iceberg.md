# Iceberg Threat Calculator

## What is this?

This is a FastAPI microservice for **MATE 2026 Task 2.2** (Iceberg Tracking) that calculates how dangerous an iceberg is to four offshore oil platforms off the coast of Newfoundland. The operator inputs the iceberg's position and keel depth, and the calculator outputs a colour-coded threat level (Green, Yellow, Red) for each platform — both for the **surface platform** itself and its **subsea assets** (pipelines, wellheads).

No machine learning, no external data. Just geographic math and threshold comparisons, designed to give judges instant answers during the demo.

### Competition Context

Judges provide iceberg data (latitude, longitude, heading, keel depth). The team must report threat levels for four real offshore oil platforms: **Hibernia**, **Sea Rose**, **Terra Nova**, and **Hebron**. Each platform needs two assessments:

1. **Surface threat** — will the iceberg collide with the platform?
2. **Subsea threat** — will the iceberg's keel damage seabed infrastructure?

---

## Architecture Overview

The calculator runs in two places — **client-side** in the Secondary UI for instant feedback, and as a **backend service** for API access.

```
┌───────────────────────┐
│     Secondary UI       │
│     (React, :5173)     │
│                        │
│  ┌──────────────────┐  │     ┌─────────────────────────────────┐
│  │ Iceberg Threat   │  │     │   iceberg-backend (:8200)       │
│  │ Page             │  │     │                                 │
│  │                  │  │     │  FastAPI Server (uvicorn)       │
│  │  Iceberg inputs: │  │     │    └── POST /api/mission/       │
│  │   lat, lon,      │──────>│        iceberg/calculate_threat  │
│  │   heading, keel  │  │     │                                 │
│  │                  │  │     │  Calculator Service              │
│  │  Client-side     │  │     │    ├── Haversine distance (nm)  │
│  │  calculator      │  │     │    ├── Surface threat logic     │
│  │  (same logic)    │  │     │    └── Subsea threat logic      │
│  └──────────────────┘  │     │                                 │
│                        │     │  Hardcoded platform data:       │
│  Output:               │     │    Hibernia, Sea Rose,          │
│   Platform grid with   │     │    Terra Nova, Hebron           │
│   Green/Yellow/Red     │     └─────────────────────────────────┘
│   threat chips         │
└───────────────────────┘
```

The frontend has its own TypeScript implementation of the same algorithm (`src/utils/icebergCalculator.ts`), so it works **without the backend running**. The backend exists for API consumers and as the authoritative calculation source.

---

## Quick Start

### Prerequisites
- Python 3.11+
- pip or Poetry

### 1. Install dependencies

```bash
cd iceberg-backend
pip install -e .
```

### 2. Start the server

```bash
uvicorn app.main:app --port 8200
```

### 3. Verify it's running

```bash
curl http://localhost:8200/api/health
# → {"status":"ok","service":"iceberg-backend"}
```

### 4. Test a calculation

```bash
curl -X POST http://localhost:8200/api/mission/iceberg/calculate_threat \
  -H "Content-Type: application/json" \
  -d '{"iceberg_lat": 46.5, "iceberg_lon": -48.3, "iceberg_heading": 180, "keel_depth": 90}'
```

---

## The Algorithm

### Step 1: Distance (Haversine Formula)

The [Haversine formula](https://en.wikipedia.org/wiki/Haversine_formula) calculates the great-circle distance between two points on Earth. We use Earth's radius in nautical miles (3440.065 nm) so the output is directly in **nautical miles** — the unit required by the MATE spec.

```
haversine(iceberg_lat, iceberg_lon, platform_lat, platform_lon) → distance in nm
```

This runs once per platform, giving four distances.

> **Note:** The MATE manual states "1 minute of latitude = 1 nautical mile", which is the definition of a nautical mile. The Haversine formula naturally respects this.

### Step 2: Surface Threat Logic

How likely is the iceberg to physically hit the platform?

| Condition | Threat | Meaning |
|-----------|--------|---------|
| Distance > 10 nm | **Green** | Safe — far away |
| 5 ≤ Distance ≤ 10 nm | **Yellow** | Caution — approaching |
| Distance < 5 nm | **Red** | Critical — imminent collision |

**Grounding Override:** If `keel_depth ≥ 1.1 × platform_depth`, the iceberg runs aground on the seabed before reaching the platform. Surface threat becomes **Green** regardless of distance.

Example: Hibernia sits in 78 m of water. An iceberg with keel depth ≥ 85.8 m (78 × 1.1) would scrape the bottom and stop.

### Step 3: Subsea Threat Logic

How likely is the iceberg's keel to damage seabed infrastructure (pipelines, wellheads)?

Only applies if distance ≤ 25 nm. Beyond 25 nm, subsea threat is always **Green**.

| Keel Depth vs Platform Depth | Threat | Reasoning |
|------------------------------|--------|-----------|
| keel ≥ 110% of depth | **Green** | Iceberg grounds — stops moving before reaching assets |
| 90% ≤ keel < 110% of depth | **Red** | Keel is right at seabed level — direct contact |
| 70% ≤ keel < 90% of depth | **Yellow** | Keel approaching seabed, some risk |
| keel < 70% of depth | **Green** | Keel passes well above seabed — safe |

The most dangerous scenario is when the keel depth is *almost exactly* the ocean depth — it drags along the bottom where infrastructure sits. Too deep and it grounds to a halt (safe). Too shallow and it sails right over (also safe).

---

## Platform Constants

These are hardcoded from the MATE 2026 competition manual:

| Platform | Latitude | Longitude | Depth (m) |
|----------|----------|-----------|-----------|
| **Hibernia** | 43.7504 | -48.7819 | 78 |
| **Sea Rose** | 46.7895 | -48.1417 | 107 |
| **Terra Nova** | 46.4000 | -48.4000 | 91 |
| **Hebron** | 46.5440 | -48.4980 | 93 |

All four are real oil platforms in the Jeanne d'Arc Basin off Newfoundland, Canada.

---

## API Endpoint

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Health check |
| `POST` | `/api/mission/iceberg/calculate_threat` | Calculate threat levels for all platforms |

### Request

```json
{
  "iceberg_lat": 46.5000,
  "iceberg_lon": -48.3000,
  "iceberg_heading": 180.0,
  "keel_depth": 90.0
}
```

| Field | Type | Description |
|-------|------|-------------|
| `iceberg_lat` | float | Latitude of the iceberg |
| `iceberg_lon` | float | Longitude of the iceberg |
| `iceberg_heading` | float | Heading of the iceberg in degrees (data completeness — not used in threat calculation) |
| `keel_depth` | float | Depth of the iceberg's keel in metres |

### Response

```json
[
  {
    "platform_name": "Hibernia",
    "distance_nm": 165.2,
    "surface_threat": "Green",
    "subsea_threat": "Green"
  },
  {
    "platform_name": "Sea Rose",
    "distance_nm": 19.42,
    "surface_threat": "Green",
    "subsea_threat": "Yellow"
  },
  {
    "platform_name": "Terra Nova",
    "distance_nm": 8.12,
    "surface_threat": "Yellow",
    "subsea_threat": "Red"
  },
  {
    "platform_name": "Hebron",
    "distance_nm": 11.3,
    "surface_threat": "Green",
    "subsea_threat": "Red"
  }
]
```

Threat values are strictly `"Green"`, `"Yellow"`, or `"Red"` — the frontend uses these to render colour-coded chips.

---

## Project Structure

```
iceberg-backend/
├── app/
│   ├── main.py                # FastAPI app, CORS, router registration
│   ├── config.py              # Settings (port 8200, CORS origins)
│   ├── models/
│   │   └── iceberg.py         # IcebergInput, PlatformThreatResult (Pydantic)
│   ├── routers/
│   │   ├── health.py          # GET /api/health
│   │   └── iceberg.py         # POST /api/mission/iceberg/calculate_threat
│   └── services/
│       └── calculator.py      # Haversine + threat logic + platform constants
└── pyproject.toml             # Dependencies (fastapi, pydantic-settings, uvicorn)
```

Follows the same layout as [photogrammetry-backend](../photogrammetry/photogrammetry.md).

---

## Frontend Integration

The Secondary UI (`team-bath-rov-secondary-ui`) has a matching client-side implementation at `src/utils/icebergCalculator.ts`. This means the **Calculate Threats** button works offline without the backend.

The Iceberg Threat page (`/iceberg-threat`) provides:

- **Input grid** — editable platform data (pre-filled with the four platforms)
- **Iceberg inputs** — latitude, longitude, heading, keel depth
- **Output grid** — distance (nm), surface threat, subsea threat with colour-coded chips
- **Image upload** — for the iceberg tracking map provided by judges

---

## Troubleshooting

### Port 8200 already in use

```bash
lsof -i :8200
# Kill the process, or change the port:
PORT=8201 uvicorn app.main:app --port 8201
```

### CORS errors from the frontend

The backend allows `localhost:5173` and `localhost:3000` by default. If the frontend runs on a different port, update `CORS_ORIGINS` in `app/config.py` or set the `CORS_ORIGINS` environment variable.

### Threat levels all showing "Unknown"

Press the **Calculate Threats** button on the Iceberg Threat page. The output grid only updates when you explicitly run the calculation. Ensure iceberg latitude and longitude are non-zero.
