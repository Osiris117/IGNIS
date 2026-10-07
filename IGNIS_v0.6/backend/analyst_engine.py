"""IGNIS v0.9 — Intelligence Analyst.

Convierte los números que ya calculan los motores v0.7 (evolución de eventos) y
v0.8 (contexto ambiental) en un **briefing legible**, bilingüe y —lo importante—
**explicable**: cada frase viaja acompañada de las cifras exactas que la sostienen
y de la fuente de cada cifra.

Principio de diseño: aquí NO hay modelo generativo ni texto inventado. Son
plantillas deterministas que sólo se rellenan con valores medidos. Si un dato no
existe, la frase correspondiente no se escribe (y el briefing lo declara).

    >>> briefing = await build_briefing(track, lang="es")
    >>> briefing["sentences"][0]["text"]
    'IGN-2026-0008 se expande: la intensidad subió 93% entre la primera y la última observación.'

Cada frase trae ``citations`` con la métrica, el valor y la fuente, de modo que la
interfaz puede mostrar el "por qué" de cada afirmación.
"""

from __future__ import annotations

import asyncio
import csv
import io
import os
import statistics
from datetime import datetime, timedelta
from typing import Any, Iterable

from backend.archive_store import archive_store
from backend.environment_engine import build_environment_intelligence

# --------------------------------------------------------------------------- #
# Textos (es / en)
# --------------------------------------------------------------------------- #
T: dict[str, dict[str, str]] = {
    "es": {
        "headline_expanding": "{id} se expande: la intensidad subió {delta}% entre la primera y la última observación.",
        "headline_declining": "{id} se debilita: la intensidad cayó {delta}% entre la primera y la última observación.",
        "headline_emerging": "{id} es un evento emergente: sólo hay {frames} observación(es) y aún no hay tendencia.",
        "headline_stable": "{id} se mantiene estable: la intensidad varió apenas {delta}% dentro del ruido del método.",
        "headline_extinct": "{id} dejó de observarse hace {since} día(s); se clasifica EXTINTO con la última señal del {last}.",
        "headline_unknown": "{id} no tiene suficientes observaciones para clasificar su evolución.",
        "activity": "Se acumulan {detections} detecciones en {frames} día(s) con observación, con un pico de {peak_frp} MW de potencia radiativa el {peak_date}.",
        "activity_short": "Se registran {detections} detecciones en {frames} día(s) con observación.",
        "sensors": "Dos familias de sensores independientes coinciden: {families}. La confianza media de las detecciones es {confidence}/100.",
        "sensors_single": "Las detecciones provienen de una sola familia de sensores ({families}); la confirmación cruzada es limitada.",
        "motion": "El centroide se desplazó {path} km en total y {net} km netos hacia el {bearing} (±{speed} km/h aparentes). Es una estimación de deriva aparente entre pasadas, no un modelo de propagación.",
        "motion_static": "El centroide apenas se movió ({net} km netos): el evento es esencialmente estacionario entre pasadas.",
        "drought_dry": "El terreno llega seco: la precipitación de 90 días es de {mm} mm, percentil {pct} frente a {years} años de ERA5 en ese punto → {category}.",
        "drought_normal": "El terreno no muestra déficit marcado: {mm} mm en 90 días, percentil {pct} frente a {years} años de ERA5 → {category}.",
        "fuel": "El combustible vegetal es {fuel} (NDVI ≈ {ndvi}, compuesto de {date} de MODIS).",
        "smoke": "La columna atmosférica muestra {smoke} (AOD ≈ {aod}).",
        "smoke_pyro": "El índice de piro-cumulonimbos de OMPS es {pyro}, compatible con aerosoles de combustión.",
        "baseline_up": "Contexto histórico: en el mismo mes y la misma ventana geográfica, la actividad local está {pct}% por encima de la media de {years} años del archivo (z = {z}).",
        "baseline_down": "Contexto histórico: la actividad local está {pct}% por debajo de la media de {years} años para ese mes (z = {z}).",
        "baseline_typical": "Contexto histórico: la actividad local es típica para ese mes ({pct}% frente a la media de {years} años, z = {z}).",
        "baseline_none": "Sin ancla histórica: el archivo local no cubre años previos de este mes y no hay FIRMS_MAP_KEY para la consulta en vivo.",
        "confidence_high": "Confianza {score}/100 ({label}): {components}.",
        "uncertainty": "Incertidumbre declarada: {items}.",
        "env_missing": "Sin contexto ambiental para {date} (las capas de GIBS o ERA5 no respondieron).",
    },
    "en": {
        "headline_expanding": "{id} is expanding: intensity rose {delta}% between the first and the last observation.",
        "headline_declining": "{id} is weakening: intensity fell {delta}% between the first and the last observation.",
        "headline_emerging": "{id} is an emerging event: only {frames} observation(s) so far, no trend yet.",
        "headline_stable": "{id} is holding steady: intensity moved just {delta}%, within method noise.",
        "headline_extinct": "{id} has not been seen for {since} day(s); classified EXTINCT as of the last signal on {last}.",
        "headline_unknown": "{id} does not have enough observations to classify its evolution.",
        "activity": "{detections} detections accumulated across {frames} observed day(s), peaking at {peak_frp} MW of radiative power on {peak_date}.",
        "activity_short": "{detections} detections recorded across {frames} observed day(s).",
        "sensors": "Two independent sensor families agree: {families}. Mean detection confidence is {confidence}/100.",
        "sensors_single": "Detections come from a single sensor family ({families}); cross-confirmation is limited.",
        "motion": "The centroid travelled {path} km overall and {net} km net toward {bearing} (±{speed} km/h apparent). This is apparent drift between overpasses, not a spread model.",
        "motion_static": "The centroid barely moved ({net} km net): the event is essentially stationary between overpasses.",
        "drought_dry": "The landscape is dry: 90-day rainfall is {mm} mm, percentile {pct} against {years} years of ERA5 at that point → {category}.",
        "drought_normal": "No marked deficit: {mm} mm over 90 days, percentile {pct} against {years} years of ERA5 → {category}.",
        "fuel": "Fuel load is {fuel} (NDVI ≈ {ndvi}, MODIS composite of {date}).",
        "smoke": "The atmospheric column shows {smoke} (AOD ≈ {aod}).",
        "smoke_pyro": "OMPS pyro-cumulonimbus index is {pyro}, consistent with combustion aerosols.",
        "baseline_up": "Historical context: for the same month and area, local activity is {pct}% above the {years}-year archive mean (z = {z}).",
        "baseline_down": "Historical context: local activity is {pct}% below the {years}-year mean for that month (z = {z}).",
        "baseline_typical": "Historical context: local activity is typical for that month ({pct}% vs. the {years}-year mean, z = {z}).",
        "baseline_none": "No historical anchor: the local archive does not cover prior years for this month and no FIRMS_MAP_KEY is set for the live query.",
        "confidence_high": "Confidence {score}/100 ({label}): {components}.",
        "uncertainty": "Declared uncertainty: {items}.",
        "env_missing": "No environmental context for {date} (GIBS or ERA5 layers did not respond).",
    },
}

CAVEATS = {
    "es": [
        "Cada frase está atada a una cifra medida; no hay texto generado libremente.",
        "Las identidades persistentes y los estados son etiquetas analíticas, no un registro oficial de incidentes.",
        "El entorno (sequía, NDVI, AOD) describe contexto; no es un pronóstico de peligro ni una atribución de humo.",
        "Producto de contexto: no usar para decisiones de vida o seguridad.",
    ],
    "en": [
        "Every sentence is bound to a measured number; no free-form generated text.",
        "Persistent identities and lifecycle states are analytical labels, not an official incident record.",
        "Environment (drought, NDVI, AOD) describes context; it is not a danger forecast or smoke attribution.",
        "Context product: not for life or safety decisions.",
    ],
}


def _t(lang: str, key: str, **kw: Any) -> str:
    template = T.get(lang, T["es"]).get(key) or T["es"].get(key) or key
    try:
        text = template.format(**kw)
    except (KeyError, IndexError):
        text = template
    if lang == "es":
        # Separador decimal español (65,4 %) para cualquier cifra que llegue sin formatear.
        import re as _re

        text = _re.sub(r"(?<![vV\w])(\d+)\.(\d+)", r"\1,\2", text)
    return text


def _cite(metric: str, value: Any, source: str, unit: str | None = None) -> dict[str, Any]:
    return {"metric": metric, "value": value, "unit": unit, "source": source}


def _sentence(sid: str, block: str, text: str, citations: Iterable[dict[str, Any]] = ()) -> dict[str, Any]:
    return {"id": sid, "block": block, "text": text, "citations": [c for c in citations]}


def _fmt(value: Any, digits: int = 1, lang: str = "es") -> str:
    """Números legibles con el separador decimal del idioma (es: 65,4 · en: 65.4)."""
    if value is None:
        return "—"
    if isinstance(value, float) or (isinstance(value, int) and not isinstance(value, bool)):
        text = f"{float(value):.{digits}f}".rstrip("0").rstrip(".")
        if lang == "es":
            text = text.replace(".", ",")
        return text
    return str(value)


def _index(value: float | None, cap: float) -> float | None:
    if value is None:
        return None
    return round(min(100.0, max(0.0, value / cap * 100.0)), 1)


# --------------------------------------------------------------------------- #
# Bloques narrativos
# --------------------------------------------------------------------------- #
def _headline(track: dict[str, Any], lang: str) -> dict[str, Any]:
    status = (track.get("status") or "UNKNOWN").upper()
    delta = track.get("intensity_delta_pct")
    key = {
        "EXPANDING": "headline_expanding",
        "DECLINING": "headline_declining",
        "EMERGING": "headline_emerging",
        "STABLE": "headline_stable",
        "EXTINCT": "headline_extinct",
    }.get(status, "headline_unknown")
    citations: list[dict[str, Any]] = []
    kw: dict[str, Any] = {"id": track.get("id", "IGNIS")}
    if key in ("headline_expanding", "headline_declining", "headline_stable"):
        kw["delta"] = _fmt(abs(delta or 0.0), lang=lang)
        citations.append(_cite("intensity_delta_pct", delta, "IGNIS Fire Evolution Engine", "%"))
    elif key == "headline_emerging":
        kw["frames"] = track.get("frames_observed", 0)
        citations.append(_cite("frames_observed", track.get("frames_observed"), "IGNIS Fire Evolution Engine"))
    elif key == "headline_extinct":
        kw["since"] = track.get("frames_since_last", 0)
        kw["last"] = track.get("last_seen", "—")
        citations.append(_cite("frames_since_last", track.get("frames_since_last"), "IGNIS Fire Evolution Engine"))
    text = _t(lang, key, **kw)
    return {
        "headline": text,
        "headline_citations": citations,
        "status": status,
        "status_basis": track.get("status_basis"),
    }


def _activity(track: dict[str, Any], lang: str) -> dict[str, Any]:
    peak = track.get("peak") or {}
    citations = [
        _cite("detections_total", track.get("detections_total"), "NASA FIRMS (MODIS + VIIRS)"),
        _cite("frames_observed", track.get("frames_observed"), "NASA FIRMS (MODIS + VIIRS)"),
    ]
    if peak.get("total_frp") is not None:
        citations.append(_cite("peak_total_frp_mw", peak.get("total_frp"), "NASA FIRMS", "MW"))
    key = "activity" if peak.get("date") else "activity_short"
    text = _t(
        lang,
        key,
        detections=track.get("detections_total", 0),
        frames=track.get("frames_observed", 0),
        peak_frp=_fmt(peak.get("total_frp"), lang=lang),
        peak_date=peak.get("date", "—"),
    )
    return _sentence("activity", "activity", text, citations)


def _sensors(track: dict[str, Any], lang: str) -> dict[str, Any]:
    families = track.get("families") or []
    sources = track.get("sources") or []
    confidence = track.get("mean_confidence")
    citations = [_cite("sensor_families", len(families), "FIRMS source metadata")]
    if confidence is not None:
        citations.append(_cite("mean_confidence", confidence, "FIRMS confidence field"))
    key = "sensors" if len(families) > 1 else "sensors_single"
    text = _t(lang, key, families=" + ".join(families) or "—", confidence=_fmt(confidence, lang=lang))
    return _sentence("sensors", "sensors", text, citations)


def _motion(track: dict[str, Any], lang: str) -> dict[str, Any]:
    traj = track.get("trajectory") or {}
    net = traj.get("net_displacement_km")
    path = traj.get("path_km")
    citations = [
        _cite("net_displacement_km", net, "IGNIS centroid analysis", "km"),
        _cite("path_km", path, "IGNIS centroid analysis", "km"),
    ]
    if traj.get("bearing_compass"):
        citations.append(_cite("bearing", traj.get("bearing_compass"), "IGNIS centroid analysis"))
    if net is not None and net < 5:
        return _sentence("motion", "motion", _t(lang, "motion_static", net=_fmt(net, lang=lang)), citations)
    text = _t(
        lang,
        "motion",
        path=_fmt(path, lang=lang),
        net=_fmt(net, lang=lang),
        bearing=traj.get("bearing_compass") or "—",
        speed=_fmt(traj.get("mean_speed_kmh"), 2, lang=lang),
    )
    return _sentence("motion", "motion", text, citations)


def _environment_sentences(env: dict[str, Any], lang: str, iso_date: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    out: list[dict[str, Any]] = []
    scores: dict[str, Any] = {}

    drought = env.get("drought") or {}
    if drought.get("available"):
        win = (drought.get("windows") or {}).get("90d") or {}
        percentile = drought.get("percentile")
        scores["dryness_index"] = round(100.0 - float(percentile), 1) if percentile is not None else None
        key = "drought_dry" if (percentile is not None and percentile <= 30) else "drought_normal"
        text = _t(
            lang, key,
            mm=_fmt(win.get("precip_mm"), lang=lang),
            pct=_fmt(percentile, lang=lang),
            years=win.get("history_years", 0),
            category=drought.get("category_label", "—"),
        )
        out.append(_sentence("drought", "environment", text, [
            _cite("precip_90d_mm", win.get("precip_mm"), "Open-Meteo ERA5 archive", "mm"),
            _cite("precip_percentile_90d", percentile, "Open-Meteo ERA5 archive", "percentile" if lang=="en" else "percentil"),
        ]))

    fuel = env.get("fuel") or {}
    if fuel.get("available"):
        ndvi = fuel.get("ndvi")
        scores["fuel_index"] = _index(ndvi, 0.8)
        text = _t(lang, "fuel", fuel=fuel.get("fuel_label", "—"), ndvi=_fmt(ndvi, 2, lang=lang), date=fuel.get("date", "—"))
        out.append(_sentence("fuel", "environment", text, [
            _cite("ndvi", ndvi, f"NASA GIBS · MODIS NDVI 8-day ({fuel.get('date')})"),
        ]))

    smoke = env.get("smoke") or {}
    if smoke.get("available"):
        aod = smoke.get("aod")
        scores["smoke_index"] = _index(aod, 1.0)
        out.append(_sentence("smoke", "environment", _t(lang, "smoke", smoke=smoke.get("smoke_label", "—"), aod=_fmt(aod, 2, lang=lang)), [
            _cite("aod", aod, "NASA GIBS · MODIS AOD (2 km)"),
        ]))
        pyro = (smoke.get("pyro_cumulonimbus") or {}).get("value")
        if pyro is not None and float(pyro) > 0.05:
            out.append(_sentence("pyro", "environment", _t(lang, "smoke_pyro", pyro=_fmt(pyro, 2, lang=lang)), [
                _cite("pyrocb_index", pyro, "NASA GIBS · OMPS PyroCb"),
            ]))

    if not out:
        out.append(_sentence("env_missing", "environment", _t(lang, "env_missing", date=iso_date), []))

    available_scores = [v for v in scores.values() if v is not None]
    if available_scores:
        scores["environmental_context_index"] = round(sum(available_scores) / len(available_scores), 1)
    return out, scores


async def _firms_daily_count(area: str, day: str, source: str = "MODIS_SP") -> int | None:
    """Conteo de detecciones del día en un área, directo de la API de FIRMS.

    Solo se usa para el ancla histórica cuando el archivo local no cubre años
    previos. Sin ``FIRMS_MAP_KEY`` devuelve ``None`` (y el briefing lo dice).
    """
    key = os.getenv("FIRMS_MAP_KEY")
    if not key:
        return None
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/{source}/{area}/1/{day}"
    try:
        import httpx

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url, headers={"User-Agent": "IGNIS/0.9 (NASA hackathon prototype)"})
        if response.status_code != 200:
            return None
        rows = list(csv.DictReader(io.StringIO(response.text)))
        return len(rows)
    except Exception:
        return None


async def _live_baseline(area: str, target: datetime, years: int) -> dict[str, Any] | None:
    """Ancla histórica MODIS en vivo (mismo mes-día, años previos)."""
    days: list[str] = []
    for offset in range(1, years + 1):
        try:
            days.append(target.replace(year=target.year - offset).date().isoformat())
        except ValueError:
            days.append(target.replace(year=target.year - offset, day=28).date().isoformat())
    counts = await asyncio.gather(*(_firms_daily_count(area, d) for d in days))
    values = [c for c in counts if c is not None]
    if len(values) < 3:
        return None
    mean = statistics.fmean(values)
    stdev = statistics.pstdev(values) if len(values) > 1 else 0.0
    return {
        "method": "NASA FIRMS live MODIS_SP same-calendar-day historical anchor",
        "historical_mean": round(mean, 1),
        "historical_stdev": round(stdev, 2),
        "years_used": len(values),
        "samples": [{"date": d, "detections": c} for d, c in zip(days, counts) if c is not None],
    }


async def _baseline(track: dict[str, Any], lang: str, years: int) -> tuple[dict[str, Any], dict[str, Any] | None]:
    lat, lon = track.get("lat"), track.get("lon")
    last_seen = track.get("last_seen")
    if lat is None or lon is None or not last_seen:
        return _sentence("baseline", "baseline", _t(lang, "baseline_none"), []), None
    try:
        target = datetime.strptime(str(last_seen)[:10], "%Y-%m-%d")
    except ValueError:
        return _sentence("baseline", "baseline", _t(lang, "baseline_none"), []), None
    area = f"{lon - 0.35:.3f},{lat - 0.35:.3f},{lon + 0.35:.3f},{lat + 0.35:.3f}"
    try:
        data = await asyncio.to_thread(
            archive_store.monthly_anomaly, area, target.year, target.month, years, "MODIS_SP"
        )
    except Exception:
        live = await _live_baseline(area, target, years)
        if live is None:
            return _sentence("baseline", "baseline", _t(lang, "baseline_none"), []), None
        current = track.get("detections_latest") or 0
        mean = live["historical_mean"]
        pct = ((current - mean) / mean * 100.0) if mean > 0 else (100.0 if current > 0 else 0.0)
        stdev = live["historical_stdev"]
        z = (current - mean) / stdev if stdev > 0 else 0.0
        data = {**live, "percent_change": round(pct, 1), "z_score": round(z, 2),
                "current_detections": current, "source": "MODIS_SP (live FIRMS)"}

    pct = data.get("percent_change")
    z = data.get("z_score")
    key = "baseline_up" if (pct or 0) >= 25 else "baseline_down" if (pct or 0) <= -25 else "baseline_typical"
    samples = data.get("samples", [])
    years_used = len([s for s in samples if s.get("year", 0) < target.year]) or data.get("years_used") or years
    text = _t(lang, key, pct=_fmt(pct, lang=lang), years=years_used, z=_fmt(z, 2, lang=lang))
    origin = data.get("method", "")
    source_label = ("Archivo local IGNIS · DuckDB MODIS_SP" if "local" in origin or not origin else
                    "NASA FIRMS MODIS_SP (consulta en vivo)")
    if lang == "en" and not origin.lower().startswith("nasa"):
        source_label = "IGNIS local archive · DuckDB MODIS_SP"
    citations = [
        _cite("historical_percent_change", pct, source_label, "%"),
        _cite("z_score", z, source_label),
        _cite("current_detections_window", data.get("current_detections"), source_label),
    ]
    return _sentence("baseline", "baseline", text, citations), data


WEIGHTS = {"detections": 26, "persistence": 22, "sensor_independence": 18, "frp": 18, "declared_confidence": 16}
LEVELS = {"es": {"HIGH": "alta", "MEDIUM": "media", "LOW": "baja"},
          "en": {"HIGH": "high", "MEDIUM": "medium", "LOW": "low"}}
NAMES = {"es": {"detections": "detecciones", "persistence": "persistencia",
                "sensor_independence": "independencia de sensores", "frp": "potencia radiativa",
                "declared_confidence": "confianza declarada"},
         "en": {"detections": "detections", "persistence": "persistence",
                "sensor_independence": "sensor independence", "frp": "radiative power",
                "declared_confidence": "declared confidence"}}
SECTION = "({} peso {}%)" if True else ""


def _confidence_sentence(track: dict[str, Any], lang: str) -> dict[str, Any]:
    conf = track.get("confidence") or {}
    score = conf.get("score")
    level = (conf.get("level") or "").upper()
    label = LEVELS["en" if lang == "en" else "es"].get(level, level or "—")
    components = conf.get("components") or {}
    rendered: list[str] = []
    if isinstance(components, dict):
        for key, value in components.items():
            weight = WEIGHTS.get(key)
            name = NAMES["en" if lang == "en" else "es"].get(key, key)
            rendered.append(f"{name} {_fmt(value, lang=lang)}/100" + (f" ({'peso' if lang!='en' else 'weight'} {weight}%)" if weight else ""))
    else:
        rendered = [str(x) for x in components]
    text = _t(lang, "confidence_high", score=_fmt(score, lang=lang), label=label, components=", ".join(rendered) or "—")
    return _sentence("confidence", "confidence", text, [
        _cite("event_confidence", score, "IGNIS explainable confidence model")
    ])


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
async def build_briefing(
    track: dict[str, Any],
    *,
    lang: str = "es",
    include_environment: bool = True,
    include_baseline: bool = True,
    baseline_years: int = 10,
) -> dict[str, Any]:
    """Briefing explicable para un evento persistente.

    Args:
        track: registro tal como lo produce ``backend.evolution_engine`` (o una
            versión reducida con al menos ``id``, ``status``, ``lat``, ``lon``,
            ``detections_total``, ``first_seen`` y ``last_seen``).
        lang: ``es`` o ``en``.
        include_environment: consultar NASA GIBS / ERA5 (más lento).
        include_baseline: comparar contra el archivo DuckDB local.
    """
    lang = "en" if str(lang).lower().startswith("en") else "es"
    iso_date = str(track.get("last_seen") or datetime.utcnow().date().isoformat())[:10]

    sentences: list[dict[str, Any]] = []
    head = _headline(track, lang)
    sentences.append(_sentence("activity", "activity", head["headline"], head["headline_citations"]))
    sentences.append(_activity(track, lang))
    sentences.append(_sensors(track, lang))
    sentences.append(_motion(track, lang))

    env: dict[str, Any] = {}
    env_scores: dict[str, Any] = {}
    tasks = []
    if include_environment:
        tasks.append(build_environment_intelligence(track.get("lat"), track.get("lon"), iso_date, lang=lang))
    if include_baseline:
        tasks.append(_baseline(track, lang, baseline_years))
    results = await asyncio.gather(*tasks, return_exceptions=True) if tasks else []

    baseline_data: dict[str, Any] | None = None
    idx = 0
    if include_environment:
        env_result = results[idx] if idx < len(results) else {}
        idx += 1
        if isinstance(env_result, dict):
            env = env_result
            env_sentences, env_scores = _environment_sentences(env, lang, iso_date)
            sentences.extend(env_sentences)
    if include_baseline:
        base_result = results[idx] if idx < len(results) else None
        if isinstance(base_result, tuple):
            baseline_sentence, baseline_data = base_result
            sentences.append(baseline_sentence)

    sentences.append(_confidence_sentence(track, lang))

    # Incertidumbre explícita, construida con lo que realmente limita este caso.
    uncertainty: list[str] = []
    if track.get("frames_observed", 0) <= 2:
        uncertainty.append("pocas observaciones (≤2)" if lang == "es" else "few observations (≤2)")
    if len(track.get("families") or []) <= 1:
        uncertainty.append("una sola familia de sensores" if lang == "es" else "single sensor family")
    if not (track.get("trajectory") or {}).get("bearing_deg"):
        uncertainty.append("sin vector de deriva" if lang == "es" else "no drift vector")
    if not env.get("available"):
        uncertainty.append("contexto ambiental incompleto" if lang == "es" else "incomplete environmental context")
    if (track.get("status") or "").upper() == "EXTINCT":
        uncertainty.append("evento sin señal reciente" if lang == "es" else "no recent signal")
    if not uncertainty:
        uncertainty.append("método heurístico de vínculo entre clústeres" if lang == "es" else "heuristic cluster-linking method")
    sentences.append(_sentence("uncertainty", "uncertainty", _t(lang, "uncertainty", items="; ".join(uncertainty)), []))

    return {
        "version": "0.9.0",
        "engine": "IGNIS Intelligence Analyst",
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "lang": lang,
        "track_id": track.get("id"),
        "status": (track.get("status") or "UNKNOWN").upper(),
        "headline": head["headline"],
        "sentences": sentences,
        "scores": env_scores,
        "environment": {
            "summary": env.get("summary"),
            "available": env.get("available"),
            "caveat": env.get("caveat"),
        },
        "baseline": baseline_data,
        "method": (
            "Plantillas deterministas rellenadas con métricas medidas; sin generación libre de texto."
            if lang == "es"
            else "Deterministic templates filled with measured metrics; no free-form text generation."
        ),
        "caveats": CAVEATS[lang],
    }
