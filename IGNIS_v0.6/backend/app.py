from __future__ import annotations

import asyncio
import csv
import io
import json
import math
import os
import random
import statistics
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.archive_store import ARCHIVE_SOURCES, INBOX_DIR, archive_store
from backend.context_engine import build_environment_context, cluster_fire_events
from backend.analyst_engine import build_briefing
from backend.environment_engine import LAYERS as ENV_LAYERS, build_environment_intelligence
from backend.evolution_engine import track_evolution

ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "static"
DATA_DIR = ROOT / "data"
load_dotenv(ROOT / ".env")

APP_VERSION = "0.9.0"
app = FastAPI(title="IGNIS — Earth Fire Intelligence", version=APP_VERSION)

# El preview del workspace (y cualquier iframe con sandbox="allow-scripts") expone
# el documento con ORIGEN OPACO ("null"): toda petición —incluido el propio
# /static— se vuelve cross-origin. Sin estos encabezados Cesium no puede cargar
# basemap, SkyBox, workers ni /api/*. IGNIS es una herramienta local sin cookies
# ni credenciales, así que permitir cualquier origen no expone nada.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex=".*",
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

SOURCES = {
    "VIIRS_NOAA21_NRT": "VIIRS · NOAA-21 NRT",
    "VIIRS_NOAA20_NRT": "VIIRS · NOAA-20 NRT",
    "MODIS_NRT": "MODIS · NRT",
    "MODIS_SP": "MODIS · Standard Processing",
    "VIIRS_NOAA20_SP": "VIIRS · NOAA-20 SP",
    "VIIRS_SNPP_NRT": "VIIRS · Suomi NPP NRT",
    "VIIRS_SNPP_SP": "VIIRS · Suomi NPP SP",
}
ALLOWED_SOURCES = set(SOURCES)
DEFAULT_HARMONIZATION_SOURCES = ("MODIS_SP", "VIIRS_NOAA20_SP")

_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_CACHE_TTL_SECONDS = int(os.getenv("IGNIS_CACHE_TTL", "90"))
_CACHE_LOCK = asyncio.Lock()
EVENT_RADIUS_KM = float(os.getenv("IGNIS_EVENT_RADIUS_KM", "28"))
EVENT_WINDOW_HOURS = float(os.getenv("IGNIS_EVENT_WINDOW_HOURS", "36"))
EVENT_MIN_POINTS = int(os.getenv("IGNIS_EVENT_MIN_POINTS", "2"))


def candidate_events(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return cluster_fire_events(
        rows,
        spatial_km=EVENT_RADIUS_KM,
        temporal_hours=EVENT_WINDOW_HOURS,
        min_points=EVENT_MIN_POINTS,
    )


def _number(row: dict[str, str], *keys: str) -> float | None:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            try:
                return float(value)
            except ValueError:
                continue
    return None


def sensor_family(source: str, instrument: str = "") -> str:
    text = f"{source} {instrument}".upper()
    if "MODIS" in text:
        return "MODIS"
    if "VIIRS" in text:
        return "VIIRS"
    return "OTHER"


def normalize_confidence(raw: str) -> int:
    value = (raw or "").strip()
    low = value.lower()
    if low in {"l", "low"}:
        return 30
    if low in {"n", "nominal", "medium"}:
        return 65
    if low in {"h", "high"}:
        return 95
    try:
        return max(0, min(100, int(float(value)))) if value else 0
    except ValueError:
        return 0


def normalize_row(row: dict[str, str], source: str) -> dict[str, Any] | None:
    lat = _number(row, "latitude", "lat")
    lon = _number(row, "longitude", "lon")
    if lat is None or lon is None:
        return None

    frp = _number(row, "frp") or 0.0
    brightness = _number(row, "bright_ti4", "brightness")
    confidence_raw = (row.get("confidence") or "").strip()
    confidence = normalize_confidence(confidence_raw)

    # Visualization score only. Not an official NASA fire-severity product.
    severity_score = min(100.0, max(0.0, 0.60 * min(frp / 120.0, 1.0) * 100 + 0.40 * confidence))
    if severity_score >= 72:
        severity = "critical"
    elif severity_score >= 45:
        severity = "high"
    else:
        severity = "moderate"

    instrument = row.get("instrument", "")
    return {
        "lat": round(lat, 6),
        "lon": round(lon, 6),
        "frp": round(frp, 2),
        "brightness": brightness,
        "confidence": confidence,
        "confidence_raw": confidence_raw,
        "date": row.get("acq_date", ""),
        "time": str(row.get("acq_time", "")).zfill(4),
        "satellite": row.get("satellite", ""),
        "instrument": instrument,
        "daynight": row.get("daynight", ""),
        "source": source,
        "family": sensor_family(source, instrument),
        "severity": severity,
        "severity_score": round(severity_score, 1),
    }


def _safe_area(area: str) -> str:
    if area == "world":
        return area
    parts = area.split(",")
    if len(parts) != 4:
        raise HTTPException(400, "area must be 'world' or west,south,east,north")
    try:
        west, south, east, north = map(float, parts)
    except ValueError as exc:
        raise HTTPException(400, "Invalid coordinates") from exc
    if not (-180 <= west <= 180 and -180 <= east <= 180 and -90 <= south <= 90 and -90 <= north <= 90):
        raise HTTPException(400, "Coordinates outside valid range")
    if south >= north:
        raise HTTPException(400, "south must be less than north")
    if east <= west:
        raise HTTPException(400, "viewport cannot cross the date line in v0.6")
    return f"{west:g},{south:g},{east:g},{north:g}"


def _safe_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(400, "date must use YYYY-MM-DD") from exc
    if parsed > date.today():
        raise HTTPException(400, "date cannot be in the future")
    return parsed.isoformat()


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 1.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return max(ordered[0], 1.0)
    idx = (len(ordered) - 1) * q
    lo, hi = math.floor(idx), math.ceil(idx)
    if lo == hi:
        return max(ordered[lo], 1.0)
    value = ordered[lo] * (hi - idx) + ordered[hi] * (idx - lo)
    return max(value, 1.0)


def deterministic_sample(items: list[dict[str, Any]], max_points: int) -> list[dict[str, Any]]:
    if len(items) <= max_points:
        return items
    step = len(items) / max_points
    return [items[math.floor(i * step)] for i in range(max_points)]


def _grid_key(lat: float, lon: float, grid_deg: float) -> tuple[int, int]:
    return (math.floor(lat / grid_deg), math.floor(lon / grid_deg))


def _level(score: float) -> str:
    if score >= 75:
        return "extreme"
    if score >= 50:
        return "high"
    if score >= 25:
        return "moderate"
    return "low"


def harmonize_day(rows: list[dict[str, Any]], grid_deg: float) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Fuse sensors onto a common grid using within-sensor normalization.

    This intentionally avoids treating MODIS and VIIRS raw detection counts as directly
    equivalent. Each source is normalized against its own spatial distribution first,
    then source scores are averaged inside the common grid.
    """
    if not rows:
        return [], {
            "detections": 0,
            "cells": 0,
            "activity_mean": 0.0,
            "activity_max": 0.0,
            "families": [],
            "agreement_cells": 0,
        }

    grouped: dict[tuple[int, int], dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for item in rows:
        grouped[_grid_key(item["lat"], item["lon"], grid_deg)][item["source"]].append(item)

    source_stats: dict[str, dict[str, float]] = {}
    all_sources = sorted({item["source"] for item in rows})
    for source in all_sources:
        counts: list[float] = []
        mean_frps: list[float] = []
        for bucket in grouped.values():
            src_rows = bucket.get(source, [])
            if src_rows:
                counts.append(float(len(src_rows)))
                mean_frps.append(sum(x["frp"] for x in src_rows) / len(src_rows))
        source_stats[source] = {
            "count_p95": _percentile(counts, 0.95),
            "frp_p95": _percentile(mean_frps, 0.95),
        }

    families_available = sorted({item["family"] for item in rows if item["family"] != "OTHER"})
    cells: list[dict[str, Any]] = []
    agreement_cells = 0

    for (gy, gx), bucket in grouped.items():
        per_source: dict[str, Any] = {}
        scores: list[float] = []
        family_set: set[str] = set()
        total_detections = 0
        total_frp = 0.0
        confidence_values: list[float] = []

        for source, src_rows in bucket.items():
            count = len(src_rows)
            mean_frp = sum(x["frp"] for x in src_rows) / count
            max_frp = max(x["frp"] for x in src_rows)
            mean_conf = sum(x["confidence"] for x in src_rows) / count
            norms = source_stats[source]
            count_norm = min(1.0, count / norms["count_p95"])
            frp_norm = min(1.0, mean_frp / norms["frp_p95"])
            confidence_norm = mean_conf / 100.0
            source_score = 100.0 * (0.25 * count_norm + 0.55 * frp_norm + 0.20 * confidence_norm)
            scores.append(source_score)
            family_set.update(x["family"] for x in src_rows if x["family"] != "OTHER")
            total_detections += count
            total_frp += sum(x["frp"] for x in src_rows)
            confidence_values.extend(x["confidence"] for x in src_rows)
            per_source[source] = {
                "family": src_rows[0]["family"],
                "detections": count,
                "mean_frp": round(mean_frp, 2),
                "max_frp": round(max_frp, 2),
                "mean_confidence": round(mean_conf, 1),
                "normalized_score": round(source_score, 1),
            }

        # Bonus only reflects corroboration between sensor families; it is small so a
        # single-family cell can still score highly when activity is strong.
        agreement = len(family_set) / max(1, len(families_available))
        if len(family_set) >= 2:
            agreement_cells += 1
        base_score = sum(scores) / len(scores)
        activity_score = min(100.0, base_score + (8.0 if len(family_set) >= 2 else 0.0))

        cells.append({
            "lat": round((gy + 0.5) * grid_deg, 5),
            "lon": round((gx + 0.5) * grid_deg, 5),
            "grid_deg": grid_deg,
            "detections": total_detections,
            "mean_frp": round(total_frp / total_detections, 2),
            "mean_confidence": round(sum(confidence_values) / len(confidence_values), 1),
            "activity_score": round(activity_score, 1),
            "activity_level": _level(activity_score),
            "sensor_agreement": round(agreement, 2),
            "families": sorted(family_set),
            "sources": per_source,
        })

    cells.sort(key=lambda item: item["activity_score"], reverse=True)
    scores = [x["activity_score"] for x in cells]
    return cells, {
        "detections": len(rows),
        "cells": len(cells),
        "activity_mean": round(sum(scores) / len(scores), 1) if scores else 0.0,
        "activity_max": round(max(scores), 1) if scores else 0.0,
        "families": families_available,
        "agreement_cells": agreement_cells,
    }


def _cache_key(*parts: object) -> str:
    return "|".join(str(x) for x in parts)


async def _cache_get(key: str) -> dict[str, Any] | None:
    now = time.time()
    async with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached and now - cached[0] < _CACHE_TTL_SECONDS:
            return dict(cached[1])
    return None


async def _cache_put(key: str, body: dict[str, Any]) -> None:
    async with _CACHE_LOCK:
        _CACHE[key] = (time.time(), body)
        if len(_CACHE) > 120:
            oldest = sorted(_CACHE.items(), key=lambda item: item[1][0])[:30]
            for old_key, _ in oldest:
                _CACHE.pop(old_key, None)


def _map_key() -> str:
    key = os.getenv("FIRMS_MAP_KEY", "").strip()
    if not key:
        raise HTTPException(
            503,
            "FIRMS_MAP_KEY is not configured. Copy .env.example to .env and add your NASA FIRMS MAP_KEY.",
        )
    return key


async def fetch_firms(source: str, area: str, days: int, start_date: str | None = None) -> list[dict[str, Any]]:
    if source not in ALLOWED_SOURCES:
        raise HTTPException(400, f"Source not allowed: {source}")
    key = _map_key()
    suffix = f"/{start_date}" if start_date else ""
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/{source}/{area}/{days}{suffix}"
    try:
        async with httpx.AsyncClient(timeout=40.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise HTTPException(504, f"NASA FIRMS timed out for {source}. Try a smaller viewport.") from exc
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        raise HTTPException(502, f"NASA FIRMS returned HTTP {status} for {source}.") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Could not contact NASA FIRMS for {source}: {exc}") from exc

    rows: list[dict[str, Any]] = []
    reader = csv.DictReader(io.StringIO(response.text))
    for row in reader:
        item = normalize_row(row, source)
        if item:
            rows.append(item)
    return rows


async def fetch_firms_soft(source: str, area: str, days: int, start_date: str | None) -> tuple[str, list[dict[str, Any]], str | None]:
    try:
        rows = await fetch_firms(source, area, days, start_date)
        return source, rows, None
    except HTTPException as exc:
        return source, [], str(exc.detail)


def _parse_sources(value: str | None) -> list[str]:
    if not value:
        return list(DEFAULT_HARMONIZATION_SOURCES)
    sources = [x.strip() for x in value.split(",") if x.strip()]
    bad = [x for x in sources if x not in ALLOWED_SOURCES]
    if bad:
        raise HTTPException(400, f"Unsupported sources: {', '.join(bad)}")
    if not sources:
        raise HTTPException(400, "At least one source is required")
    return list(dict.fromkeys(sources))


def _demo_frames() -> list[dict[str, Any]]:
    with open(DATA_DIR / "sample_fires.json", "r", encoding="utf-8") as f:
        payload = json.load(f)
    base = payload.get("fires", [])
    today = date.today()
    frames: list[dict[str, Any]] = []
    source_cycle = ["MODIS_SP", "VIIRS_NOAA20_SP", "MODIS_SP"]

    # Deterministic synthetic analytical demo. Never labelled as NASA data.
    for offset in range(5):
        frame_date = (today - timedelta(days=4 - offset)).isoformat()
        fires: list[dict[str, Any]] = []
        keep_mod = 2 + (offset % 3)
        for idx, original in enumerate(base):
            if idx % 5 == 0 and offset in {0, 3}:
                continue
            item = dict(original)
            item["date"] = frame_date
            item["lat"] = round(float(item["lat"]) + ((idx % 3) - 1) * 0.035 * offset, 5)
            item["lon"] = round(float(item["lon"]) + ((idx % 4) - 1.5) * 0.028 * offset, 5)
            item["frp"] = round(float(item.get("frp", 0)) * (0.72 + 0.13 * offset + (idx % 4) * 0.03), 2)
            item["source"] = source_cycle[(idx + offset) % len(source_cycle)]
            item["family"] = sensor_family(item["source"], item.get("instrument", ""))
            fires.append(item)
            # Add a second sensor observation near the same cell to demonstrate agreement.
            if idx % keep_mod == 0:
                twin = dict(item)
                twin["lat"] = round(item["lat"] + 0.018, 5)
                twin["lon"] = round(item["lon"] - 0.016, 5)
                twin["source"] = "MODIS_SP" if item["family"] == "VIIRS" else "VIIRS_NOAA20_SP"
                twin["family"] = sensor_family(twin["source"])
                twin["frp"] = round(item["frp"] * 0.88, 2)
                fires.append(twin)
        cells, summary = harmonize_day(fires, 0.12)
        frames.append({"date": frame_date, "fires": fires, "cells": cells, "summary": summary})
    return frames


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "version": APP_VERSION,
        "firms_key_configured": bool(os.getenv("FIRMS_MAP_KEY", "").strip()),
        "default_source": os.getenv("FIRMS_SOURCE", "VIIRS_NOAA21_NRT"),
        "cache_ttl_seconds": _CACHE_TTL_SECONDS,
        "harmonization": True,
        "historical_archive": archive_store.status(),
        "earth_context_engine": True,
        "candidate_event_clustering": True,
    }


@app.get("/api/config")
def config() -> dict[str, Any]:
    default_source = os.getenv("FIRMS_SOURCE", "VIIRS_NOAA21_NRT")
    if default_source not in ALLOWED_SOURCES:
        default_source = "VIIRS_NOAA21_NRT"
    return {
        "version": APP_VERSION,
        "firms_key_configured": bool(os.getenv("FIRMS_MAP_KEY", "").strip()),
        "default_source": default_source,
        "sources": [{"id": key, "label": value} for key, value in SOURCES.items()],
        "harmonization_sources": list(DEFAULT_HARMONIZATION_SOURCES),
        "recommended_refresh_minutes": 15,
        "max_api_days": 5,
        "archive": archive_store.status(),
        "archive_sources": [{"id": key, "label": value} for key, value in ARCHIVE_SOURCES.items()],
        "context": {
            "weather": "Open-Meteo / ERA5-Land or forecast",
            "air_quality": "Open-Meteo / Copernicus CAMS",
            "event_clustering": True,
            "event_radius_km": EVENT_RADIUS_KM,
            "event_window_hours": EVENT_WINDOW_HOURS,
            "event_min_points": EVENT_MIN_POINTS,
        },
    }


@app.get("/api/fires/demo")
def demo_fires() -> JSONResponse:
    with open(DATA_DIR / "sample_fires.json", "r", encoding="utf-8") as f:
        payload = json.load(f)
    payload["version"] = APP_VERSION
    return JSONResponse(payload)


@app.get("/api/harmonize/demo")
def demo_harmonized() -> JSONResponse:
    frames = _demo_frames()
    all_rows = [fire for frame in frames for fire in frame.get("fires", [])]
    return JSONResponse({
        "mode": "demo-harmonized",
        "version": APP_VERSION,
        "method": "common-grid + within-sensor normalization + candidate spatiotemporal events",
        "grid_deg": 0.12,
        "sources": list(DEFAULT_HARMONIZATION_SOURCES),
        "frames": frames,
        "events": candidate_events(all_rows),
        "warning": "Synthetic analytical demo; not NASA observations.",
    })


@app.get("/api/fires/query")
async def query_fires(
    area: str = Query("-118,14,-86,33", description="west,south,east,north"),
    source: str = Query("VIIRS_NOAA21_NRT"),
    days: int = Query(1, ge=1, le=5),
    start_date: str | None = Query(None, description="YYYY-MM-DD; omit for most recent"),
    max_points: int = Query(6000, ge=100, le=20000),
) -> JSONResponse:
    area = _safe_area(area)
    start_date = _safe_date(start_date)
    cache_key = _cache_key("query", source, area, days, start_date, max_points)
    cached = await _cache_get(cache_key)
    if cached:
        cached["cache"] = "hit"
        return JSONResponse(cached)

    rows = await fetch_firms(source, area, days, start_date)
    total = len(rows)
    sampled = deterministic_sample(rows, max_points)
    body = {
        "mode": "historical" if start_date else "live",
        "version": APP_VERSION,
        "source": source,
        "area": area,
        "days": days,
        "start_date": start_date,
        "total_received": total,
        "returned": len(sampled),
        "sampled": len(sampled) < total,
        "cache": "miss",
        "fires": sampled,
    }
    await _cache_put(cache_key, body)
    return JSONResponse(body)


@app.get("/api/fires/current")
async def current_fires(
    area: str = Query("-118,14,-86,33"),
    source: str = Query("VIIRS_NOAA21_NRT"),
    days: int = Query(1, ge=1, le=5),
    max_points: int = Query(6000, ge=100, le=20000),
) -> JSONResponse:
    return await query_fires(area=area, source=source, days=days, start_date=None, max_points=max_points)


@app.get("/api/harmonize")
async def harmonize(
    area: str = Query("-118,14,-86,33"),
    start_date: str | None = Query(None, description="YYYY-MM-DD; omit for most recent"),
    days: int = Query(5, ge=1, le=5),
    sources: str | None = Query(None, description="comma-separated FIRMS sources"),
    grid_deg: float = Query(0.10, ge=0.04, le=0.5),
    max_points_per_frame: int = Query(5000, ge=200, le=10000),
) -> JSONResponse:
    area = _safe_area(area)
    start_date = _safe_date(start_date)
    requested_sources = _parse_sources(sources)
    cache_key = _cache_key("harmonize", area, start_date, days, ",".join(requested_sources), grid_deg, max_points_per_frame)
    cached = await _cache_get(cache_key)
    if cached:
        cached["cache"] = "hit"
        return JSONResponse(cached)

    results = await asyncio.gather(*(fetch_firms_soft(source, area, days, start_date) for source in requested_sources))
    all_rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    available_sources: list[str] = []
    for source, rows, error in results:
        if rows:
            available_sources.append(source)
            all_rows.extend(rows)
        elif error:
            warnings.append(f"{source}: {error}")

    if not all_rows:
        raise HTTPException(502, "No FIRMS observations were returned for the selected sources/date/area. " + " | ".join(warnings))

    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in all_rows:
        by_date[row["date"]].append(row)

    frames: list[dict[str, Any]] = []
    for frame_date in sorted(by_date):
        frame_rows = by_date[frame_date]
        cells, summary = harmonize_day(frame_rows, grid_deg)
        frames.append({
            "date": frame_date,
            "fires": deterministic_sample(frame_rows, max_points_per_frame),
            "cells": cells,
            "summary": summary,
        })

    events = candidate_events(all_rows)
    body = {
        "mode": "harmonized-historical" if start_date else "harmonized-live",
        "version": APP_VERSION,
        "method": "common-grid + within-sensor normalization + sensor-family agreement",
        "grid_deg": grid_deg,
        "area": area,
        "start_date": start_date,
        "days": days,
        "requested_sources": requested_sources,
        "available_sources": available_sources,
        "warnings": warnings,
        "cache": "miss",
        "frames": frames,
        "events": events,
        "event_method": f"{EVENT_RADIUS_KM:g} km / {EVENT_WINDOW_HOURS:g} h candidate thermal-anomaly clustering",
        "event_caveat": "Candidate clusters are not official wildfire incidents or perimeters.",
    }
    await _cache_put(cache_key, body)
    return JSONResponse(body)


@app.get("/api/analytics/baseline")
async def baseline(
    area: str = Query("-118,14,-86,33"),
    target_date: str = Query(..., description="YYYY-MM-DD"),
    years: int = Query(5, ge=2, le=10),
    days: int = Query(1, ge=1, le=5),
) -> JSONResponse:
    """Historical anomaly anchored to MODIS SP for long-term consistency.

    VIIRS is used by the harmonized map for modern detail, while this baseline keeps a
    single long-running sensor family to avoid manufacturing cross-sensor equivalence.
    """
    area = _safe_area(area)
    target = datetime.strptime(_safe_date(target_date) or "", "%Y-%m-%d").date()
    cache_key = _cache_key("baseline", area, target.isoformat(), years, days)
    cached = await _cache_get(cache_key)
    if cached:
        cached["cache"] = "hit"
        return JSONResponse(cached)

    query_dates: list[date] = [target]
    for n in range(1, years + 1):
        try:
            query_dates.append(target.replace(year=target.year - n))
        except ValueError:  # Feb 29
            query_dates.append(target.replace(year=target.year - n, day=28))

    results = await asyncio.gather(*(fetch_firms_soft("MODIS_SP", area, days, d.isoformat()) for d in query_dates))
    counts: list[dict[str, Any]] = []
    for (_, rows, error), d in zip(results, query_dates):
        counts.append({"date": d.isoformat(), "detections": len(rows), "error": error})

    current = counts[0]["detections"]
    historical = [x["detections"] for x in counts[1:] if x["error"] is None]
    if not historical:
        raise HTTPException(502, "Historical MODIS baseline could not be constructed.")

    mean = statistics.fmean(historical)
    stdev = statistics.pstdev(historical) if len(historical) > 1 else 0.0
    z_score = (current - mean) / stdev if stdev > 0 else (0.0 if current == mean else (3.0 if current > mean else -3.0))
    pct_change = ((current - mean) / mean * 100.0) if mean > 0 else (100.0 if current > 0 else 0.0)
    if z_score >= 2:
        label = "exceptional"
    elif z_score >= 1:
        label = "elevated"
    elif z_score <= -1:
        label = "below-normal"
    else:
        label = "typical"

    body = {
        "version": APP_VERSION,
        "method": "MODIS_SP same-calendar-window historical anchor",
        "area": area,
        "target_date": target.isoformat(),
        "days": days,
        "years_requested": years,
        "current_detections": current,
        "historical_mean": round(mean, 1),
        "historical_stdev": round(stdev, 2),
        "percent_change": round(pct_change, 1),
        "z_score": round(z_score, 2),
        "anomaly_label": label,
        "samples": counts,
        "cache": "miss",
        "note": "Baseline intentionally uses MODIS only for long-term consistency; VIIRS remains part of the modern harmonized visualization.",
    }
    await _cache_put(cache_key, body)
    return JSONResponse(body)

# ---------------------------------------------------------------------------
# v0.4 — Burning Activity Calendar (retained in v0.6)
# ---------------------------------------------------------------------------
REGIONS: dict[str, dict[str, Any]] = {
    "mexico": {"label": "Mexico", "area": "-118,14,-86,33", "camera": [-102.5, 23.5, 5600000], "season": [1, 2, 3, 4, 5]},
    "amazon": {"label": "Amazon Basin", "area": "-80,-20,-44,8", "camera": [-61.5, -7.0, 5200000], "season": [7, 8, 9, 10]},
    "california": {"label": "California", "area": "-125,32,-114,42", "camera": [-119.5, 37.0, 3600000], "season": [6, 7, 8, 9, 10]},
    "med": {"label": "Mediterranean", "area": "-10,30,40,46", "camera": [20.0, 37.0, 5000000], "season": [5, 6, 7, 8, 9]},
    "australia": {"label": "Australia", "area": "112,-44,154,-10", "camera": [134.0, -25.0, 6200000], "season": [11, 12, 1, 2]},
}


def _calendar_level(score: float) -> str:
    if score >= 80:
        return "extreme"
    if score >= 60:
        return "very-high"
    if score >= 40:
        return "high"
    if score >= 20:
        return "moderate"
    return "low"


def _demo_calendar_score(region: str, year: int, month: int) -> float:
    """Deterministic synthetic seasonality for interface testing only."""
    region_cfg = REGIONS.get(region, REGIONS["mexico"])
    season = set(region_cfg["season"])
    adjacent = {((m - 2) % 12) + 1 for m in season} | {(m % 12) + 1 for m in season}
    base = 14.0
    if month in season:
        base = 58.0
    elif month in adjacent:
        base = 31.0

    # Stable pseudo-variation without random state.
    signature = sum(ord(ch) for ch in region) + year * 17 + month * 29
    variation = ((signature * 37) % 23) - 11
    trend = max(-4.0, min(10.0, (year - 2003) * 0.26))

    # A few deterministic event years make the UX useful for anomaly exploration.
    event = 0.0
    if (year + month + len(region)) % 17 == 0:
        event += 25.0
    if month in season and (year * month) % 29 == 0:
        event += 16.0
    return round(max(2.0, min(100.0, base + variation + trend + event)), 1)


def _calendar_demo_payload(region: str, start_year: int, end_year: int) -> dict[str, Any]:
    if region not in REGIONS:
        raise HTTPException(400, f"Unknown region preset: {region}")
    current_year = date.today().year
    start_year = max(2003, start_year)
    end_year = min(current_year, end_year)
    if start_year > end_year:
        raise HTTPException(400, "start_year must not be after end_year")
    if end_year - start_year > 40:
        raise HTTPException(400, "Calendar range is too large")

    rows: list[dict[str, Any]] = []
    for year in range(start_year, end_year + 1):
        months: list[dict[str, Any]] = []
        for month in range(1, 13):
            if year == current_year and month > date.today().month:
                months.append({"month": month, "available": False, "score": None, "level": "future"})
                continue
            score = _demo_calendar_score(region, year, month)
            months.append({
                "month": month,
                "available": True,
                "score": score,
                "level": _calendar_level(score),
                "detections": int(round(score * 11.3)),
                "frp_mean": round(6.0 + score * 0.82, 1),
            })
        rows.append({"year": year, "months": months})

    return {
        "version": APP_VERSION,
        "mode": "demo-calendar",
        "region": region,
        "region_label": REGIONS[region]["label"],
        "area": REGIONS[region]["area"],
        "start_year": start_year,
        "end_year": end_year,
        "rows": rows,
        "warning": "Synthetic calendar for UX/demo only. Values are not NASA observations.",
    }


def _normalize_calendar_samples(samples: list[dict[str, Any]]) -> None:
    valid = [x for x in samples if x.get("available") and x.get("error") is None]
    if not valid:
        return
    counts = [float(x["detections"]) for x in valid]
    frps = [float(x["frp_mean"]) for x in valid]
    count_p95 = _percentile(counts, 0.95)
    frp_p95 = _percentile(frps, 0.95)
    for item in valid:
        count_norm = min(1.0, item["detections"] / count_p95) if count_p95 else 0.0
        frp_norm = min(1.0, item["frp_mean"] / frp_p95) if frp_p95 else 0.0
        score = 100.0 * (0.65 * count_norm + 0.35 * frp_norm)
        item["score"] = round(score, 1)
        item["level"] = _calendar_level(score)


@app.get("/api/analytics/calendar/demo")
def calendar_demo(
    region: str = Query("mexico"),
    start_year: int = Query(2003, ge=2000, le=2100),
    end_year: int = Query(date.today().year, ge=2000, le=2100),
) -> JSONResponse:
    return JSONResponse(_calendar_demo_payload(region, start_year, end_year))


@app.get("/api/analytics/calendar/sample")
async def calendar_sample(
    area: str = Query("-118,14,-86,33"),
    start_year: int = Query(date.today().year - 3, ge=2000, le=2100),
    end_year: int = Query(date.today().year, ge=2000, le=2100),
    sample_days: int = Query(3, ge=1, le=5),
    anchor_day: int = Query(10, ge=1, le=23),
) -> JSONResponse:
    """Standardized monthly sample using MODIS SP.

    FIRMS Area API accepts 1..5 day windows, so this endpoint intentionally samples
    one equal-length window per month. It is a seasonal comparison aid, NOT a full
    monthly fire total. Full-month archive ingestion is a v0.5+ local archive data path.
    """
    area = _safe_area(area)
    current = date.today()
    if start_year > end_year:
        raise HTTPException(400, "start_year must not be after end_year")
    if end_year > current.year:
        end_year = current.year
    if end_year - start_year > 5:
        raise HTTPException(400, "NASA sampled calendar is limited to 6 years per request to protect FIRMS quota.")

    cache_key = _cache_key("calendar-sample", area, start_year, end_year, sample_days, anchor_day)
    cached = await _cache_get(cache_key)
    if cached:
        cached["cache"] = "hit"
        return JSONResponse(cached)

    targets: list[tuple[int, int, date]] = []
    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            target = date(year, month, anchor_day)
            if target > current:
                continue
            targets.append((year, month, target))

    semaphore = asyncio.Semaphore(4)

    async def fetch_month(year: int, month: int, target: date) -> dict[str, Any]:
        async with semaphore:
            _, rows, error = await fetch_firms_soft("MODIS_SP", area, sample_days, target.isoformat())
        if error:
            return {
                "year": year, "month": month, "available": False, "date": target.isoformat(),
                "detections": 0, "frp_mean": 0.0, "score": None, "level": "unavailable", "error": error,
            }
        frps = [float(x.get("frp", 0.0)) for x in rows]
        return {
            "year": year,
            "month": month,
            "available": True,
            "date": target.isoformat(),
            "detections": len(rows),
            "frp_mean": round(statistics.fmean(frps), 2) if frps else 0.0,
            "score": 0.0,
            "level": "low",
            "error": None,
        }

    flat = await asyncio.gather(*(fetch_month(y, m, d) for y, m, d in targets))
    _normalize_calendar_samples(flat)
    lookup = {(x["year"], x["month"]): x for x in flat}
    rows_out: list[dict[str, Any]] = []
    for year in range(start_year, end_year + 1):
        months: list[dict[str, Any]] = []
        for month in range(1, 13):
            item = lookup.get((year, month))
            if item is None:
                months.append({"month": month, "available": False, "score": None, "level": "future"})
            else:
                months.append({k: v for k, v in item.items() if k != "year"})
        rows_out.append({"year": year, "months": months})

    body = {
        "version": APP_VERSION,
        "mode": "nasa-sampled-calendar",
        "source": "MODIS_SP",
        "area": area,
        "start_year": start_year,
        "end_year": end_year,
        "sample_days": sample_days,
        "anchor_day": anchor_day,
        "rows": rows_out,
        "cache": "miss",
        "sampling_note": (
            f"Each month is represented by a standardized {sample_days}-day MODIS_SP sample beginning on day {anchor_day}. "
            "Scores are normalized within this request; they are not complete monthly totals."
        ),
    }
    await _cache_put(cache_key, body)
    return JSONResponse(body)


def _region_demo_frames(region: str, start: date, days: int) -> list[dict[str, Any]]:
    if region not in REGIONS:
        raise HTTPException(400, f"Unknown region preset: {region}")
    west, south, east, north = map(float, REGIONS[region]["area"].split(","))
    width, height = east - west, north - south
    source_cycle = ["MODIS_SP", "VIIRS_NOAA20_SP", "MODIS_SP", "VIIRS_NOAA20_SP"]
    frames: list[dict[str, Any]] = []
    for offset in range(days):
        d = start + timedelta(days=offset)
        monthly_score = _demo_calendar_score(region, d.year, d.month)
        point_count = max(12, min(95, int(10 + monthly_score * 0.72)))
        fires: list[dict[str, Any]] = []
        for idx in range(point_count):
            cluster = idx % 4
            cx = [0.28, 0.47, 0.68, 0.78][cluster]
            cy = [0.42, 0.64, 0.31, 0.56][cluster]
            jitter_x = (((idx * 37 + d.day * 11 + offset * 7) % 101) / 100.0 - 0.5) * 0.20
            jitter_y = (((idx * 53 + d.month * 13 + offset * 5) % 97) / 96.0 - 0.5) * 0.20
            lon = west + width * max(0.03, min(0.97, cx + jitter_x))
            lat = south + height * max(0.03, min(0.97, cy + jitter_y))
            source = source_cycle[(idx + offset) % len(source_cycle)]
            confidence = 42 + ((idx * 17 + d.day) % 57)
            frp = 7.0 + monthly_score * (0.22 + ((idx % 11) / 35.0))
            severity_score = min(100.0, 0.60 * min(frp / 120.0, 1.0) * 100 + 0.40 * confidence)
            severity = "critical" if severity_score >= 72 else "high" if severity_score >= 45 else "moderate"
            fires.append({
                "lat": round(lat, 6), "lon": round(lon, 6), "frp": round(frp, 2),
                "brightness": None, "confidence": confidence, "confidence_raw": str(confidence),
                "date": d.isoformat(), "time": str(900 + (idx * 13) % 900).zfill(4),
                "satellite": "DEMO", "instrument": sensor_family(source), "daynight": "D",
                "source": source, "family": sensor_family(source), "severity": severity,
                "severity_score": round(severity_score, 1),
            })
        cells, summary = harmonize_day(fires, 0.12)
        frames.append({"date": d.isoformat(), "fires": fires, "cells": cells, "summary": summary})
    return frames


@app.get("/api/harmonize/demo/date")
def demo_harmonized_date(
    region: str = Query("mexico"),
    start_date: str = Query(..., description="YYYY-MM-DD"),
    days: int = Query(5, ge=1, le=5),
) -> JSONResponse:
    start = datetime.strptime(_safe_date(start_date) or "", "%Y-%m-%d").date()
    frames = _region_demo_frames(region, start, days)
    all_rows = [fire for frame in frames for fire in frame.get("fires", [])]
    return JSONResponse({
        "mode": "demo-harmonized-historical",
        "version": APP_VERSION,
        "method": "synthetic common-grid temporal demonstration + candidate events",
        "region": region,
        "area": REGIONS.get(region, REGIONS["mexico"])["area"],
        "grid_deg": 0.12,
        "sources": ["MODIS_SP", "VIIRS_NOAA20_SP"],
        "frames": frames,
        "events": candidate_events(all_rows),
        "warning": "Synthetic historical demonstration; not NASA observations.",
    })


# ---------------------------------------------------------------------------
# v0.5 — Local Historical Data Engine (DuckDB + Parquet)
# ---------------------------------------------------------------------------

def _archive_sources(value: str | None) -> list[str] | None:
    if not value:
        return None
    items = [x.strip() for x in value.split(",") if x.strip()]
    bad = [x for x in items if x not in ARCHIVE_SOURCES]
    if bad:
        raise HTTPException(400, f"Unsupported local archive sources: {', '.join(bad)}")
    return list(dict.fromkeys(items))


def _archive_date(value: str) -> date:
    safe = _safe_date(value)
    return datetime.strptime(safe or "", "%Y-%m-%d").date()


@app.get("/api/archive/status")
def archive_status() -> JSONResponse:
    body = archive_store.status()
    body["version"] = APP_VERSION
    body["archive_sources"] = [{"id": k, "label": v} for k, v in ARCHIVE_SOURCES.items()]
    return JSONResponse(body)


@app.post("/api/archive/import")
async def archive_import(
    file: UploadFile = File(...),
    source: str = Form(...),
) -> JSONResponse:
    if source not in ARCHIVE_SOURCES:
        raise HTTPException(400, f"Unsupported archive source: {source}")
    filename = Path(file.filename or "firms_archive.csv").name
    suffix = Path(filename).suffix.lower()
    if suffix not in {".csv", ".txt", ".zip"}:
        raise HTTPException(400, "Upload a FIRMS CSV, TXT or ZIP file.")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = INBOX_DIR / f"{timestamp}_{filename}"
    try:
        with target.open("wb") as handle:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
        results = await asyncio.to_thread(archive_store.import_path, target, source)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, f"Archive import failed: {exc}") from exc
    return JSONResponse({
        "version": APP_VERSION,
        "source": source,
        "results": [r.__dict__ for r in results],
        "archive": archive_store.status(),
    })


@app.get("/api/archive/calendar")
def archive_calendar(
    area: str = Query("-118,14,-86,33"),
    start_year: int = Query(2003, ge=2000, le=2100),
    end_year: int = Query(date.today().year, ge=2000, le=2100),
    sources: str | None = Query("MODIS_SP"),
) -> JSONResponse:
    area = _safe_area(area)
    try:
        body = archive_store.calendar(area, start_year, end_year, _archive_sources(sources))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    body["version"] = APP_VERSION
    body["archive"] = archive_store.status()
    return JSONResponse(body)


@app.get("/api/archive/harmonize")
def archive_harmonize(
    area: str = Query("-118,14,-86,33"),
    start_date: str = Query(..., description="YYYY-MM-DD"),
    days: int = Query(5, ge=1, le=31),
    sources: str | None = Query(None),
    grid_deg: float = Query(0.10, ge=0.04, le=0.5),
    max_points_per_frame: int = Query(1600, ge=100, le=5000),
) -> JSONResponse:
    area = _safe_area(area)
    start = _archive_date(start_date)
    selected_sources = _archive_sources(sources)
    try:
        rows = archive_store.fires(area, start, days, selected_sources, max_points_per_day=max_points_per_frame)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_date[row["date"]].append(row)
    frames: list[dict[str, Any]] = []
    for offset in range(days):
        frame_date = (start + timedelta(days=offset)).isoformat()
        frame_rows = deterministic_sample(by_date.get(frame_date, []), max_points_per_frame)
        cells, summary = harmonize_day(frame_rows, grid_deg)
        frames.append({"date": frame_date, "fires": frame_rows, "cells": cells, "summary": summary})
    return JSONResponse({
        "mode": "local-archive-harmonized",
        "version": APP_VERSION,
        "method": "local DuckDB archive + common-grid harmonization + candidate events",
        "area": area,
        "start_date": start.isoformat(),
        "days": days,
        "sources": selected_sources or [],
        "grid_deg": grid_deg,
        "frames": frames,
        "events": candidate_events(rows),
        "event_method": f"{EVENT_RADIUS_KM:g} km / {EVENT_WINDOW_HOURS:g} h candidate thermal-anomaly clustering",
        "archive": archive_store.status(),
        "warning": None if rows else "No local archive observations matched this period/AOI.",
    })


@app.get("/api/archive/anomaly")
def archive_anomaly(
    area: str = Query("-118,14,-86,33"),
    target_year: int = Query(..., ge=2000, le=2100),
    target_month: int = Query(..., ge=1, le=12),
    years: int = Query(10, ge=2, le=20),
    source: str = Query("MODIS_SP"),
) -> JSONResponse:
    area = _safe_area(area)
    try:
        body = archive_store.monthly_anomaly(area, target_year, target_month, years, source)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    body["version"] = APP_VERSION
    return JSONResponse(body)


# ---------------------------------------------------------------------------
# v0.6 — Earth Context Engine
# ---------------------------------------------------------------------------
@app.get("/api/context/environment")
async def environment_context(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    event_date: str = Query(..., description="YYYY-MM-DD"),
) -> JSONResponse:
    safe = _safe_date(event_date)
    context_date = safe or event_date
    cache_key = _cache_key("context", round(lat, 3), round(lon, 3), context_date)
    cached = await _cache_get(cache_key)
    if cached:
        cached["cache"] = "hit"
        return JSONResponse(cached)
    body = await build_environment_context(lat, lon, context_date)
    body["version"] = APP_VERSION
    body["cache"] = "miss"
    await _cache_put(cache_key, body)
    return JSONResponse(body)


@app.get("/api/events/demo")
def events_demo() -> JSONResponse:
    frames = _demo_frames()
    rows = [fire for frame in frames for fire in frame.get("fires", [])]
    return JSONResponse({
        "version": APP_VERSION,
        "mode": "demo-candidate-events",
        "events": candidate_events(rows),
        "caveat": "Synthetic demo clusters; not NASA observations and not official incidents.",
    })


# --------------------------------------------------------------------------- #
# v0.7 — Fire Evolution Engine
# --------------------------------------------------------------------------- #
# Synthetic, deterministic demo scenario. Each seed narrates a full lifecycle:
# EMERGING -> EXPANDING -> peak -> DECLINING (plus one EXTINCT stream) so the
# evolution engine can be explored without a FIRMS MAP_KEY and without internet.
EVOLUTION_SCENARIOS: dict[str, dict[str, Any]] = {
    "mexico": {
        "label": "Mexico · multi-region synthetic evolution scenario",
        "camera": (-101.5, 20.5, 4200000),
        "seeds": [
            {"name": "Sierra Norte de Puebla", "lat": 19.92, "lon": -97.98,
             "detections": [3, 8, 17, 24, 9], "frp": (28, 96), "drift": (0.12, -0.185),
             "spread_km": (5, 34), "families": ("MODIS", "VIIRS")},
            {"name": "Durango highlands", "lat": 25.12, "lon": -105.12,
             "detections": [4, 4, 5, 4, 4], "frp": (22, 61), "drift": (0.018, 0.026),
             "spread_km": (7, 14), "families": ("MODIS",)},
            {"name": "Chiapas frontier", "lat": 16.35, "lon": -92.55,
             "detections": [0, 0, 6, 14, 21], "frp": (34, 128), "drift": (0.095, -0.068),
             "spread_km": (4, 30), "families": ("VIIRS",)},
            {"name": "Yucatan grassland pulse", "lat": 20.42, "lon": -88.94,
             "detections": [5, 3, 2, 1, 0], "frp": (18, 44), "drift": (-0.035, 0.020),
             "spread_km": (6, 12), "families": ("VIIRS", "MODIS")},
        ],
    },
    "amazon": {
        "label": "Amazon Basin · synthetic evolution scenario",
        "camera": (-60.5, -7.5, 4600000),
        "seeds": [
            {"name": "Mato Grosso arc", "lat": -11.4, "lon": -55.7,
             "detections": [5, 12, 26, 31, 14], "frp": (40, 180), "drift": (-0.10, 0.155),
             "spread_km": (6, 40), "families": ("MODIS", "VIIRS")},
            {"name": "Pará deforestation front", "lat": -6.9, "lon": -52.4,
             "detections": [2, 5, 11, 18, 23], "frp": (35, 140), "drift": (0.085, -0.12),
             "spread_km": (5, 32), "families": ("VIIRS", "MODIS")},
            {"name": "Cerrado savanna", "lat": -14.8, "lon": -47.6,
             "detections": [6, 5, 4, 3, 2], "frp": (20, 70), "drift": (0.045, 0.062),
             "spread_km": (6, 16), "families": ("MODIS",)},
        ],
    },
}


def _evolution_demo_frames(region: str = "mexico", days: int = 5) -> list[dict[str, Any]]:
    scenario = EVOLUTION_SCENARIOS.get(region) or EVOLUTION_SCENARIOS["mexico"]
    today = date.today()
    frames: list[dict[str, Any]] = []
    for offset in range(days):
        frame_date = (today - timedelta(days=days - 1 - offset)).isoformat()
        rng = random.Random(f"ignis-evolution-{region}-{offset}")
        fires: list[dict[str, Any]] = []
        for seed in scenario["seeds"]:
            count = int(seed["detections"][min(offset, len(seed["detections"]) - 1)]) if offset < len(seed["detections"]) else 0
            if count <= 0:
                continue
            lat0 = float(seed["lat"]) + float(seed["drift"][0]) * offset
            lon0 = float(seed["lon"]) + float(seed["drift"][1]) * offset
            spread_min, spread_max = seed["spread_km"]
            spread = min(spread_max, spread_min + (spread_max - spread_min) * (count / max(1, max(seed["detections"]))))
            frp_lo, frp_hi = seed["frp"]
            for k in range(count):
                lat = lat0 + rng.uniform(-1, 1) * spread / 111.0
                lon = lon0 + rng.uniform(-1, 1) * spread / (111.0 * max(0.2, math.cos(math.radians(lat0))))
                frp = round(rng.uniform(frp_lo, frp_hi) * (0.55 + 0.9 * (count / max(1, max(seed["detections"])))), 1)
                if "VIIRS" in seed["families"] and (k % 2 == 0):
                    source, instrument, sat = "VIIRS_NOAA20_SP", "VIIRS", "NOAA-20"
                    conf_raw, conf = "n" if frp < frp_hi * 0.7 else "h", None
                else:
                    source, instrument, sat = "MODIS_SP", "MODIS", "Terra"
                    conf_raw, conf = ("h" if frp > frp_hi * 0.5 else "n"), None
                confidence = normalize_confidence(conf_raw)
                severity_score = min(100.0, max(0.0, 0.60 * min(frp / 120.0, 1.0) * 100 + 0.40 * confidence))
                severity = "critical" if severity_score >= 72 else "high" if severity_score >= 45 else "moderate"
                fires.append({
                    "lat": round(lat, 6), "lon": round(lon, 6), "frp": frp,
                    "brightness": round(300 + frp * 0.35, 2), "confidence": confidence,
                    "confidence_raw": conf_raw, "date": frame_date,
                    "time": f"{rng.randint(1, 23):02d}{rng.choice(['00', '12', '24', '36', '48'])}",
                    "satellite": sat, "instrument": instrument,
                    "daynight": rng.choice(["D", "N"]), "source": source,
                    "family": sensor_family(source, instrument),
                    "severity": severity, "severity_score": round(severity_score, 1),
                    "seed": seed["name"],
                })
        cells, summary = harmonize_day(fires, 0.10)
        frames.append({"date": frame_date, "fires": fires, "cells": cells, "summary": summary})
    return frames


def _evolution_from_frames(frames: list[dict[str, Any]], session: str, min_points: int = 2) -> dict[str, Any]:
    per_frame = [{"date": f["date"], "events": candidate_events(f.get("fires", []))} for f in frames]
    engine = track_evolution(per_frame, session=session)
    # Deriva los indicadores de panel desde los eventos cuando el frame no trae summary
    # (p. ej. frames construidos desde el archivo local).
    for frame, built in zip(frames, per_frame):
        events = built["events"]
        if not frame.get("summary"):
            scores = [float(e.get("event_score") or 0.0) for e in events]
            frame["summary"] = {
                "activity_mean": round(sum(scores) / len(scores), 1) if scores else 0.0,
                "agreement_cells": sum(1 for e in events if len(e.get("families") or []) >= 2),
                "cells": len(events),
                "method": "Derived from candidate events (archive frames carry no harmonization grid).",
            }
        frame["events"] = events
    engine["per_frame"] = [
        {"date": f["date"], "events": f["events"], "count": len(f["events"])} for f in per_frame
    ]
    return engine


# --------------------------------------------------------------------------- #
# v0.8 — Environmental Intelligence
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# v0.9 — IGNIS Intelligence Analyst
# --------------------------------------------------------------------------- #
@app.get("/api/analyst/sample")
def analyst_sample(lang: str = Query("es", pattern="^(es|en)$")) -> JSONResponse:
    """Briefing de ejemplo para que la interfaz pueda mostrarlo sin selección previa."""
    frames = _evolution_demo_frames("mexico", 5)
    engine = _evolution_from_frames(frames, session="DEMO-MEXICO", min_points=2)
    tracks = [t for t in engine["tracks"] if t["status"] != "EXTINCT"] or engine["tracks"]
    if not tracks:
        raise HTTPException(503, "No tracks available for a sample briefing.")
    return JSONResponse({
        "version": APP_VERSION,
        "mode": "analyst-sample",
        "track": tracks[0],
        "usage": "POST /api/analyst/briefing with {\"track\": <track>, \"lang\": \"es|en\"}",
        "lang": lang,
    })


@app.post("/api/analyst/briefing")
async def analyst_briefing(payload: dict[str, Any]) -> JSONResponse:
    """Narrativa explicable de un evento persistente.

    Cuerpo esperado::

        {"track": { ...registro del motor de evolución... },
         "lang": "es", "environment": true, "baseline": true, "baseline_years": 10}

    Cada frase del briefing viaja con las cifras exactas que la sostienen.
    """
    track = payload.get("track")
    if not isinstance(track, dict) or not track.get("id"):
        raise HTTPException(422, "Se requiere un objeto 'track' con al menos 'id'.")
    lang = str(payload.get("lang", "es")).lower()[:2]
    if lang not in ("es", "en"):
        lang = "es"
    include_environment = bool(payload.get("environment", True))
    include_baseline = bool(payload.get("baseline", True))
    try:
        years = int(payload.get("baseline_years", 10))
    except (TypeError, ValueError):
        years = 10
    years = max(2, min(15, years))

    body = await build_briefing(
        track,
        lang=lang,
        include_environment=include_environment,
        include_baseline=include_baseline,
        baseline_years=years,
    )
    return JSONResponse(body)


@app.get("/api/environment/catalog")
def environment_catalog() -> JSONResponse:
    """Capas GIBS verificadas (con su TileMatrixSet correcto) para la UI."""
    return JSONResponse({
        "version": APP_VERSION,
        "provider": "NASA GIBS (WMTS, sin API key)",
        "url_template": "https://gibs.earthdata.nasa.gov/wmts/epsg4326/best/{layer}/default/{date}/{tms}/{matrix}/{row}/{col}.{ext}",
        "note_for_ui": "El orden es TileRow/TileCol (fila = latitud).",
        "layers": [
            {
                "key": key, "id": cfg["id"], "label": cfg.get("label", cfg["id"]),
                "role": cfg["role"], "tms": cfg["tms"], "matrix": cfg["tile_matrix_id"],
                "colormap": cfg.get("colormap"), "units": cfg["units"],
                "extension": "jpg" if "TrueColor" in cfg["id"] else "png",
            }
            for key, cfg in ENV_LAYERS.items()
        ],
    })


@app.get("/api/environment/intelligence")
async def environment_intelligence(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    event_date: str = Query(..., description="YYYY-MM-DD"),
    drought: bool = Query(True, description="Incluir percentil de sequía ERA5 (más lento)"),
    lang: str = Query("es", pattern="^(es|en)$", description="Idioma de las frases de evidencia"),
) -> JSONResponse:
    safe = _safe_date(event_date)
    target = safe or event_date
    cache_key = _cache_key("environment", lang, round(lat, 3), round(lon, 3), target, drought)
    cached = await _cache_get(cache_key)
    if cached:
        cached["cache"] = "hit"
        return JSONResponse(cached)
    body = await build_environment_intelligence(lat, lon, target, include_drought=drought, lang=lang)
    body["cache"] = "miss"
    await _cache_put(cache_key, body)
    return JSONResponse(body)


@app.get("/api/evolution/demo")
def evolution_demo(region: str = Query("mexico", pattern="^(mexico|amazon)$"), days: int = Query(5, ge=3, le=10)) -> JSONResponse:
    frames = _evolution_demo_frames(region, days)
    engine = _evolution_from_frames(frames, session=f"DEMO-{region.upper()}", min_points=2)
    scenario = EVOLUTION_SCENARIOS.get(region) or EVOLUTION_SCENARIOS["mexico"]
    return JSONResponse({
        "version": APP_VERSION,
        "mode": "evolution-demo",
        "region": region,
        "region_label": scenario["label"],
        "camera": scenario["camera"],
        "frames": frames,
        "events": (engine["per_frame"][-1]["events"] if engine.get("per_frame") else []),
        "evolution": engine,
        "environmental_catalog": "/api/environment/catalog",
        "sources": ["MODIS_SP", "VIIRS_NOAA20_SP"],
        "warning": "Synthetic evolution scenario for engine demonstration. Not NASA observations.",
        "caveat": engine["caveat"],
    })


@app.get("/api/evolution/archive")
def evolution_archive(
    area: str = Query(...),
    start_date: str = Query(...),
    days: int = Query(5, ge=2, le=31),
    sources: str | None = Query(None),
) -> JSONResponse:
    safe_area = _safe_area(area)
    start = _archive_date(start_date) if start_date else date.today() - timedelta(days=days)
    status = archive_store.status()
    if not status.get("ready"):
        raise HTTPException(400, "Local archive is empty. Import FIRMS files first, or load the evolution demo.")
    chosen = _archive_sources(sources)
    frames: list[dict[str, Any]] = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        rows = archive_store.fires(safe_area, day, 1, chosen)
        frames.append({"date": day.isoformat(), "fires": rows, "cells": [], "summary": {}})
    frames = [f for f in frames if f["fires"]]
    if not frames:
        raise HTTPException(404, "No archived observations in that window.")
    engine = _evolution_from_frames(frames, session="ARCHIVE", min_points=2)
    return JSONResponse({
        "version": APP_VERSION,
        "mode": "evolution-archive",
        "region": "viewport",
        "region_label": f"LOCAL ARCHIVE · {safe_area}",
        "frames": frames,
        "events": (engine["per_frame"][-1]["events"] if engine.get("per_frame") else []),
        "evolution": engine,
        "sources": sorted({f.get("source") for frame in frames for f in frame["fires"] if f.get("source")}),
        "warning": "Local archived FIRMS observations. Tracking identity remains heuristic.",
        "caveat": engine["caveat"],
    })
