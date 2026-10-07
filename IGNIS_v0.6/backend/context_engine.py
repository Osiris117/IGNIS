from __future__ import annotations

import hashlib
import math
from collections import defaultdict, deque
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    a1, a2 = math.radians(lat1), math.radians(lat2)
    dlat = a2 - a1
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(a1) * math.cos(a2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def _event_time(row: dict[str, Any]) -> datetime:
    ds = str(row.get("date") or "1970-01-01")
    ts = str(row.get("time") or "0000").zfill(4)[:4]
    try:
        return datetime.strptime(ds + ts, "%Y-%m-%d%H%M").replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.strptime(ds, "%Y-%m-%d").replace(tzinfo=timezone.utc)


class _DSU:
    def __init__(self, n: int) -> None:
        self.p = list(range(n))
        self.r = [0] * n

    def find(self, x: int) -> int:
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a: int, b: int) -> None:
        a, b = self.find(a), self.find(b)
        if a == b:
            return
        if self.r[a] < self.r[b]:
            a, b = b, a
        self.p[b] = a
        if self.r[a] == self.r[b]:
            self.r[a] += 1


def cluster_fire_events(
    rows: list[dict[str, Any]],
    spatial_km: float = 28.0,
    temporal_hours: float = 36.0,
    min_points: int = 2,
) -> list[dict[str, Any]]:
    """Group hotspot observations into candidate spatiotemporal events.

    This is an analytical grouping, not an official fire perimeter or incident ID.
    It intentionally operates on thermal-anomaly centroids and preserves that caveat.
    """
    if not rows:
        return []

    items = sorted(enumerate(rows), key=lambda pair: _event_time(pair[1]))
    ordered_rows = [r for _, r in items]
    times = [_event_time(r) for r in ordered_rows]
    n = len(ordered_rows)
    dsu = _DSU(n)

    cell_deg = max(0.05, spatial_km / 111.0)
    grid: dict[tuple[int, int], deque[int]] = defaultdict(deque)
    temporal_seconds = temporal_hours * 3600.0

    for i, row in enumerate(ordered_rows):
        lat, lon = float(row["lat"]), float(row["lon"])
        gy, gx = math.floor(lat / cell_deg), math.floor(lon / cell_deg)
        for yy in range(gy - 1, gy + 2):
            for xx in range(gx - 1, gx + 2):
                q = grid.get((yy, xx))
                if not q:
                    continue
                while q and (times[i] - times[q[0]]).total_seconds() > temporal_seconds:
                    q.popleft()
                for j in q:
                    other = ordered_rows[j]
                    if haversine_km(lat, lon, float(other["lat"]), float(other["lon"])) <= spatial_km:
                        dsu.union(i, j)
        grid[(gy, gx)].append(i)

    groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for i, row in enumerate(ordered_rows):
        groups[dsu.find(i)].append(row)

    events: list[dict[str, Any]] = []
    for group in groups.values():
        if len(group) < min_points:
            continue
        group_times = [_event_time(r) for r in group]
        weights = [max(1.0, float(r.get("frp") or 0.0)) for r in group]
        wsum = sum(weights)
        lat = sum(float(r["lat"]) * w for r, w in zip(group, weights)) / wsum
        lon = sum(float(r["lon"]) * w for r, w in zip(group, weights)) / wsum
        distances = [haversine_km(lat, lon, float(r["lat"]), float(r["lon"])) for r in group]
        total_frp = sum(float(r.get("frp") or 0.0) for r in group)
        max_frp = max(float(r.get("frp") or 0.0) for r in group)
        mean_conf = sum(float(r.get("confidence") or 0.0) for r in group) / len(group)
        severity_signal = min(100.0, 28 * math.log1p(len(group)) + 0.34 * min(total_frp, 180) + 0.16 * mean_conf)
        if severity_signal >= 78:
            severity = "critical"
        elif severity_signal >= 55:
            severity = "high"
        else:
            severity = "moderate"
        families = sorted({str(r.get("family") or "OTHER") for r in group if str(r.get("family") or "OTHER") != "OTHER"})
        sources = sorted({str(r.get("source") or "") for r in group if r.get("source")})
        start, end = min(group_times), max(group_times)
        signature = f"{start.date()}|{round(lat,2)}|{round(lon,2)}|{len(group)}"
        event_id = "EVT-" + hashlib.sha1(signature.encode("utf-8")).hexdigest()[:10].upper()
        events.append({
            "id": event_id,
            "lat": round(lat, 5),
            "lon": round(lon, 5),
            "detections": len(group),
            "start": start.isoformat().replace("+00:00", "Z"),
            "end": end.isoformat().replace("+00:00", "Z"),
            "duration_hours": round(max(0.0, (end - start).total_seconds() / 3600.0), 1),
            "total_frp": round(total_frp, 1),
            "max_frp": round(max_frp, 1),
            "mean_confidence": round(mean_conf, 1),
            "radius_km": round(max(distances) if distances else 0.0, 1),
            "severity": severity,
            "event_score": round(severity_signal, 1),
            "families": families,
            "sources": sources,
            "bbox": {
                "west": round(min(float(r["lon"]) for r in group), 5),
                "south": round(min(float(r["lat"]) for r in group), 5),
                "east": round(max(float(r["lon"]) for r in group), 5),
                "north": round(max(float(r["lat"]) for r in group), 5),
            },
            "member_count": len(group),
            "candidate_event": True,
            "caveat": "Spatiotemporal cluster of satellite thermal anomalies; not an official incident perimeter or confirmed wildfire.",
        })

    return sorted(events, key=lambda e: (e["event_score"], e["detections"], e["total_frp"]), reverse=True)


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


def _safe_values(values: Any) -> list[float]:
    return [float(v) for v in (values or []) if v is not None]


def dryness_context_score(weather: dict[str, Any]) -> dict[str, Any]:
    """Transparent heuristic for display only; this is NOT an official fire-weather index."""
    temp = weather.get("temperature_max_c")
    rh = weather.get("relative_humidity_min_pct")
    wind = weather.get("wind_speed_max_kmh")
    precip = weather.get("precipitation_sum_mm")
    soil = weather.get("soil_moisture_mean")
    components: list[float] = []
    if temp is not None:
        components.append(max(0.0, min(1.0, (float(temp) - 15.0) / 25.0)))
    if rh is not None:
        components.append(max(0.0, min(1.0, (70.0 - float(rh)) / 55.0)))
    if wind is not None:
        components.append(max(0.0, min(1.0, float(wind) / 55.0)))
    if precip is not None:
        components.append(max(0.0, min(1.0, 1.0 - float(precip) / 12.0)))
    if soil is not None:
        components.append(max(0.0, min(1.0, (0.45 - float(soil)) / 0.35)))
    score = 100.0 * (sum(components) / len(components)) if components else 0.0
    label = "very dry" if score >= 75 else "dry" if score >= 55 else "mixed" if score >= 35 else "moist"
    return {
        "score": round(score, 1),
        "label": label,
        "method": "IGNIS transparent heuristic; not FWI/NFDRS or an operational fire-danger product.",
        "components_used": len(components),
    }


async def fetch_weather_context(lat: float, lon: float, event_date: str, timeout: float = 12.0) -> dict[str, Any]:
    target = datetime.strptime(event_date[:10], "%Y-%m-%d").date()
    today = date.today()
    # ERA5/ERA5-Land archive has a short publication delay; use forecast endpoint for recent dates.
    recent = (today - target).days <= 5
    if recent:
        hourly = "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,wind_direction_10m,soil_moisture_0_to_1cm,vapour_pressure_deficit"
        soil_key = "soil_moisture_0_to_1cm"
        past_days = max(0, min(7, (today - target).days + 1))
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": hourly,
            "past_days": past_days,
            "forecast_days": 1,
            "timezone": "UTC",
        }
        provider = "Open-Meteo recent weather model blend"
    else:
        hourly = "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,wind_direction_10m,soil_moisture_0_to_7cm,vapour_pressure_deficit"
        soil_key = "soil_moisture_0_to_7cm"
        url = "https://archive-api.open-meteo.com/v1/archive"
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": target.isoformat(),
            "end_date": target.isoformat(),
            "hourly": hourly,
            "timezone": "UTC",
            "models": "era5",
        }
        provider = "Open-Meteo ERA5 reanalysis"

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()

    h = payload.get("hourly") or {}
    times = h.get("time") or []
    keep = [i for i, t in enumerate(times) if str(t).startswith(target.isoformat())]
    if not keep:
        keep = list(range(len(times)))

    def vals(key: str) -> list[float]:
        raw = h.get(key) or []
        return [float(raw[i]) for i in keep if i < len(raw) and raw[i] is not None]

    temp = vals("temperature_2m")
    rh = vals("relative_humidity_2m")
    precip = vals("precipitation")
    wind = vals("wind_speed_10m")
    wind_dir = vals("wind_direction_10m")
    soil = vals(soil_key)
    vpd = vals("vapour_pressure_deficit")
    weather = {
        "provider": provider,
        "date": target.isoformat(),
        "temperature_mean_c": _mean(temp),
        "temperature_max_c": round(max(temp), 2) if temp else None,
        "relative_humidity_mean_pct": _mean(rh),
        "relative_humidity_min_pct": round(min(rh), 2) if rh else None,
        "precipitation_sum_mm": round(sum(precip), 2) if precip else None,
        "wind_speed_mean_kmh": _mean(wind),
        "wind_speed_max_kmh": round(max(wind), 2) if wind else None,
        "wind_direction_mean_deg": _mean(wind_dir),
        "soil_moisture_mean": _mean(soil),
        "vapour_pressure_deficit_mean_kpa": _mean(vpd),
        "hours": len(keep),
    }
    weather["dryness_context"] = dryness_context_score(weather)
    return weather


async def fetch_air_quality_context(lat: float, lon: float, event_date: str, timeout: float = 12.0) -> dict[str, Any]:
    target = datetime.strptime(event_date[:10], "%Y-%m-%d").date()
    delta = (date.today() - target).days
    if delta < 0 or delta > 7:
        return {
            "available": False,
            "reason": "Air-quality context is limited to the recent archived/forecast window in this prototype.",
            "provider": "Open-Meteo Air Quality / CAMS",
        }
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "pm2_5,aerosol_optical_depth,dust",
        "past_days": max(0, delta + 1),
        "forecast_days": 1,
        "timezone": "UTC",
    }
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.get("https://air-quality-api.open-meteo.com/v1/air-quality", params=params)
        response.raise_for_status()
        payload = response.json()
    h = payload.get("hourly") or {}
    times = h.get("time") or []
    keep = [i for i, t in enumerate(times) if str(t).startswith(target.isoformat())]

    def vals(key: str) -> list[float]:
        raw = h.get(key) or []
        return [float(raw[i]) for i in keep if i < len(raw) and raw[i] is not None]

    pm25 = vals("pm2_5")
    aod = vals("aerosol_optical_depth")
    dust = vals("dust")
    return {
        "available": bool(keep),
        "provider": "Open-Meteo Air Quality / Copernicus CAMS",
        "date": target.isoformat(),
        "pm2_5_mean_ugm3": _mean(pm25),
        "pm2_5_max_ugm3": round(max(pm25), 2) if pm25 else None,
        "aerosol_optical_depth_mean": _mean(aod),
        "dust_mean_ugm3": _mean(dust),
        "note": "PM2.5/AOD are atmospheric context, not proof that smoke came from the selected candidate fire event.",
    }


async def build_environment_context(lat: float, lon: float, event_date: str) -> dict[str, Any]:
    weather: dict[str, Any]
    air: dict[str, Any]
    warnings: list[str] = []
    try:
        weather = await fetch_weather_context(lat, lon, event_date)
    except Exception as exc:
        weather = {"available": False, "error": str(exc), "provider": "Open-Meteo"}
        warnings.append(f"Weather context unavailable: {exc}")
    try:
        air = await fetch_air_quality_context(lat, lon, event_date)
    except Exception as exc:
        air = {"available": False, "error": str(exc), "provider": "Open-Meteo Air Quality / CAMS"}
        warnings.append(f"Air-quality context unavailable: {exc}")
    return {
        "lat": round(lat, 5),
        "lon": round(lon, 5),
        "date": event_date[:10],
        "weather": weather,
        "air_quality": air,
        "warnings": warnings,
        "disclaimer": "Context layers are analytical aids. They are not operational fire-danger, smoke attribution, evacuation, or life-safety products.",
    }
