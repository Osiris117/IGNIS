# IGNIS v0.9.1 — Intelligence Analyst (UI/UX, modo claro y accesibilidad)

IGNIS is a cross-platform 3D wildfire/thermal-anomaly intelligence prototype built around NASA FIRMS MODIS/VIIRS observations. v0.9 adds the **Intelligence Analyst**: an explainable, bilingual (ES/EN) briefing per persistent event — every sentence bound to the measured figures that back it (citations with metric, value and source) — plus a **light/dark theme switch** and a **language switch** for the whole interface. It builds on v0.8 (drought percentiles from ERA5, vegetation/fuel from MODIS NDVI, smoke/aerosols from MODIS AOD + OMPS, switchable NASA GIBS layers), v0.7 (Fire Evolution Engine: persistent event IDs, lifecycle states, apparent drift, trails, explainable Event Confidence Score), v0.6 Earth Context Engine and the v0.5 DuckDB + Parquet archive.

## v0.9.1 highlights

- **Modo claro arreglado de raíz**: el conmutador ya no depende de `transition:all`
  (que dejaba los colores a medio interpolar en Chromium). Tokens en `:root` +
  `html[data-theme="light"]`, transiciones por propiedad y clase `theme-switching`
  durante el cambio.
- **Token de superficie interna** (`--inset-rgb`): calendario y gestor de archivo
  dejan de pintarse con la sombra (`--shadow-rgb`), que era la causa de las
  superficies oscuras en modo claro.
- **Sistema visual (skill UI/UX · HUD/Sci-Fi FUI)**: 9 iconos SVG en línea
  (sin emojis), foco visible para teclado, `cursor:pointer`, chips que no se
  parten en dos líneas, scrollbars finas, `prefers-reduced-motion`, responsive
  1440/1024/760.
- **Auditoría de contraste automatizada** (Playwright + CDP sobre el iframe del
  preview, con verificación por píxel): **0 fallos AA** en 5 estados × 2
  comprobaciones y 0 errores de JavaScript.
- **Recoloreo vivo al cambiar de tema**: estados de evento, severidad y retícula
  de calor leen la paleta del tema activo (`IGNIS_RERENDER`).
- Docs: [`docs/UI_UX_SYSTEM.md`](docs/UI_UX_SYSTEM.md)

## v0.9 highlights

- **Explainable briefing per event**: headline + sentences, each carrying citations (metric, value, unit, source).
- **Deterministic templates over measured data**: no free-form text generation, no invented figures.
- **Contextual indices 0-100**: dryness, fuel, smoke and a combined environmental context index.
- **Historical anchor**: same-month, same-area comparison from the local DuckDB archive (falls back to live FIRMS MODIS when `FIRMS_MAP_KEY` is set).
- **Bilingual interface (ES / EN)**: header, panels, buttons, select options, toasts, calendar notes, engine evidence and the briefing itself; Spanish decimal separators included.
- **Light / dark theme**: systematic light palette generated from the dark one, with Cesium globe adjustments (no solar lighting, brighter base imagery).
- Docs: [`docs/INTELLIGENCE_ANALYST.md`](docs/INTELLIGENCE_ANALYST.md) · [`docs/ENVIRONMENTAL_INTELLIGENCE.md`](docs/ENVIRONMENTAL_INTELLIGENCE.md)

## v0.8 highlights

- **Per-event environmental context**: drought percentile (30/90/180/365 d vs. up to 10 years of ERA5 at the same point) + ET0/precipitation ratio.
- **Fuel / vegetation**: MODIS Terra NDVI 8-day composite (250 m) read through the official GIBS colormap; classes SPARSE → VERY_HIGH.
- **Smoke**: AOD classes CLEAN → VERY_HEAVY, plus OMPS pyro-cumulonimbus detections.
- **Globe layers**: AEROSOLES, VEGETACIÓN, COLOR REAL and PIRO-CB toggles synced with the timeline (NASA GIBS WMTS, no API key).
- **Graceful degradation**: every layer answers `{"available": false, "reason": ...}` instead of inventing values, and reports `date` vs. `requested_date` when the composite lags behind.
- Docs: [`docs/ENVIRONMENTAL_INTELLIGENCE.md`](docs/ENVIRONMENTAL_INTELLIGENCE.md) · validation in [`VALIDATION.md`](VALIDATION.md).

## v0.7 highlights

- **Persistent event IDs** (`IGN-YYYY-NNNN`) backed by a local registry (`data/events/track_registry.json`).
- **Lifecycle classification** with an explicit intensity rule and configurable threshold.
- **Apparent centroid drift** (bearing + net displacement), clearly labeled as *not* a spread model.
- **Explainable Event Confidence** with per-component weights and printed evidence.
- **Globe rendering**: evolution trails with growing alpha, per-state colors, pulsing markers.
- **REPLAY LIFECYCLE**: cinematic camera replay from first signal to last observation.
- **God's Eye HUD**: local Cesium SkyBox stars, atmosphere, FXAA + bloom, leader line + animated reticle, tracking banner, cursor lat/lon readout.
- **Real offline data**: bulk FIRMS CSVs (no MAP_KEY) can be imported and tracked locally (see `docs/OFFLINE_DEMO.md`).
- New endpoints: `GET /api/evolution/demo`, `GET /api/evolution/archive`.

Docs: `docs/EVOLUTION_ENGINE.md` (methodology + limits), `docs/OFFLINE_DEMO.md` (offline pack + real data).

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
GET  /api/evolution/demo
GET  /api/evolution/archive
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
│  ├─ context_engine.py
│  └─ evolution_engine.py
├─ data/
│  ├─ sample_fires.json
│  └─ archive/
├─ static/
│  ├─ index.html
│  ├─ styles.css
│  └─ app.js
├─ docs/
│  ├─ EVOLUTION_ENGINE.md
│  └─ OFFLINE_DEMO.md
├─ tools/
│  └─ fetch_firms_snapshot.py
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

**The browser UI is now fully offline**: CesiumJS 1.126 is vendored in `static/vendor/cesium/` and the globe uses the Natural Earth II imagery + SkyBox shipped with Cesium (no CDN requests). NASA FIRMS and Open-Meteo/CAMS remain backend-only dependencies; with a local archive imported, IGNIS runs disconnected end-to-end. See `docs/OFFLINE_DEMO.md`.

## Next high-value milestone

v0.8 should add **Environmental Intelligence**: vegetation/fuel context, drought indices, smoke/aerosol layers over the globe, and weather-driven risk context per persistent track. v0.9 should add the **IGNIS Intelligence Analyst**: data-grounded automatic narrative per event, with every sentence tied to the underlying numbers.

See `EARTH_CONTEXT_ENGINE.md`, `HISTORICAL_ENGINE.md`, and `HARMONIZATION.md` for methodology and caveats.
