# IGNIS v0.5 — Harmonization & Temporal Method

> v0.6 keeps this harmonization method and adds candidate event/context analysis. See `EARTH_CONTEXT_ENGINE.md`.


## Why harmonization is necessary

MODIS and VIIRS do not have identical spatial resolution, sampling characteristics or raw hotspot density. IGNIS therefore **does not directly add raw MODIS and VIIRS detection counts and call them equivalent**.

## Spatial fusion prototype

For each selected day and area of interest:

1. Fetch Standard Processing hotspot observations from the selected FIRMS sources.
2. Convert every source to the same internal schema.
3. Place detections on a common geographic grid (default `0.10°`, approximately 11 km north-south).
4. For each source independently, calculate a spatial activity score from:
   - detection density in the cell (25%)
   - mean Fire Radiative Power / FRP (55%)
   - mean confidence (20%)
5. Normalize density and FRP against the 95th percentile **of that same source in the selected area/day**.
6. Average source scores inside each common grid cell.
7. Add a small corroboration bonus when both MODIS and VIIRS sensor families detect activity in the same cell.

This produces the IGNIS `activity_score` (0–100) plus `sensor_agreement`.

## Historical anomaly

Long-term anomaly uses `MODIS_SP` as a historical anchor because MODIS provides the longer record. For a target calendar date, IGNIS compares MODIS detections against the same calendar window in prior years and returns historical mean, standard deviation, percent change, z-score and a qualitative anomaly label.

VIIRS remains part of the modern harmonized map without pretending that VIIRS observations existed across the full MODIS era.

## Burning Activity Calendar

v0.4 introduced two calendar modes; v0.5 adds a third local-archive mode:

### FULL DEMO 2003–now
A deterministic synthetic calendar used only to demonstrate the complete product experience. It is explicitly labelled as non-NASA data.

### NASA SAMPLE
A real FIRMS mode anchored to `MODIS_SP`. FIRMS Area API accepts only 1–5 day query windows, so IGNIS samples one **equal-length window at the same point of every month**. The default is a 3-day window beginning on day 10.

For each sample IGNIS calculates:
- detections
- mean FRP
- a request-relative 0–100 activity score (65% detection density, 35% mean FRP)

This is useful for standardized seasonal comparison but **is not a complete monthly total**.

## Why the sampled API calendar does not fake monthly totals

A 3-day FIRMS query cannot scientifically represent all fire detections in a month. The application therefore says `NASA SAMPLE` rather than `MONTHLY TOTAL`. A full historical calendar requires archive ingestion or another complete-month data pipeline.

## Suomi-NPP transition

Suomi-NPP remains selectable for legacy historical analysis, but IGNIS v0.5 defaults to MODIS + NOAA-20 for Standard Processing harmonization. The application architecture is ready to prioritize NOAA-20/NOAA-21 going forward.

## What the scores are — and are not

All IGNIS scores are transparent **hackathon analytical indices**. They are not official NASA wildfire-severity classifications and should not be used for operational emergency decisions without scientific validation.

## v0.5 scientific/data upgrade

The next serious analytical upgrade is to ingest historical archives into Parquet/DuckDB, calculate complete monthly statistics, deduplicate fire events across adjacent satellite detections/days, stratify baselines by biome/season and validate weighting against challenge references and NASA literature.
