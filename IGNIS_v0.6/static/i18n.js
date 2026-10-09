/* ==========================================================================
   IGNIS v0.9 — Capa de idioma (ES / EN)
   - HTML_PAIRS: traducción de todos los textos estáticos de index.html.
     Se aplica recorriendo los nodos de texto y sustituyendo coincidencias
     exactas, así que los valores dinámicos (IDs, cifras, fechas) nunca se
     tocan por accidente.
   - MSG: cadenas generadas por JavaScript (avisos, estados), con parámetros.
   - Persistencia tolerante: en el preview (iframe sandbox) localStorage puede
     lanzar SecurityError por origen opaco; se ignora y se sigue funcionando.
   ========================================================================== */
window.IGNIS_I18N = (function () {
  'use strict';

  /* --- 1 · textos estáticos del HTML: [inglés, español] ------------------- */
  const HTML_PAIRS = [
    /* el orden importa: las claves más largas primero */
    ['EARTH FIRE INTELLIGENCE', 'INTELIGENCIA DE INCENDIOS EN LA TIERRA'],
    ['// ENVIRONMENTAL INTELLIGENCE', '// INTELIGENCIA AMBIENTAL'],
    ['// INTELLIGENCE ANALYST', '// ANALISTA DE INTELIGENCIA'],
    ['// INTELLIGENCE ANALYST', '// ANALISTA DE INTELIGENCIA'],
    ['FEED', 'FUENTE'], ['SENSORS', 'SENSORES'], ['REGION', 'REGIÓN'],
    ['ARCHIVE', 'ARCHIVO'], ['EVENTS', 'EVENTOS'], ['STATUS', 'ESTADO'], ['RENDERER', 'RENDER'],
    ['INTELLIGENCE MODE', 'MODO DE INTELIGENCIA'],
    ['HOTSPOTS', 'PUNTOS CALIENTES'], ['FUSION GRID', 'MALLA DE FUSIÓN'],
    ['FIRE EVENTS', 'EVENTOS DE FUEGO'], ['EVOLUTION', 'EVOLUCIÓN'],
    ['LOAD FIRE EVOLUTION (v0.7)', 'CARGAR EVOLUCIÓN DE INCENDIOS (v0.7)'],
    ['TRACK LOCAL ARCHIVE · REAL NASA DATA', 'SEGUIR ARCHIVO LOCAL · DATOS NASA REALES'],
    ['LOAD ANALYTICAL DEMO', 'CARGAR DEMO ANALÍTICA'],
    ['NASA · HARMONIZE REGION', 'NASA · ARMONIZAR REGIÓN'],
    ['BURNING ACTIVITY CALENDAR', 'CALENDARIO DE ACTIVIDAD'],
    ['LOCAL ARCHIVE MANAGER', 'GESTOR DE ARCHIVO LOCAL'],
    ['EXPORT INTELLIGENCE SNAPSHOT', 'EXPORTAR SNAPSHOT'],
    ['AREA OF INTEREST', 'ÁREA DE INTERÉS'], ['REGION PRESET', 'REGIÓN PREDEFINIDA'],
    ['FLY TO REGION', 'VOLAR A LA REGIÓN'], ['TIMELINE START DATE', 'FECHA INICIAL DEL TIMELINE'],
    ['Historical requests use FIRMS Standard Processing sources. Calendar cells can drive this date automatically. Event mode clusters nearby thermal anomalies; it does not create official incident perimeters.',
     'Las consultas históricas usan fuentes FIRMS de procesamiento estándar. Las celdas del calendario pueden fijar esta fecha. El modo de eventos agrupa anomalías térmicas cercanas; no crea perímetros oficiales de incendios.'],
    ['Current viewport', 'Vista actual'],
    ['WINDOW', 'VENTANA'], ['1 DAY', '1 DÍA'], ['3 DAYS', '3 DÍAS'], ['5 DAYS', '5 DÍAS'],
    ['SENSOR FUSION', 'FUSIÓN DE SENSORES'], ['legacy', 'heredado'],
    ['COMMON GRID', 'MALLA COMÚN'],
    ['~6 km · fine', '~6 km · fina'], ['~11 km · balanced', '~11 km · equilibrada'],
    ['ENVIRONMENTAL LAYERS', 'CAPAS AMBIENTALES'], ['needs internet', 'necesita internet'],
    ['NASA GIBS layers follow the timeline date. Without internet they are inactive; analysis does not depend on them.',
     'Las capas NASA GIBS siguen la fecha del timeline. Sin internet quedan inactivas; el análisis no depende de ellas.'],
    ['AEROSOLS', 'AEROSOLES'], ['VEGETATION', 'VEGETACIÓN'], ['TRUE COLOR', 'COLOR REAL'],
    ['PYRO-CB · SMOKE', 'PIRO-CB · HUMO'],
    ['INTELLIGENCE', 'INTELIGENCIA'],
    /* opciones de <select> */
    ['Mexico', 'México'], ['Amazon Basin', 'Cuenca Amazónica'], ['Mediterranean', 'Mediterráneo'],
    ['MODIS · Standard Processing', 'MODIS · Procesamiento estándar'],
    ['VIIRS · Suomi-NPP Standard Processing', 'VIIRS · Suomi-NPP estándar'],
    ['VIIRS · NOAA-20 Standard Processing', 'VIIRS · NOAA-20 estándar'],
    ['VIIRS · NOAA-21 Archive', 'VIIRS · Archivo NOAA-21'],
    ['TRACKED FIRE EVENTS', 'EVENTOS DE FUEGO SEGUIDOS'],
    ['VISIBLE FUSION CELLS', 'CELDAS DE FUSIÓN VISIBLES'],
    ['ACTIVE CANDIDATE EVENTS', 'EVENTOS CANDIDATOS ACTIVOS'],
    ['INTELLIGENCE ANALYST · BRIEFING', 'ANALISTA DE INTELIGENCIA · INFORME'],
    ['COPY', 'COPIAR'],
    ['LOCAL FULL-MONTH', 'MES COMPLETO LOCAL'], ['MODIS API', 'API MODIS'],
    ['Loading environmental context…', 'Cargando contexto ambiental…'],
    ['Context unavailable', 'Contexto no disponible'],
    ['HOTSPOT FILTERS', 'FILTROS DE PUNTOS'],
    ['Moderate', 'Moderado'], ['High', 'Alto'], ['Critical', 'Crítico'],
    ['NOW', 'AHORA'], ['BURNING ACTIVITY', 'ACTIVIDAD ACTUAL'],
    ['VISIBLE DETECTIONS', 'DETECCIONES VISIBLES'], ['ACTIVITY INDEX', 'ÍNDICE DE ACTIVIDAD'],
    ['Sensor-balanced score for the selected frame.', 'Puntuación balanceada por sensores del frame seleccionado.'],
    ['AGREEMENT CELLS', 'CELDAS DE ACUERDO'],
    ['HISTORICAL ANOMALY', 'ANOMALÍA HISTÓRICA'],
    ['COMPARE WITH PRIOR YEARS', 'COMPARAR CON AÑOS PREVIOS'],
    ['NO BASELINE', 'SIN LÍNEA BASE'],
    ['Uses a MODIS historical anchor for consistency.', 'Usa un ancla histórica MODIS por consistencia.'],
    ['SELECTED PERIOD', 'PERIODO SELECCIONADO'], ['NONE', 'NINGUNO'],
    ['Open the Burning Activity Calendar', 'Abre el Calendario de Actividad'],
    ['LOCAL ARCHIVE', 'ARCHIVO LOCAL'], ['OBSERVATIONS', 'OBSERVACIONES'],
    ['No historical files imported', 'Sin archivos históricos importados'],
    ['Select a persistent event to generate its explainable briefing. Every sentence carries its citations.',
     'Selecciona un evento persistente para generar un informe explicable. Cada frase incluye sus citas.'],
    ['FIRE EVOLUTION ENGINE', 'MOTOR DE EVOLUCIÓN DE INCENDIOS'],
    ['NO TRACKS', 'SIN SEGUIMIENTOS'],
    ['Load the evolution demo or a multi-day dataset.', 'Carga la demo de evolución o un conjunto de varios días.'],
    ['Persistent event identities will appear here.', 'Las identidades persistentes aparecerán aquí.'],
    ['CANDIDATE FIRE EVENTS', 'EVENTOS DE FUEGO CANDIDATOS'],
    ['Load a multi-day dataset to build candidate events.', 'Carga datos de varios días para construir eventos candidatos.'],
    ['ENVIRONMENTAL CONTEXT', 'CONTEXTO AMBIENTAL'],
    ['SELECT A FIRE EVENT', 'SELECCIONA UN EVENTO'],
    ['Weather, dryness and recent air-quality context will appear here.', 'El tiempo, la sequedad y la calidad del aire reciente aparecerán aquí.'],
    ['DRYNESS CONTEXT', 'CONTEXTO DE SEQUEDAD'],
    ['TEMP MAX', 'TEMP MÁX'], ['RH MIN', 'HR MÍN'], ['WIND MAX', 'VIENTO MÁX'],
    ['RAIN', 'LLUVIA'], ['SOIL MOIST.', 'HUMEDAD SUELO'], ['WIND DIR', 'DIR. VIENTO'],
    ['Context is analytical only — not an operational fire-danger, smoke-attribution, evacuation or life-safety product.',
     'El contexto es solo analítico — no es un producto operativo de peligro de incendio, atribución de humo, evacuación o seguridad.'],
    ['SELECT A SIGNAL', 'SELECCIONA UNA SEÑAL'],
    ['Click a hotspot, fusion cell, candidate event or track', 'Haz clic en un punto caliente, celda, evento o seguimiento'],
    ['HOTSPOT INTELLIGENCE', 'INTELIGENCIA DEL PUNTO'],
    ['ENVIRONMENT · v0.8', 'ENTORNO · v0.8'],
    ['DROUGHT (percentile)', 'SEQUÍA (percentil)'],
    ['FUEL / VEGETATION', 'COMBUSTIBLE / VEGETACIÓN'],
    ['SMOKE / AEROSOLS', 'HUMO / AEROSOLES'],
    ['not queried', 'sin consultar'],
    ['FRP / SCORE', 'FRP / PUNTUACIÓN'],
    ['CONFIDENCE', 'CONFIANZA'], ['ACQUIRED', 'ADQUIRIDO'],
    ['DETECTIONS (BARS) · FRP (LINE)', 'DETECCIONES (BARRAS) · FRP (LÍNEA)'],
    ['PERSISTENCE', 'PERSISTENCIA'], ['PEAK', 'PICO'], ['DRIFT', 'DERIVA'],
    ['EVENT CONFIDENCE', 'CONFIANZA DEL EVENTO'],
    ['▶ REPLAY LIFECYCLE', '▶ REPRODUCIR CICLO'], ['■ STOP', '■ PARAR'],
    ['Persistent identity and lifecycle state are analytical labels — not an official incident record.',
     'La identidad persistente y el estado son etiquetas analíticas — no un registro oficial de incidentes.'],
    ['HISTORICAL PATTERN EXPLORER', 'EXPLORADOR DE PATRONES HISTÓRICOS'],
    ['Explore seasonal fire activity through time.', 'Explora la actividad de incendios a lo largo del tiempo.'],
    ['FULL DEMO', 'DEMO COMPLETA'], ['NASA SAMPLE', 'MUESTRA NASA'],
    ['FROM', 'DESDE'], ['TO', 'HASTA'], ['LOAD', 'CARGAR'],
    ['Synthetic full-history demo. Not NASA observations.', 'Demo sintética completa. No son observaciones NASA.'],
    ['LOW', 'BAJO'], ['MODERATE', 'MODERADO'], ['VERY HIGH', 'MUY ALTO'], ['EXTREME', 'EXTREMO'],
    ['SELECT A CELL → DATE + REGION → LOAD ON GLOBE', 'SELECCIONA UNA CELDA → FECHA + REGIÓN → CARGA EN EL GLOBO'],
    ['OFFLINE HISTORICAL DATA ENGINE', 'MOTOR HISTÓRICO OFFLINE'],
    ['Import FIRMS CSV/TXT/ZIP files into DuckDB and build a Parquet analytical snapshot.',
     'Importa archivos FIRMS CSV/TXT/ZIP a DuckDB y construye un snapshot analítico Parquet.'],
    ['FILES', 'ARCHIVOS'], ['COVERAGE', 'COBERTURA'], ['STORE', 'ALMACÉN'],
    ['DUCKDB + PARQUET', 'DUCKDB + PARQUET'],
    ['IMPORT NASA FIRMS ARCHIVE', 'IMPORTAR ARCHIVO NASA FIRMS'],
    ['SENSOR / SOURCE IN FILE', 'SENSOR / FUENTE DEL ARCHIVO'],
    ['SELECT FIRMS FILE', 'SELECCIONAR ARCHIVO FIRMS'],
    ['CSV, TXT or ZIP · kept locally for provenance', 'CSV, TXT o ZIP · se conserva localmente'],
    ['IMPORT INTO IGNIS', 'IMPORTAR EN IGNIS'], ['IMPORTING…', 'IMPORTANDO…'],
    ['LOCAL COVERAGE', 'COBERTURA LOCAL'], ['No files imported yet.', 'Aún no hay archivos importados.'],
    ['TEMPORAL INTELLIGENCE', 'INTELIGENCIA TEMPORAL'], ['PLAY', 'REPRODUCIR'],
    ['V0.9.4 · INTELLIGENCE ANALYST', 'V0.9.4 · ANALISTA DE INTELIGENCIA'],
    ['V0.8 · ENVIRONMENTAL INTELLIGENCE', 'V0.8 · INTELIGENCIA AMBIENTAL'],
    ['FIRMS · PERSISTENT TRACKS · EVENT EVOLUTION · ERA5-LAND · CAMS · DUCKDB · PARQUET',
     'FIRMS · SEGUIMIENTOS · EVOLUCIÓN DE EVENTOS · ERA5-LAND · CAMS · DUCKDB · PARQUET'],
    ['THERMAL ANOMALIES ≠ CONFIRMED WILDFIRE · NOT FOR LIFE/PROPERTY SAFETY DECISIONS',
     'ANOMALÍAS TÉRMICAS ≠ INCENDIO CONFIRMADO · NO PARA DECISIONES DE SEGURIDAD'],
    ['STOP','PARAR'], ['SIMULATED','SIMULADO'], ['REPLAY LIFECYCLE','REPRODUCIR CICLO'],
    ['BUILDING TEMPORAL MATRIX…','CONSTRUYENDO MATRIZ TEMPORAL…'], ['CALENDAR FAILED','FALLÓ EL CALENDARIO'],
    /* FIX: estaban invertidos ([es, en]); el walker jamás los encontraba en modo EN */
    ['3D MAP IN SAFE MODE', 'MAPA 3D EN MODO SEGURO'],
    ['RETRY RENDER', 'REINTENTAR RENDER'],
    /* Analista de inteligencia (v0.9) */
    ['INTELLIGENCE ANALYST · BRIEFING', 'ANALISTA DE INTELIGENCIA · INFORME'],
    ['GENERATE BRIEFING', 'GENERAR INFORME'],
    ['BRIEFING FOR', 'INFORME DE'],
    ['EVIDENCE', 'EVIDENCIA'],
    ['Waiting for a track. Open one from the globe or press GENERATE BRIEFING.', 'Esperando un seguimiento. Abre uno del globo o pulsa GENERAR INFORME.'],
    ['Contextual indices (0-100)', 'Índices contextuales (0-100)'],
    ['DRYNESS', 'SEQUEDAD'], ['FUEL', 'COMBUSTIBLE'], ['SMOKE', 'HUMO'], ['CONTEXT', 'CONTEXTO'],
    ['Every sentence is bound to a measured figure. Hover a line to see its citations.',
     'Cada frase está atada a una cifra medida. Pasa el cursor por una línea para ver sus citas.'],
    ['Copied to clipboard.', 'Copiado al portapapeles.'],
    ['Briefing failed', 'Falló el informe'],
    ['No briefing data', 'Sin datos de informe'],
    ['SIMULATED CONTEXT · demonstration only', 'CONTEXTO SIMULADO · solo demostración'],
  ];

  /* --- 2 · cadenas generadas en JavaScript -------------------------------- */
  const MSG = {
    es: {
      sensors_n: '{0} FUENTES', sensors_none: 'SIN SEÑAL',
      tip_mode_hotspots: 'Puntos calientes individuales de FIRMS (MODIS + VIIRS).',
      tip_mode_heat: 'Celdas de actividad armonizadas en la malla común multi-sensor.',
      tip_mode_events: 'Eventos candidatos agrupando anomalías térmicas cercanas.',
      tip_mode_evolution: 'Identidades persistentes de incendios seguidas entre días.',
      tip_evo_demo: 'Carga el escenario sintético de evolución (5 días).',
      tip_evo_archive: 'Rastrea tu archivo local importado: datos NASA reales, sin API.',
      tip_demo: 'Demo analítica de armonización (simulada, sin internet).',
      tip_harmonize: 'Descarga y armoniza observaciones NASA de la región (requiere FIRMS_MAP_KEY e internet).',
      tip_harmonize_no_key: 'Configura FIRMS_MAP_KEY en .env para consultar datos NASA en vivo.',
      tip_calendar: 'Explora patrones estacionales históricos y carga un periodo en el globo.',
      tip_archive: 'Importa archivos FIRMS CSV/TXT/ZIP a DuckDB; funciona sin conexión.',
      tip_export: 'Descarga un snapshot JSON del estado analítico actual.',
      tip_fly: 'Vuela la cámara a la región predefinida.',
      tip_date: 'Fecha inicial de las consultas históricas a FIRMS.',
      tip_window: 'Ventana de días consultada a FIRMS (1 a 5).',
      tip_src: 'Incluir o excluir este sensor en la fusión.',
      tip_grid: 'Tamaño de celda de la malla de armonización.',
      tip_layer_aerosol: 'Espesor óptico de aerosoles MODIS (diario). Suavizado para lectura visual.',
      tip_layer_ndvi: 'Índice de vegetación NDVI, compuesto de 8 días.',
      tip_layer_truecolor: 'Reflectancia verdadera a color. Combina 3 días en una imagen para rellenar huecos de órbita. Al alejarte se muestra el mapa base hasta que haya detalle suficiente.',
      tip_layer_pyro: 'Índice OMPS de piro-cumulonimbos: humo de incendios intensos.',
      tip_analyst: 'Genera un informe explicable, con citas medibles, del evento seleccionado.',
      tip_sev: 'Mostrar u ocultar esta severidad en el globo.',
      tip_prev: 'Frame anterior del timeline.', tip_next: 'Frame siguiente del timeline.',
      tip_play: 'Reproduce la secuencia de frames (inteligencia temporal).',
      tip_slider: 'Inteligencia temporal: arrastra para cambiar el frame; las capas se actualizan al hacer pausa.',
      tip_baseline: 'Compara la actividad del periodo seleccionado con años previos.',
      status_online: 'EN LÍNEA', status_loading: 'CARGANDO', status_error: 'ERROR',
      status_syncing: 'SINCRONIZANDO', status_localdb: 'BD LOCAL', status_analyzing: 'ANALIZANDO',
      status_calendar: 'CALENDARIO', status_importing: 'IMPORTANDO', status_tracking: 'SEGUIMIENTO',
      status_safe: 'RENDER SEGURO', status_offline: 'SIN CONEXIÓN',
      feed_demo: 'DEMO SIMULADA', feed_nasa_history: 'HISTÓRICO NASA', feed_nasa_fusion: 'FUSIÓN NASA',
      data_origin_demo: 'DEMOSTRACIÓN · puntos y fechas simulados. No representan incendios observados.',
      data_origin_observations: 'Observaciones térmicas satelitales · una anomalía no confirma un incendio.',
      env_visible_date: 'Fecha de referencia {0}',
      env_layer_date: '{0}: referencia {1}',
      env_layer_loading: '{0}: cargando {1}; se conserva {2}',
      env_problem: '{0}: {1}; imagen anterior {2}',
      env_playback_frozen: 'Capas fijas durante la reproducción.',
      layer_no_coverage: 'Sin cobertura para esta fecha o zona',
      layer_offline: 'Sin internet; selección conservada',
      feed_local: 'ARCHIVO LOCAL', feed_empty: 'VACÍO', feed_ready: 'LISTO',
      kicker_hotspot: 'INTELIGENCIA DEL PUNTO', kicker_cell: 'CELDA DE MALLA ARMONIZADA',
      severity_high: 'ALTO', severity_critical: 'CRÍTICO', severity_moderate: 'MODERADO', severity_low: 'BAJO',
      layer_aerosol: 'AEROSOLES (AOD)', layer_ndvi: 'VEGETACIÓN (NDVI)',
      layer_truecolor: 'COLOR REAL', layer_pyro: 'PIRO-CUMULONIMBOS (OMPS)',
      toast_zoom: 'Acércate más antes de consultar. La vista es demasiado amplia o cruza la línea de fecha.',
      toast_partial: 'Cobertura parcial de sensores: {0}',
      toast_demo_loaded: 'Demo analítica cargada. Es simulada y muestra el flujo de armonización.',
      toast_demo_fail: 'Falló la demo: {0}',
      toast_period: 'Periodo cargado: {0} · {1}. Datos sintéticos.',
      toast_select_sensor: 'Selecciona al menos una fuente de sensores.',
      toast_harmonized: 'Observaciones NASA armonizadas en una malla común.',
      toast_import_first: 'Primero importa datos del archivo FIRMS. Abre el Gestor de Archivo Local.',
      toast_archive_loaded: 'Cargados {0} día(s) desde el archivo DuckDB local. Sin peticiones a la API de NASA.',
      toast_load_frame: 'Carga primero un frame del timeline.',
      toast_baseline_needs_key: 'Se necesita FIRMS_MAP_KEY para la línea base en vivo, o usa el modo Archivo Local.',
      toast_env_context: 'Contexto ambiental: {0}',
      toast_load_dataset: 'Carga primero un conjunto analítico.',
      toast_snapshot: 'Snapshot de inteligencia exportado como JSON.',
      toast_no_tracks: 'Aún no hay seguimientos. Pulsa CARGAR EVOLUCIÓN DE INCENDIOS (v0.7).',
      toast_load_timeline: 'Carga primero un timeline de varios días.',
      toast_calendar_years: 'El año DESDE debe ser anterior al año HASTA.',
      toast_demo_region: 'La demo completa necesita una región predefinida; se usa México.',
      toast_archive_empty: 'Tu archivo local está vacío. Importa archivos FIRMS.',
      toast_calendar_key: 'El calendario de muestra NASA requiere FIRMS_MAP_KEY en .env.',
      toast_select_file: 'Selecciona primero un archivo FIRMS CSV, TXT o ZIP.',
      toast_import_done: 'Importación completa: {0} observaciones nuevas.',
      toast_viewport_active: 'La vista actual ya es tu área activa.',
      toast_evo_demo: 'Motor de Evolución: {0} seguimientos persistentes ({1} multi-frame). Escenario sintético.',
      toast_evo_fail: 'Falló la demo de evolución: {0}',
      toast_real_tracks: 'DATOS NASA REALES · {0} seguimientos persistentes ({1} multi-frame) del archivo local.',
      toast_select_track: 'Selecciona primero un evento rastreado.',
      toast_single_frame: 'Este seguimiento tiene un solo frame observado.',
      toast_replay_done: 'Reproducción del ciclo completa: {0} — {1}.',
      toast_render_light: 'Render simplificado para mantener el planeta operativo.',
      toast_render_retry: 'Render reintentado con efectos completos.',
      toast_render_fail: 'No se pudo reiniciar el render: {0}',
      toast_layer_on: 'Capa {0} · {1} (NASA GIBS){2}',
      toast_layer_lag: ' · compuesto de {0} día(s) antes',
      toast_layer_off: 'Capa {0} desactivada.',
      toast_basemap_local: 'Sin conexión con OpenStreetMap: se usa el globo Natural Earth II local (baja resolución).',
      toast_layer_fail: 'No se pudo añadir {0}: {1}',
      toast_layer_unavailable: 'NASA GIBS no está disponible para {0}. Se conserva la selección y, si existe, la imagen anterior.',
      toast_archive_status: 'No se pudo leer el estado del archivo: {0}',
      toast_config: 'No se pudo leer la configuración: {0}',
      layer_unreachable: 'NASA GIBS no respondió (¿sin internet?)',
      toast_briefing_done: 'Informe generado: {0} frases con {1} citas verificables.',
      toast_briefing_fail: 'Falló el informe: {0}',
      aoi_eye: 'OJO {0} KM', aoi_alt: 'ALT {0} KM',
      calendar_demo_note: 'Demo sintética para explorar la interfaz. No son observaciones NASA.',
      calendar_archive_note: 'ARCHIVO LOCAL: observaciones mensuales completas. Funciona sin llamadas a la API de NASA.',
      calendar_sample_note: 'Modo muestra NASA: ventanas MODIS de igual longitud para comparar estaciones; no son meses completos.',
      calendar_score_tip: '{0} · puntuación {1}{2}', calendar_unavailable_tip: '{0} sin datos',
      calendar_selected_area: 'Área seleccionada',
      calendar_activity: 'ACTIVIDAD {0} / 100{1}',
      calendar_qualifier_archive: 'detecciones locales completas',
      calendar_qualifier_nasa: 'detecciones de muestra',
      calendar_qualifier_demo: 'detecciones demo',
      anomaly_typical: 'TÍPICO', anomaly_elevated: 'ELEVADO', anomaly_exceptional: 'EXCEPCIONAL', anomaly_below: 'BAJO LO NORMAL',
      anomaly_note: '{0} · {1} detecciones históricas · z={2}',
      cell_agreement: '{0}% · acuerdo {1}%', event_score: 'Σ {0} MW · puntuación {1}',
      event_confidence: '{0}% · {1} detecciones',
      dryness_unknown: 'DESCONOCIDO', dryness_mixed: 'MIXTO', dryness_dry: 'SECO',
      dryness_very_dry: 'MUY SECO', dryness_abnormally_dry: 'ANORMALMENTE SECO',
      weather_unavailable: 'tiempo no disponible', air_unavailable: 'calidad del aire no disponible',
      region_mexico: 'México', region_amazon: 'Cuenca Amazónica', region_california: 'California',
      region_mediterranean: 'Mediterráneo', region_australia: 'Australia', region_viewport: 'Vista actual',
      env_loading: 'consultando NASA GIBS + ERA5…',
      env_none: 'sin evidencia disponible (¿sin internet?)',
      env_unavailable: 'entorno no disponible',
      analyst_loading: 'redactando informe con los datos medidos…',
      analyst_hint: 'Selecciona un evento persistente para generar su informe explicable.',
      short_dryness: 'SEQUEDAD', short_fuel: 'COMBUSTIBLE', short_smoke: 'HUMO', short_context: 'CONTEXTO',
      word_detections: 'detecciones', word_detection: 'detección', kicker_track: 'EVENTO DE FUEGO PERSISTENTE',
      kicker_event: 'EVENTO DE FUEGO CANDIDATO · {0}',
      ev_none: 'No hay eventos candidatos multi-detección en este periodo.',
      ev_row_summary: '{0} detecciones · {1} h · radio {2} km',
      state_emerging: 'EMERGENTE', state_expanding: 'EN EXPANSIÓN', state_stable: 'ESTABLE',
      state_declining: 'EN DECLIVE', state_extinct: 'EXTINTO',
      track_row: '{0} frames · {1} detecciones · {2} h', track_drift: 'deriva {0}',
      track_intensity: 'intensidad {0}% respecto al frame anterior',
      track_no_recent: 'sin detecciones vinculadas en el último frame de estos datos',
      track_caveat: 'La identidad persistente vincula grupos espaciotemporales mediante una heurística; no es un identificador oficial. El movimiento es deriva aparente del centroide, no un modelo de propagación.',
      track_drift_note: 'Deriva aparente del centroide entre pasadas satelitales; no es un modelo de propagación del fuego.',
      track_caveat_short: 'Etiqueta analítica; no es un registro oficial de incidentes.',
      track_peak: 'pico', tracking_summary: '{0} · {1}% CONF · {2} DET',
      replay_lifecycle: '▶ REPRODUCIR CICLO', replaying: '● REPRODUCIENDO',
      identity_reused: 'IDENTIDAD REUTILIZADA', identity_new: 'IDENTIDAD NUEVA',
      conf_detections: 'DETECCIONES', conf_persistence: 'PERSISTENCIA', conf_sensors: 'SENSORES',
      conf_frp: 'FRP PICO', conf_declared: 'CONF. DECLARADA',
      sev_signal: 'SEÑAL', sev_low: 'BAJO', sev_medium: 'MEDIO', sev_moderate: 'MODERADO', sev_high: 'ALTO', sev_critical: 'CRÍTICO',
      env_no_data: 'sin dato', env_pending: 'consulta pendiente', env_analyzing: 'consultando NASA GIBS + ERA5…',
      env_unavailable_short: 'entorno no disponible',
      track_summary: '{0} seguimiento(s) persistente(s) · {1} multi-frame · radio de vínculo {2} km',
      render_alert_no_webgl_t: 'SIN ACELERACIÓN 3D',
      render_alert_no_webgl_b: 'Este navegador no expone WebGL, así que Cesium no puede dibujar el planeta. Prueba en Chrome/Edge/Firefox actualizados o activa la aceleración por hardware.',
      render_alert_stopped_t: 'MAPA 3D DETENIDO',
      render_alert_stopped_b: 'El visor dejó de dibujar cuadros. Detalle del motor: {0}. Se desactivaron los efectos pesados; la analítica y las APIs siguen funcionando.',
      /* explicaciones del motor de confianza (vienen del backend en inglés) */
      ev_detections: '{0} detecciones en {1} frame(s)',
      ev_persistence: 'persistencia {0} h',
      ev_sensors_one: '1 familia de sensores independiente: {0}',
      ev_sensors_many: '{0} familias de sensores independientes: {1}',
      ev_peak_frp: 'FRP pico {0} MW',
      ev_declared: 'confianza declarada media {0}%',
      'INTELLIGENCE ANALYST · BRIEFING': 'ANALISTA DE INTELIGENCIA · INFORME',
      'COPY': 'COPIAR',
    },
    en: {
      sensors_n: '{0} SOURCES', sensors_none: 'NO SIGNAL',
      tip_mode_hotspots: 'Individual FIRMS thermal anomalies (MODIS + VIIRS).',
      tip_mode_heat: 'Harmonized activity cells on the common multi-sensor grid.',
      tip_mode_events: 'Candidate events clustering nearby thermal anomalies.',
      tip_mode_evolution: 'Persistent fire identities tracked across days.',
      tip_evo_demo: 'Loads the synthetic 5-day evolution scenario.',
      tip_evo_archive: 'Tracks your imported local archive: real NASA data, no API.',
      tip_demo: 'Analytical harmonization demo (simulated, works offline).',
      tip_harmonize: 'Downloads and harmonizes NASA observations for the region (needs FIRMS_MAP_KEY + internet).',
      tip_harmonize_no_key: 'Configure FIRMS_MAP_KEY in .env to query live NASA data.',
      tip_calendar: 'Explores historical seasonal patterns and loads a period on the globe.',
      tip_archive: 'Imports FIRMS CSV/TXT/ZIP files into DuckDB; works offline.',
      tip_export: 'Downloads a JSON snapshot of the current analytical state.',
      tip_fly: 'Flies the camera to the preset region.',
      tip_date: 'Start date for historical FIRMS queries.',
      tip_window: 'Day window queried from FIRMS (1 to 5).',
      tip_src: 'Include or exclude this sensor from the fusion.',
      tip_grid: 'Cell size of the harmonization grid.',
      tip_layer_aerosol: 'MODIS aerosol optical depth (daily). Smoothed for visual reading.',
      tip_layer_ndvi: 'NDVI vegetation index, 8-day composite.',
      tip_layer_truecolor: 'True-color reflectance. Combines 3 days into one image to fill orbit gaps. When zoomed out, the base map appears until enough detail is available.',
      tip_layer_pyro: 'OMPS pyro-cumulonimbus index: smoke from intense fires.',
      tip_analyst: 'Generates an explainable briefing, with measured citations, for the selected event.',
      tip_sev: 'Show or hide this severity on the globe.',
      tip_prev: 'Previous timeline frame.', tip_next: 'Next timeline frame.',
      tip_play: 'Plays the frame sequence (temporal intelligence).',
      tip_slider: 'Temporal intelligence: drag to change the frame; layers refresh on pause.',
      tip_baseline: 'Compares the selected period activity with prior years.',
      status_online: 'ONLINE', status_loading: 'LOADING', status_error: 'ERROR',
      status_syncing: 'SYNCING', status_localdb: 'LOCAL DB', status_analyzing: 'ANALYZING',
      status_calendar: 'CALENDAR', status_importing: 'IMPORTING', status_tracking: 'TRACKING',
      status_safe: 'SAFE RENDER', status_offline: 'OFFLINE',
      feed_demo: 'SIMULATED DEMO', feed_nasa_history: 'NASA HISTORY', feed_nasa_fusion: 'NASA FUSION',
      data_origin_demo: 'DEMONSTRATION · simulated points and dates. These are not observed fires.',
      data_origin_observations: 'Satellite thermal observations · an anomaly does not confirm a wildfire.',
      env_visible_date: 'Reference date {0}',
      env_layer_date: '{0}: reference {1}',
      env_layer_loading: '{0}: loading {1}; retaining {2}',
      env_problem: '{0}: {1}; previous image {2}',
      env_playback_frozen: 'Layers stay fixed during playback.',
      layer_no_coverage: 'No coverage for this date or location',
      layer_offline: 'Offline; selection retained',
      feed_local: 'LOCAL ARCHIVE', feed_empty: 'EMPTY', feed_ready: 'READY',
      kicker_hotspot: 'HOTSPOT INTELLIGENCE', kicker_cell: 'HARMONIZED GRID CELL',
      severity_high: 'HIGH', severity_critical: 'CRITICAL', severity_moderate: 'MODERATE', severity_low: 'LOW',
      layer_aerosol: 'AEROSOLS (AOD)', layer_ndvi: 'VEGETATION (NDVI)',
      layer_truecolor: 'TRUE COLOR', layer_pyro: 'PYRO-CUMULONIMBUS (OMPS)',
      toast_zoom: 'Zoom closer before querying. The viewport is too large or crosses the date line.',
      toast_partial: 'Partial sensor coverage: {0}',
      toast_demo_loaded: 'Analytical demo loaded. It is simulated and demonstrates the harmonization workflow.',
      toast_demo_fail: 'Demo load failed: {0}',
      toast_period: 'Demo period loaded: {0} · {1}. Synthetic data.',
      toast_select_sensor: 'Select at least one sensor source.',
      toast_harmonized: 'NASA observations harmonized on a common grid.',
      toast_import_first: 'Import NASA FIRMS archive data first. Open Local Archive Manager.',
      toast_archive_loaded: 'Loaded {0} day(s) from the local DuckDB archive. No NASA API request used.',
      toast_load_frame: 'Load a timeline frame first.',
      toast_baseline_needs_key: 'NASA FIRMS MAP_KEY is required for a live baseline, or use Local Archive mode.',
      toast_env_context: 'Environmental context: {0}',
      toast_load_dataset: 'Load an analytical dataset first.',
      toast_snapshot: 'Intelligence snapshot exported as JSON.',
      toast_no_tracks: 'No evolution tracks loaded yet. Press LOAD FIRE EVOLUTION (v0.7).',
      toast_load_timeline: 'Load a multi-day timeline first.',
      toast_calendar_years: 'Calendar FROM year must be before TO year.',
      toast_demo_region: 'Full demo needs a preset region; using Mexico.',
      toast_archive_empty: 'Your local archive is empty. Import FIRMS files first.',
      toast_calendar_key: 'NASA sampled calendar requires FIRMS_MAP_KEY in .env.',
      toast_select_file: 'Select a FIRMS CSV, TXT or ZIP file first.',
      toast_import_done: 'Archive import complete: {0} new observations.',
      toast_viewport_active: 'Current viewport is already your active area.',
      toast_evo_demo: 'Fire Evolution Engine: {0} persistent tracks ({1} multi-frame). Synthetic scenario.',
      toast_evo_fail: 'Evolution demo failed: {0}',
      toast_real_tracks: 'NASA REAL DATA · {0} persistent tracks ({1} multi-frame) from the local archive.',
      toast_select_track: 'Select a tracked event first.',
      toast_single_frame: 'This track has a single observed frame.',
      toast_replay_done: 'Lifecycle replay complete: {0} — {1}.',
      toast_render_light: 'Simplified render to keep the planet operational.',
      toast_render_retry: 'Render retried with full effects.',
      toast_render_fail: 'Could not restart the render: {0}',
      toast_layer_on: 'Layer {0} · {1} (NASA GIBS){2}',
      toast_layer_lag: ' · composite {0} day(s) earlier',
      toast_layer_off: 'Layer {0} disabled.',
      toast_basemap_local: 'OpenStreetMap unreachable: falling back to the local Natural Earth II globe (low resolution).',
      toast_layer_fail: 'Could not add {0}: {1}',
      toast_layer_unavailable: 'NASA GIBS is unavailable for {0}. Selection and any previous image are retained.',
      toast_archive_status: 'Could not read archive status: {0}',
      toast_config: 'Could not read configuration: {0}',
      layer_unreachable: 'NASA GIBS did not respond (offline?)',
      toast_briefing_done: 'Briefing generated: {0} sentences with {1} verifiable citations.',
      toast_briefing_fail: 'Briefing failed: {0}',
      aoi_eye: 'EYE {0} KM', aoi_alt: 'ALT {0} KM',
      calendar_demo_note: 'Synthetic full-history demo for interface exploration. Not NASA observations.',
      calendar_archive_note: 'LOCAL ARCHIVE: complete imported monthly observations. Works without NASA API calls.',
      calendar_sample_note: 'NASA sampled mode: equal-length MODIS windows for seasonal comparison; not complete monthly data.',
      calendar_score_tip: '{0} · score {1}{2}', calendar_unavailable_tip: '{0} unavailable',
      calendar_selected_area: 'Selected area',
      calendar_activity: 'ACTIVITY {0} / 100{1}',
      calendar_qualifier_archive: 'complete local detections',
      calendar_qualifier_nasa: 'sampled detections',
      calendar_qualifier_demo: 'demo detections',
      anomaly_typical: 'TYPICAL', anomaly_elevated: 'ELEVATED', anomaly_exceptional: 'EXCEPTIONAL', anomaly_below: 'BELOW-NORMAL',
      anomaly_note: '{0} · {1} historical detections · z={2}',
      cell_agreement: '{0}% · agreement {1}%', event_score: 'Σ {0} MW · score {1}',
      event_confidence: '{0}% · {1} detections',
      dryness_unknown: 'UNKNOWN', dryness_mixed: 'MIXED', dryness_dry: 'DRY',
      dryness_very_dry: 'VERY DRY', dryness_abnormally_dry: 'ABNORMALLY DRY',
      weather_unavailable: 'weather unavailable', air_unavailable: 'air quality unavailable',
      region_mexico: 'Mexico', region_amazon: 'Amazon Basin', region_california: 'California',
      region_mediterranean: 'Mediterranean', region_australia: 'Australia', region_viewport: 'Current viewport',
      env_loading: 'querying NASA GIBS + ERA5…',
      env_none: 'no evidence available (offline?)',
      env_unavailable: 'environment unavailable',
      analyst_loading: 'writing the briefing from measured data…',
      analyst_hint: 'Select a persistent event to generate its explainable briefing.',
      short_dryness: 'DRYNESS', short_fuel: 'FUEL', short_smoke: 'SMOKE', short_context: 'CONTEXT',
      word_detections: 'detections', word_detection: 'detection', kicker_track: 'PERSISTENT FIRE EVENT',
      kicker_event: 'CANDIDATE FIRE EVENT · {0}',
      ev_none: 'No multi-detection candidate events in this period.',
      ev_row_summary: '{0} detections · {1} h · {2} km radius',
      state_emerging: 'EMERGING', state_expanding: 'EXPANDING', state_stable: 'STABLE',
      state_declining: 'DECLINING', state_extinct: 'EXTINCT',
      track_row: '{0} frames · {1} detections · {2} h', track_drift: 'drift {0}',
      track_intensity: 'intensity {0}% vs previous frame',
      track_no_recent: 'no linked detections in the most recent frame of this dataset',
      track_caveat: 'Persistent identity is a heuristic link between spatiotemporal clusters, not an official incident ID. Movement is apparent centroid drift, not a propagation model.',
      track_drift_note: 'Apparent centroid drift between satellite overpasses; NOT a fire-spread or propagation model.',
      track_caveat_short: 'Analytical label — not an official incident record.',
      track_peak: 'peak', tracking_summary: '{0} · {1}% CONF · {2} DET',
      replay_lifecycle: '▶ REPLAY LIFECYCLE', replaying: '● REPLAYING',
      identity_reused: 'IDENTITY REUSED', identity_new: 'NEW IDENTITY',
      conf_detections: 'DETECTIONS', conf_persistence: 'PERSISTENCE', conf_sensors: 'SENSORS',
      conf_frp: 'PEAK FRP', conf_declared: 'DECLARED CONF.',
      sev_signal: 'SIGNAL', sev_low: 'LOW', sev_medium: 'MEDIUM', sev_moderate: 'MODERATE', sev_high: 'HIGH', sev_critical: 'CRITICAL',
      env_no_data: 'no data', env_pending: 'not queried', env_analyzing: 'querying NASA GIBS + ERA5…',
      env_unavailable_short: 'environment unavailable',
      track_summary: '{0} persistent track(s) · {1} multi-frame · link radius {2} km',
      render_alert_no_webgl_t: 'NO 3D ACCELERATION',
      render_alert_no_webgl_b: 'This browser does not expose WebGL, so Cesium cannot draw the planet. Try an up-to-date Chrome/Edge/Firefox or enable hardware acceleration.',
      render_alert_stopped_t: '3D MAP STOPPED',
      render_alert_stopped_b: 'The viewer stopped drawing frames. Engine detail: {0}. Heavy effects were disabled; analytics and APIs keep working.',
      ev_detections: '{0} detections across {1} frame(s)',
      ev_persistence: 'persistence {0} h',
      ev_sensors_one: '1 independent sensor family: {0}',
      ev_sensors_many: '{0} independent sensor families: {1}',
      ev_peak_frp: 'peak FRP {0} MW',
      ev_declared: 'mean declared confidence {0}%',
      'INTELLIGENCE ANALYST · BRIEFING': 'INTELLIGENCE ANALYST · BRIEFING',
      'COPY': 'COPY',
    },
  };

  /* --- 3 · motor ---------------------------------------------------------- */
  const LOOKUP = { es: {}, en: {} };
  for (const [en, es] of HTML_PAIRS) {
    if (en !== es) { LOOKUP.es[en] = es; LOOKUP.en[es] = en; }
  }

  // OPTION sí se traduce: los <select> muestran su texto (los valores no se tocan).
  const SKIP_TAGS = new Set(['SCRIPT', 'STYLE', 'INPUT', 'TEXTAREA']);
  let lang = 'es';
  const listeners = [];

  function detect() {
    try {
      const stored = localStorage.getItem('ignis-lang');
      if (stored === 'es' || stored === 'en') return stored;
    } catch (e) { /* origen opaco: sin almacenamiento */ }
    const nav = (navigator.language || 'es').toLowerCase();
    return nav.startsWith('es') ? 'es' : 'en';
  }

  function t(key, ...vars) {
    const table = MSG[lang] || MSG.es;
    // 1) mensajes propios del JS  2) textos del HTML (claves escritas en inglés)  3) la clave
    let text = table[key] || MSG.es[key] || (lang === 'es' ? LOOKUP.es[key] : null) || key;
    vars.forEach((v, i) => { text = text.replace('{' + i + '}', v); });
    return text;
  }

  function translateNode(node) {
    const raw = node.nodeValue;
    if (!raw) return;
    const trimmed = raw.trim();
    if (!trimmed) return;
    const hit = LOOKUP[lang] && LOOKUP[lang][trimmed];
    if (hit) node.nodeValue = raw.replace(trimmed, hit);
  }

  function translateAttributes(root) {
    /* v0.9.4 — tooltips nativos localizados: cualquier elemento con data-tip
       recibe su title en el idioma activo. */
    root.querySelectorAll('[data-tip]').forEach(el => {
      el.title = t(el.getAttribute('data-tip'));
    });
    root.querySelectorAll('[data-i18n-title]').forEach(el => {
      const key = el.getAttribute('data-i18n-title');
      const table = { es: {}, en: {} };
      if (key === 'collapse') el.title = lang === 'es' ? 'Minimizar panel' : 'Minimize panel';
      if (key === 'calendar') el.title = lang === 'es' ? 'Calendario de actividad' : 'Burning activity calendar';
    });
  }

  function apply(next, options) {
    lang = next === 'en' ? 'en' : 'es';
    const root = (options && options.root) || document.body;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode(n) {
        const parent = n.parentElement;
        if (!parent) return NodeFilter.FILTER_REJECT;
        if (SKIP_TAGS.has(parent.tagName)) return NodeFilter.FILTER_REJECT;
        if (parent.closest('[data-i18n-skip]')) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach(translateNode);
    translateAttributes(root);
    document.documentElement.lang = lang;
    document.title = lang === 'es'
      ? 'IGNIS · Inteligencia de incendios (anomalías térmicas NASA FIRMS)'
      : 'IGNIS · Fire intelligence (NASA FIRMS thermal anomalies)';
    try { localStorage.setItem('ignis-lang', lang); } catch (e) {}
    listeners.forEach(fn => { try { fn(lang); } catch (e) {} });
  }

  function onChange(fn) { listeners.push(fn); }

  return {
    t,
    apply,
    onChange,
    detect,
    get lang() { return lang; },
    set lang(v) { apply(v); },
  };
})();
