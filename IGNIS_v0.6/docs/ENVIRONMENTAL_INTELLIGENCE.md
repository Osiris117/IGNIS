# IGNIS v0.8 — Environmental Intelligence

> "Los satélites nos dan observaciones. IGNIS las convierte en entendimiento."
> La v0.8 añade el **contexto ambiental** de cada evento persistente: qué tan seco
> está el terreno, cuánto combustible vegetal hay y qué se está respirando en el aire.

Este documento describe **qué mide**, **con qué fuente**, **cómo se calcula** y
**qué NO se puede afirmar**. Todo dato numérico que muestra la interfaz es
trazable a una fuente pública y a una fecha concreta.

---

## 1. Las tres preguntas

| Pregunta | Capa | Fuente | Producto |
|---|---|---|---|
| ¿El terreno está seco? | Sequía | Open-Meteo ERA5 (reanálisis) | percentil de precipitación 30/90/180/365 días |
| ¿Hay combustible vegetal? | Vegetación / fuel | NASA GIBS | MODIS Terra NDVI compuesto de 8 días (250 m) |
| ¿Hay humo o aerosoles? | Humo | NASA GIBS | MODIS Terra AOD (2 km) + OMPS PyroCb (2 km) |

Complementos presentes en el motor (no siempre con datos útiles): humedad de suelo
SMAP (`SMAP_L3_Passive_Day_Soil_Moisture`) y anomalías térmicas MODIS
(`MODIS_Terra_Thermal_Anomalies_All`).

---

## 2. Cómo se calcula

### 2.1 Sequía — percentil contra la propia historia del lugar
- Se descarga el archivo diario de ERA5 para el punto exacto (precipitación y ET0).
- Se acumulan ventanas de **30, 90, 180 y 365 días**.
- Cada acumulado se compara con **los mismos acumulados de hasta 10 años previos**
  en ese mismo punto: se reporta el **percentil** (no un umbral universal).
- Categorías: `EXCEPTIONAL` → `EXTREME` → `SEVERE` → `MODERATE` → `ABNORMALLY_DRY`
  → `NEAR_NORMAL` → húmedas.
- Se añade el cociente **ET0 / precipitación** (demanda atmosférica vs. agua recibida).

*Ejemplo verificado (Chiapas, 2026-10-05):* 289.1 mm en 90 días → percentil 11.1
frente a 9 años de historia → **sequía moderada**.

### 2.2 Vegetación / combustible — NDVI coloreado
- Tile WMTS de GIBS `MODIS_Terra_NDVI_8Day` (compuesto de 8 días, 250 m).
- El color del píxel se traduce a valor físico con la **colormap oficial** de GIBS,
  usando el atributo `value` (unidades NDVI), **nunca** `sourceValue` (escala ×10⁴).
- Clases: `<0.10` SPARSE · `<0.25` LOW · `<0.40` MODERATE · `<0.60` HIGH · `≥0.60` VERY_HIGH.

*Validación geográfica ejecutada:* CDMX 0.098 (urbano) · Chiapas 0.765 (selva) ·
Sahara 0.123 (desierto) · Mato Grosso 0.695 (cerrado/Amazonía).

### 2.3 Humo — AOD + piro-cumulonimbos
- AOD (profundidad óptica de aerosol) → `CLEAN` < 0.10 · `LIGHT` < 0.25 ·
  `MODERATE` < 0.50 · `HEAVY` < 1.00 · `VERY_HEAVY` ≥ 1.00.
- PyroCb (OMPS) se reporta aparte: marca aerosoles de **incendios convectivos**.

### 2.4 Muestreo robusto (lo que costó depurarlo)
1. **Grilla GIBS**: no es una grilla 2ⁿ. Se usa la grilla real verificada
   (L0 2×1 … L8 320×160) con `tile_for()`.
2. **Orden del REST de GIBS**: `/{TileMatrix}/{TileRow}/{TileCol}` — la **fila
   (latitud) va antes que la columna**. Invertirlas devuelve tiles válidos de otra
   parte del mundo (bug real detectado: CDMX "leía" Brasil).
3. **Mediana de vecindad** (9→27→63 px) y, si hay huecos, mediana de los 25 píxeles
   válidos más cercanos; se reporta `valid_pixels`.
4. **Lookback con validación de contenido**: si el tile del día pedido no existe
   (404) *o existe pero viene vacío* (GIBS publica el compuesto del día en curso
   antes de procesarlo), se retrocede hasta 3 días. La respuesta indica
   `date` (usado) y `requested_date` (pedido).

---

## 3. API

| Endpoint | Parámetros | Devuelve |
|---|---|---|
| `GET /api/environment/catalog` | — | Capas GIBS verificadas con su TileMatrixSet |
| `GET /api/environment/intelligence` | `lat`, `lon`, `event_date` (YYYY-MM-DD), `drought` (bool) | Contexto completo por evento |

Estructura típica:

```json
{
  "available": ["drought", "fuel", "smoke"],
  "summary": {
    "drought": "cerca de lo normal",
    "fuel": "vegetación muy alta (bosque cerrado)",
    "smoke": "aerosoles ligeros"
  },
  "fuel": { "ndvi": 0.82, "fuel_class": "VERY_HIGH",
            "evidence": "NDVI ≈ 0.82 → vegetación muy alta (bosque cerrado) (compuesto de 2026-10-06; el de 2026-10-07 aún no traía datos)",
            "date": "2026-10-06", "requested_date": "2026-10-07" },
  "caveat": "Contexto ambiental derivado de productos satelitales públicos; no es un producto operativo ni un pronóstico de peligro."
}
```

Cada capa **degrada con dignidad**: si no hay dato, responde
`{"available": false, "reason": "<explicación>", "date": ..., "requested_date": ...}`
en lugar de inventar un valor.

---

## 4. Capas sobre el globo (UI)

Chips conmutables en el panel izquierdo (`05 ENVIRONMENTAL LAYERS`):

| Chip | Producto GIBS | TileMatrixSet | α |
|---|---|---|---|
| AEROSOLES | `MODIS_Terra_Aerosol` | 2km | 0.72 |
| VEGETACIÓN | `MODIS_Terra_NDVI_8Day` | 250m | 0.82 |
| COLOR REAL | `MODIS_Terra_CorrectedReflectance_TrueColor` | 250m | 0.92 |
| PIRO-CB · HUMO | `OMPS_Aerosol_Index_PyroCumuloNimbus` | 2km | 0.42 |

- La fecha de la capa **sigue el timeline** (`refreshEnvLayers()` al cambiar de frame).
- Se arranca con 1 día de rezago (`lagDays`) porque los compuestos de GIBS se
  publican con retraso; si aun así falla, se retrocede día a día (máx. 3).
- Si GIBS no responde (demo sin internet), el chip se marca en rojo y el análisis
  sigue funcionando: **las capas son contexto visual, no dependencia crítica**.

---

## 5. Límites declarados (importante para el jurado)

1. El NDVI/AOD se leen del **tile colorizado**, no del HDF/NetCDF científico:
   el valor es una **aproximación cualitativa** derivada de la colormap oficial.
2. El percentil de sequía es **relativo al propio registro** del punto: un mismo
   número puede significar cosas distintas en Chiapas y en Mato Grosso.
3. Las capas GIBS requieren internet. En modo offline quedan desactivadas por diseño.
4. Nada de esto **confirma un incendio** ni predice propagación: describe el
   entorno en el que se observaron anomalías térmicas.
5. SMAP de humedad de suelo tiene cobertura intermitente: se reporta solo cuando
   hay píxel válido.
