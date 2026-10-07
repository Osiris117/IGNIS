# IGNIS v0.9 — Intelligence Analyst

> "Los satélites nos dan observaciones. IGNIS las convierte en entendimiento."
> La v0.9 convierte los números de la v0.7 (evolución de eventos) y la v0.8
> (contexto ambiental) en un **briefing legible y explicable**, en español o inglés.

## El principio: cada frase lleva su recibo

No hay modelo generativo. Son **plantillas deterministas** rellenadas con métricas
medidas; cada frase viaja con la lista de **citas** que la sostienen (métrica,
valor, unidad y fuente). Si un dato no existe, la frase no se escribe.

```json
{ "id": "activity",
  "block": "activity",
  "text": "IGN-2026-0008 se expande: la intensidad subió 93% entre la primera y la última observación.",
  "citations": [ { "metric": "intensity_delta_pct", "value": 93.0, "unit": "%",
                   "source": "IGNIS Fire Evolution Engine" } ] }
```

## Estructura del briefing

| Bloque | Qué dice | Fuente de los datos |
|---|---|---|
| `activity` | Titular de estado (EXPANDING / DECLINING / STABLE / EMERGING / EXTINCT) + detecciones, FRP pico | Motor de evolución v0.7 · NASA FIRMS |
| `sensors` | Cuántas familias de sensores coinciden y su confianza media | Metadatos FIRMS (MODIS / VIIRS) |
| `motion` | Deriva aparente del centroide (km, rumbo, velocidad media) — **no** es un modelo de propagación | Análisis de centroides IGNIS |
| `environment` | Sequía (percentil ERA5), combustible (NDVI), humo (AOD) y PyroCb | v0.8 · Open-Meteo ERA5 + NASA GIBS |
| `baseline` | Contexto histórico del mismo mes y zona | Archivo local DuckDB (o FIRMS en vivo con `FIRMS_MAP_KEY`) |
| `confidence` | Score explicable con el peso de cada componente | Modelo de confianza v0.7 |
| `uncertainty` | Qué limita este caso concreto (pocas observaciones, un solo sensor, sin vector de deriva…) | Derivado de los propios datos |

Además se devuelven **índices contextuales 0-100** (`dryness_index`, `fuel_index`,
`smoke_index`, `environmental_context_index`) para la barra superior del panel.

## API

```http
POST /api/analyst/briefing
{ "track": { ...registro del motor de evolución... },
  "lang": "es", "environment": true, "baseline": true, "baseline_years": 10 }

GET /api/analyst/sample?lang=es     # briefing de ejemplo (demo sintética) para
                                    # que la interfaz muestre algo sin selección
GET /api/environment/intelligence?lat&lon&event_date&lang=es   # v0.8, ahora bilingüe
```

Respuesta: `headline`, `sentences[]` (con `citations[]`), `scores`, `environment`,
`baseline`, `method`, `caveats`. Los números se formatean con el separador decimal
del idioma (ES: `65,4 %` · EN: `65.4 %`).

## Interfaz

- **Botón `06 INTELLIGENCE ANALYST → GENERATE BRIEFING`**: abre el panel con el
  briefing del último evento seleccionado (o de un ejemplo si no hay ninguno).
- Cada línea trae su etiqueta de bloque (`ACT`, `SENS`, `DRIFT`, `ENV`, `HIST`,
  `CONF`, `UNC`) y debajo las **citas** en formato `métrica · valor · fuente`.
- `COPY` copia el briefing completo al portapapeles.
- Los pies del panel recuerdan el método y los límites del producto.

## Bilingüismo (ES / EN)

- Selector `ES | EN` en la barra superior; el idioma se guarda (si el navegador lo
  permite) y por defecto sigue el idioma del sistema.
- Traduce **toda** la superficie: cabecera, paneles, botones, opciones de los
  selectores, avisos flotantes, notas del calendario, etiquetas de estado, los
  textos de evidencia del motor ambiental y el briefing completo.
- Los **nombres propios de las fuentes** no se traducen a propósito
  ("IGNIS Fire Evolution Engine", "FIRMS confidence field", "Open-Meteo ERA5
  archive"): son identificadores verificables.

## Modo claro / oscuro

- Botón `◐` en la barra superior. El tema oscuro es el original tipo *mission
  control*; el claro usa el mismo diseño sobre fondo claro (pensado para proyector
  o sala iluminada).
- El tema claro se genera de forma sistemática a partir de los colores del oscuro
  (paleta verde/cian, viñeta y líneas de escaneo atenuadas) y ajusta el globo 3D:
  brillo y gamma de las imágenes base, sin iluminación solar, sin bloom/HDR, y
  `baseColor`/`backgroundColor` claros para que el Cesium no quede negro.
- Si Cesium no está disponible, el resto de la interfaz cambia igual.

## Límites (igual de explícitos que en la v0.8)

1. Las frases describen **anomalías térmicas candidatas**; no confirman incendios.
2. La deriva del centroide es **aparente**, entre pasadas de satélite.
3. El ancla histórica usa MODIS de forma deliberada por consistencia temporal.
4. Si no hay datos suficientes, el briefing **lo dice** en vez de rellenar.
5. Producto de contexto: no usar para decisiones de vida o seguridad.
