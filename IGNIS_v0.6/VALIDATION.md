# IGNIS — Validation Notes

## v0.7 validation (2026-10-07)

Entorno: sandbox Linux + Chromium headless (Playwright) con WebGL por software
(SwiftShader), Cesium 1.126 vendorizado, Python 3.13, DuckDB 1.5.6.

### Navegador real (no solo curl)

| Comprobación | Resultado |
|---|---|
| Carga completa de la UI con Cesium local | OK · **0 peticiones externas** |
| Capas de imagen del globo | `imageryLayers = 1` · `layer.ready = true` · `tilesLoaded = true` |
| Post-proceso cinematográfico | `skyBox = true` · `bloom = true` · `fxaa = true` |
| Errores de consola / peticiones fallidas | **0 / 0** en todas las corridas |
| Modo EVOLUTION con datos sintéticos | 4 pistas · 4 filas en panel · gráfico de 5 barras · 5 barras de confianza · 6 líneas de evidencia |
| Banner de seguimiento + reticle + líder | visibles, 8 nodos SVG, sin solaparse con el dossier (verificado por geometría de pantalla) |
| Modo EVOLUTION con archivo NASA real | 227 pistas · 640 entidades de estela · 227 marcadores |
| Modo HOTSPOTS con archivo NASA real | 286 detecciones visibles |
| Estelas tras el fix de imagen | visibles con alfa creciente por frame |

### Bug crítico encontrado y corregido (v0.6 → v0.7)

`imageryProvider` como opción del `Viewer` **fue eliminada en Cesium 1.104** y se
ignora en silencio. Prueba A/B en el mismo navegador y versión:

| Construcción | `imageryLayers.length` |
|---|---|
| `imageryProvider: new Cesium.OpenStreetMapImageryProvider(...)` (código v0.6) | **0** |
| `baseLayer: Cesium.ImageryLayer.fromProviderAsync(...)` (v0.7) | **1** (ready) |

Consecuencia en v0.6: el globo se dibujaba únicamente con `globe.baseColor`
(`#07100d`) — el "planeta oscuro" no era decisión estética.

### Motor de evolución — datos reales (no sintéticos)

Snapshot FIRMS vía servicio masivo público (sin MAP_KEY):

| Producto | Tamaño | Observaciones | Import |
|---|---|---|---|
| MODIS C6.1 Global 7d | 5.0 MB | 64,565 | 1.8 s |
| Suomi-NPP VIIRS C2 Global 7d | 26.8 MB | 327,831 | 2.1 s |
| **Total en DuckDB** | — | **392,396** (2026-09-30 → 2026-10-07) | **~4 s** |

Ejecución con `area = México (-118,14,-86,33)`, 8 días:

- 227 pistas persistentes · 92 multi-frame · 640 entidades de estela.
- Estados: `EXPANDING 12 · DECLINING 18 · STABLE 5 · EMERGING 7 · EXTINCT 185`.
- Mejor pista seleccionada automáticamente: `IGN-2026-0008 EXPANDING`, 694
  detecciones en 7 frames, 168 h, MODIS + VIIRS, confianza **93 % (HIGH)**.
- Calendario del archivo (México, 2026): septiembre 192 detecciones · octubre
  473 detecciones (meses anteriores a la ventana importada aparecen como no
  disponibles, no como ceros falsos).

### Correcciones de contrato de API en esta ronda

- `GET /api/evolution/demo` devolvía **500** (`KeyError: 'events'`): los frames
  sintéticos no llevan clave `events` (se construye en `per_frame`). Corregido y
  verificado con `TestClient` y servidor real: **200** en `region=mexico|amazon`.
- `GET /api/evolution/archive` con archivo vacío: **400** con mensaje explícito
  (no 500).
- Frames de archivo ahora derivan `summary.activity_mean` y
  `summary.agreement_cells` desde los propios eventos (antes el panel mostraba
  0.0 y 0 aunque hubiera eventos).

### Workflow validado

```text
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8010
→ LOAD FIRE EVOLUTION (v0.7)          → escenario sintético narrado (EMERGING→EXTINCT)
→ TRACK LOCAL ARCHIVE · REAL NASA DATA → pistas sobre FIRMS real
→ clic en pista → dossier + REPLAY LIFECYCLE
→ EXPORT INTELLIGENCE SNAPSHOT         → JSON con tracks, confianza y caveats
```

---

## v0.6 validation (ronda anterior, entorno de build)

- Python compile check: passed (`backend`, launcher and importer).
- JavaScript syntax check with Node: passed.
- HTML/JavaScript ID-reference consistency: 82 JS DOM references, 0 missing IDs.
- FastAPI health endpoint: HTTP 200, version `0.6.0`.
- FastAPI config endpoint: HTTP 200.
- Harmonized analytical demo: HTTP 200, 5 temporal frames.
- Candidate-event layer: 30 candidate events generated in the packaged synthetic demo.
- Candidate-event caveat metadata: present on every demo event.
- Burning Activity Calendar demo: HTTP 200.
- Local Archive status route: HTTP 200 even with an empty archive.
- Real Uvicorn server startup on localhost: passed.
- Root UI route: HTTP 200.
- Event clustering performance smoke test: ~20,000 synthetic observations clustered successfully using the temporal-pruned spatial index.
- Environmental-context endpoint logic tested with a deterministic local stub, including cache hit behavior.

### Autopsia de esa ronda (hecha en v0.7)

- **Context engine con red real: nunca se había probado.** Verificado ahora:
  `lat=34.05, lon=-118.24, 2026-10-05` → Open-Meteo recent blend, Tmax 39.3 °C,
  RH min 20 %, VPD 3.28 kPa, **dryness 81.7 "very dry"** (5/5 componentes);
  `lat=19.43, lon=-99.13, 2024-06-15` → ERA5 reanalysis, Tmax 28.7 °C, dryness
  74.3. CAMS: `available: true`, PM2.5 18.3 µg/m³, AOD 0.08. Sin warnings.
- **CesiumJS desde CDN**: resuelto en v0.7 (vendorizado local).
- **`.env.example` inexistente**: añadido.
- **`.gitignore` inexistente**: añadido (protege `.env` con la MAP_KEY y evita
  commitear el DuckDB local).


---

## Validación v0.8 — Environmental Intelligence

### 1. NDVI contra conocimiento geográfico (test ejecutado, 2026-10-06)
| Punto | NDVI medido | Esperado | Resultado |
|---|---|---|---|
| CDMX (urbano) | 0.098 | < 0.45 | ✓ |
| Chiapas (selva Lacandona) | 0.765 | > 0.55 | ✓ |
| Sahara (desierto) | 0.123 | < 0.25 | ✓ |
| Mato Grosso (cerrado) | 0.695 | alto | ✓ |

### 2. Sequía (percentiles reales, ERA5)
| Punto | Ventana | Precipitación | Percentil | Categoría |
|---|---|---|---|---|
| CDMX | 30 d | 281.9 mm | 90.0 | muy húmedo |
| CDMX | 365 d | 1366.3 mm | 88.9 | húmedo |
| Mato Grosso | 90 d | 62.1 mm | 44.4 | cerca de lo normal (media histórica 58.3, 9 años) |
| Chiapas | 90 d | 289.1 mm | 11.1 | sequía moderada (D1) |

### 3. Bugs corregidos en esta versión
- **Orden fila/columna en el REST de GIBS**: `/{TileMatrix}/{TileRow}/{TileCol}`.
  Con el orden invertido los tiles eran válidos pero de **otra región** (CDMX
  "leía" el NDVI de Brasil). Corregido y cubierto por la validación geográfica.
- **`{Time}` no sustituido**: Cesium enviaba la URL con `%7BTime%7D` (HTTP 400).
  La fecha ahora va literal y la capa se recrea al mover el timeline.
- **Tiles vacíos aceptados**: GIBS devuelve 200 con un compuesto aún sin procesar.
  Ahora se valida contenido (píxeles opacos) antes de aceptar y, si no, se
  retrocede en el tiempo (hasta 3 días), reportando `date` vs `requested_date`.
- **Falso positivo del watchdog 3D**: `scene.renderError` es un Event de Cesium y
  bastaba un suscriptor interno para activar el aviso "MODO SEGURO" con el globo
  funcionando. Ahora el criterio es si el globo **deja de dibujar cuadros**.
- **Colormap**: se usa el atributo `value` (unidades físicas) y no `sourceValue`
  (escalado ×10⁴), que producía AOD 192.5 en lugar de ~0.1.

### 4. Prueba dentro del iframe sandbox (entorno real del preview)
`overlayVisible:false` · `renderer:"WEBGL · SW · SANDBOX"` · tiles GIBS 200 ·
capas activas sin fallos · consola sin errores · dossier con bloque ENTORNO
poblado (sequía 22.2 %, NDVI 0.82, AOD 0.19).
