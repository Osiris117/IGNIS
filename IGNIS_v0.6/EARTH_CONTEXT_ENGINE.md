# IGNIS v0.6 — Earth Context Engine

## Purpose

v0.6 turns a stream of satellite thermal-anomaly detections into higher-level **candidate fire events** and adds environmental context around those events. The design goal is not to claim that IGNIS has an official wildfire perimeter. Instead, IGNIS preserves the underlying FIRMS observations and builds an explicitly labeled analytical grouping for exploration.

## 1. Candidate Fire Events

### Inputs

Normalized FIRMS observations containing at least:

- latitude / longitude
- acquisition date and time
- FRP
- confidence
- sensor family / source

### Spatiotemporal linking

Two observations may be connected when both conditions are satisfied:

- spatial distance <= `IGNIS_EVENT_RADIUS_KM` (default 28 km)
- acquisition-time separation <= `IGNIS_EVENT_WINDOW_HOURS` (default 36 h)

The implementation uses a geographic grid index plus a disjoint-set/union-find structure. Linked observations can form a multi-day event through temporal chaining. A group must contain at least `IGNIS_EVENT_MIN_POINTS` observations (default 2).

These thresholds are engineering defaults for the prototype, not scientific constants. They are configurable in `.env`.

### Event summary

Each candidate event includes:

- stable event ID
- FRP-weighted centroid
- first / last observation
- duration
- observation count
- total and maximum FRP
- mean confidence
- MODIS / VIIRS families participating
- approximate cluster radius
- bounding box
- visualization priority score

The cluster radius and bounding box describe **observation spread**, not a burned-area or incident perimeter.

## 2. Event priority score

`event_score` is a transparent UI prioritization heuristic. It combines:

- number of linked detections
- cumulative FRP
- mean confidence

It is capped at 100 and maps to moderate / high / critical visual categories. It is not a NASA severity product, emergency classification, or fire-behavior forecast.

## 3. Weather and land-surface context

For a selected real candidate event, IGNIS requests point context at the event centroid.

### Historical context

Open-Meteo Historical Weather API with ERA5-Land is used for older dates. Variables include:

- 2 m temperature
- relative humidity
- precipitation
- 10 m wind speed and direction
- near-surface soil moisture
- vapor pressure deficit

### Recent context

For the most recent days, IGNIS uses the Open-Meteo forecast/historical-forecast-compatible feed because reanalysis datasets have a publication delay.

## 4. Dryness Context Score

IGNIS computes a clearly labeled **Dryness Context Score** from available temperature, humidity, wind, precipitation and soil-moisture fields.

This score exists to provide an interpretable prototype signal. It is explicitly **not**:

- Canadian FWI
- NFDRS
- an official drought index
- an operational fire-danger rating

The UI displays that caveat next to the score.

## 5. Smoke / aerosol context

For recent events, IGNIS requests Open-Meteo Air Quality data backed by Copernicus CAMS and displays:

- PM2.5
- aerosol optical depth (AOD)
- dust where available

These values provide atmospheric context. IGNIS does **not** attribute observed PM2.5 or AOD to a specific candidate fire event.

For older events, smoke context is reported as unavailable rather than invented.

## 6. Demo isolation

The analytical demo uses synthetic candidate events and therefore also uses synthetic environmental context. Real meteorological observations are never silently attached to synthetic fire events.

## 7. Data provenance and safety

NASA FIRMS active-fire products represent satellite-derived active fire / thermal anomalies. A detection can be associated with fire, hot smoke, agriculture or other hot sources, and cloud cover can obscure detections. IGNIS therefore uses the term **candidate event** throughout the event layer.

IGNIS is a hackathon/research prototype. It must not be used for evacuation, emergency response, preservation of life/property, or operational fire-management decisions.

## 8. API additions

```text
GET /api/context/environment?lat=...&lon=...&event_date=YYYY-MM-DD
GET /api/events/demo
```

The existing harmonization endpoints now also return an `events` array:

```text
GET /api/harmonize/demo
GET /api/harmonize/demo/date
GET /api/harmonize
GET /api/archive/harmonize
```

## 9. UI additions

v0.6 adds:

- `FIRE EVENTS` globe mode
- translucent event-spread rings
- ranked event list
- event detail view
- environmental-context panel
- recent aerosol / PM2.5 context
- Dryness Context Score
- JSON intelligence-snapshot export
- persistent FIRMS safety disclaimer

## 10. Known limitations / next work

- Candidate-event clustering should eventually be validated against known incident datasets.
- Event identity is currently recalculated per requested window; a persistent event registry is a future step.
- Event spread is not a fire perimeter.
- Weather context is point-based at the event centroid; future versions should sample the event extent.
- Smoke context is atmospheric co-location only; transport / source attribution requires a dedicated model.
- The Python backend and local archive are cross-platform, but the current web UI still loads CesiumJS from a CDN. A fully disconnected package should vendor CesiumJS and use its bundled Natural Earth II imagery.
