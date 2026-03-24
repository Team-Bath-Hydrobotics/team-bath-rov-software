# Pilot Operations Guide: Task 2.2 — Iceberg Tracking

> **Competition:** MATE 2026 Explorer — Task 2.2
> **Maximum points:** Varies by number of icebergs tracked and accuracy
> **Time pressure:** Judges provide iceberg data throughout the demo — fast response matters

---

## Scoring Breakdown

| Step | What you do | Points | Judge interaction |
|------|------------|--------|-------------------|
| **1. Receive data** | Judge gives iceberg lat, lon, heading, keel depth | — | Listen carefully, write it all down |
| **2. Enter data** | Input all four values into the Iceberg Threat page | — | — |
| **3. Calculate** | Press "Calculate Threats" | — | — |
| **4. Report surface threats** | Read out Green/Yellow/Red for each platform | Scored per platform | Judge checks against expected answers |
| **5. Report subsea threats** | Read out Green/Yellow/Red for each platform | Scored per platform | Judge checks against expected answers |

The judge may provide **multiple icebergs** over the course of the demo. Each iceberg is a separate calculation — clear the old inputs and enter the new data each time.

---

## The Flow

```
┌────────────────────────────────────────────────────┐
│  Judge gives iceberg data:                          │
│    Latitude, Longitude, Heading, Keel Depth         │
└───────────────────────┬────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────┐
│  Copilot enters data into Iceberg Threat page:     │
│    4 input fields on the left panel                 │
│                                                     │
│  Platform data is PRE-FILLED:                       │
│    Hibernia, Sea Rose, Terra Nova, Hebron           │
│    (coordinates and depths already loaded)           │
└───────────────────────┬────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────┐
│  Press "Calculate Threats"                          │
│                                                     │
│  Output grid updates instantly:                     │
│    Platform | Distance | Surface | Subsea           │
│    Hibernia |  165 nm  |  Green  | Green            │
│    Sea Rose |   19 nm  |  Green  | Yellow           │
│    Terra N. |    8 nm  | Yellow  |  Red             │
│    Hebron   |   11 nm  |  Green  |  Red             │
└───────────────────────┬────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────┐
│  Report to judge:                                   │
│    "For this iceberg, Hibernia surface threat is    │
│     Green, subsea is Green. Sea Rose surface is     │
│     Green, subsea is Yellow..." etc.                │
└────────────────────────────────────────────────────┘
```

---

## What You Know Before Starting

| Given | Value |
|-------|-------|
| **Hibernia** | 43.7504°N, 48.7819°W, depth 78 m |
| **Sea Rose** | 46.7895°N, 48.1417°W, depth 107 m |
| **Terra Nova** | 46.4000°N, 48.4000°W, depth 91 m |
| **Hebron** | 46.5440°N, 48.4980°W, depth 93 m |
| **Judge provides** | Iceberg latitude, longitude, heading, keel depth |

The platform data is **pre-loaded** in the Secondary UI. You should not need to edit it unless the judge provides corrected coordinates.

---

## Competition Procedure

### Step 1: Open the Iceberg Threat Page

Navigate to **Iceberg Threat** in the Secondary UI sidebar. Verify the four platforms are loaded in the input grid with correct names, coordinates, and depths.

### Step 2: Upload the Iceberg Image (if provided)

If the judge gives you a map or image of the iceberg location:

1. Click **"Upload Iceberg Image"**
2. Select the file (JPG, PNG, HEIC supported)
3. The image displays in the left panel for reference

### Step 3: Enter Iceberg Data

When the judge gives you iceberg data, enter it into the four fields:

| Field | What to enter | Example |
|-------|--------------|---------|
| **Iceberg Latitude** | Latitude from the judge | `46.5` |
| **Iceberg Longitude** | Longitude from the judge (negative for West) | `-48.3` |
| **Heading (°)** | Heading in degrees | `180` |
| **Keel Depth (m)** | Depth of the iceberg's keel in metres | `90` |

> **Watch the sign on longitude.** Newfoundland longitudes are negative (West). If the judge says "48.3 West", enter `-48.3`.

### Step 4: Calculate

Press **"Calculate Threats"**. The output grid updates instantly with:

- **Distance (nm)** — how far the iceberg is from each platform
- **Surface Threat** — Green, Yellow, or Red chip
- **Subsea Threat** — Green, Yellow, or Red chip

### Step 5: Report to the Judge

Read out the results for each platform. Be clear and systematic:

> "For this iceberg:
>
> - Hibernia — surface threat Green, subsea threat Green, distance 165 nautical miles.
> - Sea Rose — surface threat Green, subsea threat Yellow, distance 19 nautical miles.
> - Terra Nova — surface threat Yellow, subsea threat Red, distance 8 nautical miles.
> - Hebron — surface threat Green, subsea threat Red, distance 11 nautical miles."

### Step 6: Next Iceberg

If the judge provides another iceberg, clear the input fields and repeat from Step 3.

---

## Understanding the Threat Levels

### Surface Threat (will the iceberg hit the platform?)

| Colour | Meaning | Distance |
|--------|---------|----------|
| **Green** | Safe | > 10 nm, or iceberg grounds before arrival |
| **Yellow** | Caution | 5–10 nm |
| **Red** | Critical | < 5 nm |

**Key detail:** If the iceberg's keel is deep enough (≥ 110% of the water depth at the platform), it runs aground on the seabed and stops. Surface threat becomes Green even if the iceberg is very close.

### Subsea Threat (will the keel damage seabed infrastructure?)

Only applies within 25 nm. Beyond 25 nm, subsea threat is always Green.

| Colour | Meaning | Keel depth vs ocean depth |
|--------|---------|---------------------------|
| **Green** | Grounded or passing above | keel ≥ 110% depth (grounded) or keel < 70% depth (passing above) |
| **Yellow** | Approaching seabed | 70–90% of depth |
| **Red** | Keel at seabed level | 90–110% of depth |

---

## Recommended Strategy

| Time | Pilot | Copilot |
|------|-------|---------|
| Before demo | — | Verify platform data is loaded, test with sample values |
| Judge gives data | — | Write down all four values immediately |
| +10 sec | Continue other tasks | Enter values, press Calculate |
| +20 sec | — | Report results to judge clearly |
| Next iceberg | — | Clear inputs, repeat |

This task is **fast** — each iceberg should take under 30 seconds from data entry to reporting. The copilot handles everything; the pilot stays focused on driving.

---

## Troubleshooting During Competition

| Problem | Quick fix |
|---------|-----------|
| All threats showing "Unknown" | Press the **Calculate Threats** button |
| Distance is 0 for all platforms | Check iceberg lat/lon are entered (not still zero) |
| Unexpected Green for a close iceberg | Keel depth may be triggering the grounding override — verify the keel depth value |
| Longitude sign wrong | Newfoundland is West — enter negative longitude (e.g. `-48.3`) |
| Platform data looks wrong | The input grid is editable — correct any values, then recalculate |
| Backend not running | The frontend calculator works offline — no backend needed |

---

## Pre-Competition Checklist

- [ ] Secondary UI running (`npm run dev` in `team-bath-rov-secondary-ui`)
- [ ] Iceberg Threat page loads with four platforms pre-filled
- [ ] Test calculation: enter sample iceberg data, verify coloured chips appear
- [ ] Copilot knows which fields to enter and the sign convention for longitude
- [ ] Practice reading out results clearly: "Platform X — surface Green, subsea Yellow"
- [ ] **Roles assigned:**
    - **Pilot:** Continues driving the ROV — this task is copilot-only
    - **Copilot:** Enters iceberg data, presses Calculate, reports to judge
