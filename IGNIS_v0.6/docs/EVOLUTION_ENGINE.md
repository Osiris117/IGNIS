# IGNIS v0.7 — Fire Evolution Engine

## Propósito

v0.7 convierte los *candidate fire events* de v0.6 (grupos espacio-temporales de
anomalías térmicas) en **eventos con identidad persistente y ciclo de vida**.
El objetivo es poder responder: *¿qué está pasando, cómo evolucionó, y qué tan
seguro estamos de que es el mismo fenómeno?*

Todo el motor mantiene la regla interpretativa del proyecto: nada de esto es un
incendio confirmado ni un perímetro oficial.

## 1. Identidad persistente

Cada cluster candidato recibe un identificador estable `IGN-<año>-<secuencia>`
(p. ej. `IGN-2026-0008`) mediante un registro local:

```text
data/events/track_registry.json
```

Reglas de vínculo (`LINKING`):

- un cluster nuevo se une a una pista existente si su centroide cae dentro de
  `IGNIS_TRACK_MATCH_KM` (por defecto **60 km**) de la última posición conocida;
- y si la separación temporal entre observaciones es menor que
  `IGNIS_TRACK_MAX_GAP_HOURS` (por defecto **48 h**);
- como máximo **un frame por pista** (una observación por ciclo de paso satelital).

En una misma sesión de carga, si un cluster aparece "cerca en el tiempo y el
espacio" de una identidad reciente del mismo dataset, se reutiliza el ID de
registro (`identity: "reused"`). Esto es lo que permite re-ejecutar el análisis
sin multiplicar identidades: **la identidad es persistente, pero sigue siendo
una etiqueta analítica heurística**, no un ID oficial de incidente.

## 2. Ciclo de vida (clasificación de estado)

La intensidad por frame es

```text
intensity(frame) = detections × (1 + min(total_FRP, 600) / 600)
```

—es decir, ponderada por detecciones y no solo por FRP, porque un pico de FRP en
una sola pasada no equivale a un evento sostenido.

Comparando el último frame observado contra el anterior:

| Δ intensidad | Estado | Significado |
|---|---|---|
| sin frame actual y gap > 0 | `EXTINCT` | no hay detecciones vinculadas en el frame más reciente |
| ≥ +20 % | `EXPANDING` | actividad al alza |
| entre −20 % y +20 % | `STABLE` | actividad sostenida |
| ≤ −20 % | `DECLINING` | actividad a la baja |
| 1 solo frame | `EMERGING` | recién detectado |

Umbral configurable con `IGNIS_TRACK_STATE_DELTA`.

## 3. Movimiento aparente (no es propagación)

Con los centroides por frame se calcula:

- desplazamiento neto (`net_displacement_km`) y rumbo (`bearing_deg` / brújula);
- recorrido acumulado (`path_km`) y velocidad media (`mean_speed_kmh`).

**Advertencia metodológica explícita en la API y la UI:** esto es *deriva
aparente del centroide entre pasadas satelitales*. No es un modelo de
propagación de incendio, no estima velocidad de avance del frente y no debe
usarse para pronóstico de comportamiento del fuego.

## 4. Event Confidence Score (explicable)

`confidence()` devuelve score 0–100 **con sus componentes y la evidencia**:

| Componente | Peso | Normalización |
|---|---|---|
| Detecciones | 26 % | saturación a 50 |
| Persistencia | 22 % | 60 % duración (48 h) + 40 % frames (5) |
| Independencia de sensores | 18 % | 0 familias = 0 · 1 = 55 · 2 = 87 · 3+ = 100 |
| FRP pico | 18 % | saturación a 120 MW |
| Confianza declarada | 16 % | media de la confianza FIRMS normalizada |

La UI muestra las cinco barras + la lista de razones ("61 detecciones en 5
frames", "persistencia 96 h", "2 familias de sensores", …). El método está
marcado como heurística transparente, **no** como probabilidad oficial.

## 5. Tracks, trails y replay

- `trail`: posiciones por frame (para dibujar la estela sobre el globo).
- `timeline`: métricas por frame (para el gráfico de ciclo de vida).
- `per_frame`: clusters crudos de cada frame, para auditoría.

En el globo, el modo **EVOLUTION** dibuja la estela con alfa creciente hacia el
presente, el anillo de dispersión del último frame observado y el estado por
color (naranja = expanding, verde = stable, cian = declining, ámbar = emerging,
gris = extinct). `REPLAY LIFECYCLE` recorre los frames del track con cámara
cinematográfica para narrar el evento.

## 6. Endpoints

```text
GET /api/evolution/demo?region=mexico|amazon&days=3..10
GET /api/evolution/archive?area=...&start_date=...&days=2..31
```

`/api/evolution/archive` construye frames por día desde el archivo DuckDB local
(observaciones FIRMS reales o del usuario) y deriva los indicadores de panel
desde los propios eventos cuando no existe malla de armonización.

## 7. Límites conocidos (honestidad metodológica)

1. La identidad persistente es heurística: con `match_km` alto, dos eventos
   distintos y cercanos pueden fusionarse; con uno bajo, un evento grande puede
   fragmentarse. El registro guarda `reuses` para poder auditar ese efecto.
2. La ventana de vínculo es transitiva: un evento puede encadenar frames
   mientras cada salto sea menor que `MAX_GAP_HOURS` (igual que en v0.6).
3. La clasificación de estado depende del muestreo: con `days=7` (pasadas
   diarias) un evento de vida corta puede verse como `EMERGING → EXTINCT`.
4. `deriva aparente` ≠ propagación; con eventos grandes, el centroide puede
   moverse aunque el frente no avance.
5. El score de confianza pondera evidencia satelital, no verificación en campo.
