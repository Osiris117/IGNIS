/* Contextual help stays outside scroll panels so it cannot be clipped. */
(function () {
  'use strict';

  const COPY = {
    modes: [
      ['Modos del mapa', 'Puntos calientes muestra detecciones; Malla agrupa sensores por celdas; Eventos agrupa señales cercanas; Evolución relaciona esas señales entre fechas. Son análisis de anomalías térmicas, no confirmaciones ni perímetros oficiales de incendios.'],
      ['Map modes', 'Hotspots shows detections; Fusion Grid combines sensors in cells; Events groups nearby signals; Evolution links those signals across dates. These are thermal-anomaly analyses, not confirmed fires or official incident perimeters.']
    ],
    area: [
      ['Área de interés', 'La región limita las consultas y el análisis. “Vista actual” usa el área visible del globo. “Volar a la región” solo mueve la cámara; para cambiar los datos debes cargar la demo, consultar NASA o usar el archivo local.'],
      ['Area of interest', 'The region bounds data requests and analysis. “Current viewport” uses the visible globe area. “Fly to region” moves the camera; load a demo, request NASA data or use the local archive to change the dataset.']
    ],
    sensors: [
      ['Fusión de sensores', 'MODIS y VIIRS observan a distintas horas y resoluciones. Activar una fuente la incluye en la consulta y la fusión. Varias detecciones pueden corresponder al mismo lugar: no sumes los conteos de sensores como incendios distintos.'],
      ['Sensor fusion', 'MODIS and VIIRS observe at different times and resolutions. Enabling a source includes it in requests and fusion. Multiple detections can refer to the same place: sensor counts do not represent separate fires.']
    ],
    layers: [
      ['Capas ambientales', 'Añaden imágenes NASA GIBS de aerosoles, vegetación, color real y aerosoles elevados asociados a humo. Necesitan internet y pueden tener nubes, huecos o cobertura parcial. No son detecciones de incendios. La fecha de la imagen puede diferir si se usa un compuesto o el último día disponible.'],
      ['Environmental layers', 'These add NASA GIBS imagery of aerosols, vegetation, true color and elevated aerosols associated with smoke. Internet is required; clouds, gaps and partial coverage are possible. They are not fire detections. Composites or the latest available day may differ from the selected date.']
    ],
    analyst: [
      ['Informe explicable', 'Selecciona un seguimiento y genera un resumen de sus observaciones y contexto. Sus citas permiten revisar la evidencia. Si la fuente es DEMO, las señales son simuladas; el contexto externo no confirma que esos puntos sean incendios reales.'],
      ['Explainable briefing', 'Select a track to summarize its observations and context. Citations let you review the evidence. When the source is DEMO, the signals are simulated; external context does not confirm that those points are real fires.']
    ],
    filters: [
      ['Filtros de severidad', 'Muestran u ocultan grupos de anomalías según su clasificación analítica. El color expresa intensidad o puntuación del dato; no determina por sí solo el tamaño de un incendio ni el peligro para una población.'],
      ['Severity filters', 'Show or hide anomaly groups by their analytical classification. Color represents the signal intensity or score; it does not determine fire size or danger to a community.']
    ],
    activity: [
      ['Actividad visible', 'El conteo cambia con el modo, los filtros y la fecha: puede contar detecciones, celdas o eventos. El índice combina señales de sensores en una escala relativa de 0 a 100; no es un índice oficial de riesgo de incendio.'],
      ['Visible activity', 'The count changes with the mode, filters and date: it can count detections, cells or events. The index combines sensor signals on a relative 0–100 scale; it is not an official fire-risk index.']
    ],
    baseline: [
      ['Comparación histórica', 'Compara la actividad de un periodo con años anteriores usando una referencia MODIS consistente. Una anomalía elevada significa más actividad que esa referencia, no mayor gravedad de cada señal. La cobertura y las ventanas de muestreo importan.'],
      ['Historical comparison', 'Compare period activity against earlier years using a consistent MODIS reference. An elevated anomaly means more activity than that reference, not that each signal is more severe. Coverage and sampling windows matter.']
    ],
    period: [
      ['Periodo seleccionado', 'Muestra el mes o periodo elegido en el calendario. Revisa el modo del calendario: Demo es sintético, Archivo local usa tus observaciones importadas y Muestra NASA cubre ventanas de muestreo, no necesariamente meses completos.'],
      ['Selected period', 'Shows the month or period chosen in the calendar. Check the calendar mode: Demo is synthetic, Local Archive uses imported observations and NASA Sample covers sampling windows, which may not represent complete months.']
    ],
    archive: [
      ['Archivo local', 'Importa archivos NASA FIRMS CSV, TXT o ZIP para consultarlos sin internet. Solo hay datos de las fechas y regiones incluidas en tus archivos. Un archivo vacío o un día sin registros no equivale a ausencia comprobada de incendios.'],
      ['Local archive', 'Import NASA FIRMS CSV, TXT or ZIP files for offline use. Only the dates and regions contained in your files are available. An empty archive or a day without records does not prove that no fires occurred.']
    ],
    evolution: [
      ['Evolución de señales', 'Relaciona detecciones cercanas entre días para estimar persistencia, desplazamiento e intensidad. Un seguimiento puede aparecer o desaparecer por cobertura del satélite. La identidad y el estado son etiquetas analíticas, no incidentes confirmados.'],
      ['Signal evolution', 'Links nearby detections across days to estimate persistence, movement and intensity. Tracks can appear or disappear because of satellite coverage. Their identity and lifecycle state are analytical labels, not confirmed incidents.']
    ],
    events: [
      ['Eventos candidatos', 'Agrupa anomalías térmicas cercanas en tiempo y espacio. Una agrupación puede corresponder a fuego, actividad industrial u otras fuentes de calor. Revisa su procedencia y evidencia antes de interpretar el resultado.'],
      ['Candidate events', 'Groups thermal anomalies close in time and space. A group may reflect fire, industrial activity or other heat sources. Review its source and evidence before interpreting the result.']
    ],
    context: [
      ['Contexto ambiental', 'Añade meteorología, humedad del suelo y calidad del aire alrededor de la señal. Es contexto de modelos y observaciones: el viento, la sequedad o los aerosoles no prueban el origen de un incendio ni atribuyen el humo a ese punto.'],
      ['Environmental context', 'Adds weather, soil moisture and air-quality context around the signal. These are model and observation inputs: wind, dryness or aerosols do not prove a fire origin or attribute smoke to that point.']
    ],
    date: [
      ['Fecha inicial', 'Fija el primer día de una consulta histórica. Usa la ventana para elegir cuántos días cargar. Cambiar la fecha no convierte una demo en datos reales: la fuente elegida determina qué observaciones se muestran.'],
      ['Start date', 'Sets the first day of a historical request. Use the window to choose how many days to load. Changing a date does not turn a demo into real data: the selected source determines the observations shown.']
    ],
    window: [
      ['Ventana de días', 'Número de días incluidos en una consulta histórica FIRMS: 1, 3 o 5. Varias fechas permiten seguir cambios; con un solo día no se puede reconstruir una evolución temporal.'],
      ['Day window', 'Number of days included in a historical FIRMS request: 1, 3 or 5. Multiple dates allow temporal tracking; a single day cannot reconstruct an evolution sequence.']
    ],
    grid: [
      ['Malla común', 'Agrupa observaciones en celdas aproximadas de 6, 11 o 22 km. Una malla fina conserva más detalle; una amplia facilita comparar regiones. La celda no representa un perímetro quemado ni la resolución original del sensor.'],
      ['Common grid', 'Groups observations in approximate 6, 11 or 22 km cells. A finer grid retains more detail; a larger grid supports regional comparisons. Cells are not burned-area perimeters or the native sensor resolution.']
    ],
    frp: [
      ['FRP y puntuación', 'FRP es la potencia radiativa del fuego estimada por el satélite, en megavatios (MW). En una celda o evento puede mostrarse una suma o puntuación analítica. No es temperatura, superficie quemada ni número de incendios.'],
      ['FRP and score', 'FRP is satellite-estimated fire radiative power, in megawatts (MW). A cell or event can show a sum or analytical score. It is not temperature, burned area or the number of fires.']
    ],
    confidence: [
      ['Confianza de la detección', 'Indica la calidad de identificación térmica del sensor. MODIS y VIIRS usan escalas distintas. Una confianza alta no confirma por sí sola un incendio forestal: revisa el lugar, la fuente y otras observaciones.'],
      ['Detection confidence', 'Indicates the sensor’s confidence in identifying a thermal signal. MODIS and VIIRS use different scales. High confidence alone does not confirm a wildfire: review the location, source and other observations.']
    ],
    acquired: [
      ['Hora de observación', 'Fecha y hora en que el satélite registró la señal, en UTC. No es la hora de inicio de un incendio. La observación puede llegar después del paso del satélite.'],
      ['Acquisition time', 'The date and time the satellite recorded the signal, in UTC. This is not a fire’s start time. An observation may become available after the satellite overpass.']
    ],
    event_confidence: [
      ['Confianza del seguimiento', 'Puntuación analítica basada en la evidencia del seguimiento, como repetición, sensores y coherencia temporal. Es distinta de la confianza original de cada detección y no es una probabilidad oficial de incendio.'],
      ['Track confidence', 'An analytical score based on track evidence, such as repeated observations, sensors and temporal consistency. It differs from each detection’s sensor confidence and is not an official fire probability.']
    ],
    calendar: [
      ['Calendario de actividad', 'Cada celda resume un mes y permite cargar su periodo en el mapa. Los colores comparan actividad, no peligro. Comprueba la fuente: Demo es simulada; Archivo local usa archivos importados; Muestra NASA consulta ventanas comparables y requiere conexión.'],
      ['Activity calendar', 'Each cell summarizes a month and can load its period on the map. Colors compare activity, not danger. Check the source: Demo is simulated; Local Archive uses imported files; NASA Sample requests comparable windows and requires internet.']
    ],
    archive_import: [
      ['Importar observaciones', 'Elige el sensor que corresponde al archivo FIRMS y luego el CSV, TXT o ZIP descargado. IGNIS conserva la procedencia y almacena las observaciones localmente. No mezcles un archivo de un sensor con una fuente distinta.'],
      ['Import observations', 'Choose the sensor matching your FIRMS file, then select the downloaded CSV, TXT or ZIP. IGNIS preserves source provenance and stores observations locally. Do not label a file as a different sensor.']
    ],
    archive_coverage: [
      ['Cobertura del archivo', 'Indica qué sensores, fechas y observaciones has importado. El calendario local usa esos registros, sin consultas NASA. Los huecos pueden ser falta de archivos o cobertura, no ausencia de actividad.'],
      ['Archive coverage', 'Shows imported sensors, dates and observations. The local calendar uses those records without NASA requests. Gaps can reflect missing files or coverage rather than no activity.']
    ],
    feed: [
      ['Procedencia de los datos', 'DEMO significa señales inventadas para probar la interfaz; no son incendios ni observaciones NASA. Histórico/Fusión NASA usa consultas FIRMS; Archivo local usa archivos importados. NASA detecta anomalías térmicas, que también pueden incluir fuentes industriales o plataformas marinas. Las imágenes ambientales pueden ser reales aunque los puntos sean demo; no validan esas señales simuladas.'],
      ['Data provenance', 'DEMO means synthetic signals for testing the interface; they are not fires or NASA observations. NASA History/Fusion uses FIRMS requests; Local Archive uses imported files. NASA detects thermal anomalies, which can include industrial sources or offshore platforms. Environmental imagery can be real while points are simulated; it does not validate demo signals.']
    ],
    renderer: [
      ['Render del globo', 'GPU usa aceleración gráfica. SOFTWARE o SAFE indica un modo más ligero cuando no hay aceleración suficiente. El render no cambia los datos; muchas capas pueden ralentizar la visualización.'],
      ['Globe renderer', 'GPU uses graphics acceleration. SOFTWARE or SAFE indicates a lighter mode when acceleration is insufficient. Rendering does not change the data; many layers can slow the display.']
    ],
    timeline: [
      ['Timeline y reproducción', 'La barra recorre las fechas cargadas y las flechas avanzan un día o frame. Reproducir muestra la secuencia; volver a pulsarlo la pausa. La cámara y las capas seleccionadas se conservan. Durante la reproducción las imágenes ambientales mantienen su última fecha cargada y se sincronizan al pausar.'],
      ['Timeline and playback', 'The slider moves through loaded dates; arrows step one day or frame. Play shows the sequence; press it again to pause. The camera and selected layers are preserved. Environmental imagery keeps its last loaded date during playback and synchronizes on pause.']
    ],
    aerosol: [
      ['Aerosoles · AOD', 'AOD mide cuánto atenúan la luz los aerosoles de la columna atmosférica. Puede incluir humo, polvo o contaminación: no identifica por sí solo su causa ni concentración a nivel del suelo. La imagen diaria puede no cubrir toda la región.'],
      ['Aerosols · AOD', 'AOD measures how aerosols in the atmospheric column attenuate light. It may include smoke, dust or pollution: it does not identify the cause or ground-level concentration on its own. Daily imagery may not cover the whole region.']
    ],
    ndvi: [
      ['Vegetación · NDVI', 'Índice del verdor de la vegetación, con un compuesto de 8 días. Ayuda a contextualizar cobertura vegetal; no mide directamente combustible seco ni riesgo de incendio. Nubes y agua pueden producir valores bajos o huecos.'],
      ['Vegetation · NDVI', 'An index of vegetation greenness from an 8-day composite. It gives vegetation-cover context; it does not directly measure dry fuel or fire risk. Clouds and water can produce low values or gaps.']
    ],
    truecolor: [
      ['Color real', 'Imagen óptica del satélite, similar a una fotografía. Se combinan hasta 3 días para rellenar huecos de órbita; por eso algunas zonas pueden tener otra fecha. Al alejarte se muestra el mapa base. Nubes, costuras y zonas sin cobertura son posibles.'],
      ['True color', 'Optical satellite imagery, similar to a photograph. Up to 3 days are combined to fill orbital gaps, so some areas may show a different date. The base map is used at distant zoom levels. Clouds, seams and coverage gaps are possible.']
    ],
    pyro: [
      ['Humo · OMPS', 'El índice de aerosoles OMPS resalta aerosoles absorbentes elevados que pueden estar asociados a humo o polvo. No confirma una nube piro-cumulonimbo ni el origen del humo en un incendio concreto. Sus píxeles son más amplios que los de una fotografía.'],
      ['Smoke · OMPS', 'The OMPS aerosol index highlights elevated absorbing aerosols that may be associated with smoke or dust. It does not confirm a pyrocumulonimbus cloud or trace smoke to a specific fire. Its pixels are coarser than photographic imagery.']
    ],
    export: [
      ['Exportar estado', 'Descarga un archivo JSON con el conjunto y estado analítico actuales, incluida su procedencia. Es útil para revisar o compartir resultados; no exporta una declaración oficial de incidentes.'],
      ['Export state', 'Downloads a JSON file containing the current dataset and analytical state, including provenance. It supports review or sharing; it does not export an official incident declaration.']
    ],
    harmonize: [
      ['Consultar NASA FIRMS', 'Descarga detecciones de las fuentes activas para la región, fecha y ventana elegidas. Requiere internet y una clave FIRMS configurada. Los datos son anomalías térmicas observadas, no una lista verificada de incendios forestales.'],
      ['Request NASA FIRMS data', 'Downloads detections from enabled sources for the selected region, start date and window. Internet and a configured FIRMS key are required. These are observed thermal anomalies, not a verified list of wildfires.']
    ],
    demo: [
      ['Demo analítica', 'Carga observaciones sintéticas para probar la fusión de sensores y explorar la interfaz sin internet. No representa actividad real en la fecha o región mostradas. Usa NASA o el archivo local para analizar observaciones reales.'],
      ['Analytical demo', 'Loads synthetic observations to test sensor fusion and explore the interface offline. It does not represent real activity for the displayed date or region. Use NASA or the local archive to analyze real observations.']
    ],
    evo_demo: [
      ['Demo de evolución', 'Escenario sintético de 5 días que permite probar seguimientos, reproducción y métricas. Las señales, posiciones y cambios son ejemplos; no corresponden a incendios observados.'],
      ['Evolution demo', 'A synthetic 5-day scenario for testing tracks, playback and metrics. Signals, positions and changes are examples; they do not correspond to observed fires.']
    ],
    evo_archive: [
      ['Seguir archivo real', 'Relaciona tus observaciones FIRMS importadas entre fechas, sin pedir datos a NASA. Necesita cobertura de varios días para estimar evolución. Un seguimiento es una agrupación analítica, no un incidente oficial.'],
      ['Track the real archive', 'Links imported FIRMS observations across dates without requesting NASA data. Multi-day coverage is needed to estimate evolution. Tracks are analytical groupings, not official incidents.']
    ],
    fly: [
      ['Mover la cámara', 'Centra el globo en la región predefinida. No descarga ni sustituye observaciones. Puedes arrastrar el globo y usar la rueda o los gestos táctiles para acercarte.'],
      ['Move the camera', 'Centers the globe on the selected preset region. It does not download or replace observations. Drag the globe and use the wheel or touch gestures to zoom.']
    ],
    calendar_demo: [
      ['Calendario demo', 'Historia sintética para explorar patrones y cargar ejemplos. Los conteos y colores no son observaciones NASA ni actividad real.'],
      ['Demo calendar', 'Synthetic history for exploring patterns and loading examples. Counts and colors are not NASA observations or real activity.']
    ],
    calendar_archive: [
      ['Calendario del archivo', 'Resume los registros FIRMS importados por mes. Funciona sin internet, pero solo cubre lo contenido en tu archivo.'],
      ['Archive calendar', 'Summarizes imported FIRMS records by month. It works offline, but only covers the contents of your archive.']
    ],
    calendar_nasa: [
      ['Muestra histórica NASA', 'Compara ventanas MODIS de igual duración para explorar estaciones. No son meses completos. Requiere internet y la clave FIRMS configurada.'],
      ['Historical NASA sample', 'Compares equal-length MODIS windows to explore seasonal patterns. These are not complete months. Internet and a configured FIRMS key are required.']
    ]
  };

  const TIP_KEYS = {
    tip_mode_hotspots: 'modes', tip_mode_heat: 'grid',
    tip_mode_events: 'events', tip_mode_evolution: 'evolution',
    tip_evo_demo: 'evo_demo', tip_evo_archive: 'evo_archive',
    tip_demo: 'demo', tip_harmonize: 'harmonize', tip_calendar: 'calendar',
    tip_archive: 'archive', tip_export: 'export', tip_fly: 'fly',
    tip_layer_aerosol: 'aerosol', tip_layer_ndvi: 'ndvi',
    tip_layer_truecolor: 'truecolor', tip_layer_pyro: 'pyro',
    tip_analyst: 'analyst', tip_baseline: 'baseline'
  };

  const buttons = [];
  let activeButton = null;
  let pinned = false;
  let closeTimer = null;
  let suppressFocus = false;
  const popover = document.createElement('div');
  popover.id = 'ignisHelpPopover';
  popover.className = 'help-popover';
  popover.hidden = true;
  popover.dataset.i18nSkip = 'help';
  popover.setAttribute('role', 'dialog');
  popover.setAttribute('aria-labelledby', 'ignisHelpTitle');
  popover.setAttribute('aria-describedby', 'ignisHelpBody');
  popover.innerHTML = '<div class="help-popover-head"><strong id="ignisHelpTitle"></strong><button type="button" class="help-close">×</button></div><p id="ignisHelpBody"></p>';
  document.body.appendChild(popover);
  const title = popover.querySelector('strong');
  const body = popover.querySelector('p');
  const closeButton = popover.querySelector('.help-close');

  function copy(key) {
    return COPY[key][window.IGNIS_I18N?.lang === 'en' ? 1 : 0];
  }

  function position() {
    if (!activeButton || popover.hidden) return;
    const box = activeButton.getBoundingClientRect();
    const gap = 10;
    const margin = 12;
    const width = popover.offsetWidth;
    const height = popover.offsetHeight;
    let left = box.right + gap;
    if (left + width > innerWidth - margin) left = box.left - width - gap;
    left = Math.max(margin, Math.min(left, innerWidth - width - margin));
    const top = Math.max(margin, Math.min(box.top, innerHeight - height - margin));
    popover.style.left = left + 'px';
    popover.style.top = top + 'px';
  }

  function close(restoreFocus) {
    clearTimeout(closeTimer);
    const previous = activeButton;
    if (previous) {
      previous.setAttribute('aria-expanded', 'false');
      previous.removeAttribute('aria-describedby');
    }
    popover.hidden = true;
    activeButton = null;
    pinned = false;
    if (restoreFocus && previous) {
      suppressFocus = true;
      previous.focus({preventScroll: true});
      queueMicrotask(() => { suppressFocus = false; });
    }
  }

  function open(button, pin) {
    clearTimeout(closeTimer);
    if (activeButton && activeButton !== button) close(false);
    activeButton = button;
    pinned = pin;
    const entry = copy(button.dataset.helpKey);
    title.textContent = entry[0];
    body.textContent = entry[1];
    button.setAttribute('aria-expanded', 'true');
    button.setAttribute('aria-describedby', 'ignisHelpBody');
    popover.hidden = false;
    position();
  }

  function scheduleClose() {
    if (pinned) return;
    clearTimeout(closeTimer);
    closeTimer = setTimeout(() => {
      if (document.activeElement === activeButton || popover.contains(document.activeElement)) return;
      close(false);
    }, 180);
  }

  function makeButton(key) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'help-button';
    button.dataset.helpKey = key;
    button.textContent = '?';
    button.setAttribute('aria-haspopup', 'dialog');
    button.setAttribute('aria-expanded', 'false');
    button.setAttribute('aria-controls', popover.id);
    button.addEventListener('pointerenter', event => {
      if (event.pointerType === 'touch' || pinned) return;
      open(button, false);
    });
    button.addEventListener('pointerleave', scheduleClose);
    button.addEventListener('focus', () => {
      if (!suppressFocus && !pinned) open(button, false);
    });
    button.addEventListener('blur', scheduleClose);
    button.addEventListener('click', event => {
      event.preventDefault();
      event.stopPropagation();
      if (activeButton === button && pinned) close(false);
      else open(button, true);
    });
    buttons.push(button);
    return button;
  }

  function addHeadingHelp(element, key) {
    const button = makeButton(key);
    if (element.matches('label')) {
      const row = document.createElement('div');
      row.className = 'help-label-row';
      element.before(row);
      row.append(element, button);
    } else {
      element.classList.add('help-heading');
      if (element.classList.contains('timeline')) button.classList.add('timeline-help');
      if (element.classList.contains('metric')) button.classList.add('metric-help');
      element.appendChild(button);
    }
  }

  function addControlHelp(control, key) {
    const row = document.createElement('div');
    row.className = 'help-control-row';
    if (control.matches('.primary, .secondary')) row.classList.add('help-action-row');
    if (control.matches('.seg')) row.classList.add('help-segment-row');
    control.before(row);
    row.append(control, makeButton(key));
  }

  document.querySelectorAll('[data-help]').forEach(element => {
    const key = element.dataset.help;
    if (COPY[key]) addHeadingHelp(element, key);
  });
  document.querySelectorAll('button[data-tip]').forEach(control => {
    const key = TIP_KEYS[control.dataset.tip];
    if (key) addControlHelp(control, key);
  });
  document.querySelectorAll('#calendarMode [data-calendar-mode]').forEach(control => {
    addControlHelp(control, 'calendar_' + control.dataset.calendarMode);
  });
  document.querySelectorAll('.toggle-row').forEach(label => {
    const source = label.querySelector('[data-tip="tip_src"]');
    const severity = label.querySelector('[data-tip="tip_sev"]');
    if (source || severity) addHeadingHelp(label, source ? 'sensors' : 'filters');
  });

  function localize() {
    const english = window.IGNIS_I18N?.lang === 'en';
    buttons.forEach(button => {
      button.setAttribute('aria-label', (english ? 'Help: ' : 'Ayuda: ') + copy(button.dataset.helpKey)[0]);
    });
    closeButton.setAttribute('aria-label', english ? 'Close help' : 'Cerrar ayuda');
    if (activeButton) open(activeButton, pinned);
  }
  localize();
  window.IGNIS_I18N?.onChange(localize);
  closeButton.addEventListener('click', () => close(true));
  popover.addEventListener('pointerenter', () => clearTimeout(closeTimer));
  popover.addEventListener('pointerleave', scheduleClose);
  popover.addEventListener('focusout', scheduleClose);
  document.addEventListener('pointerdown', event => {
    if (activeButton && !popover.contains(event.target) && !event.target.closest('.help-button')) close(false);
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && activeButton) {
      event.preventDefault();
      close(popover.contains(document.activeElement));
    }
  });
  window.addEventListener('resize', position);
  document.addEventListener('scroll', event => {
    if (activeButton && !popover.contains(event.target)) close(false);
  }, true);
})();
