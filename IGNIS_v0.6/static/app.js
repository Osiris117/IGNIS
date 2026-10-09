/* IGNIS v0.6 — Earth Context Engine + candidate fire-event intelligence */
/* Basemap v0.9.3: 'auto' = tiles OSM nítidos con internet y, si fallan
   (sin conexión), degradación elegante al Natural Earth II local. Antes el
   NE II (≈20 km/píxel) era la ÚNICA base: por eso el globo se veía pixeleado.
   Pon 'osm' o 'local' para forzar uno u otro. */
const IGNIS_BASEMAP='auto';
const IGNIS_SOFT=ignisSoftwareRenderer();
function ignisLocalBaseLayer(){
  return Cesium.ImageryLayer.fromProviderAsync(Cesium.TileMapServiceImageryProvider.fromUrl(Cesium.buildModuleUrl('Assets/Textures/NaturalEarthII')));
}
function ignisOsmLayer(){
  return new Cesium.ImageryLayer(new Cesium.OpenStreetMapImageryProvider({url:'https://tile.openstreetmap.org/',credit:'© OpenStreetMap contributors'}));
}
const ignisBaseLayer=(IGNIS_BASEMAP==='local')?ignisLocalBaseLayer():ignisOsmLayer();
const viewer = new Cesium.Viewer('cesiumContainer', {
  animation:false,timeline:false,fullscreenButton:false,homeButton:false,geocoder:false,
  navigationHelpButton:false,sceneModePicker:false,baseLayerPicker:false,infoBox:false,selectionIndicator:false,
  terrainProvider:new Cesium.EllipsoidTerrainProvider(),
  orderIndependentTranslucency:!IGNIS_SOFT,
  baseLayer:ignisBaseLayer
});
viewer.scene.globe.baseColor=Cesium.Color.fromCssColorString('#07100d');
viewer.scene.globe.enableLighting=true;viewer.scene.backgroundColor=Cesium.Color.fromCssColorString('#020403');
viewer.scene.skyBox.show=false;viewer.scene.sun.show=false;viewer.scene.moon.show=false;viewer.scene.fog.enabled=true;viewer.scene.fog.density=.00015;
/* v0.9.3: antes el zoom mínimo era 800 km; con 250 km el usuario puede acercar
   hasta ver detalle fino de la base OSM en vez de textura estirada. */
viewer.scene.screenSpaceCameraController.minimumZoomDistance=250000;viewer.scene.screenSpaceCameraController.maximumZoomDistance=65000000;
/* v0.9.3: detectar SwiftShader/llvmpipe ANTES de activar efectos: el shader de
   HDR/bloom no compila en GPUs por software y Cesium detenía el render dejando
   un panel modal que bloqueaba TODA la interfaz (botones "muertos"). */

/* v0.9.3 — degradación elegante de la base 'auto': si OSM no responde (sin
   internet o red bloqueada), se cambia sola por el NE II local. */
let ignisBaseFallbackUsed=IGNIS_BASEMAP==='local';
function ignisUseLocalBase(){
  if(ignisBaseFallbackUsed||IGNIS_BASEMAP!=='auto')return;
  ignisBaseFallbackUsed=true;
  try{
    const idx=Math.max(0,viewer.imageryLayers.indexOf(ignisBaseLayer));
    viewer.imageryLayers.remove(ignisBaseLayer);
    viewer.imageryLayers.add(ignisLocalBaseLayer(),idx);
    viewer.scene.requestRender();
    showToast(TT('toast_basemap_local'),5600);
  }catch(error){
    ignisBaseFallbackUsed=false;
    console.warn('[IGNIS] No se pudo cargar el mapa local:',error);
  }
}
if(IGNIS_BASEMAP==='auto'){
  let osmFails=0;
  // Los fallos de tesela se emiten en el provider; el errorEvent de la capa
  // solo informa de errores al crear el provider.
  ignisBaseLayer.imageryProvider.errorEvent.addEventListener(()=>{
    if(++osmFails>=3)ignisUseLocalBase();
  });
  if(navigator.onLine===false)setTimeout(ignisUseLocalBase,0);
}

/* v0.9.3 — nitidez: render a resolución nativa y más detalle de tiles.
   El globo "pixeleado" venía de resolutionScale=1 en pantallas HiDPI y del
   maximumScreenSpaceError por defecto (2) que no pide tiles finos al acercar.
   Con renderer por software se conserva el rendimiento (escala 1, SSE 2) y la
   clase CSS perf-soft apaga los blur costosos (ver styles.css). */
function ignisSoftwareRenderer(){
  try{
    const c=document.createElement('canvas');
    const gl=c.getContext('webgl2')||c.getContext('webgl');
    if(!gl)return false;
    const d=gl.getExtension('WEBGL_debug_renderer_info');
    const r=String(d?gl.getParameter(d.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER));
    return /SwiftShader|llvmpipe|Software|ANGLE \(Software/i.test(r);
  }catch(e){return false;}
}
(function qualityGrade(){
  try{
    window.IGNIS_SOFT=IGNIS_SOFT;
    viewer.resolutionScale=IGNIS_SOFT?1:Math.min(window.devicePixelRatio||1,2);
    viewer.scene.globe.maximumScreenSpaceError=IGNIS_SOFT?2:1.25;
    viewer.scene.globe.tileCacheSize=IGNIS_SOFT?240:1000;
    if(IGNIS_SOFT){
      document.body.classList.add('perf-soft');
      viewer.targetFrameRate=15;
      try{viewer.scene.msaaSamples=1;}catch(e){console.warn('[IGNIS] MSAA no configurable:',e);}
      /* Render bajo demanda: los cambios de cámara, datos y tiles piden frames
         explícitos. En SwiftShader, forzar 8 fps solo para animar marcadores
         ocupaba el hilo principal y retrasaba los botones varios segundos. */
      viewer.scene.requestRenderMode=true;
      viewer.scene.maximumRenderTimeChange=Infinity;
    }
  }catch(e){}
})();

/* --- v0.7 God's Eye: calidad cinematográfica, todo con recursos locales --- */
const IGNIS_CINEMATIC=true;
const IGNIS_TERMINATOR=true;   // iluminación solar real (día/noche)
(function cinematicGrade(){
  if(!IGNIS_CINEMATIC)return;
  try{
    const s=viewer.scene;
    if(IGNIS_SOFT){
      /* v0.9.3: con GPU por software la iluminación solar dinámica y la
         atmósfera de cielo cuestan casi todo el frame; se desactivan y el
         visor pasa a render bajo demanda (requestRenderMode). */
      s.skyBox.show=false;
      s.skyAtmosphere.show=false;
      s.globe.showGroundAtmosphere=false;
      s.globe.enableLighting=false;
      s.fog.enabled=false;
      /* v0.9.4: Cesium deja highDynamicRange=true por defecto; en GPUs por
         software el pipeline HDR lava la imagen y encarece cada frame. */
      s.highDynamicRange=false;
      s.postProcessStages.fxaa.enabled=false;
      if(s.postProcessStages.bloom)s.postProcessStages.bloom.enabled=false;
    }else{
      s.skyBox.show=true;                      // campo de estrellas local (Assets/SkyBox)
      s.skyAtmosphere.show=true;
      s.skyAtmosphere.hueShift=-0.02;
      s.skyAtmosphere.saturationShift=0.12;
      s.skyAtmosphere.brightnessShift=-0.12;
      s.globe.atmosphereLightIntensity=6;
      s.globe.showGroundAtmosphere=false;  // evita el aspecto lechoso en zoom regional
      s.globe.enableLighting=IGNIS_TERMINATOR;
      s.globe.dynamicAtmosphereLighting=true;
      s.globe.dynamicAtmosphereLightingFromSun=true;
    }
    /* FIX v0.9.3: en renderer por software estos shaders de postproceso no
       compilan ("Fragment shader failed to compile") y el visor moría. */
    if(!IGNIS_SOFT){
      s.highDynamicRange=true;
      s.postProcessStages.fxaa.enabled=true;   // bordes suaves tipo visor cinematográfico
      if(s.postProcessStages.bloom){           // resplandor de los hotspots
        s.postProcessStages.bloom.enabled=true;
        s.postProcessStages.bloom.uniforms.glowOnly=false;
        s.postProcessStages.bloom.uniforms.contrast=128;
        s.postProcessStages.bloom.uniforms.brightness=-0.15;
        s.postProcessStages.bloom.uniforms.delta=1.6;
        s.postProcessStages.bloom.uniforms.sigma=2.6;
        s.postProcessStages.bloom.uniforms.stepSize=1.0;
      }
    }
    s.globe.lightingFadeOutDistance=6.5e7;
    s.globe.nightFadeInDistance=2.5e7;
    s.fog.density=0.00011;
    s.screenSpaceCameraController.inertiaSpin=.86;
    s.screenSpaceCameraController.inertiaZoom=.78;
  }catch(err){console.warn('IGNIS cinematic grade parcial:',err);}
})();
function tuneImagery(){
  try{
    const layer=viewer.imageryLayers.get(0);
    if(layer){layer.brightness=1.08;layer.contrast=1.12;layer.saturation=1.0;layer.gamma=1.0;}
  }catch(e){}
}
viewer.scene.globe.tileLoadProgressEvent.addEventListener(n=>{if(n===0)tuneImagery();});
setTimeout(tuneImagery,2500);setTimeout(tuneImagery,9000);

/* Entrada de cámara cinematográfica al cargar — v0.9.3: el planeta arranca
   YA CERCA (10.5 Mm sobre México) y se aproxima a 4.3 Mm en 3.4 s; antes
   empezaba a 22-30 Mm (planeta diminuto) con un vuelo de 6.5 s. */
function cinematicIntro(){
  viewer.camera.setView({destination:Cesium.Cartesian3.fromDegrees(-104.5,24.5,10500000)});
  viewer.camera.flyTo({destination:Cesium.Cartesian3.fromDegrees(-102.2,23.4,4300000),duration:3.4,easingFunction:Cesium.EasingFunction.QUADRATIC_IN_OUT});
}

viewer.camera.setView({destination:Cesium.Cartesian3.fromDegrees(-102.5,23.5,9000000)});

const REGIONS={
  mexico:{label:'Mexico',area:'-118,14,-86,33',camera:[-102.5,23.5,5600000]},
  amazon:{label:'Amazon Basin',area:'-80,-20,-44,8',camera:[-61.5,-7,5200000]},
  california:{label:'California',area:'-125,32,-114,42',camera:[-119.5,37,3600000]},
  med:{label:'Mediterranean',area:'-10,30,40,46',camera:[20,37,5000000]},
  australia:{label:'Australia',area:'112,-44,154,-10',camera:[134,-25,6200000]},
};
const MONTHS=['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'];
const MONTHS_ES=['ENE','FEB','MAR','ABR','MAY','JUN','JUL','AGO','SEP','OCT','NOV','DIC'];
function monthLabel(month){return (window.IGNIS_I18N?.lang==='es'?MONTHS_ES:MONTHS)[month-1]||'—';}
const fireCollection=viewer.scene.primitives.add(new Cesium.PointPrimitiveCollection());
const heatCollection=viewer.scene.primitives.add(new Cesium.PointPrimitiveCollection());
const eventCollection=viewer.scene.primitives.add(new Cesium.PointPrimitiveCollection());
const eventDataSource=new Cesium.CustomDataSource('candidate-event-spread');viewer.dataSources.add(eventDataSource);
const trailDataSource=new Cesium.CustomDataSource('fire-evolution-trails');viewer.dataSources.add(trailDataSource);
const reticleDataSource=new Cesium.CustomDataSource('ignis-reticle');viewer.dataSources.add(reticleDataSource);
let config=null,archiveStatus=null,frames=[],candidateEvents=[],frameIndex=0,viewMode='hotspots',playTimer=null,lastArea=null,lastMode='demo',lastPayload=null;
let calendarMode='demo',calendarPayload=null;
let evolution=null,evolutionTracks=[],selectedTrack=null,replayToken=0,pulsePrimitives=[];
const $=id=>document.getElementById(id);
/* v0.9.1 — paleta por tema: sobre un globo claro los acentos saturados no se leen.
   Se mantienen los mismos significados (aviso/activo/estable/frío) con otro brillo. */
const PALETTES={
  dark:{emerging:'#ffdc6a',expanding:'#ff9e42',stable:'#a6ff77',declining:'#46ffd2',extinct:'#789184',
        moderate:'#ffdc6a',high:'#ff9e42',critical:'#ff4e36',
        heat:['#a6ff77','#ffdc6a','#ff9e42','#ff3f35'],
        anomaly:['#a6ff77','#ffdc6a','#ff9e42','#ff4e36']},
  light:{emerging:'#8a6d00',expanding:'#b45309',stable:'#1f7a3d',declining:'#0b7a68',extinct:'#547260',
        moderate:'#8a6d00',high:'#b45309',critical:'#b91c1c',
        heat:['#1f7a3d','#8a6d00','#b45309','#b91c1c'],
        anomaly:['#1f7a3d','#8a6d00','#b45309','#b91c1c']}
};
function pal(){return PALETTES[(document.documentElement.dataset.theme==='light')?'light':'dark'];}
function severityColorOf(key){return Cesium.Color.fromCssColorString(pal()[key]||pal().moderate);}
function heatColor(score){const c=pal().heat;return Cesium.Color.fromCssColorString(score<25?c[0]:score<50?c[1]:score<75?c[2]:c[3]);}
function showToast(message,ms=3600){const el=$('toast');el.textContent=message;el.classList.remove('hidden');clearTimeout(showToast.t);showToast.t=setTimeout(()=>el.classList.add('hidden'),ms);}
function clockTick(){const d=new Date();$('clock').textContent=d.toISOString().slice(11,19)+' UTC';}setInterval(clockTick,1000);clockTick();
function filterEnabled(severity){return $(severity)?.checked??true;}
/* v0.9 — i18n: las cadenas generadas en JS pasan por el diccionario. */
const TT=(key,...vars)=>window.IGNIS_I18N?window.IGNIS_I18N.t(key,...vars):key;
function dataToday(){return config?.current_date||new Date().toISOString().slice(0,10);}
function sevLabel(value){const key='sev_'+String(value||'signal').toLowerCase();const out=TT(key);return out===key?String(value||'signal').toUpperCase():out;}
function trackStateLabel(value){const key='state_'+String(value||'').toLowerCase();const out=TT(key);return out===key?String(value||'—'):out;}
function translateEvolutionText(line){
  if(!line||window.IGNIS_I18N?.lang!=='es')return line;
  const intensity=/^intensity ([+-]?\d+)% vs previous frame$/.exec(line);
  if(intensity)return TT('track_intensity',intensity[1]);
  if(line==='no linked detections in the most recent frame of this dataset')return TT('track_no_recent');
  if(line==='Persistent identity is a heuristic link between spatiotemporal clusters, not an official incident ID. Movement is apparent centroid drift, not a propagation model.')return TT('track_caveat');
  if(line==='Apparent centroid drift between satellite overpasses; NOT a fire-spread or propagation model.')return TT('track_drift_note');
  return line;
}
/* Las explicaciones del score de confianza llegan del backend en inglés: se
   traducen aquí con patrones, sin inventar cifras (sólo se conservan los números). */
function translateEvidence(line){
  if(!window.IGNIS_I18N||window.IGNIS_I18N.lang!=='es')return line;
  let m;
  if((m=/^(\d+) detections across (\d+) frame\(s\)$/.exec(line)))return TT('ev_detections',m[1],m[2]);
  if((m=/^persistence (\d+) h$/.exec(line)))return TT('ev_persistence',m[1]);
  if((m=/^(\d+) independent sensor family\(ies\): (.+)$/.exec(line)))return Number(m[1])===1?TT('ev_sensors_one',m[2]):TT('ev_sensors_many',m[1],m[2]);
  if((m=/^peak FRP (\d+) MW$/.exec(line)))return TT('ev_peak_frp',m[1]);
  if((m=/^mean declared confidence (\d+)%$/.exec(line)))return TT('ev_declared',m[1]);
  return line;
}
/* v0.9 — hooks del shell (tema claro/oscuro e idioma) */
window.IGNIS_APPLY_THEME=function(theme){
  try{
    const light=theme==='light';
    viewer.scene.globe.baseColor=Cesium.Color.fromCssColorString(light?'#dfe9ea':'#07100d');
    viewer.scene.backgroundColor=Cesium.Color.fromCssColorString(light?'#e8f0f2':'#020403');
    viewer.scene.globe.enableLighting=light?false:(IGNIS_SOFT?false:IGNIS_TERMINATOR);
    viewer.scene.skyBox.show=!light&&!IGNIS_SOFT;
    /* v0.9.4: en renderer por software el tema oscuro NO debe re-activar el
       pipeline HDR/bloom (lavaba la imagen y mataba el frame en SwiftShader). */
    viewer.scene.fog.enabled=!light&&!IGNIS_SOFT;
    try{viewer.scene.postProcessStages.bloom.enabled=!light&&!IGNIS_SOFT;}catch(e){}
    try{viewer.scene.highDynamicRange=!light&&!IGNIS_SOFT;}catch(e){}
    for(let i=0;i<viewer.imageryLayers.length;i++){
      const l=viewer.imageryLayers.get(i);
      const isEnv=!!l._ignisEnvKey;
      if(!isEnv){l.brightness=light?1.30:1.08;l.gamma=light?1.06:1.12;}
    }
    document.querySelectorAll('.scanline').forEach(el=>el.classList.toggle('hidden',light));
    const v=document.querySelector('.vignette');if(v)v.classList.toggle('hidden',light);
    viewer.scene.requestRender();
  }catch(e){console.warn('[IGNIS] No se pudo aplicar el tema al globo:',e);}
};
window.IGNIS_RERENDER=function(){
  /* Cada paso con su propio try: que un fallo no impida refrescar el resto. */
  const paso=f=>{try{f();}catch(e){}};
  paso(renderFrame);paso(drawHud);paso(renderTrackingBanner);paso(renderEvolutionPanel);paso(updateRegionLabel);
  if(selectedTrack){
    paso(()=>renderTrackDetail(selectedTrack));
    paso(()=>{$('detailSeverity').style.color=STATE_COLOR[selectedTrack.status]||pal().stable;});
  }
  paso(()=>{const p=$('calendarPanel');if(typeof calendarPayload!=='undefined'&&calendarPayload&&p&&!p.classList.contains('hidden'))renderCalendar(calendarPayload);});
};
function refreshArchiveTop(){const n=Number(archiveStatus?.observations||0);$('archiveTop').textContent=n?TT('feed_ready'):TT('feed_empty');$('archiveTop').classList.toggle('ok',!!n);}
function applyFeedLabel(){if(lastMode.includes('archive'))$('feedMode').textContent=TT('feed_local');else if(lastMode.includes('demo'))$('feedMode').textContent=TT('feed_demo');else if(lastMode.includes('historical'))$('feedMode').textContent=TT('feed_nasa_history');else $('feedMode').textContent=TT('feed_nasa_fusion');const note=$('dataOriginNote');if(note){note.textContent=TT(lastMode.includes('demo')?'data_origin_demo':'data_origin_observations');note.classList.toggle('is-demo',lastMode.includes('demo'));}}
let lastSourceCount=0;
function refreshSensorLabel(){$('sensorName').textContent=lastSourceCount?TT('sensors_n',lastSourceCount):TT('sensors_none');}
let lastStatus={key:'status_online',ok:true};
function setStatus(key,ok=true){lastStatus={key,ok};$('systemStatus').textContent=TT(key);$('systemStatus').classList.toggle('ok',ok);}
function fmtBytes(n){if(!n)return '0 B';const u=['B','KB','MB','GB'];let i=0,v=Number(n);while(v>=1024&&i<u.length-1){v/=1024;i++;}return `${v.toFixed(i?1:0)} ${u[i]}`;}
function selectedSources(){const out=[];if($('srcModis').checked)out.push('MODIS_SP');if($('srcSnpp').checked)out.push('VIIRS_SNPP_SP');if($('srcN20').checked)out.push('VIIRS_NOAA20_SP');return out;}
function viewportArea(){const rect=viewer.camera.computeViewRectangle(viewer.scene.globe.ellipsoid);if(!rect)return REGIONS.mexico.area;const west=Cesium.Math.toDegrees(rect.west),east=Cesium.Math.toDegrees(rect.east),south=Math.max(-89,Cesium.Math.toDegrees(rect.south)),north=Math.min(89,Cesium.Math.toDegrees(rect.north));const span=((east-west)+360)%360;if(span>175||north-south>100||east<west){showToast(TT('toast_zoom'),4800);return null;}return [west,south,east,north].map(v=>v.toFixed(3)).join(',');}
function selectedArea(){const key=$('regionPreset').value;return key==='viewport'?viewportArea():REGIONS[key]?.area||REGIONS.mexico.area;}
function selectedRegion(){const key=$('regionPreset').value;return REGIONS[key]?key:null;}
function updateRegionLabel(){const key=$('regionPreset').value;const translated=TT('region_'+key);$('regionName').textContent=(translated===('region_'+key)?(REGIONS[key]?.label||key):translated).toUpperCase();}
function flyRegion(key){const region=REGIONS[key];if(!region)return;const [lon,lat,h]=region.camera;viewer.camera.flyTo({destination:Cesium.Cartesian3.fromDegrees(lon,lat,h),duration:1.6});}
function daysInMonth(year,month){return new Date(Date.UTC(year,month,0)).getUTCDate();}

function renderHotspots(fires){fireCollection.removeAll();const filtered=fires.filter(f=>filterEnabled(f.severity));filtered.forEach((fire,idx)=>{const c=severityColorOf(fire.severity);const size=fire.severity==='critical'?9:fire.severity==='high'?7:5;fireCollection.add({position:Cesium.Cartesian3.fromDegrees(fire.lon,fire.lat,9000),color:c.withAlpha(.96),outlineColor:c.withAlpha(.25),outlineWidth:5,pixelSize:size,scaleByDistance:new Cesium.NearFarScalar(1.5e6,1.9,3.5e7,.65),translucencyByDistance:new Cesium.NearFarScalar(2e6,1,5e7,.5),id:{type:'ignis-fire',idx,fire}});});return filtered.length;}
function renderHeat(cells){heatCollection.removeAll();cells.forEach((cell,idx)=>{const c=heatColor(cell.activity_score);const size=8+Math.sqrt(Math.max(1,cell.detections))*3.2;heatCollection.add({position:Cesium.Cartesian3.fromDegrees(cell.lon,cell.lat,12000),color:c.withAlpha(.38+.004*Math.min(cell.activity_score,80)),outlineColor:c.withAlpha(.9),outlineWidth:1,pixelSize:Math.min(30,size),scaleByDistance:new Cesium.NearFarScalar(1.5e6,2.0,3.5e7,.8),id:{type:'ignis-cell',idx,cell}});});return cells.length;}
function eventActiveOnDate(event,date){if(!date)return true;const start=(event.start||'').slice(0,10),end=(event.end||'').slice(0,10);return (!start||date>=start)&&(!end||date<=end);}
function renderEvents(events,date){eventCollection.removeAll();eventDataSource.entities.removeAll();const active=(events||[]).filter(e=>eventActiveOnDate(e,date)&&filterEnabled(e.severity));active.forEach((event,idx)=>{const c=severityColorOf(event.severity);const size=Math.min(30,12+Math.sqrt(Math.max(1,event.detections||1))*3.4);eventCollection.add({position:Cesium.Cartesian3.fromDegrees(event.lon,event.lat,18000),color:c.withAlpha(.30),outlineColor:c.withAlpha(.98),outlineWidth:3,pixelSize:size,scaleByDistance:new Cesium.NearFarScalar(1.2e6,2.1,3.5e7,.72),id:{type:'ignis-event',idx,event}});const ring=eventDataSource.entities.add({position:Cesium.Cartesian3.fromDegrees(event.lon,event.lat),ellipse:{semiMajorAxis:Math.max(3000,(event.radius_km||3)*1000),semiMinorAxis:Math.max(3000,(event.radius_km||3)*1000),material:c.withAlpha(.055),outline:true,outlineColor:c.withAlpha(.42),height:0}});ring._ignisEvent=event;});return active.length;}
function renderEventList(events){
  const list=$('eventList');if(!list)return;
  list.replaceChildren();$('eventTop').textContent=Number(events?.length||0).toLocaleString();
  if(!(events||[]).length){const empty=document.createElement('div');empty.className='source-empty';empty.textContent=TT('ev_none');list.appendChild(empty);return;}
  for(const event of events.slice(0,8)){
    const b=document.createElement('button');b.className='event-row';
    const body=document.createElement('div'),name=document.createElement('strong'),detail=document.createElement('span'),score=document.createElement('em');
    name.textContent=event.id;
    detail.textContent=TT('ev_row_summary',event.detections,event.duration_hours,event.radius_km);
    score.textContent=Math.round(event.event_score||0);
    body.append(name,detail);b.append(body,score);
    b.addEventListener('click',()=>{viewer.camera.flyTo({destination:Cesium.Cartesian3.fromDegrees(event.lon,event.lat,Math.max(450000,Math.min(1800000,(event.radius_km||30)*26000))),duration:1.25});openEvent(event);});
    list.appendChild(b);
  }
}
function countFamilies(fires){let modis=0,viirs=0;for(const f of fires){if((f.family||'').toUpperCase()==='MODIS')modis++;else if((f.family||'').toUpperCase()==='VIIRS')viirs++;}return{modis,viirs};}
function renderFrame(){
  if(!frames.length){fireCollection.removeAll();heatCollection.removeAll();eventCollection.removeAll();$('fireCount').textContent='0';$('activityIndex').textContent='—';$('timelineDate').textContent='—';viewer.scene.requestRender();return;}
  frameIndex=Math.max(0,Math.min(frameIndex,frames.length-1));const frame=frames[frameIndex];const fires=frame.fires||[],cells=frame.cells||[],summary=frame.summary||{};
  fireCollection.show=viewMode==='hotspots';heatCollection.show=viewMode==='heat';eventCollection.show=viewMode==='events'||viewMode==='evolution';eventDataSource.show=viewMode==='events';trailDataSource.show=viewMode==='evolution';
  if(viewMode!=='evolution')pulsePrimitives=[];
  let visible=0;
  if(viewMode==='hotspots')visible=renderHotspots(fires);
  else if(viewMode==='heat')visible=renderHeat(cells);
  else if(viewMode==='evolution')visible=renderEvolutionFrame(frame.date);
  else visible=renderEvents(candidateEvents,frame.date);
  scheduleEnvRefresh();
  $('fireCount').textContent=visible.toLocaleString();$('countLabel').textContent=viewMode==='hotspots'?TT('VISIBLE DETECTIONS'):viewMode==='heat'?TT('VISIBLE FUSION CELLS'):viewMode==='evolution'?TT('TRACKED FIRE EVENTS'):TT('ACTIVE CANDIDATE EVENTS');const fam=countFamilies(fires.filter(f=>filterEnabled(f.severity))); /* FIX: coherente con el conteo visible filtrado */$('modisCount').textContent=fam.modis.toLocaleString();$('viirsCount').textContent=fam.viirs.toLocaleString();$('agreementCount').textContent=(summary.agreement_cells||0).toLocaleString();$('activityIndex').textContent=Number(summary.activity_mean||0).toFixed(1);$('activityMeter').style.width=`${Math.min(100,summary.activity_mean||0)}%`;$('timelineDate').textContent=frame.date||'—';$('frameSlider').max=Math.max(0,frames.length-1);$('frameSlider').value=frameIndex;
  viewer.scene.requestRender();
}
function applyHarmonized(payload){
  stopPlayback({refresh:false});
  lastPayload=payload;frames=payload.frames||[];candidateEvents=payload.events||[];frameIndex=Math.max(0,frames.length-1);lastMode=payload.mode||'harmonized';
  evolution=payload.evolution||null;evolutionTracks=evolution?.tracks||[];selectedTrack=null;
  renderEvolutionPanel();clearReticle();
  /* FIX: 'evolution-archive' también viene del DuckDB local; antes caía al
     else y se etiquetaba como "FUSIÓN NASA" (fuente equivocada en el HUD). */
  applyFeedLabel();
  const src=(payload.available_sources||payload.sources||[]);lastSourceCount=src.length;refreshSensorLabel();renderEventList(candidateEvents);setStatus('status_online');renderFrame();
  if(payload.warnings?.length)showToast(TT('toast_partial',payload.warnings[0]),6500);else if(payload.warning)showToast(payload.warning,5200);
}

function applyArchiveStatus(status){
  archiveStatus=status||{};const n=Number(archiveStatus.observations||0);refreshArchiveTop();$('archiveCount').textContent=n.toLocaleString();$('archiveCoverage').textContent=n?`${archiveStatus.min_date} → ${archiveStatus.max_date}`:TT('No historical files imported');
  $('archiveManagerCount').textContent=n.toLocaleString();$('archiveManagerImports').textContent=Number(archiveStatus.imports||0).toLocaleString();$('archiveManagerCoverage').textContent=n?`${archiveStatus.min_date} → ${archiveStatus.max_date}`:'—';
  const list=$('archiveSourceList');if(!list)return;list.innerHTML='';if(!(archiveStatus.sources||[]).length){list.innerHTML=`<div class="source-empty">${TT('No files imported yet.')}</div>`;return;}
  for(const src of archiveStatus.sources){const row=document.createElement('div');row.className='source-row';row.innerHTML=`<div><strong>${src.label||src.id}</strong><span>${src.min_date} → ${src.max_date}</span></div><em>${Number(src.observations).toLocaleString()}</em>`;list.appendChild(row);}
}
async function loadArchiveStatus(){try{const res=await fetch('/api/archive/status');if(!res.ok)throw new Error(`HTTP ${res.status}`);applyArchiveStatus(await res.json());}catch(err){showToast(TT('toast_archive_status',err.message),4800);}}
async function loadConfig(){try{const res=await fetch('/api/config');if(!res.ok)throw new Error(`HTTP ${res.status}`);config=await res.json();$('historyDate').max=dataToday();if(!$('historyDate').value||$('historyDate').value>dataToday())$('historyDate').value=dataToday();applyArchiveStatus(config.archive||{});if(!config.firms_key_configured){$('btnHarmonize').dataset.tip='tip_harmonize_no_key';$('btnHarmonize').title=TT('tip_harmonize_no_key');}}catch(err){showToast(TT('toast_config',err.message),5000);}}

async function loadAnalyticalDemo(){setStatus('status_loading');try{const res=await fetch('/api/harmonize/demo');if(!res.ok)throw new Error(`HTTP ${res.status}`);applyHarmonized(await res.json());lastArea=null;showToast(TT('toast_demo_loaded'),5200);}catch(err){setStatus('status_error',false);showToast(TT('toast_demo_fail',err.message),6000);}}
async function loadDemoPeriod(startDate,region){setStatus('status_loading');try{const url=`/api/harmonize/demo/date?region=${encodeURIComponent(region)}&start_date=${encodeURIComponent(startDate)}&days=${$('historyDays').value}`;const res=await fetch(url);if(!res.ok){const e=await res.json().catch(()=>({}));throw new Error(e.detail||`HTTP ${res.status}`);}applyHarmonized(await res.json());lastArea=REGIONS[region].area;showToast(TT('toast_period',REGIONS[region].label,startDate),5200);}catch(err){setStatus('status_error',false);showToast(err.message,6500);}}
async function loadHarmonized(){const area=selectedArea();if(!area)return;const sources=selectedSources();if(!sources.length){showToast(TT('toast_select_sensor'));return;}setStatus('status_syncing');lastArea=area;try{const dateValue=$('historyDate').value;const today=new Date().toISOString().slice(0,10);const startDate=dateValue&&dateValue!==today?`&start_date=${encodeURIComponent(dateValue)}`:'';const url=`/api/harmonize?area=${encodeURIComponent(area)}${startDate}&days=${$('historyDays').value}&sources=${encodeURIComponent(sources.join(','))}&grid_deg=${$('gridSize').value}`;const res=await fetch(url);if(!res.ok){const e=await res.json().catch(()=>({}));throw new Error(e.detail||`HTTP ${res.status}`);}applyHarmonized(await res.json());showToast(TT('toast_harmonized'));}catch(err){setStatus('status_error',false);showToast(err.message,6500);}}
function archiveSelectedSources(){const available=new Set((archiveStatus?.sources||[]).map(x=>x.id));let chosen=selectedSources().filter(x=>available.has(x));if(!chosen.length)chosen=[...(archiveStatus?.sources||[])].map(x=>x.id);return chosen;}
async function loadArchivePeriod(startDate,days){const area=selectedArea();if(!area)return;if(!archiveStatus?.ready){showToast(TT('toast_import_first'),5200);return;}const sources=archiveSelectedSources();setStatus('status_localdb');lastArea=area;try{const url=`/api/archive/harmonize?area=${encodeURIComponent(area)}&start_date=${encodeURIComponent(startDate)}&days=${days}&sources=${encodeURIComponent(sources.join(','))}&grid_deg=${$('gridSize').value}&max_points_per_frame=1600`;const res=await fetch(url);if(!res.ok){const e=await res.json().catch(()=>({}));throw new Error(e.detail||`HTTP ${res.status}`);}const data=await res.json();applyHarmonized(data);showToast(TT('toast_archive_loaded',days),5200);}catch(err){setStatus('status_error',false);showToast(err.message,6500);}}

let lastAnomaly=null;
function renderAnomaly(data,labelPrefix='MODIS API'){lastAnomaly={data,labelPrefix};const sign=data.percent_change>0?'+':'';$('anomalyValue').textContent=`${sign}${Number(data.percent_change).toFixed(0)}%`;const anomKey={exceptional:'anomaly_exceptional',elevated:'anomaly_elevated','below-normal':'anomaly_below',typical:'anomaly_typical'}[String(data.anomaly_label||'typical').toLowerCase()]||'anomaly_typical';
  $('anomalyLabel').textContent=TT(anomKey);$('anomalyNote').textContent=TT('anomaly_note',TT(labelPrefix),data.historical_mean,data.z_score);const an=pal().anomaly;const color=data.z_score>=2?an[3]:data.z_score>=1?an[2]:data.z_score<=-1?pal().declining:an[0];$('anomalyValue').style.color=color;}
async function loadBaseline(){const area=lastArea||selectedArea();if(!area)return;const target=frames[frameIndex]?.date||$('historyDate').value;if(!target){showToast(TT('toast_load_frame'));return;}setStatus('status_analyzing');try{let url,label;if(lastMode.includes('archive')){const d=new Date(`${target}T00:00:00Z`);url=`/api/archive/anomaly?area=${encodeURIComponent(area)}&target_year=${d.getUTCFullYear()}&target_month=${d.getUTCMonth()+1}&years=10&source=MODIS_SP`;label='LOCAL FULL-MONTH';}else{if(!config?.firms_key_configured){showToast(TT('toast_baseline_needs_key'),5600);setStatus('status_online');return;}url=`/api/analytics/baseline?area=${encodeURIComponent(area)}&target_date=${target}&years=5&days=1`;label='MODIS API';}const res=await fetch(url);if(!res.ok){const e=await res.json().catch(()=>({}));throw new Error(e.detail||`HTTP ${res.status}`);}renderAnomaly(await res.json(),label);setStatus('status_online');}catch(err){setStatus('status_error',false);showToast(err.message,6500);}}

function detailSource(text){return (lastMode.includes('demo')?'DEMO · ':'')+(text||'—');}
function hideEvolutionBlocks(){['evoDetail','evoIntel'].forEach(id=>$(id)?.classList.add('hidden'));selectedTrack=null;clearReticle();renderTrackingBanner();renderEvolutionPanel();}
function openFire(fire){hideEvolutionBlocks();
  loadEnvironmentIntelligence(fire.lat,fire.lon,(fire.date||'').slice(0,10));$('detailEmpty').classList.add('hidden');$('detailCard').classList.remove('hidden');$('detailKicker').textContent=TT('kicker_hotspot');$('detailSeverity').textContent=sevLabel(fire.severity);$('detailSeverity').style.color=(fire.severity==='critical')?pal().critical:(fire.severity==='high')?pal().high:pal().moderate;$('detailCoords').textContent=`${Number(fire.lat).toFixed(4)}, ${Number(fire.lon).toFixed(4)}`;$('detailFrp').textContent=`${fire.frp??0} MW`;$('detailConfidence').textContent=`${fire.confidence??0}%`;$('detailTime').textContent=`${fire.date||'—'} ${fire.time||''} UTC`;$('detailSatellite').textContent=detailSource(fire.source||fire.satellite);}
function openCell(cell){hideEvolutionBlocks();$('detailEmpty').classList.add('hidden');$('detailCard').classList.remove('hidden');$('detailKicker').textContent=TT('kicker_cell');$('detailSeverity').textContent=sevLabel(cell.activity_level);$('detailSeverity').style.color=heatColor(cell.activity_score).toCssColorString();$('detailCoords').textContent=`${Number(cell.lat).toFixed(4)}, ${Number(cell.lon).toFixed(4)}`;$('detailFrp').textContent=`ACT ${cell.activity_score} · ${cell.mean_frp} MW`;$('detailConfidence').textContent=TT('cell_agreement',cell.mean_confidence,Math.round((cell.sensor_agreement||0)*100));$('detailTime').textContent=frames[frameIndex]?.date||'—';$('detailSatellite').textContent=detailSource((cell.families||[]).join(' + '));}
function resetContext(message){$('contextPlaceholder').classList.remove('hidden');$('contextPlaceholder').innerHTML=`${message||TT('SELECT A FIRE EVENT')}<br><small>${TT('Weather, dryness and recent air-quality context will appear here.')}</small>`;$('contextContent').classList.add('hidden');}
function fmtValue(value,suffix=''){return value==null||Number.isNaN(Number(value))?'—':`${Number(value).toFixed(1)}${suffix}`;}
let lastContextData=null;
function renderContext(data,demo=false){lastContextData={data,demo};const w=data.weather||{},a=data.air_quality||{},dry=w.dryness_context||{};$('contextPlaceholder').classList.add('hidden');$('contextContent').classList.remove('hidden');$('drynessScore').textContent=fmtValue(dry.score,' / 100');const drynessKey='dryness_'+String(dry.label||'unknown').toLowerCase().replaceAll(' ','_');$('drynessLabel').textContent=TT(drynessKey)===drynessKey?String(dry.label||'unknown').toUpperCase():TT(drynessKey);$('ctxTemp').textContent=fmtValue(w.temperature_max_c,'°C');$('ctxHumidity').textContent=fmtValue(w.relative_humidity_min_pct,'%');$('ctxWind').textContent=fmtValue(w.wind_speed_max_kmh,' km/h');$('ctxRain').textContent=fmtValue(w.precipitation_sum_mm,' mm');$('ctxSoil').textContent=fmtValue(w.soil_moisture_mean,' m³/m³');$('ctxPm25').textContent=a.available===false?'N/A':fmtValue(a.pm2_5_mean_ugm3,' µg/m³');$('ctxAod').textContent=a.available===false?'N/A':fmtValue(a.aerosol_optical_depth_mean,'');$('ctxWindDir').textContent=fmtValue(w.wind_direction_mean_deg,'°');$('contextSource').textContent=demo?TT('SIMULATED CONTEXT · demonstration only'):`${w.provider||TT('weather_unavailable')} · ${a.provider||TT('air_unavailable')}`;}
function demoContext(event){const seed=Math.abs(Math.sin((event.lat||0)*1.73+(event.lon||0)*.61+(event.event_score||0)));const temp=22+16*seed,humidity=58-35*seed,wind=10+32*(1-seed/2),rain=Math.max(0,6-8*seed),soil=.12+.23*(1-seed),score=Math.min(96,35+58*seed);return{weather:{provider:'IGNIS synthetic demo',temperature_max_c:temp,relative_humidity_min_pct:humidity,wind_speed_max_kmh:wind,wind_direction_mean_deg:((event.event_score||0)*3.6)%360,precipitation_sum_mm:rain,soil_moisture_mean:soil,dryness_context:{score,label:score>75?'very dry':score>55?'dry':'mixed'}},air_quality:{available:true,provider:'IGNIS synthetic demo',pm2_5_mean_ugm3:12+48*seed,aerosol_optical_depth_mean:.08+.42*seed}};}
async function loadEventContext(event){if(lastMode.includes('demo')){renderContext(demoContext(event),true);return;}resetContext(TT('Loading environmental context…'));try{const date=(event.start||frames[frameIndex]?.date||'').slice(0,10);const url=`/api/context/environment?lat=${encodeURIComponent(event.lat)}&lon=${encodeURIComponent(event.lon)}&event_date=${encodeURIComponent(date)}`;const res=await fetch(url);if(!res.ok){const e=await res.json().catch(()=>({}));throw new Error(e.detail||`HTTP ${res.status}`);}renderContext(await res.json());}catch(err){resetContext(TT('Context unavailable'));showToast(TT('toast_env_context',err.message),6200);}}
function openEvent(event){hideEvolutionBlocks();$('detailEmpty').classList.add('hidden');$('detailCard').classList.remove('hidden');$('detailKicker').textContent=TT('kicker_event',event.id);$('detailSeverity').textContent=sevLabel(event.severity);$('detailSeverity').style.color=(event.severity==='critical')?pal().critical:(event.severity==='high')?pal().high:pal().moderate;$('detailCoords').textContent=`${Number(event.lat).toFixed(4)}, ${Number(event.lon).toFixed(4)}`;$('detailFrp').textContent=TT('event_score',event.total_frp||0,event.event_score||0);$('detailConfidence').textContent=TT('event_confidence',event.mean_confidence||0,event.detections||0);$('detailTime').textContent=`${(event.start||'—').slice(0,16)} → ${(event.end||'—').slice(0,16)}`;$('detailSatellite').textContent=detailSource((event.families||[]).join(' + '));loadEventContext(event);}
function exportSnapshot(){if(!lastPayload){showToast(TT('toast_load_dataset'));return;}const frame=frames[frameIndex]||null;
  const evolutionOut=evolution?{engine:'fire-evolution',session:evolution.session,status_counts:evolution.status_counts,tracks_total:evolution.tracks_total,tracks_multi_frame:evolution.tracks_multi_frame,selected_track:selectedTrack?{id:selectedTrack.id,status:selectedTrack.status,confidence:selectedTrack.confidence,trajectory:selectedTrack.trajectory,timeline:selectedTrack.timeline}:null,method:evolution.method,caveat:evolution.caveat}:null;
  const out={ignis_version:(config&&config.version)||'0.9.4',generated_at:new Date().toISOString(),mode:lastMode,region:$('regionName').textContent,frame,events:candidateEvents,evolution:evolutionOut,method:lastPayload.method||null,caveat:'Satellite thermal anomalies, candidate clusters and persistent tracks are analytical signals, not confirmed wildfire incidents or official perimeters.'};const blob=new Blob([JSON.stringify(out,null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=`IGNIS_snapshot_${(frame?.date||'current')}.json`;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(a.href),1200); /* FIX: sin append, Firefox no dispara la descarga */showToast(TT('toast_snapshot'));}
function setViewMode(mode){viewMode=mode;document.querySelectorAll('#viewMode .seg').forEach(b=>b.classList.toggle('active',b.dataset.mode===mode));renderFrame();renderTrackingBanner();if(mode==='evolution'&&!evolutionTracks.length)showToast(TT('toast_no_tracks'),5200);}
function stepFrame(delta){if(!frames.length)return;frameIndex=(frameIndex+delta+frames.length)%frames.length;renderFrame();}
let playGeneration=0,playRenderCleanup=null;
function stopPlayback({refresh=true}={}){
  playGeneration++;clearTimeout(playTimer);playTimer=null;
  if(playRenderCleanup){playRenderCleanup();playRenderCleanup=null;}
  $('btnPlay').textContent=TT('PLAY');
  if(refresh)scheduleEnvRefresh();
  updateEnvLayerStatus();
}
function togglePlay(){
  if(playTimer){stopPlayback();return;}
  if(frames.length<2){showToast(TT('toast_load_timeline'));return;}
  $('btnPlay').textContent=TT('STOP');clearTimeout(envRefreshTimer);
  // No acumular ticks mientras SwiftShader sigue dibujando el frame anterior.
  // Las imágenes ambientales se conservan durante toda la reproducción.
  cancelPendingEnvLayers();
  const generation=++playGeneration;
  const queue=()=>{playTimer=setTimeout(()=>{
    if(generation!==playGeneration)return;
    let finished=false;
    const complete=()=>{if(finished)return;finished=true;cleanup();if(generation===playGeneration)queue();};
    const remove=viewer.scene.postRender.addEventListener(complete);
    const fallback=setTimeout(complete,4000);
    const cleanup=()=>{remove();clearTimeout(fallback);playRenderCleanup=null;};
    playRenderCleanup=cleanup;
    stepFrame(1);
  },IGNIS_SOFT?1500:900);};
  queue();updateEnvLayerStatus();
}

function openCalendar(){$('calendarPanel').classList.remove('hidden');loadCalendar();}
function closeCalendar(){$('calendarPanel').classList.add('hidden');}
function setCalendarMode(mode){
  calendarMode=mode;document.querySelectorAll('#calendarMode .seg').forEach(b=>b.classList.toggle('active',b.dataset.calendarMode===mode));const now=Number(dataToday().slice(0,4));
  if(mode==='demo'){$('calendarStartYear').value=2003;$('calendarEndYear').value=now;$('calendarNote').textContent=TT('calendar_demo_note');}
  else if(mode==='archive'){const min=archiveStatus?.min_date?Number(archiveStatus.min_date.slice(0,4)):2003;const max=archiveStatus?.max_date?Number(archiveStatus.max_date.slice(0,4)):now;$('calendarStartYear').value=Math.max(2000,min);$('calendarEndYear').value=Math.min(now,max);$('calendarNote').textContent=TT('calendar_archive_note');}
  else{$('calendarStartYear').value=Math.max(2003,now-3);$('calendarEndYear').value=now;$('calendarNote').textContent=TT('calendar_sample_note');}
}
function calendarRegionForDemo(){const key=selectedRegion();return key||'mexico';}
function calendarCellDate(year,month,item){if(item?.date)return item.date;const day=calendarMode==='archive'?1:10;return `${year}-${String(month).padStart(2,'0')}-${String(day).padStart(2,'0')}`;}
function renderCalendar(payload){
  calendarPayload=payload;
  const grid=$('calendarGrid');grid.replaceChildren();
  const corner=document.createElement('div');corner.className='cal-header year';corner.textContent=TT('YEAR');grid.appendChild(corner);
  for(let month=1;month<=12;month++){
    const h=document.createElement('div');h.className='cal-header';h.textContent=monthLabel(month);grid.appendChild(h);
  }
  for(const row of payload.rows||[]){
    const y=document.createElement('div');y.className='cal-year';y.textContent=row.year;grid.appendChild(y);
    for(const item of row.months||[]){
      const b=document.createElement('button');b.className=`cal-cell level-${item.level||'future'}`;b.disabled=!item.available;
      b.dataset.year=row.year;b.dataset.month=item.month;
      const score=item.score==null?'—':Math.round(item.score);
      b.innerHTML=`<strong>${score}</strong><span>${item.detections!=null?Number(item.detections).toLocaleString():' '}</span>`;
      const dateLabel=`${monthLabel(item.month)} ${row.year}`;
      const count=item.detections!=null?` · ${Number(item.detections).toLocaleString()} ${TT('word_detections')}`:'';
      b.title=item.available?TT('calendar_score_tip',dateLabel,score,count):TT('calendar_unavailable_tip',dateLabel);
      if(item.available)b.addEventListener('click',()=>selectCalendarCell(row.year,item));
      grid.appendChild(b);
    }
  }
  const region=selectedRegion();
  $('calendarSubtitle').textContent=`${region?TT('region_'+region):(payload.region_label||TT('calendar_selected_area'))} · ${payload.start_year}–${payload.end_year}`;
  if(payload.sampling_note)$('calendarNote').textContent=TT(payload.sampling_note);
  if(payload.warning)$('calendarNote').textContent=payload.warning;
}
async function loadCalendar(){
  const start=Number($('calendarStartYear').value),end=Number($('calendarEndYear').value);if(start>end){showToast(TT('toast_calendar_years'));return;}setStatus('status_calendar');
  try{let url;if(calendarMode==='demo'){const region=calendarRegionForDemo();if(!selectedRegion())showToast(TT('toast_demo_region'),3800);url=`/api/analytics/calendar/demo?region=${encodeURIComponent(region)}&start_year=${start}&end_year=${end}`;}
    else if(calendarMode==='archive'){if(!archiveStatus?.ready){showToast(TT('toast_archive_empty'),5200);openArchive();setStatus('status_online');return;}const area=selectedArea();if(!area)return;const available=new Set((archiveStatus.sources||[]).map(x=>x.id));const baselineSource=available.has('MODIS_SP')?'MODIS_SP':(archiveStatus.sources?.[0]?.id||'');url=`/api/archive/calendar?area=${encodeURIComponent(area)}&start_year=${start}&end_year=${end}&sources=${encodeURIComponent(baselineSource)}`;}
    else{if(!config?.firms_key_configured){showToast(TT('toast_calendar_key'),5200);setStatus('status_online');return;}const area=selectedArea();if(!area)return;url=`/api/analytics/calendar/sample?area=${encodeURIComponent(area)}&start_year=${start}&end_year=${end}&sample_days=3&anchor_day=10`;}
    $('calendarGrid').innerHTML=`<div class="calendar-loading">${TT('BUILDING TEMPORAL MATRIX…')}</div>`;const res=await fetch(url);if(!res.ok){const e=await res.json().catch(()=>({}));throw new Error(e.detail||`HTTP ${res.status}`);}renderCalendar(await res.json());setStatus('status_online');
  }catch(err){setStatus('status_error',false);$('calendarGrid').innerHTML=`<div class="calendar-loading error">${TT('CALENDAR FAILED')}</div>`;showToast(err.message,6500);}
}
let selectedPeriodData=null;
function renderSelectedPeriod(){
  if(!selectedPeriodData)return;
  const {year,month,item,mode}=selectedPeriodData;
  $('selectedPeriod').textContent=`${monthLabel(month)} ${year}`;
  const count=item.detections!=null?` · ${Number(item.detections).toLocaleString()} ${TT('calendar_qualifier_'+mode)}`:'';
  $('selectedPeriodScore').textContent=TT('calendar_activity',Math.round(item.score||0),count);
}
async function selectCalendarCell(year,item){const month=item.month;let startDate=calendarCellDate(year,month,item);
  /* FIX: la celda del mes en curso puede apuntar a un día aún futuro (p.ej. día 10
     del mes actual); el backend responde 400 a fechas futuras. Se recorta a hoy. */
  const todayISO=dataToday();if(startDate>todayISO)startDate=todayISO;$('historyDate').value=startDate;selectedPeriodData={year,month,item,mode:calendarMode};renderSelectedPeriod();const region=selectedRegion()||calendarRegionForDemo();const previousRegion=lastPayload?.region||Object.keys(REGIONS).find(key=>REGIONS[key].area===lastArea);if(previousRegion&&previousRegion!==region&&REGIONS[region])flyRegion(region);closeCalendar();if(calendarMode==='demo')await loadDemoPeriod(startDate,region);else if(calendarMode==='archive')await loadArchivePeriod(startDate,daysInMonth(year,month));else await loadHarmonized();}

function openArchive(){$('archivePanel').classList.remove('hidden');loadArchiveStatus();}
function closeArchive(){$('archivePanel').classList.add('hidden');}
async function importArchive(){const input=$('archiveFile'),file=input.files?.[0];if(!file){showToast(TT('toast_select_file'));return;}const fd=new FormData();fd.append('file',file);fd.append('source',$('archiveSource').value);$('archiveProgress').classList.remove('hidden');$('btnImportArchive').disabled=true;setStatus('status_importing');try{const res=await fetch('/api/archive/import',{method:'POST',body:fd});if(!res.ok){const e=await res.json().catch(()=>({}));throw new Error(e.detail||`HTTP ${res.status}`);}const data=await res.json();applyArchiveStatus(data.archive);const inserted=(data.results||[]).reduce((a,x)=>a+Number(x.rows_inserted||0),0);showToast(TT('toast_import_done',inserted.toLocaleString()),6500);input.value='';setStatus('status_online');}catch(err){setStatus('status_error',false);showToast(err.message,7000);}finally{$('archiveProgress').classList.add('hidden');$('btnImportArchive').disabled=false;}}

const clickHandler=new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);clickHandler.setInputAction(m=>{const picked=viewer.scene.pick(m.position);const meta=picked?.id;if(meta?.type==='ignis-fire')openFire(meta.fire);if(meta?.type==='ignis-cell')openCell(meta.cell);if(meta?.type==='ignis-event')openEvent(meta.event);if(meta?.type==='ignis-track'){const t=meta.track;flyToTrack(t);openTrack(t);}if(meta?._ignisEvent)openEvent(meta._ignisEvent);},Cesium.ScreenSpaceEventType.LEFT_CLICK);

/* --- v0.7: lectura de coordenadas bajo el cursor + atajos --- */
(function cursorHud(){
  const hud=$('cursorReadout'),coords=$('cursorCoords'),height=$('cursorHeight');
  const handler=new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
  handler.setInputAction(move=>{
    const carto=viewer.camera.pickEllipsoid(move.endPosition,viewer.scene.globe.ellipsoid);
    if(!carto){hud.classList.add('hidden');return;}
    const c=Cesium.Cartographic.fromCartesian(carto);
    hud.classList.remove('hidden');
    coords.textContent=`${Cesium.Math.toDegrees(c.latitude).toFixed(3)}°, ${Cesium.Math.toDegrees(c.longitude).toFixed(3)}°`;
    height.textContent=`EYE ${(viewer.camera.positionCartographic.height/1000).toFixed(0)} KM`;
  },Cesium.ScreenSpaceEventType.MOUSE_MOVE);
})();
document.addEventListener('keydown',e=>{
  const tag=(e.target&&e.target.tagName)||'';
  if(tag==='INPUT'||tag==='SELECT'||tag==='TEXTAREA')return;
  if(e.key===' '){if(tag==='BUTTON')return;e.preventDefault();togglePlay();} /* FIX: sin esto el PLAY con foco hacía toggle doble */
  if(e.key==='e'||e.key==='E')setViewMode('evolution');
  if(e.key==='h'||e.key==='H')setViewMode('hotspots');
  if(e.key==='r'||e.key==='R')replayTrack();
});
['moderate','high','critical'].forEach(id=>$(id).addEventListener('change',renderFrame));
document.querySelectorAll('#viewMode .seg').forEach(btn=>btn.addEventListener('click',()=>setViewMode(btn.dataset.mode)));
document.querySelectorAll('#calendarMode .seg').forEach(btn=>btn.addEventListener('click',()=>{setCalendarMode(btn.dataset.calendarMode);loadCalendar();}));
$('btnHarmonizedDemo').addEventListener('click',loadAnalyticalDemo);$('btnHarmonize').addEventListener('click',loadHarmonized);$('btnBaseline').addEventListener('click',loadBaseline);$('frameSlider').addEventListener('input',e=>{if(playTimer)stopPlayback({refresh:false});frameIndex=Number(e.target.value);renderFrame();});$('btnPrev').addEventListener('click',()=>{if(playTimer)stopPlayback({refresh:false});stepFrame(-1);});$('btnNext').addEventListener('click',()=>{if(playTimer)stopPlayback({refresh:false});stepFrame(1);});$('btnPlay').addEventListener('click',togglePlay);
$('regionPreset').addEventListener('change',()=>{updateRegionLabel();const key=selectedRegion();if(key)flyRegion(key);});$('btnFlyRegion').addEventListener('click',()=>{const key=selectedRegion();if(key)flyRegion(key);else showToast(TT('toast_viewport_active'));});
$('btnCalendar').addEventListener('click',openCalendar);$('btnCloseCalendar').addEventListener('click',closeCalendar);$('btnLoadCalendar').addEventListener('click',loadCalendar);
$('btnArchive').addEventListener('click',openArchive);$('btnCloseArchive').addEventListener('click',closeArchive);$('btnImportArchive').addEventListener('click',importArchive);$('btnExport').addEventListener('click',exportSnapshot);
/* --- v0.7 --- */
$('btnEvolutionDemo').addEventListener('click',()=>loadEvolutionDemo({autoFocus:true}));
$('btnEvolutionArchive').addEventListener('click',loadEvolutionArchive);
$('btnReplayTrack').addEventListener('click',replayTrack);
$('btnStopReplay').addEventListener('click',stopReplay);
document.querySelectorAll('.env-chip').forEach(chip=>chip.addEventListener('click',()=>toggleEnvLayer(chip.dataset.env)));
$('btnCollapseDossier').addEventListener('click',()=>{
  const card=$('detailCard');card.classList.toggle('collapsed');
  $('btnCollapseDossier').textContent=card.classList.contains('collapsed')?'▸':'▾';
  drawHud();
});
document.addEventListener('keydown',e=>{if(e.key!=='Escape')return;if(!$('calendarPanel').classList.contains('hidden'))closeCalendar();if(!$('archivePanel').classList.contains('hidden'))closeArchive();});

(async()=>{
  const today=new Date().toISOString().slice(0,10),year=new Date().getFullYear();
  $('historyDate').value=today;$('historyDate').max=today;$('calendarStartYear').value=2003;$('calendarEndYear').value=year;
  updateRegionLabel();cinematicIntro();               // entrada cinematográfica God's Eye
  await loadConfig();await loadArchiveStatus();
  await loadEvolutionDemo({autoFocus:false});        // conserva el globo de la intro visible al arrancar
  /* v0.9.4: el globo arranca ya con COLOR REAL puesto para que el planeta se vea
     como satélite desde el primer segundo (petición del usuario). */
  if(navigator.onLine!==false)setTimeout(()=>{if(!envLayers.truecolor)addEnvLayer('truecolor',{quiet:true});},1500);
})();

/* ==========================================================================
   IGNIS v0.7 — Fire Evolution Engine · UI
   Persistent tracks, lifecycle states, trail rendering, HUD cinematográfico.
   ========================================================================== */
const STATE_CLASS={EMERGING:'emerging',EXPANDING:'expanding',STABLE:'stable',DECLINING:'declining',EXTINCT:'extinct'};
const STATE_COLOR=new Proxy({},{get:(_,k)=>pal()[String(k).toLowerCase()]||pal().stable});
const trackColor=track=>Cesium.Color.fromCssColorString(STATE_COLOR[track.status]||pal().stable);

function frameIndexOf(date){return frames.findIndex(f=>(f.date||'')===(date||''));}

/* --- panel --- */
function renderEvolutionPanel(){
  const list=$('evoList'),summary=$('evoSummary');if(!list||!summary)return;
  if(!evolutionTracks.length){
    summary.innerHTML=`<span class="chip">${TT('NO TRACKS')}</span><small>${TT('Load the evolution demo or a multi-day dataset.')}</small>`;
    list.innerHTML=`<div class="source-empty">${TT('Persistent event identities will appear here.')}</div>`;
    return;
  }
  const counts=evolution?.status_counts||{};
  summary.innerHTML=['EXPANDING','DECLINING','STABLE','EMERGING','EXTINCT']
    .filter(s=>counts[s]).map(s=>`<span class="chip ${STATE_CLASS[s]}">${trackStateLabel(s)} ${counts[s]}</span>`).join('')
    +`<small>${TT('track_summary',evolutionTracks.length,evolution?.tracks_multi_frame||0,evolution?.method?.link_radius_km||'—')}</small>`;
  list.innerHTML='';
  for(const track of evolutionTracks.slice(0,12)){
    const row=document.createElement('button');row.className='evo-row'+(selectedTrack?.id===track.id?' active':'');
    row.innerHTML=`<strong>${track.id}</strong>`
      +`<span class="row-state" style="color:${STATE_COLOR[track.status]||'#a6ff77'}">${trackStateLabel(track.status)}</span>`
      +`<span>${TT('track_row',track.frames_observed,track.detections_total,track.duration_hours)}${track.trajectory?.bearing_compass?` · ${TT('track_drift',track.trajectory.bearing_compass)}`:''}</span>`
      +`<span class="row-conf">${Math.round(track.confidence?.score||0)}%</span>`;
    row.addEventListener('click',()=>{flyToTrack(track);openTrack(track);});
    list.appendChild(row);
  }
}
function cinematicOffset(){ /* desplaza la vista para que el evento quede libre de paneles */
  try{const h=viewer.camera.positionCartographic.height;viewer.camera.moveRight(h*0.20);viewer.camera.moveDown(h*0.04);}catch(e){}
}
function flyToTrack(track,offset=true){
  const pts=track.trail||[];
  const lats=pts.map(p=>p.lat),lons=pts.map(p=>p.lon);
  const latSpan=(Math.max(...lats,(track.lat||0))-Math.min(...lats,(track.lat||0)))*111;
  const lonSpan=(Math.max(...lons,(track.lon||0))-Math.min(...lons,(track.lon||0)))*96;
  const diag=Math.max(20,Math.hypot(latSpan,lonSpan));
  const height=Math.max(2000000,Math.min(4200000,diag*26000));
  viewer.camera.flyTo({destination:Cesium.Cartesian3.fromDegrees(track.lon,track.lat,height),duration:1.6,complete:()=>{if(offset)cinematicOffset();}});
}

/* --- render de trails + marcadores por frame --- */
function renderEvolutionFrame(date){
  eventCollection.removeAll();trailDataSource.entities.removeAll();pulsePrimitives=[];
  const order=frames.map(f=>f.date);const nowIndex=date?order.indexOf(date):frames.length-1;
  let visible=0;
  for(const track of evolutionTracks){
    const upto=(track.timeline||[]).map((s,i)=>({...s,index:frameIndexOf(s.date)})).filter(s=>s.index>=0&&s.index<=nowIndex);
    if(!upto.length)continue;
    const selected=selectedTrack?.id===track.id;visible++;
    const color=trackColor(track);
    /* estela: segmentos con alfa creciente hacia el presente */
    for(let i=1;i<upto.length;i++){
      const a=upto[i-1],b=upto[i];
      const segAlpha=selected?0.42+0.5*(i/upto.length):0.18+0.26*(i/upto.length);
      trailDataSource.entities.add({polyline:{positions:Cesium.Cartesian3.fromDegreesArrayHeights([a.lon,a.lat,26000,b.lon,b.lat,26000]),width:selected?3.2:2.0,material:color.withAlpha(segAlpha),clampToGround:false}});
    }
    /* puntos de la trayectoria */
    upto.forEach((s,i)=>{
      trailDataSource.entities.add({position:Cesium.Cartesian3.fromDegrees(s.lon,s.lat,22000),point:{pixelSize:selected?6:4,color:color.withAlpha(0.3+0.6*(i/upto.length)),outlineColor:color.withAlpha(.9),outlineWidth:1}});
      if(selected&&i===upto.length-1){
        trailDataSource.entities.add({position:Cesium.Cartesian3.fromDegrees(s.lon,s.lat),ellipse:{semiMajorAxis:Math.max(2600,(s.radius_km||4)*1000),semiMinorAxis:Math.max(2600,(s.radius_km||4)*1000),material:color.withAlpha(.07),outline:true,outlineColor:color.withAlpha(.75),height:0}});
      }
    });
    /* marcador del frame actual (con pulso) */
    const last=upto[upto.length-1];
    const isCurrent=last.date===date;
    const prim=eventCollection.add({position:Cesium.Cartesian3.fromDegrees(last.lon,last.lat,24000),color:color.withAlpha(isCurrent?.85:.4),outlineColor:color.withAlpha(isCurrent?1:.5),outlineWidth:selected?4:2,pixelSize:selected?13:9,scaleByDistance:new Cesium.NearFarScalar(1.2e6,1.5,3.5e7,.6),id:{type:'ignis-track',track}});
    if(isCurrent)pulsePrimitives.push({prim,base:selected?16:11,phase:Math.random()*6.28,color});
  }
  renderTrackingBanner();
  return visible;
}

/* --- detalle --- */
function drawLifecycleChart(track){
  const svg=$('evoChart');if(!svg)return;
  const tl=track.timeline||[];if(!tl.length){svg.innerHTML='';return;}
  const W=260,H=74,pad=14;const maxDet=Math.max(...tl.map(s=>s.detections),1);const maxFrp=Math.max(...tl.map(s=>s.total_frp),1);
  const step=(W-pad*2)/Math.max(1,tl.length-1);const barW=Math.min(22,step*0.62);
  const peakDate=track.peak?.date;
  let bars='',line='',dots='',grid='',axis='';
  grid+=`<line class="grid" x1="${pad}" y1="${H-pad}" x2="${W-pad}" y2="${H-pad}"/>`;
  tl.forEach((s,i)=>{
    const x=pad+i*step;const h=Math.max(3,(s.detections/maxDet)*(H-pad*2.2));
    const cls=s.date===peakDate?'bar peak':`bar ${STATE_CLASS[track.status]||''}`;
    bars+=`<rect class="${cls}" x="${(x-barW/2).toFixed(1)}" y="${(H-pad-h).toFixed(1)}" width="${barW.toFixed(1)}" height="${h.toFixed(1)}"/>`;
    const y=H-pad-(s.total_frp/maxFrp)*(H-pad*2.2);
    line+=`${i?'L':'M'}${x.toFixed(1)},${y.toFixed(1)}`;dots+=`<circle class="dot" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="2.1"/>`;
    if(i===0||i===tl.length-1||s.date===peakDate)axis+=`<text class="axis" x="${x.toFixed(1)}" y="${H-3}" text-anchor="middle">${(s.date||'').slice(5)}</text>`;
  });
  svg.innerHTML=grid+bars+`<path class="line" d="${line}"/>`+dots+axis;
}
function renderTrackDetail(track){
  $('detailKicker').textContent=`${TT('kicker_track')} · ${track.id}`;
  $('detailSeverity').textContent=trackStateLabel(track.status);
  $('detailFrp').textContent=`Σ ${track.total_frp} MW · ${TT('track_peak')} ${track.max_frp} MW`;
  $('detailConfidence').textContent=`${track.mean_confidence}% · ${track.detections_total} ${TT('word_detections')}`;
  $('evoDetail').classList.remove('hidden');$('evoIntel').classList.remove('hidden');
  const chip=$('evoStatus');chip.textContent=trackStateLabel(track.status);chip.className=`status-chip ${STATE_CLASS[track.status]||''}`;
  $('evoIdentity').textContent=`${track.identity==='reused'?TT('identity_reused'):TT('identity_new')} · ${track.sources?.join(' + ')||'—'}`;
  $('evoBasis').textContent=translateEvolutionText(track.status_basis)||'—';
  $('evoDuration').textContent=`${track.duration_hours} h`;
  $('evoFrames').textContent=`${track.frames_observed} / ${track.frames_in_dataset}`;
  $('evoPeak').textContent=`${track.peak?.date?.slice(5)||'—'} · ${track.peak?.total_frp||0} MW`;
  const tr=track.trajectory||{};
  $('evoDrift').textContent=tr.bearing_compass?`${tr.bearing_compass} · ${tr.net_displacement_km} km`:'—';
  $('evoConfidence').textContent=`${Math.round(track.confidence?.score||0)}% · ${sevLabel(track.confidence?.level)}`;
  const bars=$('evoBars');bars.innerHTML='';
  const labels={detections:TT('conf_detections'),persistence:TT('conf_persistence'),sensor_independence:TT('conf_sensors'),frp:TT('conf_frp'),declared_confidence:TT('conf_declared')};
  for(const [key,val] of Object.entries(track.confidence?.components||{})){
    const row=document.createElement('div');row.className='cb';
    row.innerHTML=`<span>${labels[key]||key.toUpperCase()}</span><span class="cb-track"><span class="cb-fill" style="width:${Math.min(100,val)}%;display:block"></span></span><span class="cb-val">${Math.round(val)}</span>`;
    bars.appendChild(row);
  }
  const ev=$('evoEvidence');ev.innerHTML='';
  for(const line of (track.confidence?.explanations||[])){const s=document.createElement('span');s.textContent=translateEvidence(line);ev.appendChild(s);}
  const sp=document.createElement('span');
  sp.textContent=translateEvolutionText(tr.interpretation)||TT('track_drift_note');
  ev.appendChild(sp);
  $('evoCaveat').textContent=translateEvolutionText(track.caveat)||TT('track_caveat_short');
  drawLifecycleChart(track);
}
function openTrack(track){
  selectedTrack=track;
  $('detailEmpty').classList.add('hidden');$('detailCard').classList.remove('hidden');
  $('detailKicker').textContent=`${TT('kicker_track')} · ${track.id}`;
  $('detailSeverity').textContent=trackStateLabel(track.status);
  $('detailSeverity').style.color=STATE_COLOR[track.status]||'#a6ff77';
  $('detailCoords').textContent=`${Number(track.lat).toFixed(4)}, ${Number(track.lon).toFixed(4)}`;
  $('detailFrp').textContent=`Σ ${track.total_frp} MW · ${TT('track_peak')} ${track.max_frp} MW`;
  $('detailConfidence').textContent=`${track.mean_confidence}% · ${track.detections_total} ${TT('word_detections')}`;
  $('detailTime').textContent=`${(track.first_seen||'').slice(0,10)} → ${(track.last_seen||'').slice(0,10)}`;
  $('detailSatellite').textContent=detailSource((track.families||[]).join(' + '));
  renderTrackDetail(track);renderEvolutionPanel();renderFrame();renderTrackingBanner();
  loadEnvironmentIntelligence(track.lat,track.lon,(track.last_seen||'').slice(0,10));
  if(window.IGNIS_ANALYST)window.IGNIS_ANALYST.lastTrack=track;
  const card=$('detailCard');if(card)card.scrollTop=0;
}

/* --- banner de seguimiento + reticle + línea guía --- */
function renderTrackingBanner(){
  const banner=$('trackingBanner');if(!banner)return;
  if(!selectedTrack||viewMode!=='evolution'){banner.classList.add('hidden');return;}
  banner.classList.remove('hidden');
  $('trackingId').textContent=selectedTrack.id;
  $('trackingState').textContent=TT('tracking_summary',trackStateLabel(selectedTrack.status),Math.round(selectedTrack.confidence?.score||0),selectedTrack.detections_total);
}
function clearReticle(){reticleDataSource.entities.removeAll();const svg=$('leaderLayer');if(svg)svg.innerHTML='';}
function currentTrackPosition(){
  if(!selectedTrack||!frames.length)return null;
  const date=frames[frameIndex]?.date;
  const upto=(selectedTrack.timeline||[]).filter(s=>frameIndexOf(s.date)<=frameIndex);
  const last=upto[upto.length-1]||selectedTrack;return {lon:last.lon,lat:last.lat,date:last.date};
}
function drawHud(){
  const svg=$('leaderLayer');if(!svg)return;
  if(!selectedTrack||viewMode!=='evolution'||viewMode==='hotspots'){if(svg.childNodes.length)svg.innerHTML='';return;}
  const pos=currentTrackPosition();if(!pos){svg.innerHTML='';return;}
  const carto=Cesium.Cartesian3.fromDegrees(pos.lon,pos.lat,24000);
  const win=Cesium.SceneTransforms.worldToWindowCoordinates(viewer.scene,carto);
  if(!win){svg.innerHTML='';return;}
  const card=document.getElementById('detailCard');
  const box=(card&&!card.classList.contains('hidden'))?card.getBoundingClientRect():document.querySelector('.right-panel').getBoundingClientRect();
  const anchorX=box.left+box.width*0.5,anchorY=box.top+4;
  const state=STATE_CLASS[selectedTrack.status]||'stable';
  const col=STATE_COLOR[selectedTrack.status]||'#a6ff77';
  const t=(performance.now()/1000)%360;
  const r=videoR(pos)||26;
  svg.innerHTML=`
    <line class="leader-halo" x1="${win.x}" y1="${win.y}" x2="${anchorX}" y2="${anchorY}"/>
    <line class="leader" x1="${win.x}" y1="${win.y}" x2="${anchorX}" y2="${anchorY}"/>
    <g transform="translate(${win.x},${win.y}) rotate(${t})">
      <circle class="reticle-ring" r="${r+10}" transform="rotate(${-t})"/>
    </g>
    <g transform="translate(${win.x},${win.y})">
      <line class="reticle-cross" x1="${-r-16}" y1="0" x2="${-r-4}" y2="0"/>
      <line class="reticle-cross" x1="${r+4}" y1="0" x2="${r+16}" y2="0"/>
      <line class="reticle-cross" x1="0" y1="${-r-16}" x2="0" y2="${-r-4}"/>
      <line class="reticle-cross" x1="0" y1="${r+4}" x2="0" y2="${r+16}"/>
      <path class="reticle-bracket" style="stroke:${col}" d="M${-r},${-r+7} L${-r},${-r} L${-r+7},${-r} M${r-7},${-r} L${r},${-r} L${r},${-r+7} M${r},${r-7} L${r},${r} L${r-7},${r} M${-r+7},${r} L${-r},${r} L${-r},${r-7}"/>
      <text class="reticle-label" style="fill:${col}" x="${r+40}" y="${-r-4}">${selectedTrack.id} · ${trackStateLabel(selectedTrack.status)}</text>
    </g>`;
}
function videoR(){return 24;} /* FIX: el SVG trabaja en píxeles CSS (igual que
  worldToWindowCoordinates y getBoundingClientRect); multiplicar por
  devicePixelRatio dibujaba el reticle del doble de tamaño en pantallas HiDPI. */

/* --- animación: pulso + HUD --- */
/* v0.9.3: antes drawHud() reconstruía TODO el SVG (innerHTML) en cada cuadro de
   render (60 fps) y dejaba el hilo principal sin aire: los botones respondían
   con delay y las transiciones CSS se veían a tirones. Ahora ~30 fps. */
let hudLastMs=0;
viewer.scene.preRender.addEventListener(()=>{
  const time=performance.now()/1000;
  if(!IGNIS_SOFT){
    for(const item of pulsePrimitives){
      const k=0.5+0.5*Math.sin(time*2.2+item.phase);
      try{item.prim.pixelSize=item.base*(0.85+0.55*k);}catch(e){}
    }
  }
  const nowMs=performance.now();
  if(nowMs-hudLastMs>=33){hudLastMs=nowMs;drawHud();}
});

/* --- carga de datos de evolución --- */
async function loadEvolutionDemo({autoFocus=true}={}){
  setStatus('status_tracking');
  try{
    const region=selectedRegion()==='amazon'?'amazon':'mexico';
    const res=await fetch(`/api/evolution/demo?region=${region}&days=5`);
    if(!res.ok)throw new Error(`HTTP ${res.status}`);
    const payload=await res.json();
    applyHarmonized(payload);
    setViewMode('evolution');
    const best=evolutionTracks.find(t=>t.status==='EXPANDING')||evolutionTracks.find(t=>t.status!=='EXTINCT')||evolutionTracks[0];
    if(autoFocus){
      if(best){openTrack(best);flyToTrack(best);}
      else if(payload.camera)viewer.camera.flyTo({destination:Cesium.Cartesian3.fromDegrees(payload.camera[0],payload.camera[1],payload.camera[2]),duration:2.2});
    }
    showToast(TT('toast_evo_demo',payload.evolution.tracks_total,payload.evolution.tracks_multi_frame),6800);
  }catch(err){setStatus('status_error',false);showToast(TT('toast_evo_fail',err.message),6500);}
}
async function loadEvolutionArchive(){
  const area=lastArea||selectedArea();if(!area)return;
  if(!archiveStatus?.ready){showToast(TT('toast_import_first'),5600);return;}
  const start=archiveStatus.min_date||$('historyDate').value;
  const end=archiveStatus.max_date||start;
  const days=Math.min(10,Math.max(2,Math.round((new Date(end)-new Date(start))/86400000)+1));
  setStatus('status_tracking');
  try{
    const res=await fetch(`/api/evolution/archive?area=${encodeURIComponent(area)}&start_date=${encodeURIComponent(start)}&days=${days}`);
    if(!res.ok){const e=await res.json().catch(()=>({}));throw new Error(e.detail||`HTTP ${res.status}`);}
    const payload=await res.json();applyHarmonized(payload);setViewMode('evolution');
    const best=evolutionTracks.find(t=>t.status==='EXPANDING')||evolutionTracks[0];
    if(best){openTrack(best);flyToTrack(best);}
    showToast(TT('toast_real_tracks',payload.evolution.tracks_total,payload.evolution.tracks_multi_frame),7000);
  }catch(err){setStatus('status_error',false);showToast(err.message,6500);}
}

/* --- replay del ciclo de vida --- */
function stopReplay(){replayToken++;$('btnReplayTrack')?.classList.remove('playing');const b=$('btnReplayTrack');if(b)b.textContent=TT('replay_lifecycle');}
function replayTrack(){
  if(!selectedTrack){showToast(TT('toast_select_track'));return;}
  const token=++replayToken;const btn=$('btnReplayTrack');
  const steps=(selectedTrack.timeline||[]).map(s=>({index:frameIndexOf(s.date),lat:s.lat,lon:s.lon,det:s.detections}))
    .filter(s=>s.index>=0).sort((a,b)=>a.index-b.index);
  if(steps.length<2){showToast(TT('toast_single_frame'));return;}
  if(btn){btn.classList.add('playing');btn.textContent=TT('replaying');}
  let i=0;
  const advance=()=>{
    if(token!==replayToken)return;
    if(i>=steps.length){stopReplay();showToast(TT('toast_replay_done',selectedTrack.id,selectedTrack.status),5200);return;}
    const step=steps[i];frameIndex=step.index;renderFrame();
    viewer.camera.flyTo({destination:Cesium.Cartesian3.fromDegrees(step.lon,step.lat,Math.max(260000,Math.min(1100000,240000+step.det*45000))),duration:1.35});
    i++;setTimeout(advance,1750);
  };
  advance();
}

/* ==========================================================================
   v0.7.1 — Diagnóstico y resiliencia del mapa 3D
   El preview del workspace expone la página en un iframe con origen opaco:
   los workers y las peticiones cross-origin se comportan distinto. Aquí se
   reporta el estado real del renderer y se degrada con elegancia si falla.
   ========================================================================== */
(function rendererDiagnostics(){
  const env=window.IGNIS_ENV||{};
  const canvas=document.createElement('canvas');
  const gl=canvas.getContext('webgl2')||canvas.getContext('webgl');
  const software=/SwiftShader|llvmpipe|Software|ANGLE \(Software/i.test((gl&&(()=>{try{const d=gl.getExtension('WEBGL_debug_renderer_info');return d?gl.getParameter(d.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER);}catch(e){return '';}})())||'');
  const parts=[gl?'WEBGL':'NO-WEBGL'];
  if(software)parts.push('SW');
  if(env.workerMode==='blob-fallback')parts.push('WORKERS·BLOB');
  else if(env.workerMode==='none')parts.push('NO-WORKERS');
  if(env.sandboxed)parts.push('SANDBOX');
  const label=parts.join(' · ');
  const el=$('rendererStatus');
  if(el){el.textContent=label;el.classList.add(gl&&!software?'ok':'degraded');}
  try{viewer.scene.renderError.addEventListener((sc,e)=>{
    const detail=String((e&&e.message)||e).slice(0,200);
    window.IGNIS_ENV.renderErrorReal=detail;
    ignisSafeRender();
    setStatus('status_safe',false);
    showRenderAlert(TT('render_alert_stopped_t'),TT('render_alert_stopped_b',detail));
  });}catch(e){}
if(!gl){showRenderAlert(TT('render_alert_no_webgl_t'),TT('render_alert_no_webgl_b'));}
  console.info('[IGNIS] renderer:',label,'· sandboxed:',!!env.sandboxed,'· workers:',env.workerMode);
})();

/* v0.9.3 — recuperación ante renderError de Cesium: apaga los efectos pesados,
   ELIMINA el panel modal de Cesium (bloqueaba todos los clicks de la UI) y
   reinicia el bucle de render, que Cesium detiene tras el error. */
function ignisSafeRender(){
  try{viewer.scene.postProcessStages.bloom.enabled=false;}catch(e){}
  try{viewer.scene.highDynamicRange=false;}catch(e){}
  try{viewer.scene.postProcessStages.fxaa.enabled=false;}catch(e){}
  try{viewer.scene.skyBox.show=false;viewer.scene.globe.enableLighting=false;}catch(e){}
  try{document.querySelectorAll('.cesium-widget-errorPanel').forEach(n=>n.remove());}catch(e){}
  /* El error se emite dentro del frame de Cesium. Reiniciar el bucle en esa
     misma pila puede dejarlo detenido al terminar el catch interno. */
  if(ignisSafeRender.pending)return;
  ignisSafeRender.pending=true;
  setTimeout(()=>{
    ignisSafeRender.pending=false;
    try{
      document.querySelectorAll('.cesium-widget-errorPanel').forEach(n=>n.remove());
      viewer.useDefaultRenderLoop=false;
      viewer.useDefaultRenderLoop=true;
      viewer.resize();
      viewer.scene.requestRender();
    }catch(e){console.warn('[IGNIS] No se pudo reiniciar el visor:',e);}
  },0);
}
function showRenderAlert(title,body){
  const box=$('renderAlert');if(!box)return;
  $('renderAlertTitle').textContent=title;$('renderAlertBody').textContent=body;box.classList.remove('hidden');
}
function hideRenderAlert(){const box=$('renderAlert');if(box)box.classList.add('hidden');}

/* Vigilante de render: si Cesium detiene el render, se degrada en vez de morir. */
(function renderWatchdog(){
  // postUpdate sigue latiendo en requestRenderMode aunque no haya nada que
  // pintar. El vigilante anterior forzaba un dibujo cada 2,5 s: con
  // SwiftShader podía ocupar el compositor continuamente en pleno reposo.
  let lastUpdate=performance.now(),checking=false,recovering=false;
  viewer.scene.postUpdate.addEventListener(()=>{lastUpdate=performance.now();if(recovering){recovering=false;hideRenderAlert();}});
  setInterval(()=>{
    if(document.hidden||checking||performance.now()-lastUpdate<15000)return;
    checking=true;
    const before=lastUpdate;
    viewer.scene.requestRender();
    setTimeout(()=>{
      checking=false;
      if(lastUpdate!==before)return;
      if(!recovering){
        recovering=true;ignisSafeRender();setStatus('status_safe',false);
        showToast(TT('toast_render_light'),4200);
        setTimeout(()=>{
          if(lastUpdate===before){
            const detail=window.IGNIS_ENV?.renderErrorReal||'sin respuesta del motor';
            showRenderAlert(TT('render_alert_stopped_t'),TT('render_alert_stopped_b',detail));
          }else{recovering=false;hideRenderAlert();}
        },9000);
      }
    },2000);
  },3000);
})();

/* Reintento manual: recarga limpia del visor conservando el estado. */
$('btnRetryRender')?.addEventListener('click',()=>{
  hideRenderAlert();
  try{
    document.querySelectorAll('.cesium-widget-errorPanel').forEach(n=>n.remove());
    if(!IGNIS_SOFT){
      viewer.scene.highDynamicRange=true;
      viewer.scene.postProcessStages.bloom.enabled=true;
      viewer.scene.postProcessStages.fxaa.enabled=true;
    }
    if(!IGNIS_SOFT){viewer.scene.skyBox.show=true;viewer.scene.globe.enableLighting=IGNIS_TERMINATOR;}
    viewer.useDefaultRenderLoop=false;viewer.useDefaultRenderLoop=true;
    viewer.resize();
    tuneImagery();
    renderFrame();drawHud();
    showToast(TT('toast_render_retry'),4200);
  }catch(e){showToast(TT('toast_render_fail',e.message),6000);}
});

/* ==========================================================================
   IGNIS v0.8 — Environmental Intelligence (UI)
   1) Capas NASA GIBS conmutables sobre el globo, sincronizadas con el timeline.
   2) Bloque ENTORNO en el dossier: sequía, vegetación y humo por evento.
   Nota GIBS: el orden del REST es {TileMatrix}/{TileRow}/{TileCol}.

   FIX DE RENDER (v0.9.2): antes se usaba el endpoint epsg4326 con una
   GeographicTilingScheme. Los TileMatrixSet 4326 de GIBS NO son potencias de
   dos (verificado contra WMTSCapabilities: nivel 1 = 3×2, nivel 5 = 40×20),
   mientras Cesium asume 2^L×2^L: los tiles se pedían con índices de otra
   rejilla y las capas caían en el lugar equivocado del globo (o daban 404 y
   desaparecían). El endpoint epsg3857 usa rejillas GoogleMapsCompatible_LevelN
   estándar (2^L×2^L) que calzan exacto con WebMercatorTilingScheme.
   ========================================================================== */
const ENV_CATALOG={
  aerosol:{id:'MODIS_Terra_Aerosol',tms:'GoogleMapsCompatible_Level6',maxLevel:6,ext:'png',alpha:.6,lagDays:1,smooth:true,label:'AEROSOLES (AOD)'},
  ndvi:{id:'MODIS_Terra_NDVI_8Day',tms:'GoogleMapsCompatible_Level9',maxLevel:9,ext:'png',alpha:.82,lagDays:2,label:'VEGETACIÓN (NDVI)'},
  /* v0.9.4: el proxy convierte el relleno negro en alfa y combina tres días
     en una sola imagen para rellenar huecos de órbita. */
  truecolor:{id:'MODIS_Terra_CorrectedReflectance_TrueColor',tms:'GoogleMapsCompatible_Level9',maxLevel:9,ext:'png',alpha:.97,lagDays:2,composite:true,label:'COLOR REAL'},
  pyro:{id:'OMPS_Aerosol_Index_PyroCumuloNimbus',tms:'GoogleMapsCompatible_Level6',maxLevel:6,ext:'png',alpha:.62,lagDays:1,smooth:true,label:'PIRO-CUMULONIMBOS (OMPS)'},
};
let envLayers={};           // imágenes visibles, con fecha propia por producto
let envLayerDate=null;      // compatibilidad: fecha visible de COLOR REAL
const envSelections=new Set();
const envPending=new Map(),envLayerCache=new Map(),envProblems=new Map();
let envRefreshTimer=null;
function currentEnvDate(){return frames[frameIndex]?.date||dataToday();}
function envDateOffset(date,days){const d=new Date(date+'T00:00:00Z');d.setUTCDate(d.getUTCDate()-days);return d.toISOString().slice(0,10);}
function envChip(key){return document.querySelector(`.env-chip[data-env="${key}"]`);}
function updateEnvLayerStatus(){
  const lines=[];
  for(const key of envSelections){
    const chip=envChip(key),rec=envLayers[key],pending=envPending.get(key),problem=envProblems.get(key);
    if(chip){
      chip.classList.toggle('selected',true);
      chip.classList.toggle('active',!!rec);
      chip.classList.toggle('loading',!!pending);
      chip.classList.toggle('failed',!!problem);
      chip.setAttribute('aria-pressed','true');
      chip.dataset.state=pending?'loading':problem?'unavailable':'ready';
      chip.dataset.date=rec?.topDate||'';
      chip.title=TT(chip.dataset.tip)+(rec?' · '+TT('env_visible_date',rec.topDate):'')+(problem?' · '+TT(problem):'');
    }
    const name=TT('layer_'+key);
    if(pending)lines.push(TT('env_layer_loading',name,pending.topDate,rec?.topDate||'—'));
    else if(problem)lines.push(TT('env_problem',name,TT(problem),rec?.topDate||'—'));
    else if(rec)lines.push(TT('env_layer_date',name,rec.topDate));
  }
  const status=$('envLayerStatus');
  if(status)status.textContent=(playTimer?TT('env_playback_frozen')+' ':'')+lines.join(' · ');
  envLayerDate=envLayers.truecolor?.date||Object.values(envLayers)[0]?.date||null;
}
function cleanupEnvPending(rec){
  clearTimeout(rec.timer);clearTimeout(rec.checkTimer);
  rec.removeProgress?.();rec.removeProgress=null;
}
function orderEnvLayers(){
  for(const key of ['truecolor','ndvi','aerosol','pyro']){
    const records=[envLayers[key],envPending.get(key)].filter(Boolean);
    for(const rec of new Set(records))for(const layer of rec.layers){
      if(viewer.imageryLayers.contains(layer))viewer.imageryLayers.raiseToTop(layer);
    }
  }
}
function destroyEnvRecord(rec){
  cleanupEnvPending(rec);
  for(const layer of rec.layers){if(viewer.imageryLayers.contains(layer))viewer.imageryLayers.remove(layer,true);}
  envLayerCache.delete(rec.cacheKey);
}
function removeEnvLayer(key){
  envSelections.delete(key);envProblems.delete(key);
  const pending=envPending.get(key);if(pending)cleanupEnvPending(pending);
  envPending.delete(key);delete envLayers[key];
  for(const rec of [...envLayerCache.values()])if(rec.key===key)destroyEnvRecord(rec);
  const chip=envChip(key);
  if(chip){chip.classList.remove('active','selected','loading','failed');chip.setAttribute('aria-pressed','false');chip.dataset.state='off';chip.dataset.date='';chip.title=TT(chip.dataset.tip);}
  updateEnvLayerStatus();viewer.scene.requestRender();
}
function cancelPendingEnvLayers({includeInitial=false}={}){
  for(const [key,rec] of envPending){
    // La primera carga aún debe confirmar cobertura; reproducir no la
    // convierte en una imagen lista. Solo se cancela un reemplazo de fecha.
    if(envLayers[key]===rec&&!includeInitial)continue;
    cleanupEnvPending(rec);envPending.delete(key);
    if(envLayers[key]===rec)delete envLayers[key];
    destroyEnvRecord(rec);
  }
  updateEnvLayerStatus();
}
function markEnvUnavailable(key,reason='layer_unreachable'){
  const pending=envPending.get(key);
  if(pending){
    cleanupEnvPending(pending);envPending.delete(key);
    if(envLayers[key]===pending)delete envLayers[key];
    destroyEnvRecord(pending);
  }
  const first=envProblems.get(key)!==reason;
  envProblems.set(key,reason);updateEnvLayerStatus();
  if(first)showToast(TT('toast_layer_unavailable',TT('layer_'+key)),4800);
}
function finishEnvLayer(key,rec){
  if(envPending.get(key)!==rec||!envSelections.has(key))return;
  cleanupEnvPending(rec);envPending.delete(key);
  const old=envLayers[key];
  if(old&&old!==rec)for(const layer of old.layers)layer.show=false;
  rec.ready=true;envLayers[key]=rec;envProblems.delete(key);
  // Reusar la fecha anterior sin volver a descargarla; dos fechas por capa
  // mantienen acotada la memoria y evitan destruir el globo al reanudar.
  const others=[...envLayerCache.values()].filter(item=>item.key===key&&item!==rec).sort((a,b)=>b.used-a.used);
  for(const stale of others.slice(1))destroyEnvRecord(stale);
  rec.used=performance.now();orderEnvLayers();updateEnvLayerStatus();viewer.scene.requestRender();
}
function addEnvLayer(key,opts={}){
  const cfg=ENV_CATALOG[key];if(!cfg)return;
  envSelections.add(key);
  if(navigator.onLine===false){envProblems.set(key,'layer_offline');updateEnvLayerStatus();return;}
  const date=currentEnvDate(),topDate=envDateOffset(date,cfg.lagDays||1),cacheKey=key+'|'+date;
  if(envPending.get(key)?.date===date||envLayers[key]?.date===date&&!envProblems.has(key)){updateEnvLayerStatus();return;}
  const previousPending=envPending.get(key);
  if(previousPending){cleanupEnvPending(previousPending);envPending.delete(key);if(envLayers[key]===previousPending)delete envLayers[key];destroyEnvRecord(previousPending);}
  envProblems.delete(key);
  const cached=envLayerCache.get(cacheKey);
  if(cached?.ready){
    for(const layer of envLayers[key]?.layers||[])layer.show=false;
    for(const layer of cached.layers)layer.show=true;
    envLayers[key]=cached;cached.used=performance.now();orderEnvLayers();updateEnvLayerStatus();viewer.scene.requestRender();return;
  }
  const rec={key,date,topDate,cacheKey,layers:[],successes:0,detailSuccesses:0,requestedDetail:false,failures:new Set(),missing:new Set(),used:performance.now(),ready:false};
  try{
    const url=cfg.composite?`/api/gibs/composite/${topDate}/{z}/{y}/{x}.png`:`/api/gibs/tile/${cfg.id}/${topDate}/{z}/{y}/{x}.${cfg.ext}`;
    const provider=new Cesium.UrlTemplateImageryProvider({url,tilingScheme:new Cesium.WebMercatorTilingScheme(),maximumLevel:cfg.maxLevel,credit:new Cesium.Credit('NASA GIBS · '+cfg.label)});
    const requestImage=provider.requestImage.bind(provider);
    provider.requestImage=(x,y,level,request)=>{
      if(cfg.composite&&level>=5)rec.requestedDetail=true;
      const image=requestImage(x,y,level,request);
      if(!image)return image;
      return Promise.resolve(image).then(result=>{rec.successes++;if(!cfg.composite||level>=5)rec.detailSuccesses++;return result;});
    };
    const layer=viewer.imageryLayers.addImageryProvider(provider);
    layer._ignisEnvKey=key;layer.alpha=cfg.alpha;rec.layers.push(layer);
    if(key==='pyro'){layer.colorToAlpha=Cesium.Color.fromBytes(239,239,236);layer.colorToAlphaThreshold=.07;}
    if(cfg.smooth){layer.minificationFilter=Cesium.TextureMinificationFilter.LINEAR;layer.magnificationFilter=Cesium.TextureMagnificationFilter.LINEAR;}
    envLayerCache.set(cacheKey,rec);envPending.set(key,rec);
    // La capa anterior sigue visible hasta que llegan las imágenes nuevas.
    if(!envLayers[key])envLayers[key]=rec;
    provider.errorEvent.addEventListener(error=>{
      if(!envSelections.has(key)||(!envPending.has(key)&&envLayers[key]!==rec))return;
      if(envPending.has(key)&&envPending.get(key)!==rec)return;
      const status=Number(error?.error?.statusCode||error?.error?.status||0);
      const tile=`${error.level}/${error.x}/${error.y}`;
      if(status===404){rec.missing.add(tile);return;}
      if(status>=500){rec.failures.add(tile);if(rec.failures.size>=3)markEnvUnavailable(key);}
    });
    const check=()=>{
      if(envPending.get(key)!==rec)return;
      const useful=rec.successes&&(!cfg.composite||!rec.requestedDetail||rec.detailSuccesses);
      if(useful&&viewer.scene.globe.tilesLoaded&&!rec.failures.size){
        if(rec.missing.size&&!rec.detailSuccesses)markEnvUnavailable(key,'layer_no_coverage');
        else finishEnvLayer(key,rec);
      }
    };
    rec.removeProgress=viewer.scene.globe.tileLoadProgressEvent.addEventListener(n=>{if(n===0){clearTimeout(rec.checkTimer);rec.checkTimer=setTimeout(check,100);}});
    rec.timer=setTimeout(()=>{
      if(envPending.get(key)!==rec)return;
      const useful=rec.successes&&(!cfg.composite||!rec.requestedDetail||rec.detailSuccesses);
      if(useful&&!rec.failures.size&&(!rec.missing.size||rec.detailSuccesses))finishEnvLayer(key,rec);
      else markEnvUnavailable(key,rec.missing.size?'layer_no_coverage':'layer_unreachable');
    },18000);
    orderEnvLayers();updateEnvLayerStatus();viewer.scene.requestRender();
    if(!opts.quiet)showToast(TT('toast_layer_on',TT('layer_'+key),topDate,''),3600);
  }catch(err){
    if(envLayers[key]===rec)delete envLayers[key];envPending.delete(key);destroyEnvRecord(rec);
    envProblems.set(key,'layer_unreachable');updateEnvLayerStatus();
    console.warn('[IGNIS] No se pudo cargar la capa:',key,err);
    showToast(TT('toast_layer_fail',TT('layer_'+key),err.message),5000);
  }
}
function toggleEnvLayer(key){
  if(envSelections.has(key)){removeEnvLayer(key);showToast(TT('toast_layer_off',TT('layer_'+key)),2600);}
  else addEnvLayer(key);
}
window.addEventListener('offline',()=>{
  cancelPendingEnvLayers({includeInitial:true});
  for(const key of envSelections){
    for(const layer of envLayers[key]?.layers||[])layer.show=false;
    delete envLayers[key];envProblems.set(key,'layer_offline');
  }
  updateEnvLayerStatus();ignisUseLocalBase();setStatus('status_offline',false);
});
window.addEventListener('online',()=>{
  for(const key of envSelections)addEnvLayer(key,{quiet:true});
  if(lastStatus.key==='status_offline')setStatus('status_online');
});
function refreshEnvLayers(){
  if(playTimer)return;
  for(const key of envSelections)addEnvLayer(key,{quiet:true});
}
function scheduleEnvRefresh(){
  clearTimeout(envRefreshTimer);
  if(!envSelections.size||playTimer)return;
  envRefreshTimer=setTimeout(refreshEnvLayers,400);
}

/* v0.9.4 — textos dinámicos reactivos al idioma: al cambiar ES/EN se repintan
   cabecera, contadores y botones que pinta el JS (antes quedaban congelados en
   el idioma en que se generaron). */
function refreshDynamicLabels(){
  applyFeedLabel();refreshSensorLabel();refreshArchiveTop();updateRegionLabel();
  setStatus(lastStatus.key,lastStatus.ok);
  $('btnPlay').textContent=playTimer?TT('STOP'):TT('PLAY');
  const replay=$('btnReplayTrack');if(replay)replay.textContent=replay.classList.contains('playing')?TT('replaying'):TT('replay_lifecycle');
  renderEventList(candidateEvents);
  if(archiveStatus)applyArchiveStatus(archiveStatus);
  if(lastAnomaly)renderAnomaly(lastAnomaly.data,lastAnomaly.labelPrefix);
  if(lastContextData&&!$('contextContent').classList.contains('hidden'))renderContext(lastContextData.data,lastContextData.demo);
  if(lastEnvironmentRequest&&!$('detailCard').classList.contains('hidden')){
    const {lat,lon,date}=lastEnvironmentRequest;
    loadEnvironmentIntelligence(lat,lon,date);
  }
  renderSelectedPeriod();
  updateEnvLayerStatus();
}
if(window.IGNIS_I18N&&IGNIS_I18N.onChange){
  IGNIS_I18N.onChange(()=>{try{window.IGNIS_RERENDER&&window.IGNIS_RERENDER();}catch(e){}refreshDynamicLabels();});
}

/* --- ENTORNO en el dossier --- */
/* FIX i18n: estos textos estaban hardcoded en español y además nunca se
   enviaba `lang` al backend, así que la evidencia llegaba siempre en español
   aunque la interfaz estuviera en inglés. */
function resetEnvBlock(){
  $('envDate').textContent='—';
  ['envDrought','envFuel','envSmoke'].forEach(id=>$(id).textContent='—');
  $('envEvidence').innerHTML=`<span class="env-loading">${TT('env_pending')}</span>`;
}
let lastEnvironmentRequest=null,envRequestToken=0;
async function loadEnvironmentIntelligence(lat,lon,date){
  if(!$('envBlock'))return;
  lastEnvironmentRequest={lat,lon,date};
  const token=++envRequestToken;
  resetEnvBlock();
  $('envDate').textContent=date||'—';
  $('envEvidence').innerHTML=`<span class="env-loading">${TT('env_analyzing')}</span>`;
  try{
    const lang=window.IGNIS_I18N?window.IGNIS_I18N.lang:'es';
    const res=await fetch(`/api/environment/intelligence?lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}&event_date=${encodeURIComponent(date)}&lang=${encodeURIComponent(lang)}`);
    if(!res.ok)throw new Error(`HTTP ${res.status}`);
    const d=await res.json();
    if(token!==envRequestToken||lang!==(window.IGNIS_I18N?.lang||'es'))return;
    const noData=TT('env_no_data');
    $('envDrought').textContent=d.drought?.available?`${d.drought.category_label} · ${d.drought.percentile}%`:noData;
    $('envFuel').textContent=d.fuel?.available?`${d.fuel.fuel_label} (NDVI ${d.fuel.ndvi})`:noData;
    $('envSmoke').textContent=d.smoke?.available?`${d.smoke.smoke_label} (AOD ${d.smoke.aod})`:noData;
    const lines=[...(d.drought?.evidence||[]),...(d.fuel?.evidence?[d.fuel.evidence]:[]),...(d.smoke?.evidence||[])];
    $('envEvidence').innerHTML=lines.length?lines.map(l=>`<span>${l}</span>`).join(''):`<span class="env-loading">${TT('env_none')}</span>`;
  }catch(err){
    if(token!==envRequestToken)return;
    $('envEvidence').innerHTML=`<span class="env-loading">${TT('env_unavailable_short')} (${err.message})</span>`;
  }
}
