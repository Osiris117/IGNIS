# IGNIS v0.7 — Demo offline de verdad (con datos NASA reales)

Objetivo: abrir IGNIS en un hackathon **sin internet** y que el globo, el
timeline, los eventos, la evolución y el archivo funcionen igual.

## Qué se vendorizó en v0.7

| Componente | Antes (v0.6) | Ahora (v0.7) |
|---|---|---|
| CesiumJS 1.126 | CDN jsDelivr | `static/vendor/cesium/` (13 MB, 374 archivos) |
| Imagen base del globo | Tiles de OpenStreetMap (CDN) | Natural Earth II local (`Assets/Textures/NaturalEarthII`) |
| Cielo / estrellas | Desactivado | SkyBox local (`Assets/SkyBox`) |
| Post-proceso | — | FXAA + Bloom locales |

Verificado en navegador real: **cero peticiones externas** al cargar la UI.

## Cómo se prepara el archivo de datos reales (una vez, con internet)

El servicio de **CSV masivos** de NASA FIRMS es público y **no requiere
MAP_KEY** (a diferencia de la API `area`):

```bash
cd IGNIS_v0.6
python tools/fetch_firms_snapshot.py            # 7 días global, MODIS + VIIRS
```

Equivalente manual:

```bash
curl -O https://firms.modaps.eosdis.nasa.gov/data/active_fire/modis-c6.1/csv/MODIS_C6_1_Global_7d.csv
curl -O https://firms.modaps.eosdis.nasa.gov/data/active_fire/suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_Global_7d.csv
python import_firms_archive.py MODIS_C6_1_Global_7d.csv --source MODIS_SP
python import_firms_archive.py SUOMI_VIIRS_C2_Global_7d.csv --source VIIRS_SNPP_SP
```

Resultado medido el 2026-10-07:

| Métrica | Valor |
|---|---|
| MODIS C6.1 7d | 5.0 MB · 64,565 observaciones |
| Suomi-NPP VIIRS C2 7d | 26.8 MB · 327,831 observaciones |
| Import total (ambos) | **~4 s** |
| DuckDB resultante | 37 MB (392,396 observaciones, 2026-09-30 → 2026-10-07) |

## Flujo de demo sin internet

```text
1. Arrancar:      python -m uvicorn backend.app:app --host 0.0.0.0 --port 8010
2. UI:            LOAD FIRE EVOLUTION (v0.7)        → escenario sintético narrado
3. Datos reales:  TRACK LOCAL ARCHIVE · REAL NASA DATA → pistas sobre FIRMS real
4. Explorar:      clic en un track → dossier + REPLAY LIFECYCLE
5. Exportar:      EXPORT INTELLIGENCE SNAPSHOT (JSON con tracks y confianza)
6. Calendario:    BURNING ACTIVITY CALENDAR → modo LOCAL ARCHIVE
```

Con los datos de ejemplo de arriba, el paso 3 produce en México:
**227 pistas persistentes · 92 multi-frame · 12 EXPANDING · 18 DECLINING** y
~286 hotspots reales en modo HOTSPOTS (cifras del 2026-10-07; cambian con cada
descarga porque el servicio es de 7 días móviles).

## Qué sigue necesitando internet (a propósito)

| Función | Dependencia |
|---|---|
| `NASA · HARMONIZE REGION` (API por región, históricos largos) | `FIRMS_MAP_KEY` |
| `BURNING ACTIVITY CALENDAR` en modo NASA SAMPLE | `FIRMS_MAP_KEY` |
| Contexto ambiental de eventos (ERA5-Land / CAMS) | Open-Meteo |

Todo eso es **backend**: cuando no hay red, IGNIS degrada con avisos explícitos y
la demo sigue funcionando con archivo local + escenarios sintéticos.

## Nota de latencia y cobertura

Los CSV masivos tienen ~3 h de latencia y son globales. Para regiones
específicas o ventanas históricas largas, sigue siendo mejor la API con MAP_KEY
(`import_firms_archive.py` acepta cualquier CSV/TXT/ZIP de FIRMS del portal
`firms.modaps.eosdis.nasa.gov/download`). Los dos caminos escriben en el mismo
archivo DuckDB, así que se pueden mezclar.
