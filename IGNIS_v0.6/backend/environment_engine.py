"""IGNIS v0.8 — Environmental Intelligence Engine.

Tres capas de contexto ancladas a un punto y una fecha, todas derivadas de
fuentes públicas sin API key:

1. **Drought** — percentil de precipitación tipo SPI a partir del archivo diario
   de Open-Meteo/ERA5 (misma ventana de días en los últimos N años).
2. **Fuel / vegetation** — clase de vegetación obtenida al muestrear el píxel
   del tile NDVI 8-días de NASA GIBS y mapearlo contra la colormap oficial del
   propio GIBS (no se inventan colores: se lee la paleta publicada).
3. **Smoke / aerosol** — lo mismo sobre AOD (MODIS) y el índice de aerosoles
   OMPS "PyroCumuloNimbus", que es específico de humo de incendio.

Reglas del proyecto que se mantienen:

- Todo es **contexto analítico**, nunca un producto operativo ni atribución de
  humo a un incendio concreto.
- Si falta red o el proveedor no responde, cada capa degrada a
  ``{"available": False, "reason": ...}`` sin romper el resto.
- Cada resultado incluye ``evidence`` (frases legibles) y ``caveat``.
"""

from __future__ import annotations

import asyncio
import math
import re
import statistics
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from typing import Any

import httpx

GIBS = "https://gibs.earthdata.nasa.gov"
GIBS_WMTS = f"{GIBS}/wmts/epsg4326/best"
TIMEOUT = 20.0

# Catálogo de capas verificadas contra WMTSCapabilities (TMS por capa).
LAYERS: dict[str, dict[str, Any]] = {
    "aerosol": {
        "id": "MODIS_Terra_Aerosol",
        "label": "Aerosol Optical Depth (MODIS Terra)",
        "tms": "2km",
        "level": 5,
        "tile_matrix_id": 5,
        "role": "smoke",
        "colormap": f"{GIBS}/colormaps/v1.3/MODIS_VIIRS_AOD.xml",
        "units": "AOD (sin unidad)",
    },
    "pyro": {
        "id": "OMPS_Aerosol_Index_PyroCumuloNimbus",
        "label": "Aerosol Index · PyroCumuloNimbus (OMPS)",
        "tms": "2km",
        "level": 5,
        "tile_matrix_id": 5,
        "role": "pyro_smoke",
        "colormap": f"{GIBS}/colormaps/v1.3/OMPS_Aerosol_Index.xml",
        "units": "UV Aerosol Index",
    },
    "ndvi": {
        "id": "MODIS_Terra_NDVI_8Day",
        "label": "NDVI 8-day (MODIS Terra)",
        "tms": "250m",
        "level": 6,
        "tile_matrix_id": 6,
        "role": "fuel",
        "colormap": f"{GIBS}/colormaps/v1.3/MODIS_NDVI.xml",
        "units": "NDVI",
    },
    "soil": {
        "id": "SMAP_L3_Passive_Day_Soil_Moisture",
        "label": "Soil moisture (SMAP L3, day)",
        "tms": "2km",
        "level": 5,
        "tile_matrix_id": 5,
        "role": "soil",
        "colormap": f"{GIBS}/colormaps/v1.3/SMAP_Soil_Moisture.xml",
        "units": "m³/m³",
    },
    "truecolor": {
        "id": "MODIS_Terra_CorrectedReflectance_TrueColor",
        "tms": "250m",
        "level": 6,
        "tile_matrix_id": 6,
        "role": "imagery",
        "colormap": None,
        "units": "reflectancia",
    },
    "thermal": {
        "id": "MODIS_Terra_Thermal_Anomalies_All",
        "tms": "1km",
        "level": 5,
        "tile_matrix_id": 5,
        "role": "imagery",
        "colormap": None,
        "units": "anomalías térmicas",
    },
}

_COLORMAP_CACHE: dict[str, list[tuple[tuple[int, int, int], float]]] = {}

# Grilla real de los TileMatrixSet EPSG:4326 de GIBS (leída de WMTSCapabilities y
# verificada con peticiones reales). NO es una potencia de dos: el nivel 5 es 40×20.
GIBS_GRID: dict[int, tuple[int, int]] = {
    0: (2, 1), 1: (3, 2), 2: (5, 3), 3: (10, 5), 4: (20, 10),
    5: (40, 20), 6: (80, 40), 7: (160, 80), 8: (320, 160),
}


# --------------------------------------------------------------------------- #
# utilidades de tiles (EPSG:4326 · TMS de GIBS: nivel L = 2^(L+1) × 2^L tiles)
# --------------------------------------------------------------------------- #
def tile_for(lat: float, lon: float, level: int) -> tuple[int, int, float, float]:
    """Devuelve (x, y, fracción_x, fracción_y) del tile que contiene el punto.

    Usa las dimensiones reales del TileMatrixSet de GIBS para ese nivel; cada
    nivel tiene celdas uniformes de 360/W grados de ancho y 180/H de alto.
    """
    n_x, n_y = GIBS_GRID.get(level, (2 ** (level + 1), 2 ** level))
    fx_norm = (lon + 180.0) / 360.0
    fy_norm = (90.0 - lat) / 180.0
    x = min(n_x - 1, max(0, int(fx_norm * n_x)))
    y = min(n_y - 1, max(0, int(fy_norm * n_y)))
    return x, y, fx_norm * n_x - x, fy_norm * n_y - y


def build_tile_url(layer_key: str, day: str, lat: float, lon: float) -> str:
    """URL WMTS de GIBS.

    OJO: el orden en GIBS es ``/{TileMatrix}/{TileRow}/{TileCol}`` — la FILA
    (latitud) va antes que la COLUMNA (longitud). Invertirlos devuelve tiles
    válidos pero de otra parte del mundo (bug detectado y corregido en v0.8).
    """
    cfg = LAYERS[layer_key]
    x, y, _, _ = tile_for(lat, lon, int(cfg["level"]))
    return f"{GIBS_WMTS}/{cfg['id']}/default/{day}/{cfg['tms']}/{cfg['tile_matrix_id']}/{y}/{x}.png"


async def fetch_tile(client: httpx.AsyncClient, layer_key: str, day: str, lat: float, lon: float,
                     lookback_days: int = 3) -> tuple[bytes | None, str]:
    """Descarga el tile del día pedido; si no existe, prueba días anteriores.

    SMAP no tiene pasada diaria garantizada y los compuestos (NDVI 8 días) dejan
    huecos, así que se retrocede hasta ``lookback_days`` y se reporta la fecha usada.
    """
    target = datetime.strptime(day[:10], "%Y-%m-%d").date()
    for offset in range(lookback_days + 1):
        candidate = (target - timedelta(days=offset)).isoformat()
        url = build_tile_url(layer_key, candidate, lat, lon)
        try:
            response = await client.get(url)
            if response.status_code != 200 or not response.content:
                continue
            # Un tile puede existir (HTTP 200) y venir casi vacío: GIBS publica el
            # compuesto del día en curso antes de procesarlo. Si no hay píxeles
            # opacos, se sigue retrocediendo en el tiempo.
            if _tile_has_data(response.content):
                return response.content, candidate
        except Exception:
            continue
    return None, day


def _tile_has_data(payload: bytes, min_opaque: int = 16) -> bool:
    """¿El tile trae información real? (evita aceptar compuestos aún vacíos)."""
    try:
        from PIL import Image
        import io as _io

        image = Image.open(_io.BytesIO(payload)).convert("RGBA")
        pixels = list(image.getdata())
        opaque = sum(1 for _, _, _, alpha in pixels if alpha > 10)
        return opaque >= min_opaque
    except Exception:
        return bool(payload)  # si no se puede analizar, confiar en el 200


def _freshness(sample: dict[str, Any], lang: str = "es") -> str:
    """Aviso honesto cuando el compuesto usado no es del día pedido."""
    used, asked = sample.get("date"), sample.get("requested_date")
    if used and asked and used != asked:
        return L(lang, "freshness", used=used, asked=asked)
    return ""


def config_hint(cfg: dict[str, Any]) -> dict[str, Any]:
    """Metadatos de la capa para que el consumidor sepa qué se intentó leer."""
    return {"layer": cfg["id"], "layer_label": cfg.get("label", cfg["id"]), "units": cfg["units"]}


def _range_midpoint(text: str) -> float | None:
    """GIBS publica valores como "[0,0.1)" o "[-INF,0.000)": devuelve el punto medio."""
    raw = (text or "").strip().strip("[]()")
    parts = [p.strip() for p in raw.split(",")]
    if not parts:
        return None

    def to_float(token: str) -> float:
        upper = token.upper()
        if "INF" in upper:
            return -1e9 if "-" in upper else 1e9
        return float(token)

    try:
        values = [to_float(p) for p in parts if p]
    except ValueError:
        return None
    if not values:
        return None
    finite = [v for v in values if abs(v) < 1e8]
    if finite:
        return sum(finite) / len(finite)
    return None


async def fetch_colormap(client: httpx.AsyncClient, layer_key: str) -> list[tuple[tuple[int, int, int], float]]:
    """Lee la colormap publicada por GIBS: [(rgb, valor)]. Ignora nodata y transparentes."""
    cfg = LAYERS[layer_key]
    url = cfg.get("colormap")
    if not url:
        return []
    if url in _COLORMAP_CACHE:
        return _COLORMAP_CACHE[url]
    pairs: list[tuple[tuple[int, int, int], float]] = []
    try:
        response = await client.get(url)
        response.raise_for_status()
        root = ET.fromstring(response.text)
        for entry in root.iter():
            if entry.tag.split("}")[-1] != "ColorMapEntry":
                continue
            if entry.attrib.get("nodata", "").lower() == "true":
                continue
            if entry.attrib.get("transparent", "").lower() == "true":
                continue
            rgb = entry.attrib.get("rgb")
            if not rgb:
                continue
            source = entry.attrib.get("value") or entry.attrib.get("sourceValue")  # value = unidades físicas
            value = _range_midpoint(source) if source else None
            if value is None:
                continue
            try:
                triple = tuple(int(part) for part in rgb.replace("#", "").split(",")[:3])
            except ValueError:
                continue
            if len(triple) == 3:
                pairs.append((triple, value))  # type: ignore[arg-type]
    except Exception:
        pairs = []
    _COLORMAP_CACHE[url] = pairs
    return pairs


def _nearest_colormap_value(pairs: list[tuple[tuple[int, int, int], float]], rgb: tuple[int, int, int]) -> float | None:
    if not pairs:
        return None
    best_value, best_distance = None, float("inf")
    for triple, value in pairs:
        distance = sum((a - b) ** 2 for a, b in zip(triple, rgb))
        if distance < best_distance:
            best_value, best_distance = value, distance
    if best_distance > 2600:  # demasiado lejos de cualquier entrada: píxel no representativo
        return None
    return best_value


def _sample_pixel(image_bytes: bytes, fx: float, fy: float, window: int = 9) -> tuple[int, int, int, int, int]:
    """Mediana de una vecindad de píxeles válidos alrededor del punto.

    Un solo píxel es frágil en compuestos con máscaras (nubes, agua, sin dato):
    la mediana de la vecindad es más estable para un indicador regional.
    Devuelve (r, g, b, alfa_mediana, n_validos).
    """
    from PIL import Image  # import local: Pillow solo se necesita aquí

    image = Image.open(BytesIO(image_bytes)).convert("RGBA")
    width, height = image.size
    cx = min(width - 1, max(0, int(fx * width)))
    cy = min(height - 1, max(0, int(fy * height)))
    def median_pixels(pixels: list[tuple[int, int, int, int]]) -> tuple[int, int, int, int, int]:
        n = len(pixels)
        reds = sorted(p[0] for p in pixels)
        greens = sorted(p[1] for p in pixels)
        blues = sorted(p[2] for p in pixels)
        alphas = sorted(p[3] for p in pixels)
        return reds[n // 2], greens[n // 2], blues[n // 2], alphas[n // 2], n

    for radius in (window, window * 3, window * 7):
        pixels = []
        half = radius // 2
        for y in range(max(0, cy - half), min(height, cy + half + 1)):
            for x in range(max(0, cx - half), min(width, cx + half + 1)):
                r, g, b, a = image.getpixel((x, y))
                if a > 10:
                    pixels.append((int(r), int(g), int(b), int(a)))
        if pixels:
            return median_pixels(pixels)
    # Compuesto disperso: mediana de los píxeles válidos MÁS CERCANOS del tile.
    nearest: list[tuple[float, tuple[int, int, int, int]]] = []
    for y in range(height):
        for x in range(width):
            r, g, b, a = image.getpixel((x, y))
            if a > 10:
                nearest.append(((x - cx) ** 2 + (y - cy) ** 2, (int(r), int(g), int(b), int(a))))
    if nearest:
        nearest.sort(key=lambda item: item[0])
        return median_pixels([p for _, p in nearest[:25]])
    return 0, 0, 0, 0, 0


# --------------------------------------------------------------------------- #
# 1 · sequía (Open-Meteo / ERA5)
# --------------------------------------------------------------------------- #
def _percentile_rank(values: list[float], current: float) -> float:
    if not values:
        return 50.0
    below = sum(1 for v in values if v < current)
    equal = sum(1 for v in values if v == current)
    return 100.0 * (below + 0.5 * equal) / len(values)


# --- v0.9: etiquetas bilingües (el motor sigue siendo el mismo; sólo cambia el texto) ---
LABELS: dict[str, dict[str, str]] = {
    "es": {
        "EXCEPTIONAL": "sequía excepcional (D4)", "EXTREME": "sequía extrema (D3)",
        "SEVERE": "sequía severa (D2)", "MODERATE": "sequía moderada (D1)",
        "ABNORMALLY_DRY": "anormalmente seco (D0)", "VERY_WET": "muy húmedo",
        "WET": "húmedo", "NORMAL": "cerca de lo normal",
        "SPARSE": "suelo desnudo / vegetación muy escasa",
        "LOW": "vegetación escasa (matorral seco, pastizal)",
        "HIGH": "vegetación alta (bosque abierto, sabana)",
        "VERY_HIGH": "vegetación muy alta (bosque cerrado)",
        "MODERATE_FUEL": "vegetación moderada (pastizal denso, cultivo)",
        "CLEAN": "atmósfera limpia", "LIGHT": "aerosoles ligeros",
        "MODERATE_SMOKE": "aerosoles moderados", "HEAVY": "aerosoles densos",
        "VERY_HEAVY": "aerosoles muy densos (posible humo denso o polvo)",
        "precip": "precipitación 90 días: {mm} mm (percentil {pct} frente a {years} años)",
        "category": "categoría: {label}",
        "aridity": "demanda atmosférica ET0/precip (30 d): {value}",
        "freshness": " (compuesto de {used}; el de {asked} aún no traía datos)",
        "no_tile": "sin tile con datos para {day} ni los 3 días previos ({what} de NASA GIBS)",
        "no_pixel": "tile con datos ese día, pero sin dato válido en la vecindad (nubes, océano o máscara de calidad)",
        "page_fail": "no se pudo leer el píxel: {error}",
        "nodata": "NDVI no interpretable en ese píxel (nubes/colormap)",
        "not_enough": "el archivo ERA5 no cubre suficientes años en ese punto",
        "not_enough_years": "sin años suficientes para el percentil {window}",
        "summary_pending": "contexto incompleto",
    },
    "en": {
        "EXCEPTIONAL": "exceptional drought (D4)", "EXTREME": "extreme drought (D3)",
        "SEVERE": "severe drought (D2)", "MODERATE": "moderate drought (D1)",
        "ABNORMALLY_DRY": "abnormally dry (D0)", "VERY_WET": "very wet",
        "WET": "wet", "NORMAL": "near normal",
        "SPARSE": "bare soil / very sparse vegetation",
        "LOW": "sparse vegetation (dry shrubland, grassland)",
        "HIGH": "high vegetation (open forest, savanna)",
        "VERY_HIGH": "very high vegetation (closed forest)",
        "MODERATE_FUEL": "moderate vegetation (dense grassland, crops)",
        "CLEAN": "clean atmosphere", "LIGHT": "light aerosols",
        "MODERATE_SMOKE": "moderate aerosols", "HEAVY": "dense aerosols",
        "VERY_HEAVY": "very dense aerosols (possible dense smoke or dust)",
        "precip": "90-day rainfall: {mm} mm (percentile {pct} against {years} years)",
        "category": "category: {label}",
        "aridity": "atmospheric demand ET0/precip (30 d): {value}",
        "freshness": " (composite of {used}; the {asked} one had no data yet)",
        "no_tile": "no tile with data for {day} nor the 3 prior days ({what} from NASA GIBS)",
        "no_pixel": "tile has data that day, but no valid sample in the neighbourhood (clouds, ocean or quality mask)",
        "page_fail": "pixel read failed: {error}",
        "nodata": "NDVI not interpretable at that pixel (clouds/colormap)",
        "not_enough": "ERA5 archive does not cover enough years at that point",
        "not_enough_years": "not enough years for the {window} percentile",
        "summary_pending": "incomplete context",
    },
}
LAYER_WORDS = {"aerosol": {"es": "AOD", "en": "AOD"}, "ndvi": {"es": "NDVI", "en": "NDVI"},
               "soil": {"es": "SMAP", "en": "SMAP"}, "truecolor": {"es": "color real", "en": "true color"},
               "thermal": {"es": "anomalías térmicas", "en": "thermal anomalies"},
               "pyro": {"es": "índice PyroCb", "en": "PyroCb index"}}


def L(lang: str, key: str, **kw: object) -> str:
    table = LABELS.get("en" if str(lang).lower().startswith("en") else "es")
    text = table.get(key) or LABELS["es"].get(key) or key
    try:
        return text.format(**kw)
    except (KeyError, IndexError):
        return text


def _drought_category(percentile: float, lang: str = "es") -> tuple[str, str]:
    code = (
        "EXCEPTIONAL" if percentile <= 2 else
        "EXTREME" if percentile <= 5 else
        "SEVERE" if percentile <= 10 else
        "MODERATE" if percentile <= 20 else
        "ABNORMALLY_DRY" if percentile <= 30 else
        "VERY_WET" if percentile >= 90 else
        "WET" if percentile >= 70 else
        "NORMAL"
    )
    return code, L(lang, code)


async def drought_context(lat: float, lon: float, target: date, years: int = 10, lang: str = "es") -> dict[str, Any]:
    start = target - timedelta(days=365 * years + 30)
    params = {
        "latitude": round(lat, 3),
        "longitude": round(lon, 3),
        "start_date": start.isoformat(),
        "end_date": target.isoformat(),
        "daily": "precipitation_sum,et0_fao_evapotranspiration",
        "timezone": "UTC",
    }
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
            response = await client.get("https://archive-api.open-meteo.com/v1/archive", params=params)
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        return {"available": False, "reason": f"ERA5 archive unavailable: {exc}", "provider": "Open-Meteo ERA5 archive"}

    daily = payload.get("daily") or {}
    dates = daily.get("time") or []
    precip = daily.get("precipitation_sum") or []
    et0 = daily.get("et0_fao_evapotranspiration") or []
    if not dates:
        return {"available": False, "reason": "empty archive response", "provider": "Open-Meteo ERA5 archive"}

    series: dict[str, float] = {}
    et0_series: dict[str, float] = {}
    for i, day in enumerate(dates):
        if i < len(precip) and precip[i] is not None:
            series[day] = float(precip[i])
        if i < len(et0) and et0[i] is not None:
            et0_series[day] = float(et0[i])

    target_iso = target.isoformat()

    def window_sum(end_day: date, days: int, source: dict[str, float]) -> float | None:
        total, seen = 0.0, 0
        for offset in range(days):
            key = (end_day - timedelta(days=offset)).isoformat()
            if key in source:
                total += source[key]
                seen += 1
        return total if seen >= days * 0.8 else None

    windows: dict[str, Any] = {}
    for label, days in (("30d", 30), ("90d", 90), ("180d", 180), ("365d", 365)):
        current = window_sum(target, days, series)
        if current is None:
            continue
        history: list[float] = []
        for y in range(1, years + 1):
            try:
                end = target.replace(year=target.year - y)
            except ValueError:
                end = target.replace(year=target.year - y, day=28)
            past = window_sum(end, days, series)
            if past is not None:
                history.append(past)
        if not history:
            continue
        percentile = _percentile_rank(history, current)
        windows[label] = {
            "precip_mm": round(current, 1),
            "percentile": round(percentile, 1),
            "history_years": len(history),
            "history_mean_mm": round(statistics.fmean(history), 1),
            "category": (cat := _drought_category(percentile, lang))[0],
            "category_label": cat[1],
        }

    et0_window = window_sum(target, 30, et0_series)
    precip_window = window_sum(target, 30, series)
    aridity = None
    if et0_window is not None and precip_window is not None:
        aridity = round(et0_window / max(precip_window, 1.0), 2)

    primary = windows.get("90d") or windows.get("30d") or windows.get("180d") or windows.get("365d")
    if primary is None:
        return {"available": False, "reason": L(lang, "not_enough"), "provider": "Open-Meteo ERA5 archive"}

    ninety = windows.get("90d", {})
    evidence = [
        L(lang, "precip", mm=ninety.get("precip_mm", "—"), pct=ninety.get("percentile", "—"),
          years=ninety.get("history_years", 0)),
        L(lang, "category", label=primary["category_label"]),
    ]
    if aridity is not None:
        evidence.append(L(lang, "aridity", value=aridity))

    return {
        "available": True,
        "provider": "Open-Meteo ERA5 archive (reanálisis)",
        "method": "IGNIS transparent drought percentile; NOT SPI/SPEI/D1-D4 official product.",
        "period_end": target_iso,
        "years_compared": years,
        "windows": windows,
        "primary_window": "90d" if "90d" in windows else next(iter(windows)),
        "category": primary["category"],
        "category_label": primary["category_label"],
        "percentile": primary["percentile"],
        "aridity_et0_over_precip_30d": aridity,
        "evidence": evidence,
    }


# --------------------------------------------------------------------------- #
# 2 · combustible / vegetación  ·  3 · humo / aerosoles
# --------------------------------------------------------------------------- #
def _fuel_class(ndvi: float, lang: str = "es") -> tuple[str, str]:
    code = (
        "SPARSE" if ndvi < 0.1 else
        "LOW" if ndvi < 0.25 else
        "MODERATE" if ndvi < 0.4 else
        "HIGH" if ndvi < 0.6 else
        "VERY_HIGH"
    )
    return code, L(lang, "MODERATE_FUEL" if code == "MODERATE" else code)


def _smoke_class(aod: float, lang: str = "es") -> tuple[str, str]:
    code = (
        "CLEAN" if aod < 0.1 else
        "LIGHT" if aod < 0.25 else
        "MODERATE" if aod < 0.5 else
        "HEAVY" if aod < 1.0 else
        "VERY_HEAVY"
    )
    return code, L(lang, "MODERATE_SMOKE" if code == "MODERATE" else code)


async def sample_layer(layer_key: str, lat: float, lon: float, day: str, lang: str = "es") -> dict[str, Any]:
    cfg = LAYERS[layer_key]
    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
        (tile_bytes, used_day), colormap = await asyncio.gather(
            fetch_tile(client, layer_key, day, lat, lon),
            fetch_colormap(client, layer_key),
        )
    if tile_bytes is None:
        return {
            "available": False,
            "reason": L(lang, "no_tile", day=day, what=LAYER_WORDS.get(layer_key, {}).get("en" if str(lang).lower().startswith("en") else "es", layer_key)),
            "provider": "NASA GIBS",
            "requested_date": day,
            "date": None,
            **config_hint(cfg),
        }
    x, y, fx, fy = tile_for(lat, lon, int(cfg["level"]))
    try:
        r, g, b, a, valid = _sample_pixel(tile_bytes, fx, fy)
    except Exception as exc:
        return {"available": False, "reason": L(lang, "page_fail", error=exc), "provider": "NASA GIBS"}
    if valid == 0 or a < 10:
        return {
            "available": False,
            "reason": L(lang, "no_pixel"),
            "provider": "NASA GIBS",
            "date": used_day,
            "requested_date": day,
            "tile": {"level": cfg["level"], "x": x, "y": y},
            **config_hint(cfg),
        }
    value = _nearest_colormap_value(colormap, (r, g, b))
    return {
        "available": True,
        "provider": "NASA GIBS (WMTS)",
        "layer": cfg["id"],
        "layer_label": cfg.get("label", cfg["id"]),
        "date": used_day,
        "requested_date": day,
        "tile": {"level": cfg["level"], "x": x, "y": y},
        "rgba": [r, g, b, a],
        "valid_pixels": valid,
        "sampling": "mediana de vecindad; si el compuesto tiene huecos, mediana de los 25 píxeles válidos más cercanos",
        "value": round(value, 3) if value is not None else None,
        "units": cfg["units"],
        "method": "Color del píxel mapeado contra la colormap oficial publicada por GIBS.",
        "caveat": "Valor derivado de un tile de imagen colorizado; es contexto cualitativo, no el dato científico crudo.",
    }


async def fuel_context(lat: float, lon: float, day: str, lang: str = "es") -> dict[str, Any]:
    sample = await sample_layer("ndvi", lat, lon, day, lang)
    if not sample.get("available"):
        return sample
    ndvi = sample.get("value")
    if ndvi is None:
        return {**sample, "available": False, "reason": L(lang, "nodata")}
    label, description = _fuel_class(float(ndvi), lang)
    return {
        **sample,
        "ndvi": float(ndvi),
        "fuel_class": label,
        "fuel_label": description,
        "evidence": f"NDVI ≈ {float(ndvi):.2f} → {description}{_freshness(sample, lang)}",
    }


async def smoke_context(lat: float, lon: float, day: str, lang: str = "es") -> dict[str, Any]:
    aod_sample, pyro_sample = await asyncio.gather(
        sample_layer("aerosol", lat, lon, day, lang),
        sample_layer("pyro", lat, lon, day, lang),
    )
    out: dict[str, Any] = {"aerosol": aod_sample, "pyro_cumulonimbus": pyro_sample}
    if aod_sample.get("available") and aod_sample.get("value") is not None:
        label, description = _smoke_class(float(aod_sample["value"]), lang)
        out.update(
            available=True,
            provider="NASA GIBS · MODIS AOD + OMPS PyroCb",
            aod=float(aod_sample["value"]),
            smoke_class=label,
            smoke_label=description,
            evidence=[
                f"AOD ≈ {float(aod_sample['value']):.2f} → {description}",
                (
                    f"Índice PyroCb ≈ {float(pyro_sample['value']):.2f} (aerosoles absorbentes, típicos de humo)"
                    if pyro_sample.get("available") and pyro_sample.get("value") is not None
                    else "índice PyroCb no disponible ese día"
                ),
            ],
            caveat=(
                "AOD/PyroCb son contexto atmosférico: cerca de un evento NO prueba que el humo provenga de él, "
                "ni distingue humo de polvo/polución industrial."
            ),
        )
    else:
        out.update(available=False, reason="sin dato de aerosoles para esa fecha", provider="NASA GIBS · MODIS AOD + OMPS PyroCb")
    return out


# --------------------------------------------------------------------------- #
# orquestación
# --------------------------------------------------------------------------- #
async def build_environment_intelligence(lat: float, lon: float, iso_date: str, *, include_drought: bool = True, lang: str = "es") -> dict[str, Any]:
    try:
        target = datetime.strptime(iso_date[:10], "%Y-%m-%d").date()
    except ValueError:
        target = date.today()
    day = target.isoformat()

    tasks: list[Any] = [fuel_context(lat, lon, day, lang), smoke_context(lat, lon, day, lang)]
    if include_drought:
        tasks.append(drought_context(lat, lon, target, lang=lang))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    fuel, smoke = results[0], results[1]
    drought = results[2] if include_drought else {"available": False, "reason": "omitido" if lang != "en" else "skipped"}
    for name, value in (("fuel", fuel), ("smoke", smoke), ("drought", drought)):
        if isinstance(value, Exception):
            results_map = {"fuel": {}, "smoke": {}, "drought": {}}
            results_map[name] = {"available": False, "reason": str(value)}
            if name == "fuel":
                fuel = results_map[name]
            elif name == "smoke":
                smoke = results_map[name]
            else:
                drought = results_map[name]

    available = [name for name, block in (("drought", drought), ("fuel", fuel), ("smoke", smoke)) if isinstance(block, dict) and block.get("available")]
    warnings = [
        f"{name}: {block.get('reason')}"
        for name, block in (("drought", drought), ("fuel", fuel), ("smoke", smoke))
        if isinstance(block, dict) and not block.get("available") and block.get("reason")
    ]

    return {
        "version": "0.9.1",
        "engine": "environmental-intelligence",
        "lat": round(lat, 5),
        "lon": round(lon, 5),
        "date": day,
        "available": available,
        "drought": drought,
        "fuel": fuel,
        "smoke": smoke,
        "warnings": warnings,
        "summary": {
            "drought": drought.get("category_label") if isinstance(drought, dict) and drought.get("available") else None,
            "fuel": fuel.get("fuel_label") if isinstance(fuel, dict) and fuel.get("available") else None,
            "smoke": smoke.get("smoke_label") if isinstance(smoke, dict) and smoke.get("available") else None,
        },
        "lang": "en" if str(lang).lower().startswith("en") else "es",
        "caveat": (
            "Analytical environmental context: drought by rainfall percentile, vegetation by NDVI, aerosols by AOD/OMPS. "
            "None of these is an operational fire-danger product, and co-located smoke does not attribute cause."
            if str(lang).lower().startswith("en") else
            "Contexto ambiental analítico: sequía por percentil de precipitación, vegetación por NDVI y aerosoles por AOD/OMPS. "
            "Ninguno es un producto operativo de peligro de incendio y la co-localización de humo no atribuye causa."
        ),
    }
