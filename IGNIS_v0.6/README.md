# IGNIS v0.6 — Earth Fire Intelligence

IGNIS is a cross-platform 3D wildfire/thermal-anomaly intelligence prototype built around NASA FIRMS MODIS/VIIRS observations. v0.6 adds the **Earth Context Engine**: candidate fire-event clustering, environmental context, recent aerosol/smoke indicators, and exportable intelligence snapshots while retaining the v0.5 DuckDB + Parquet historical archive.

## Run

### Windows
Double-click `INICIAR_IGNIS.bat`.

### macOS
Double-click `INICIAR_IGNIS.command`. If macOS blocks the first launch, right-click it and choose **Open**.

### Linux
```bash
chmod +x INICIAR_IGNIS.sh
./INICIAR_IGNIS.sh
```

### Universal
```bash
python start_ignis.py
```

### Docker
```bash
docker compose up --build
```

The launcher creates/reuses `.venv`, installs dependencies only when required, finds an available port, and opens the local application.

## v0.6 highlights

- New **FIRE EVENTS** globe mode.
- Spatiotemporal clustering of nearby FIRMS thermal anomalies into explicitly labeled **candidate events**.
- Event centroid, duration, detection count, total/max FRP, confidence, sensor families, cluster spread and priority score.
- Translucent event-spread rings on the 3D globe. They are **not fire perimeters**.
- Ranked candidate-event list in the command center.
- Environmental context for real events using Open-Meteo historical/recent weather data.
- ERA5-Land historical temperature, humidity, precipitation, wind, soil moisture and vapor-pressure-deficit context.
- Recent PM2.5 / aerosol optical depth context from Open-Meteo Air Quality / Copernicus CAMS.
- Transparent **IGNIS Dryness Context Score**; explicitly not an operational FWI/NFDRS product.
- Synthetic context remains synthetic in Demo mode, preventing accidental mixing of real weather with fake events.
- JSON **EXPORT INTELLIGENCE SNAPSHOT** button.
- Configurable candidate-event thresholds in `.env`.
- Persistent safety/certainty wording in the UI.

## Existing capabilities retained

- Interactive CesiumJS 3D Earth.
- NASA FIRMS live/historical API queries.
- MODIS + VIIRS common-grid harmonization.
- Sensor-family agreement signal.
- Burning Activity Calendar.
- Demo, NASA sampled-calendar and Local Archive calendar modes.
- DuckDB local historical archive.
- Parquet analytical snapshot.
- Browser/CLI FIRMS CSV/TXT/ZIP import.
- Whole-month historical playback.
- MODIS-anchored historical anomaly comparisons.
- Windows / macOS / Linux / Docker launch paths.

## Configure NASA FIRMS

Copy `.env.example` to `.env`, obtain a free FIRMS MAP_KEY, and set:

```env
FIRMS_MAP_KEY=YOUR_KEY
FIRMS_SOURCE=VIIRS_NOAA21_NRT
```

Optional event-clustering controls:

```env
IGNIS_EVENT_RADIUS_KM=28
IGNIS_EVENT_WINDOW_HOURS=36
IGNIS_EVENT_MIN_POINTS=2
```

The defaults are prototype engineering choices, not official wildfire-identification thresholds.

## Historical archive

Open **LOCAL ARCHIVE MANAGER**, select the source represented by the file, and import a NASA FIRMS `.csv`, `.txt` or `.zip`. Large files can be imported with:

```bash
python import_firms_archive.py fire_archive.csv --source MODIS_SP
```

Local data is stored in:

```text
data/archive/ignis.duckdb
data/archive/parquet/monthly_grid.parquet
data/archive/inbox/
```

## Intelligence workflow

```text
NASA FIRMS / LOCAL ARCHIVE
           │
           ▼
 normalized hotspot observations
           │
     ┌─────┴──────────┐
     ▼                ▼
common grid      candidate events
MODIS + VIIRS    space + time links
     │                │
     └─────┬──────────┘
           ▼
     3D Earth + timeline
           │
           ▼
 event environmental context
 weather · soil moisture · aerosol
           │
           ▼
 historical anomaly + export
```

## Critical interpretation rule

A NASA FIRMS point is a **satellite-derived thermal anomaly**, not automatically a confirmed wildfire. Cloud cover can also hide active-fire detections. IGNIS therefore calls its clusters **candidate fire events** and never treats their radius/bounding box as an official incident perimeter.

Do not use IGNIS for evacuation, preservation of life/property, emergency response, or operational fire-management decisions.

## Environment/context data

Real event context currently uses:

- Open-Meteo Historical Weather / ERA5-Land for older weather and land-surface context.
- Open-Meteo forecast-compatible feeds for very recent weather.
- Open-Meteo Air Quality / Copernicus CAMS for recent PM2.5 and aerosol optical depth.

These are contextual layers. PM2.5/AOD co-location does not prove that a selected event caused the aerosol signal.

## API

```text
GET  /api/health
GET  /api/config
GET  /api/fires/demo
GET  /api/fires/query
GET  /api/fires/current
GET  /api/harmonize/demo
GET  /api/harmonize/demo/date
GET  /api/harmonize
GET  /api/events/demo
GET  /api/context/environment
GET  /api/analytics/baseline
GET  /api/analytics/calendar/demo
GET  /api/analytics/calendar/sample
GET  /api/archive/status
POST /api/archive/import
GET  /api/archive/calendar
GET  /api/archive/harmonize
GET  /api/archive/anomaly
```

## Structure

```text
IGNIS_v0.6/
├─ backend/
│  ├─ app.py
│  ├─ archive_store.py
│  └─ context_engine.py
├─ data/
│  ├─ sample_fires.json
│  └─ archive/
├─ static/
│  ├─ index.html
│  ├─ styles.css
│  └─ app.js
├─ EARTH_CONTEXT_ENGINE.md
├─ HISTORICAL_ENGINE.md
├─ HARMONIZATION.md
├─ import_firms_archive.py
├─ start_ignis.py
├─ INICIAR_IGNIS.bat
├─ INICIAR_IGNIS.sh
├─ INICIAR_IGNIS.command
├─ Dockerfile
├─ compose.yml
├─ .env.example
├─ requirements.txt
└─ README.md
```

## Connectivity note

The Python service and imported historical analysis can run locally. The current browser shell still obtains CesiumJS from a CDN and therefore is not yet a fully disconnected UI package. A future offline-hardening step should vendor CesiumJS and use the Natural Earth II imagery shipped with CesiumJS.

## Next high-value milestone

v0.7 should add **persistent event identity + event evolution**: track the same candidate event across successive refreshes, visualize growth/decay, estimate movement/spread direction from the observation cloud, and allow a judge/user to replay the event lifecycle from first signal to last observation.

See `EARTH_CONTEXT_ENGINE.md`, `HISTORICAL_ENGINE.md`, and `HARMONIZATION.md` for methodology and caveats.
