# IGNIS v0.9.1 → v0.9.4 — Auditoría de fallas y correcciones

Fecha de la auditoría: 2026-10-08. Las secciones A–F conservan el historial
de cambios y pruebas recibido con el proyecto. La sección G documenta la
revisión adicional sobre esa copia; sus resultados reproducibles y las
limitaciones se detallan al final.

---

## A. Fallas de renderizado (las que se ven en el globo)

### A1 · Capas ambientales GIBS dibujadas en el lugar equivocado — **CRÍTICA**
**Archivo:** `static/app.js` (`ENV_CATALOG`, `addEnvLayer`)

Las 4 capas ambientales (Aerosoles, NDVI, Color Real, Pyro-CB) se pedían al endpoint
`epsg4326` de GIBS con una `Cesium.GeographicTilingScheme`, que asume una rejilla de
potencias de dos (nivel L → 2^(L+1) × 2^L tiles). Verificado contra las
`WMTSCapabilities.xml` en vivo: los TileMatrixSet 4326 de GIBS **no son potencias de dos**
(nivel 1 = 3×2, nivel 2 = 5×3, nivel 5 = 40×20). Cesium pedía tiles con índices de una
rejilla y GIBS los interpretaba con otra → las capas caían desplazadas/estiradas sobre
otra parte del mundo, o devolvían 404 y el reintento las eliminaba.

**Corrección:** migración al endpoint `epsg3857` con los TileMatrixSet
`GoogleMapsCompatible_Level6/9`, cuya rejilla estándar (2^L × 2^L) calza exactamente con
`WebMercatorTilingScheme`. Verificado con peticiones reales: las 4 capas devuelven
`HTTP 200 image/png|jpeg` con la nueva ruta. Se eliminó también el `customTags:{Time}`
muerto (la fecha ya viaja literal en la URL) y el campo `matrix` obsoleto del catálogo.

### A2 · El HUD reticle medía el doble en pantallas HiDPI
**Archivo:** `static/app.js` (`videoR`)

El SVG del HUD opera en píxeles CSS (igual que `worldToWindowCoordinates` y
`getBoundingClientRect`), pero el radio se multiplicaba por `devicePixelRatio` → en
pantallas retina el reticle/soporte del evento seguido salía gigante y desalineado.
Corregido a radio constante en px CSS.

### A3 · Las capas GIBS se recreaban en cada frame del timeline
**Archivo:** `static/app.js` (`refreshEnvLayers`)

Al reproducir el timeline con una capa activa, cada frame destruía y recreaba los
providers (spam de peticiones a GIBS, parpadeo, cuota). Ahora sólo se recrean cuando
cambia la fecha del frame.

### A4 · El botón PLAY hacía doble toggle con la barra espaciadora
**Archivo:** `static/app.js` (atajos de teclado)

Con el botón enfocado, el espacio disparaba el handler global **y** el click nativo del
botón (STOP→PLAY en el mismo pulso). Ahora el handler cede el espacio a los botones.

### A5 · Celda de calendario del mes en curso → error 400
**Archivos:** `static/app.js` (`selectCalendarCell`)

El calendario marca como disponible el mes actual; su celda apunta al día 10, que puede
ser futuro. El backend rechaza fechas futuras (`_safe_date`) con 400 y la selección moría
en un toast de error. Ahora la fecha se recorta a hoy antes de cargar.

### A6 · La descarga del snapshot no funcionaba en Firefox
**Archivo:** `static/app.js` (`exportSnapshot`)

`a.click()` sin anexar el `<a>` al DOM no dispara la descarga en Firefox. Corregido
(append + click + remove). Además el JSON exportado decía `ignis_version:'0.7.0'`;
ahora usa la versión real del backend.

---

## B. Fallas de lógica / datos

### B1 · Severidad de pista invertida — **CRÍTICA**
**Archivo:** `backend/evolution_engine.py`

`max((s.get("severity") or "moderate") for s in timeline)` comparaba strings:
alfabéticamente `"moderate" > "high" > "critical"`, así que cualquier pista con una
observación moderada reportaba `moderate` aunque hubiera tenido detecciones críticas.
Corregido con rango explícito `{moderate:0, high:1, critical:2}`.
*Verificado:* pista con timeline `[critical, moderate]` → ahora devuelve `critical`
(antes `moderate`).

### B2 · Fuente de datos mal etiquetada en el HUD
**Archivo:** `static/app.js` (`applyHarmonized`, `loadBaseline`)

El modo `evolution-archive` (datos reales del DuckDB local) no contenía el literal
`local-archive`, caía al `else` y el HUD lo anunciaba como **"FUSIÓN NASA"**; además la
comparación de anomalía histórica tomaba la rama de la API de NASA (que exige MAP_KEY)
en vez de la del archivo local. Ambos chequeos ahora usan `includes('archive')`.

### B3 · Pillow faltaba en requirements.txt
**Archivos:** `requirements.txt`, `backend/environment_engine.py`

El muestreo de píxeles GIBS (`_sample_pixel`) importa `PIL`; sin Pillow, **todo** el
bloque ENTORNO (combustible/humo) y el briefing del analista degradaban en silencio a
"sin dato" — incluido el despliegue Docker, que se construye sin Pillow. Añadido
`Pillow>=10.2,<13`.

### B4 · Dirección del viento promediada como magnitud lineal
**Archivo:** `backend/context_engine.py`

Promediar 350° y 10° daba 180° (sur) en lugar de 0° (norte). Añadida media circular
(atan2 de senos/cosenos). *Verificado:* `[350, 10] → 0.0`.

### B5 · Registro de identidades escrito donde cayera el CWD
**Archivo:** `backend/evolution_engine.py`

`REGISTRY_PATH` era relativa (`data/events/...`): arrancar uvicorn desde otra carpeta
escribía el registro en otro sitio y las identidades persistentes "se perdían". Ahora
ancla a la raíz del proyecto (sigue siendo overridable por env).

### B6 · Identidades persistentes no persistían en Docker
**Archivo:** `compose.yml`

`data/events/` (registro de identidades) no estaba montado como volumen: cada
`docker compose up` reiniciaba la numeración IGN-YYYY-NNNN. Añadido el volumen.

### B7 · Niveles de confianza sin traducir en el briefing
**Archivo:** `backend/analyst_engine.py`

El motor emite `HIGH/MODERATE/LOW/VERY LOW`, pero la tabla sólo mapeaba
`HIGH/MEDIUM/LOW` → el briefing en español mostraba "MODERATE"/"VERY LOW" en inglés.
Tabla completada.

### B8 · Evidencia PyroCb siempre en español
**Archivo:** `backend/environment_engine.py`

Las frases del índice PyroCb estaban hardcoded en español aun con `lang=en`. Movidas al
sistema `LABELS` bilingüe del propio motor.

### B9 · Pares de traducción invertidos en el visor 3D
**Archivo:** `static/i18n.js`

`['MAPA 3D EN MODO SEGURO','3D MAP IN SAFE MODE']` y `['REINTENTAR RENDER','RETRY RENDER']`
estaban al revés (el HTML base está en español): en modo EN la alerta de render seguro y
su botón nunca se traducían. Invertidos al formato `[inglés, español]` que espera el walker.

---

## C. Mejoras de i18n y UX (cadenas que ignoraban el idioma)

`static/app.js` usaba texto fijo aunque las claves ya existían en `i18n.js`:

| Antes (hardcoded) | Ahora |
|---|---|
| `Zoom closer before querying…` | `TT('toast_zoom')` |
| `Load a multi-day timeline first.` | `TT('toast_load_timeline')` |
| `No evolution tracks loaded yet…` | `TT('toast_no_tracks')` |
| `Full demo needs a preset region; using Mexico.` | `TT('toast_demo_region')` |
| `Load an analytical dataset first.` | `TT('toast_load_dataset')` |
| `CANDIDATE FIRE EVENT · {id}` | `TT('kicker_event', id)` *(clave nueva)* |
| `No multi-detection candidate events…` | `TT('ev_none')` *(clave nueva)* |
| Bloque ENTORNO (`sin dato`, `consulta pendiente`, …) | claves `env_*` ya existentes |

Además `loadEnvironmentIntelligence` ahora envía `lang` al backend (el endpoint ya lo
soportaba): con la interfaz en inglés la evidencia ambiental llegaba en español.
Añadido también el par `SIMULATED CONTEXT · demonstration only` que faltaba.

## D. Limpieza menor

- `backend/app.py`: eliminado el parámetro muerto `min_points` de `_evolution_from_frames` (3 sitios).
- `static/app.js`: conteo MODIS/VIIRS del panel ahora respeta los filtros de severidad (antes contaba también las detecciones ocultas).
- `static/app.js`: `demoContext` ya no produce `NaN` en la dirección del viento si falta `event_score`.
- `static/app.js`: eliminada la asignación inútil `viewer.scene.renderError=undefined` (propiedad de sólo lectura en Cesium).
- Comentario del watchdog corregido (6 lecturas × 2,5 s ≈ 15 s, no 7,5 s).

## Verificado como CORRECTO (no tocado)

- **`start_date` de FIRMS**: la documentación oficial del Area API confirma
  *"Returns data for [DATE] .. [DATE + DAY_RANGE-1]"* → la fecha **sí** es inicial; el
  uso del backend y la etiqueta "TIMELINE START DATE" son correctos.
- **Muestreo GIBS del backend** (`environment_engine.tile_for`): usa su propia tabla de
  rejillas 4326 correctas (nivel 5 = 40×20) y el orden `{TileMatrix}/{TileRow}/{TileCol}`;
  funcionaba bien y se mantiene en 4326 (máxima resolución por píxel).
- Importación DuckDB (`INSERT OR IGNORE … WITH`), calendario local, evolución desde
  archivo, clustering de eventos, worker-shim del iframe y watchdog de render: probados
  en ejecución, sin fallas.

## Pruebas realizadas tras los cambios

1. `node --check` sobre `app.js`, `i18n.js`, `ui-shell.js` — OK.
2. Unitarias sobre el código corregido: severidad de pista, media circular, `LEVELS`,
   etiquetas PyroCb bilingües, `REGISTRY_PATH` anclada — OK.
3. Servidor completo: `/api/config`, `/api/evolution/demo`, `/api/harmonize/demo`,
   `/api/harmonize/demo/date`, calendario demo, briefing ES/EN,
   `/api/environment/intelligence?lang=en` (evidencia en inglés), importación DuckDB
   (400 filas), calendario y evolución desde archivo — OK.
4. Tiles GIBS 3857 de las 4 capas con `curl` — `HTTP 200` con `image/png|jpeg`.

---

## E. v0.9.3 — Rendimiento, render por software y nitidez (capturas del usuario)

Tras revisar capturas reales de la app se corrigió una segunda tanda de fallas de
render, todas verificadas con Playwright/Chromium headless (SwiftShader):

### E1 · El panel de error de Cesium bloqueaba TODA la interfaz — **CRÍTICA**
En GPUs por software el shader de HDR/bloom no compila
(`RuntimeError: Fragment shader failed to compile`). Cesium detenía el bucle de
render y mostraba un panel modal que interceptaba todos los clicks: "los botones
no funcionan".
**Corrección:** con renderer por software ya no se activan HDR/bloom/FXAA; si aun
así llega `renderError`, `ignisSafeRender()` apaga los efectos, **elimina el panel
modal**, reinicia el bucle (`useDefaultRenderLoop`) y muestra el aviso propio de
IGNIS. CSS de seguro: `.cesium-widget-errorPanel{display:none!important}`.

### E2 · Botones con delay y animaciones a tirones
Dos causas medidas: (1) `drawHud()` reconstruía el SVG completo en cada cuadro
(60 fps); ahora ~30 fps. (2) `backdrop-filter: blur(18px)` sobre un canvas que se
redibuja constante obliga a re-desenfocar la pantalla entera; en modo `perf-soft`
se sustituye por fondo casi opaco y se apagan scanline/viñeta. (3) Con renderer
por software el visor pasa a `requestRenderMode` (render bajo demanda) con un
pulso de 8 fps sólo cuando hay animaciones activas: el hilo principal queda libre
para la UI.

### E3 · Globo "muy pixeleado"
La única base era Natural Earth II (~20 km/píxel). Ahora `IGNIS_BASEMAP='auto'`:
tiles OpenStreetMap nítidos con internet y degradación automática al NE II local
si fallan (toast avisa). Además `resolutionScale = devicePixelRatio` (capped 2),
`maximumScreenSpaceError 1.25` (pide tiles más finos al acercar),
`tileCacheSize 1000` y zoom mínimo bajado de 800 km a 250 km.

### E4 · Las capas GIBS no pintaban en el navegador del usuario (chips en rojo)
Las peticiones directas del navegador a GIBS fallaban en ciertos contextos
(iframes sandbox/CORS). Nuevo proxy de mismo origen
`GET /api/gibs/tile/{capa}/{fecha}/{z}/{y}/{x}.{ext}` en el backend: valida
capa/fecha/coordenadas, reintenta hasta 4 fechas anteriores (latencia del
compuesto GIBS) en el servidor, cachea y sirve con CORS `*`. El front usa
`UrlTemplateImageryProvider` contra el proxy. Verificado: 90 tiles servidos,
0 peticiones directas a GIBS, chips AEROSOLES y PIRO-CB en `active`, 3 capas de
imagen en el globo y georeferencia correcta (captura con TrueColor encima).

### E5 · El planeta arrancaba diminuto
Nueva entrada de cámara: arranque a 10.5 Mm sobre México y aproximación a
4.3 Mm en 3.4 s (antes 22–30 Mm y 6.5 s).

### Verificación v0.9.3 (Playwright + Chromium headless, renderer por software)
- `tools/ui_test.py`: arranque, chips de capa, cambio de modo, tema claro,
  conteo de peticiones y errores de consola → `RESULTADO: OK`, 0 errores.
- Capturas: `/tmp/shot_capas.png` (OSM nítido + AOD/Pyro activos),
  `/tmp/shot_heat.png` (TrueColor GIBS georeferenciado sobre la base).

---

## F. v0.9.4 — Capas ambientales útiles por defecto, sin huecos, idioma completo y tooltips

Sobre capturas del usuario (chips, COLOR REAL con franjas negras, globo borroso,
cabecera sin traducir en EN) se corrigió:

### F1 · "Hoyos" negros en COLOR REAL — franjas sin órbita del compuesto diario
El TrueColor de GIBS es JPEG diario sin alfa: las zonas fuera de la órbita del
satélite llegan NEGRAS y tapan el globo. Corrección en dos partes:
- **Proxy** (`/api/gibs/tile/...png` para TrueColor): convierte el relleno negro
  puro (max(r,g,b)<12) en alfa 0 a velocidad C (`ImageChops.lighter`, sin bucles
  Python) y SIEMPRE devuelve un PNG real.
- **Front**: COLOR REAL apila 3 días (más nuevo arriba); los días anteriores
  rellenan los huecos transparentes del compuesto reciente.
Verificado: tile con 6 241 px transparentes servido como RGBA/image‑png; captura
final sin franjas negras.

### F2 · Globo "desenfocado" con las capas PNG — dos causas encadenadas
1) `ImageChops.lighten` NO EXISTE (es `lighter`): la excepción caía en un
   `except` silencioso y el proxy servía bytes JPEG etiquetados `image/png`;
   Cesium no los decodifica y se queda clavado en tiles de baja resolución.
   Ahora el error se registra en el log y el fallback sirve JPEG con SU media
   type correcto.
2) `highDynamicRange` queda `true` por defecto en Cesium y el tema oscuro lo
   re-activaba (`IGNIS_APPLY_THEME`): en GPUs por software el pipeline HDR lava
   la imagen. Ahora en modo software HDR/bloom/FXAA quedan explícitamente
   apagados también al cambiar tema.
Diagnóstico hecho ocultando capas una a una en Chromium hasta aislar el origen.

### F3 · Mover la inteligencia temporal re-renderizaba todo en cada tick
`renderFrame()` recreaba los providers GIBS en cada input del slider
(par-padeo + spam de tiles). Ahora `scheduleEnvRefresh()` debota 400 ms: las
capas se actualizan una sola vez al hacer pausa. Verificado: `envLayerDate`
cambia tras la pausa, no durante el arrastre.

### F4 · COLOR REAL (o VEGETACIÓN) activo al arrancar
El globo inicia ya con la pila TrueColor puesta (si hay internet), para que el
planeta se vea como satélite desde el primer segundo.

### F5 · Aerosoles "raros" (cuadros duros de 1°)
Filtrado LINEAR de textura solo en capas gruesas (AOD, OMPS) → gradientes
suaves; alfa bajado a 0.60.

### F6 · Cabecera y dinámicos sin traducir al cambiar idioma
`setStatus()` ahora guarda la clave y todos los textos dinámicos (STATUS,
SENSORS "2 FUENTES/2 SOURCES", FEED, ARCHIVE, PLAY) se repintan con
`IGNIS_I18N.onChange` + `refreshDynamicLabels()`. Verificado ES↔EN en vivo.

### F7 · Tooltips explicativos localizados
31 controles (chips, modos, botones de carga, calendario, archivo, timeline,
filtros…) tienen `data-tip` y reciben `title=` en el idioma activo
(`translateAttributes` en i18n.js).

### F8 · Anillo de foco pegado en chips
`button:focus:not(:focus-visible){outline:none}` en styles.css; el anillo solo
aparece con navegación por teclado.

### Verificación v0.9.4
`tools/ui_test.py` → RESULTADO: OK · 0 errores de consola · 6 capas de imagen
(base + pila TrueColor×3 + 2 ambientales) · 225 tiles por proxy · 0 directos a
GIBS. `tools/ui_test3.py`: COLOR REAL activo sin click, ES↔EN reactivo,
debounce del timeline comprobado. Capturas /tmp/shot_v094_ok2.png (satélite
nítido sin huecos) y /tmp/shot_v094_timeline.png.

---

## G. Auditoría adicional de la copia recibida

### G1 · Proxy de capas: respuestas ambiguas y caché sin fecha de origen

**Causa:** el proxy trataba igual una tesela sin cobertura NASA y una falla de
red; además, una respuesta servida desde caché perdía la fecha real del
compuesto. Un cliente no podía decidir si debía dejar el chip activo o avisar
que la red había fallado.

**Corrección:** 404 si ninguna de las cinco fechas candidatas tiene cobertura;
502 para fallo del proveedor o contenido inválido; 504 para timeout. El proxy
valida la firma PNG/JPEG, conserva `X-GIBS-Date` en las respuestas de caché y
limita la caché por número de teselas, bytes y tiempo. Reutiliza conexiones HTTP.
El catálogo ambiental ahora anuncia el mismo EPSG:3857 y la misma ruta de
teselas que consume el visor. Una conversión fallida de COLOR REAL se registra
y conserva el media type JPEG correcto.

**Verificación:** una tesela real de COLOR REAL devolvió PNG RGBA 256×256 con
8 704 píxeles transparentes; AOD devolvió PNG válido; una fecha NDVI anterior
a su cobertura devolvió 404. Coordenadas inválidas dieron 400. Respuestas
simuladas de proveedor 503, imagen inválida, error de conexión y timeout se
clasificaron 502/502/502/504; el segundo acceso a caché mantuvo `X-GIBS-Date`.

### G2 · Versiones públicas inconsistentes

**Causa:** `VERSION`, el encabezado del iniciador, la API y los motores
ambiental/analista publicaban 0.9.1 aunque la copia ya contenía cambios
v0.9.4. **Corrección:** `VERSION` es la fuente de versión para el iniciador y
las respuestas de backend; la documentación visible se actualizó. Los
endpoints `/api/health`, `/api/config`, demo, evolución, analista y catálogo
devolvieron 200 con versión 0.9.4.

### G3 · Iniciador macOS sin permiso de ejecución y contexto Docker excesivo

Los dos scripts de macOS/Linux tenían modo 0644; el `.command` invocaba
`./INICIAR_IGNIS.sh`, que no era ejecutable. Ambos tienen ahora modo 0755 y
su sintaxis pasó `zsh -n` / `sh -n`. Se añadió `.dockerignore` para excluir
`.env`, `.venv`, `.git`, cachés y bases locales del contexto enviado al build.
Docker no estaba instalado en el entorno de auditoría, por lo que el build de
la imagen queda sin ejecutar aquí.

### G4 · El estado del archivo local fallaba al iniciar

`applyArchiveStatus()` leía `n` sin declararlo. El error interrumpía la carga
de configuración y quedaba oculto dentro de su `catch`. Ahora se calcula el
número de observaciones antes de usarlo; los avisos de configuración y archivo
se traducen. El archivo vacío se muestra como VACÍO / EMPTY sin excepción.

### G5 · El tema alteraba también las imágenes ambientales

El chequeo `Object.values(envLayers).indexOf(layer)` siempre fallaba porque
cada entrada guarda `{layers: [...]}`. El tema modificaba gamma/brillo de
COLOR REAL como si fuera el mapa base. Ahora comprueba los arrays de cada
capa y conserva sus valores al cambiar de tema.

### G6 · Trabajo de render innecesario y arranque cubierto por el dossier

El demo enfocaba y abría un seguimiento automáticamente, cancelando la vista
inicial del globo. Ahora carga los datos conservando la cámara de la intro y
abre el dossier solo al seleccionar un evento o pedir la evolución. En
SwiftShader, el render funciona bajo demanda, con HDR/bloom/FXAA apagados,
MSAA 1, límite de 15 cuadros por segundo y caché de 240 teselas. Los
marcadores dejan de pulsar en software y la lista se limpia al cambiar de modo.
El watchdog solicita un cuadro de comprobación antes de considerar que el
render está bloqueado; el reposo normal deja de disparar falsos avisos.

### G7 · COLOR REAL borroso y PIRO-CB con fondo gris

Cesium ampliaba teselas satelitales ancestrales de baja resolución mientras
llegaban las detalladas. Para COLOR REAL en formato PNG, los niveles z0–z4
devuelven ahora un PNG transparente local, sin consultar NASA. La base
cartográfica queda visible y nítida durante la carga; los niveles z5–z9
conservan el compuesto satelital. El tooltip explica el comportamiento al
alejarse. Las capturas de inicio y tras unos 30 segundos verifican esa mejora.

La máscara de relleno negro de COLOR REAL suaviza además los píxeles JPEG
oscuros solo en un borde de dos píxeles alrededor del hueco detectado. La
prueba mantiene opaco el terreno oscuro separado de esa franja. La conversión
medida pasó de unos 5,7 ms a 8,7 ms por tesela. El fondo gris neutro de OMPS se
hace transparente en el visor; la capa analítica original se conserva.

### G8 · Idioma del dossier y fallback offline

Se localizaron estados del seguimiento, evidencia de intensidad, confianza,
botones de replay, filas de eventos, textos de ayuda y el resumen del dossier.
El bloque ambiental vuelve a consultarse en el idioma elegido y descarta
respuestas de consultas anteriores, evitando que una respuesta tardía restaure
el idioma previo. Se eliminaron repintados duplicados del shell.
Cambiar de idioma ya no abre automáticamente un panel del analista cerrado;
solo actualiza un informe visible y descarta respuestas de un idioma anterior.

El fallback OSM estaba registrado en `ImageryLayer.errorEvent`, que informa
de la creación del provider; los fallos de teselas se emiten en
`imageryProvider.errorEvent`. Se corrigió el suscriptor y el evento offline
también cambia explícitamente al mapa Natural Earth II local. Los chips
ambientales se desactivan y el análisis demo sigue disponible.

## H. Resultados reproducibles del cierre

- Sintaxis: `node --check` para `app.js`, `i18n.js` y `ui-shell.js`;
  `python3 -m compileall -q backend tools start_ignis.py`; `git diff --check`;
  `sh -n INICIAR_IGNIS.sh` y `zsh -n INICIAR_IGNIS.command`: sin errores.
- `.venv/bin/python tools/backend_audit.py`: **9 pruebas aprobadas**. Usa
  respuestas de NASA simuladas para reproducir errores y fallback sin red.
- `.venv/bin/python tools/ui_audit.py --url http://127.0.0.1:8000/
  --output /tmp/ignis-ui-verificado`: **14 comprobaciones aprobadas** en
  Chromium headless con SwiftShader, viewport 1600×900. Se verificaron inicio,
  capas aisladas y combinadas, ES→EN→ES, tema, dossier, debounce y evento offline.
  Hubo 1 221 respuestas 200 del proxy durante toda la secuencia (incluyen
  niveles transparentes locales), **0 peticiones directas a GIBS**, **0 errores
  JavaScript/consola** y **31 tooltips presentes**. Ningún clic usó fallback DOM.
- La identidad del provider se conservó dentro de 150 ms al mover el slider;
  después de la pausa se actualizó una vez, con fecha 2026-10-08→2026-10-07.
  La pila activa conservó seis capas (base, tres días COLOR REAL, AOD y OMPS).
- `.venv/bin/python tools/ui_offline_audit.py`: arranque con internet bloqueado
  y servidor local accesible; **aprobado**. Natural Earth II visible, una capa
  base, cero capas ambientales activas, cinco frames demo, render activo y
  cero excepciones JavaScript.
- `.venv/bin/python tools/ui_language_audit.py`: regresión adicional con
  respuestas ambientales y del analista simuladas; **aprobada**. El dossier,
  contexto ambiental y nombre accesible del tema cambian de idioma; un informe
  visible se actualiza y un panel cerrado permanece cerrado. Cero excepciones
  JavaScript. `dossier_en_verificado.png` muestra este último pase.
- La API en ejecución devolvió 200 para salud, configuración, evolución demo y
  catálogo; capa desconocida 404 y coordenadas inválidas 400. COLOR REAL real
  z5 devolvió un PNG RGBA 256×256 con alfa 0–255; z0 devolvió PNG transparente.
- Las capturas y los JSON de resultados están incluidos en `evidencia_ui/`
  dentro del ZIP. Las secciones A–F mencionan capturas históricas en `/tmp`;
  las capturas entregadas corresponden al cierre documentado aquí.

### Límites medidos y pendientes

Con render completamente por software persiste latencia de entrada bajo carga
gráfica. En el pase final, el clic físico más lento tardó unos **4,96 s** en
retornar; comprobar su efecto mediante otra llamada al navegador elevó la
medición del modo calor a **6,64 s**. El handler JavaScript aislado tardó
**0,6 ms** y aplicó la clase activa inmediatamente. Las correcciones reducen
trabajo innecesario, pero **no se declara resuelto por completo el retraso de
entrada de SwiftShader**. La suite registra cada clic y cualquier fallback.

Se descartó fijar `resolutionScale=0.75`: una sonda redujo el tiempo de entrada
de 8,75 s a 2,41 s, con pérdida visible de nitidez. Se conserva escala 1 en
software. La cobertura satelital y los compuestos dependen de NASA; apilar tres
días no garantiza cobertura completa ni una imagen de un único instante. AOD
y OMPS conservan su resolución espacial original, aunque el filtrado y la
transparencia mejoran su lectura.

No se ejecutó un build Docker (no instalado), ni se midió rendimiento en GPU
física. NASA FIRMS en vivo no se probó porque no hay `FIRMS_MAP_KEY` configurada.
El archivo histórico local de esta copia está vacío; los datos anteriores no
se recuperan desde el código ni se incluyen en el paquete.

## I. Segunda revisión: coherencia geográfica, continuidad temporal y ayudas

Esta revisión responde a la captura con puntos en el mar y a los fallos
observados después del primer cierre de la sección H. Los cambios siguientes
sustituyen la implementación de capas apiladas y el vigilante descritos allí.

### I1 · Puntos de demostración sobre el mar

El generador de periodos demo distribuía señales alrededor de centros de un
rectángulo regional; ese rectángulo también cubría el Golfo y el Pacífico. No
eran observaciones NASA. Ahora usa cuatro centros interiores por región y una
dispersión inferior a 10 km; se movieron también semillas costeras del ejemplo
global. Los payloads y observaciones llevan `synthetic: true` y el satélite
`IGNIS_DEMO`. La interfaz muestra **DEMO SIMULADA**, una nota persistente de
procedencia y el prefijo DEMO en el dossier.

La regresión verifica más de 3 000 marcadores y celdas contra una máscara
terrestre Natural Earth independiente de los centros del generador. Incluye
las cinco regiones y controles negativos en el mar. Esta corrección modifica
solo la demostración: no elimina ni desplaza observaciones FIRMS reales.

### I2 · Capas que desaparecían al cambiar fechas

Los errores repetidos 5xx retiraban la capa y borraban su selección. Además,
una sola `envLayerDate` global podía marcar todas las capas como actualizadas
al añadir un producto nuevo. Ahora la selección (`envSelections`) es
independiente de las imágenes visibles y cada producto conserva su fecha.

Se mantienen las imágenes anteriores hasta disponer de las nuevas, con
mensajes visibles de carga, fecha de referencia y fallo. Un 404 o 502 no borra
la preferencia del usuario. El estado sin conexión mantiene la selección para
recuperarla al reconectar. La caché del navegador conserva como máximo dos
fechas por producto y el orden de superposición es estable. Una fecha sin
cobertura se informa explícitamente; no se presenta como ausencia de incendios.

En COLOR REAL, las respuestas transparentes de bajo nivel no bastan para
reemplazar una imagen anterior cuando ya se pidió detalle. Ambas rutas de
finalización comprueban que haya detalle válido; el límite de espera es 18 s,
por encima del timeout de la petición NASA. Si falla, queda la imagen anterior.

Elegir otra fecha del calendario en la misma región ya no reinicia la cámara.
El vuelo solo se realiza cuando se cambia a otra región conocida.

### I3 · Reproducir, pausar y volver a reproducir

Se sustituyó el intervalo fijo por pasos que esperan el dibujo anterior antes
de programar el siguiente (1,5 s en software, 0,9 s con GPU). El token de
reproducción y la limpieza de listeners impiden acumular ciclos. Reanudar en
la misma fecha conserva los proveedores y la cámara; durante la secuencia las
imágenes ambientales mantienen su última referencia y se sincronizan al pausar.
La carga de otro conjunto o el uso manual del slider/flechas detiene la reproducción.

El vigilante forzaba un render cada 2,5 s incluso en reposo. Ahora observa el
latido `postUpdate`, que sigue activo sin dibujar, y solo hace una comprobación
si faltan actualizaciones durante 15 s. La recuperación de errores sigue activa.

En renderizado por software se desactivan además la transparencia independiente
del orden y la atmósfera sobre el terreno. Se conserva `resolutionScale = 1`
para mantener el detalle de la imagen.

### I4 · Menos capas y filtrado correcto

COLOR REAL pasa de tres `ImageryLayer` a **una** por fecha visible. El nuevo
endpoint `/api/gibs/composite/{fecha}/{z}/{y}/{x}.png` mezcla D, D−1 y D−2
con alfa en el servidor, con peticiones paralelas y caché de fechas exactas.
No confunde una respuesta fallback del proxy anterior con una fecha exacta.
Los headers `X-GIBS-Dates` y `X-GIBS-Partial` informan la procedencia; la
cobertura parcial se cachea como máximo 120 s. Una prueba real devolvió PNG
RGBA 256×256, 86 957 bytes y las tres fechas 2024-07-01, 2024-06-30, 2024-06-29.

El filtrado de AOD/OMPS usaba nombres de API inexistentes y era ignorado por
un catch. Se corrigió a `TextureMinificationFilter.LINEAR`,
`TextureMagnificationFilter.LINEAR` y las propiedades `minificationFilter` /
`magnificationFilter` de la versión Cesium incluida.

### I5 · Ayudas «?» visibles

Se añadieron 55 botones circulares junto a controles y secciones. Explican
modos, origen DEMO/NASA, capas, fechas, reproducción, FRP, confianza y archivo.
Funcionan al pasar el cursor, enfocar con teclado o hacer clic; el clic fija
la explicación, y Escape, el botón de cierre o un clic exterior la cierran.
El panel de ayuda se coloca fuera de los contenedores con scroll y se ajusta
al viewport; el texto y los nombres accesibles cambian ES/EN.

### I6 · Verificación de esta revisión

- `tools/backend_audit.py`: **14 pruebas aprobadas**, incluyendo máscara
  terrestre, composición, transparencia, caché y errores 400/404/502/504.
- `tools/ui_timeline_audit.py`: **22 comprobaciones aprobadas** en el pase
  completo con teselas simuladas y respuestas 404/502/200 controladas. Se
  retuvieron respuestas para verificar la continuidad durante carga. La
  selección persistió, reanudar en la misma fecha no creó capas, y al terminar
  quedaron dos imágenes visibles para las dos opciones activadas.
- La suite temporal incluye primera carga durante reproducción y conservación
  de cámara al cambiar el mes dentro de la misma región. No hubo errores
  JavaScript; las respuestas controladas fueron 633×200, 126×404 y 68×502,
  con 36 respuestas retenidas para observar la transición.
- Las pruebas temporales usan clic DOM y no acreditan latencia física ni
  disponibilidad real de NASA. Las capturas con teselas simuladas verifican
  interfaz y estados; la inspección satelital real se registra por separado.

Se alineó también el límite de fecha del navegador con `current_date` del
servidor. Después de medianoche UTC, el selector podía ofrecer el día siguiente
mientras el backend en hora local lo rechazaba como futuro. La prueba congela
el día del servidor y verifica que configuración y validación coinciden.

La QA de ayudas con imágenes controladas aprobó **12 comprobaciones**, incluida
la apertura física del «?» del timeline en viewport de 420 px, hover, clic,
teclado, ES/EN y nombres accesibles. En reposo hubo **0 dibujos y 97 latidos de
actualización durante 6,5 s**; el clic físico de ayuda tardó **100 ms**. Estas
cifras describen el caso aislado probado y no garantizan esa latencia durante
la carga real de imágenes satelitales.

La inspección con imágenes GIBS reales aprobó **14 comprobaciones**, con
843 respuestas del proxy de estado 200, cero peticiones directas a GIBS y cero
errores JavaScript antes de simular desconexión. Se revisaron visualmente las
capturas: la imagen conserva detalle, con nubes y costuras de órbita posibles.
Los clics físicos no usaron fallback DOM. Este pase amplio, previo al ajuste
final de efectos de software, registró dos timeouts de entrada: 12,09 s al
cargar evolución y 5,62 s al cambiar idioma; ambos eventos sí llegaron a ejecutarse.

Después del ajuste, `tools/ui_playback_smoke.py` aprobó **8 comprobaciones**
con imágenes reales y clics físicos: fecha del servidor, efectos de software,
conservación de imagen y cámara, pausa, reanudación, selección y cero errores.
La ayuda tardó 215 ms y los clics de reproducción/pausa entre 1,90 y 3,62 s.
**Persiste demora bajo carga en SwiftShader**: no se presenta el problema de
latencia como resuelto, ni se extrapola este resultado a una GPU física.

Los pases finales de inicio sin red y de cambio de idioma también aprobaron:
mapa local disponible, sin modal Cesium, cero errores JavaScript, dossier y
briefing traducidos y panel del analista cerrado cuando el usuario lo cerró.

`tools/ui_continuity_smoke.py` aprobó **9 comprobaciones** después de la última
revisión: 21 PNG transparentes de bajo nivel y 42 abortos de detalle sin código
HTTP no ocultan la imagen anterior, ni por el evento de cola vacía ni después
del timeout real de 18 s. La ayuda sigue abierta si el botón conserva el foco
al retirar el puntero, y se cierra al mover el foco. Cero errores JavaScript.
