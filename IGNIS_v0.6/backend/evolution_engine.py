"""IGNIS v0.7 — Fire Evolution Engine.

Adds *persistent identity* and *lifecycle intelligence* on top of the v0.6
candidate-event clustering.

Design principles (kept deliberately consistent with the rest of IGNIS):

- Everything here operates on **candidate fire events** = spatiotemporal
  clusters of satellite thermal anomalies. They are NOT official incidents.
- Identity is **persistent but heuristic**: a same-event link is claimed only
  when a new cluster overlaps the previous position within ``match_km`` and the
  observation gap stays below ``max_gap_hours``.
- Movement / propagation output is an **apparent centroid drift**, not a fire
  spread model. Wording follows the project caveat policy.
- The confidence score is **explainable**: it returns its components and the
  human-readable evidence behind each one.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

EARTH_RADIUS_KM = 6371.0088

MATCH_KM = float(os.getenv("IGNIS_TRACK_MATCH_KM", "60"))
MAX_GAP_HOURS = float(os.getenv("IGNIS_TRACK_MAX_GAP_HOURS", "48"))
REGISTRY_GAP_HOURS = float(os.getenv("IGNIS_TRACK_REGISTRY_GAP_HOURS", "168"))  # 7 days
STATE_DELTA = float(os.getenv("IGNIS_TRACK_STATE_DELTA", "0.20"))

REGISTRY_PATH = Path(os.getenv("IGNIS_TRACK_REGISTRY", "data/events/track_registry.json"))
_REGISTRY_LOCK = threading.Lock()

COMPASS = ("N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
           "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW")


# --------------------------------------------------------------------------- #
# geometry helpers
# --------------------------------------------------------------------------- #
def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    a1, a2 = math.radians(lat1), math.radians(lat2)
    dlat, dlon = a2 - a1, math.radians(lon2 - lon1)
    h = math.sin(dlat / 2) ** 2 + math.cos(a1) * math.cos(a2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(h)))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    a1, a2 = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    y = math.sin(dlon) * math.cos(a2)
    x = math.cos(a1) * math.sin(a2) - math.sin(a1) * math.cos(a2) * math.cos(dlon)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def compass(bearing: float) -> str:
    return COMPASS[int((bearing + 11.25) % 360 // 22.5)]


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        try:
            return datetime.strptime(str(value)[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None


# --------------------------------------------------------------------------- #
# persistent identity registry
# --------------------------------------------------------------------------- #
def _load_registry() -> dict[str, Any]:
    try:
        with open(REGISTRY_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict) and isinstance(data.get("entries"), list):
            return data
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return {"version": 1, "next_index": 1, "entries": []}


def _save_registry(data: dict[str, Any]) -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(REGISTRY_PATH.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, REGISTRY_PATH)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def _next_persistent_id(registry: dict[str, Any], year: int) -> str:
    index = int(registry.get("next_index", 1))
    registry["next_index"] = index + 1
    return f"IGN-{year}-{index:04d}"


def _claim_identity(registry: dict[str, Any], session: str, year: int,
                    lat: float, lon: float, first_seen: str) -> tuple[str, bool]:
    """Return (persistent_id, reused). Reuses a recent same-place identity if any.

    La comparación se hace contra la **primera y la última** posición conocida de
    cada identidad: una pista que derivó decenas de km durante el evento vuelve a
    encontrarse al reanalizar el mismo dataset, en lugar de duplicar la identidad.
    """
    first_dt = _parse_dt(first_seen)
    best: dict[str, Any] | None = None
    best_km = MATCH_KM
    for entry in registry.get("entries", []):
        if entry.get("session") != session:
            continue
        last_dt = _parse_dt(entry.get("last_seen"))
        if first_dt and last_dt and abs((first_dt - last_dt).total_seconds()) > REGISTRY_GAP_HOURS * 3600:
            continue
        km_last = haversine_km(lat, lon, float(entry.get("lat", 0.0)), float(entry.get("lon", 0.0)))
        km_first = haversine_km(lat, lon, float(entry.get("first_lat", entry.get("lat", 0.0))),
                                float(entry.get("first_lon", entry.get("lon", 0.0))))
        km = min(km_last, km_first)
        if km <= best_km:
            best, best_km = entry, km
    if best is not None:
        best["last_seen"] = first_seen
        best["lat"], best["lon"] = lat, lon
        best["reuses"] = int(best.get("reuses", 0)) + 1
        return str(best["id"]), True
    new_id = _next_persistent_id(registry, year)
    registry["entries"].append({
        "id": new_id, "session": session, "year": year,
        "first_seen": first_seen, "last_seen": first_seen,
        "first_lat": lat, "first_lon": lon, "lat": lat, "lon": lon, "reuses": 0,
    })
    registry["entries"] = registry["entries"][-4000:]
    return new_id, False


def _update_identity(registry: dict[str, Any], persistent_id: str,
                     last_seen: str, lat: float, lon: float) -> None:
    for entry in registry.get("entries", []):
        if entry.get("id") == persistent_id:
            entry["last_seen"] = last_seen
            entry["lat"], entry["lon"] = lat, lon
            return


# --------------------------------------------------------------------------- #
# lifecycle classification + explainable confidence
# --------------------------------------------------------------------------- #
def _intensity(frame: dict[str, Any]) -> float:
    """Detection-weighted intensity used for state transitions (not a fire severity index)."""
    return float(frame.get("detections", 0)) * (1.0 + min(float(frame.get("total_frp", 0.0)), 600.0) / 600.0)


def classify_state(timeline: list[dict[str, Any]], extinct: bool) -> dict[str, Any]:
    if not timeline:
        return {"state": "UNKNOWN", "delta_pct": None, "basis": "no observations"}
    if extinct:
        return {"state": "EXTINCT", "delta_pct": None,
                "basis": "no linked detections in the most recent frame of this dataset"}
    if len(timeline) == 1:
        return {"state": "EMERGING", "delta_pct": None,
                "basis": "observed in a single frame so far"}
    prev, last = timeline[-2], timeline[-1]
    base = max(_intensity(prev), 1e-6)
    delta = (_intensity(last) - base) / base
    if delta >= STATE_DELTA:
        state, basis = "EXPANDING", f"intensity +{delta * 100:.0f}% vs previous frame"
    elif delta <= -STATE_DELTA:
        state, basis = "DECLINING", f"intensity {delta * 100:.0f}% vs previous frame"
    else:
        state, basis = "STABLE", f"intensity {delta * 100:+.0f}% vs previous frame"
    return {"state": state, "delta_pct": round(delta * 100, 1), "basis": basis}


def confidence(track: dict[str, Any]) -> dict[str, Any]:
    """Explainable 0–100 confidence that the linked observations represent one persistent event."""
    detections = float(track.get("detections_total", 0))
    frames = float(track.get("frames_observed", 1))
    duration_h = float(track.get("duration_hours", 0.0))
    families = len(track.get("families", []))
    max_frp = float(track.get("max_frp", 0.0))
    mean_conf = float(track.get("mean_confidence", 0.0))

    c_det = min(1.0, detections / 50.0)
    c_persist = min(1.0, (0.6 * min(1.0, duration_h / 48.0)) + (0.4 * min(1.0, frames / 5.0)))
    c_sensor = {0: 0.0, 1: 0.55, 2: 0.87}.get(families, 1.0)
    c_frp = min(1.0, max_frp / 120.0)
    c_decl = min(1.0, mean_conf / 100.0)

    score = 100.0 * (0.26 * c_det + 0.22 * c_persist + 0.18 * c_sensor + 0.18 * c_frp + 0.16 * c_decl)
    level = "HIGH" if score >= 80 else "MODERATE" if score >= 60 else "LOW" if score >= 40 else "VERY LOW"

    explanations: list[str] = []
    if detections:
        explanations.append(f"{int(detections)} detections across {int(frames)} frame(s)")
    if duration_h:
        explanations.append(f"persistence {duration_h:.0f} h")
    if families:
        explanations.append(f"{families} independent sensor family(ies): {', '.join(track.get('families', []))}")
    if max_frp:
        explanations.append(f"peak FRP {max_frp:.0f} MW")
    if mean_conf:
        explanations.append(f"mean declared confidence {mean_conf:.0f}%")
    return {
        "score": round(score, 1),
        "level": level,
        "method": "IGNIS transparent heuristic (detections 26% · persistence 22% · sensor independence 18% · FRP 18% · declared confidence 16%). Not an official event probability.",
        "components": {
            "detections": round(c_det * 100, 1),
            "persistence": round(c_persist * 100, 1),
            "sensor_independence": round(c_sensor * 100, 1),
            "frp": round(c_frp * 100, 1),
            "declared_confidence": round(c_decl * 100, 1),
        },
        "explanations": explanations,
    }


# --------------------------------------------------------------------------- #
# main entry point
# --------------------------------------------------------------------------- #
def track_evolution(
    frames: list[dict[str, Any]],
    *,
    session: str = "DEMO",
    match_km: float = MATCH_KM,
    max_gap_hours: float = MAX_GAP_HOURS,
    min_frames: int = 1,
    persist: bool = True,
) -> dict[str, Any]:
    """Link per-frame candidate events into persistent, evolving tracks.

    ``frames`` = [{"date": "YYYY-MM-DD", "events": [<cluster_fire_events output>]}, ...]
    ordered oldest → newest. Returns tracks with stable IDs, lifecycle state,
    apparent movement and an explainable confidence score.
    """
    ordered = sorted(frames, key=lambda f: str(f.get("date", "")))
    segments = [len(f.get("events", [])) for f in ordered]
    total_events = sum(segments)
    date_strs = [str(f.get("date", "")) for f in ordered]

    with _REGISTRY_LOCK:
        registry = _load_registry() if persist else {"version": 1, "next_index": 1, "entries": []}
        tracks: list[dict[str, Any]] = []

        for fi, frame in enumerate(ordered):
            date_str = date_strs[fi]
            for event in frame.get("events", []):
                lat, lon = float(event["lat"]), float(event["lon"])
                best, best_km = None, match_km
                for track in tracks:
                    last = track["timeline"][-1]
                    last_dt = _parse_dt(last["date"])
                    now_dt = _parse_dt(date_str)
                    if last_dt and now_dt and (now_dt - last_dt).total_seconds() > max_gap_hours * 3600:
                        continue
                    if last.get("_frame_index") == fi:  # one event per frame per track
                        continue
                    km = haversine_km(lat, lon, float(last["lat"]), float(last["lon"]))
                    if km <= best_km:
                        best, best_km = track, km
                snapshot = {
                    "date": date_str, "lat": lat, "lon": lon,
                    "detections": int(event.get("detections", 0)),
                    "total_frp": float(event.get("total_frp", 0.0)),
                    "max_frp": float(event.get("max_frp", 0.0)),
                    "radius_km": float(event.get("radius_km", 0.0)),
                    "event_score": float(event.get("event_score", 0.0)),
                    "severity": event.get("severity"),
                    "match_distance_km": round(best_km, 1) if best else None,
                    "_frame_index": fi,
                }
                if best is None:
                    year = int(date_str[:4]) if date_str[:4].isdigit() else datetime.now(timezone.utc).year
                    first_dt = _parse_dt(date_str)
                    persistent_id, reused = _claim_identity(
                        registry, session, year, lat, lon,
                        (first_dt or datetime.now(timezone.utc)).isoformat().replace("+00:00", "Z"),
                    )
                    tracks.append({
                        "id": persistent_id,
                        "identity": "reused" if reused else "new",
                        "session": session,
                        "first_frame": fi, "last_frame": fi,
                        "timeline": [snapshot],
                        "families": list(event.get("families", [])),
                        "sources": list(event.get("sources", [])),
                        "confidence_samples": [float(event.get("mean_confidence", 0.0))],
                    })
                else:
                    best["timeline"].append(snapshot)
                    best["last_frame"] = fi
                    for fam in event.get("families", []):
                        if fam not in best["families"]:
                            best["families"].append(fam)
                    for src in event.get("sources", []):
                        if src not in best["sources"]:
                            best["sources"].append(src)
                    best["confidence_samples"].append(float(event.get("mean_confidence", 0.0)))

        out: list[dict[str, Any]] = []
        for track in tracks:
            timeline = track["timeline"]
            if len(timeline) < min_frames:
                continue
            first, last = timeline[0], timeline[-1]
            start_dt, end_dt = _parse_dt(first["date"]), _parse_dt(last["date"])
            duration_h = round((end_dt - start_dt).total_seconds() / 3600.0, 1) if start_dt and end_dt else 0.0

            # apparent movement: cumulative path + net bearing. NOT a spread model.
            path_km = 0.0
            for a, b in zip(timeline, timeline[1:]):
                path_km += haversine_km(a["lat"], a["lon"], b["lat"], b["lon"])
            net_km = haversine_km(first["lat"], first["lon"], last["lat"], last["lon"])
            bearing = bearing_deg(first["lat"], first["lon"], last["lat"], last["lon"]) if net_km > 0.5 else None
            speed = round(net_km / duration_h, 2) if duration_h > 0 else None

            peak = max(timeline, key=lambda s: s["total_frp"])
            extinct = track["last_frame"] < len(ordered) - 1
            state_info = classify_state(timeline, extinct)

            record = {
                "id": track["id"],
                "identity": track["identity"],
                "session": track["session"],
                "status": state_info["state"],
                "status_basis": state_info["basis"],
                "intensity_delta_pct": state_info["delta_pct"],
                "first_seen": first["date"],
                "last_seen": last["date"],
                "frames_observed": len(timeline),
                "frames_in_dataset": len(ordered),
                "frames_since_last": (len(ordered) - 1) - track["last_frame"],
                "duration_hours": duration_h,
                "lat": last["lat"], "lon": last["lon"],
                "first_lat": first["lat"], "first_lon": first["lon"],
                "detections_total": sum(s["detections"] for s in timeline),
                "detections_latest": last["detections"],
                "total_frp": round(sum(s["total_frp"] for s in timeline), 1),
                "max_frp": round(max(s["max_frp"] for s in timeline), 1),
                "mean_confidence": round(sum(track["confidence_samples"]) / max(1, len(track["confidence_samples"])), 1),
                "severity": max((s.get("severity") or "moderate") for s in timeline),
                "families": sorted(track["families"]),
                "sources": sorted(track["sources"]),
                "peak": {"date": peak["date"], "total_frp": round(peak["total_frp"], 1),
                         "detections": peak["detections"]},
                "trajectory": {
                    "path_km": round(path_km, 1),
                    "net_displacement_km": round(net_km, 1),
                    "bearing_deg": round(bearing, 1) if bearing is not None else None,
                    "bearing_compass": compass(bearing) if bearing is not None else None,
                    "mean_speed_kmh": speed,
                    "interpretation": "Apparent centroid drift between satellite overpasses; NOT a fire-spread or propagation model.",
                },
                "trail": [{"date": s["date"], "lat": s["lat"], "lon": s["lon"],
                           "detections": s["detections"], "total_frp": s["total_frp"],
                           "radius_km": s["radius_km"], "severity": s["severity"]} for s in timeline],
                "timeline": [{"date": s["date"], "detections": s["detections"],
                              "total_frp": round(s["total_frp"], 1), "max_frp": round(s["max_frp"], 1),
                              "radius_km": s["radius_km"], "lat": s["lat"], "lon": s["lon"],
                              "severity": s["severity"], "event_score": s["event_score"]} for s in timeline],
                "candidate_event": True,
                "caveat": ("Persistent identity is a heuristic link between spatiotemporal clusters, "
                           "not an official incident ID. Movement is apparent centroid drift, not a propagation model."),
            }
            record["confidence"] = confidence(record)
            record["priority"] = round(
                0.55 * record["confidence"]["score"]
                + 0.30 * min(100.0, record["detections_total"] * 1.6)
                + 0.15 * min(100.0, record["max_frp"] * 0.5), 1)
            out.append(record)

            if persist and track["identity"] == "new":
                _update_identity(registry, track["id"], last["date"], last["lat"], last["lon"])

        if persist:
            _save_registry(registry)

    out.sort(key=lambda t: (t["status"] != "EXTINCT", t["priority"]), reverse=True)
    statuses: dict[str, int] = {}
    for track in out:
        statuses[track["status"]] = statuses.get(track["status"], 0) + 1
    return {
        "version": "0.7.0",
        "engine": "fire-evolution",
        "session": session,
        "frames": date_strs,
        "frame_count": len(ordered),
        "events_per_frame": segments,
        "events_total": total_events,
        "tracks_total": len(out),
        "tracks_multi_frame": sum(1 for t in out if t["frames_observed"] > 1),
        "status_counts": statuses,
        "tracks": out,
        "method": {
            "link_radius_km": match_km,
            "max_observation_gap_hours": max_gap_hours,
            "state_delta_threshold": STATE_DELTA,
            "note": ("Tracks link candidate-event clusters when they overlap within the link radius and the "
                     "observation gap stays under the maximum. Identity is persistent across refreshes via a "
                     "local registry, yet remains a heuristic analytical label."),
        },
        "caveat": "Candidate events are clustered thermal anomalies; identities and lifecycle states are analytical, not official incident data.",
    }
