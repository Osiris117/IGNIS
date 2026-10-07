# IGNIS v0.5 — Historical Data Engine

> v0.6 retains this historical engine unchanged and layers candidate event/context analysis on top. See `EARTH_CONTEXT_ENGINE.md`.


## Purpose

v0.5 adds a local analytical layer for historical NASA FIRMS active-fire/hotspot observations. The goal is to let the competition demo explore complete imported months without making hundreds of live API calls.

The engine is deliberately split into two data paths:

1. **NASA live / short historical API path** — near-real-time or 1–5 day FIRMS API requests.
2. **Local archive path** — user-imported FIRMS archive CSV/TXT/ZIP files stored in DuckDB and summarized to Parquet.

This distinction matters: a 3-day API sample is useful for a fast seasonal comparison, but it is not a complete monthly total. The local archive calendar is the path intended for complete-month analysis.

## Storage

Canonical store:

```text
data/archive/ignis.duckdb
```

Portable analytical snapshot:

```text
data/archive/parquet/monthly_grid.parquet
```

Uploaded source files are kept in:

```text
data/archive/inbox/
```

This preserves provenance and makes it possible to reproduce an import.

## Canonical observation schema

Every imported sensor is mapped to a common structure:

- source
- sensor family (MODIS / VIIRS)
- latitude / longitude
- acquisition date / time
- FRP
- normalized confidence (0–100)
- brightness (when available)
- satellite
- instrument
- day/night flag
- origin file
- ingestion timestamp

The importer accepts the standard latitude, longitude and acquisition-date fields used by FIRMS CSV exports. Sensor-specific brightness columns are mapped when available.

## Deduplication

IGNIS computes a deterministic event key from:

```text
source + lat + lon + date + time + FRP + satellite
```

The key is a primary key in DuckDB. Re-importing the same file therefore does not duplicate observations. In addition, SHA-256 is stored for each imported file so the UI can identify an exact repeated upload.

## Monthly calendar

The **LOCAL ARCHIVE** calendar queries the imported observations directly and groups by calendar month for the selected rectangular area of interest.

Each cell reports real imported values for:

- detection count
- total FRP
- mean FRP
- max FRP
- active days

The displayed `0–100` activity score is still an IGNIS visualization index, not an official NASA severity scale. It is normalized within the selected calendar period/AOI using:

```text
68% detection density + 32% total FRP
```

The normalization makes the matrix visually interpretable while the raw values remain available in the payload.

## Full-month anomaly

When a local archive frame is active, **COMPARE WITH PRIOR YEARS** switches to a full-month baseline instead of the old 1-day API baseline.

The default anchor is `MODIS_SP`, comparing the selected month against the same month in up to 10 prior years. This avoids treating MODIS and VIIRS detection density as directly interchangeable over the whole record.

The response includes:

- current detections
- historical mean
- historical standard deviation
- percent difference
- z-score
- anomaly label

## Harmonized month playback

Selecting a LOCAL ARCHIVE calendar cell loads the whole calendar month into the timeline (up to 31 daily frames). Each day can still be displayed as:

- individual hotspots
- harmonized common-grid cells

For UI performance, daily hotspot payloads are deterministically capped. The complete monthly calendar statistic is computed separately from the complete imported store and is not derived from the display sample.

## Import methods

### UI

Open **LOCAL ARCHIVE MANAGER**, select the sensor/source, choose a `.csv`, `.txt` or `.zip` FIRMS archive file and press **IMPORT INTO IGNIS**.

### CLI

For very large files:

```bash
python import_firms_archive.py /path/to/archive.csv --source MODIS_SP
```

or:

```bash
python import_firms_archive.py archive1.csv archive2.csv --source VIIRS_NOAA20_SP
```

## Archive-source labels

v0.5 supports:

- `MODIS_SP`
- `VIIRS_SNPP_SP`
- `VIIRS_NOAA20_SP`
- `VIIRS_NOAA21_ARCHIVE`

The source must be selected explicitly during import so IGNIS never guesses which satellite family an arbitrary file represents.

## Scientific caveats

- Active-fire detections are not the same thing as burned-area products.
- Detection counts are affected by sensor resolution, orbit, cloud/smoke obscuration and data availability.
- Cross-sensor raw counts must not be interpreted as one perfectly homogeneous long-term measurement.
- The IGNIS activity score is a hackathon analytical/visual index, not an operational emergency metric.
- For long-term anomalies, use a stable sensor family/source such as MODIS Standard Processing when coverage allows.
