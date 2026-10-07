/* IGNIS v0.6 — Earth Context Engine + candidate fire-event intelligence */
/* Basemap: 'local' usa Natural Earth II incluido en el build local de Cesium (funciona SIN internet).
   Pon 'osm' para usar tiles de OpenStreetMap (requiere conexión).
   OJO: en Cesium >= 1.104 la opción del Viewer es `baseLayer`; `imageryProvider` fue eliminada
   y se ignora en silencio (el globo quedaba únicamente con globe.baseColor). */
const IGNIS_BASEMAP='local';
const ignisBaseLayer=IGNIS_BASEMAP==='osm'
  ? Cesium.ImageryLayer.fromProviderAsync(Promise.resolve(new Cesium.OpenStreetMapImageryProvider({url:'https://tile.openstreetmap.org/',credit:'© OpenStreetMap contributors'})))
  : Cesium.ImageryLayer.fromProviderAsync(Cesium.TileMapServiceImageryProvider.fromUrl(Cesium.buildModuleUrl('Assets/Textures/NaturalEarthII')));
const viewer = new Cesium.Viewer('cesiumContainer', {
  animation:false,timeline:false,fullscreenButton:false,homeButton:false,geocoder:false,
  navigationHelpButton:false,sceneModePicker:false,baseLayerPicker:false,infoBox:false,selectionIndicator:false,
  terrainProvider:new Cesium.EllipsoidTerrainProvider(),
  baseLayer:ignisBaseLayer
});
viewer.scene.globe.baseColor=Cesium.Color.fromCssColorString('#07100d');
viewer.scene.globe.enableLighting=true;viewer.scene.backgroundColor=Cesium.Color.fromCssColorString('#020403');
viewer.scene.skyBox.show=false;viewer.scene.sun.show=false;viewer.scene.moon.show=false;viewer.scene.fog.enabled=true;viewer.scene.fog.density=.00015;
viewer.scene.screenSpaceCameraController.minimumZoomDistance=800000;viewer.scene.screenSpaceCameraController.maximumZoomDistance=65000000;

/* --- v0.7 God's Eye: calidad cinematográfica, todo con recursos locales --- */
const IGNIS_CINEMATIC=true;
const IGNIS_TERMINATOR=true;   // iluminación solar real (día/noche)
(function cinematicGrade(){
  if(!IGNIS_CINEMATIC)return;
  try{
    const s=viewer.scene;
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

/* Entrada de cámara cinematográfica al cargar */
function cinematicIntro(){
  viewer.camera.setView({destination:Cesium.Cartesian3.fromDegrees(-140,52,30000000)});
  viewer.camera.flyTo({destination:Cesium.Cartesian3.fromDegrees(-102.5,23.5,5600000),duration:6.5,easingFunction:Cesium.EasingFunction.QUADRATIC_IN_OUT});
}

viewer.camera.setView({destination:Cesium.Cartesian3.fromDegrees(-20,15,22000000)});

const REGIONS={
  mexico:{label:'Mexico',area:'-118,14,-86,33',camera:[-102.5,23.5,5600000]},
  amazon:{label:'Amazon Basin',area:'-80,-20,-44,8',camera:[-61.5,-7,5200000]},
  california:{label:'California',area:'-125,32,-114,42',camera:[-119.5,37,3600000]},
  med:{label:'Mediterranean',area:'-10,30,40,46',camera:[20,37,5000000]},
  australia:{label:'Australia',area:'112,-44,154,-10',camera:[134,-25,6200000]},
};
const MONTHS=['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'];
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
const severityColor={moderate:Cesium.Color.fromCssColorString('#ffdc6a'),high:Cesium.Color.fromCssColorString('#ff9e42'),critical:Cesium.Color.fromCssColorString('#ff4e36')};
const heatStops=[[25,Cesium.Color.fromCssColorString('#a6ff77')],[50,Cesium.Color.fromCssColorString('#ffdc6a')],[75,Cesium.Color.fromCssColorString('#ff9e42')],[101,Cesium.Color.fromCssColorString('#ff3f35')]];
function heatColor(score){return (heatStops.find(([cut])=>score<cut)||heatStops[heatStops.length-1])[1];}
function showToast(message,ms=3600){const el=$('toast');el.textContent=message;el.classList.remove('hidden');clearTimeout(showToast.t);showToast.t=setTimeout(()=>el.classList.add('hidden'),ms);}
function clockTick(){const d=new Date();$('clock').textContent=d.toISOString().slice(11,19)+' UTC';}setInterval(clockTick,1000);clockTick();
function filterEnabled(severity){return $(severity)?.checked??true;}
function setStatus(text,ok=true){$('systemStatus').textContent=text;$('systemStatus').classList.toggle('ok',ok);}
function fmtBytes(n){if(!n)return '0 B';const u=['B','KB','MB','GB'];let i=0,v=Number(n);while(v>=1024&&i<u.length-1){v/=1024;i++;}return `${v.toFixed(i?1:0)} ${u[i]}`;}
function selectedSources(){const out=[];if($('srcModis').checked)out.push('MODIS_SP');if($('srcSnpp').checked)out.push('VIIRS_SNPP_SP');if($('srcN20').checked)out.push('VIIRS_NOAA20_SP');return out;}
function viewportArea(){const rect=viewer.camera.computeViewRectangle(viewer.scene.globe.ellipsoid);if(!rect)return REGIONS.mexico.area;const west=Cesium.Math.toDegrees(rect.west),east=Cesium.Math.toDegrees(rect.east),south=Math.max(-89,Cesium.Math.toDegrees(rect.south)),north=Math.min(89,Cesium.Math.toDegrees(rect.north));const span=((east-west)+360)%360;if(span>175||north-south>100||east<west){showToast('Zoom closer before querying. The viewport is too large or crosses the date line.',4800);return null;}return [west,south,east,north].map(v=>v.toFixed(3)).join(',');}
function selectedArea(){const key=$('regionPreset').value;return key==='viewport'?viewportArea():REGIONS[key]?.area||REGIONS.mexico.area;}
function selectedRegion(){const key=$('regionPreset').value;return REGIONS[key]?key:null;}
function updateRegionLabel(){const key=$('regionPreset').value;$('regionName').textContent=key==='viewport'?'VIEWPORT':(REGIONS[key]?.label||key).toUpperCase();}
function flyRegion(key){const region=REGIONS[key];if(!region)return;const [lon,lat,h]=region.camera;viewer.camera.flyTo({destination:Cesium.Cartesian3.fromDegrees(lon,lat,h),duration:1.6});}
function daysInMonth(year,month){return new Date(Date.UTC(year,month,0)).getUTCDate();}

function renderHotspots(fires){fireCollection.removeAll();const filtered=fires.filter(f=>filterEnabled(f.severity));filtered.forEach((fire,idx)=>{const c=severityColor[fire.severity]||severityColor.moderate;const size=fire.severity==='critical'?9:fire.severity==='high'?7:5;fireCollection.add({position:Cesium.Cartesian3.fromDegrees(fire.lon,fire.lat,9000),color:c.withAlpha(.96),outlineColor:c.withAlpha(.25),outlineWidth:5,pixelSize:size,scaleByDistance:new Cesium.NearFarScalar(1.5e6,1.9,3.5e7,.65),translucencyByDistance:new Cesium.NearFarScalar(2e6,1,5e7,.5),id:{type:'ignis-fire',idx,fire}});});return filtered.length;}
function renderHeat(cells){heatCollection.removeAll();cells.forEach((cell,idx)=>{const c=heatColor(cell.activity_score);const size=8+Math.sqrt(Math.max(1,cell.detections))*3.2;heatCollection.add({position:Cesium.Cartesian3.fromDegrees(cell.lon,cell.lat,12000),color:c.withAlpha(.38+.004*Math.min(cell.activity_score,80)),outlineColor:c.withAlpha(.9),outlineWidth:1,pixelSize:Math.min(30,size),scaleByDistance:new Cesium.NearFarScalar(1.5e6,2.0,3.5e7,.8),id:{type:'ignis-cell',idx,cell}});});return cells.length;}
function eventActiveOnDate(event,date){if(!date)return true;const start=(event.start||'').slice(0,10),end=(event.end||'').slice(0,10);return (!start||date>=start)&&(!end||date<=end);}
function renderEvents(events,date){eventCollection.removeAll();eventDataSource.entities.removeAll();const active=(events||[]).filter(e=>eventActiveOnDate(e,date)&&filterEnabled(e.severity));active.forEach((event,idx)=>{const c=severityColor[event.severity]||severityColor.high;const size=Math.min(30,12+Math.sqrt(Math.max(1,event.detections||1))*3.4);eventCollection.add({position:Cesium.Cartesian3.fromDegrees(event.lon,event.lat,18000),color:c.withAlpha(.30),outlineColor:c.withAlpha(.98),outlineWidth:3,pixelSize:size,scaleByDistance:new Cesium.NearFarScalar(1.2e6,2.1,3.5e7,.72),id:{type:'ignis-event',idx,event}});const ring=eventDataSource.entities.add({position:Cesium.Cartesian3.fromDegrees(event.lon,event.lat),ellipse:{semiMajorAxis:Math.max(3000,(event.radius_km||3)*1000),semiMinorAxis:Math.max(3000,(event.radius_km||3)*1000),material:c.withAlpha(.055),outline:true,outlineColor:c.withAlpha(.42),height:0}});ring._ignisEvent=event;});return active.length;}
function renderEventList(events){const list=$('eventList');if(!list)return;list.innerHTML='';$('eventTop').textContent=Number(events?.length||0).toLocaleString();if(!(events||[]).length){list.innerHTML='<div class="source-empty">No multi-detection candidate events in this period.</div>';return;}for(const event of events.slice(0,8)){const b=document.createElement('button');b.className='event-row';b.innerHTML=`<div><strong>${event.id}</strong><span>${event.detections} detections · ${event.duration_hours} h · ${event.radius_km} km radius</span></div><em>${Math.round(event.event_score||0)}</em>`;b.addEventListener('click',()=>{viewer.camera.flyTo({destination:Cesium.Cartesian3.fromDegrees(event.lon,event.lat,Math.max(450000,Math.min(1800000,(event.radius_km||30)*26000))),duration:1.25});openEvent(event);});list.appendChild(b);}}
function countFamilies(fires){let modis=0,viirs=0;for(const f of fires){if((f.family||'').toUpperCase()==='MODIS')modis++;else if((f.family||'').toUpperCase()==='VIIRS')viirs++;}return{modis,viirs};}
function renderFrame(){
  if(!frames.length){fireCollection.removeAll();heatCollection.removeAll();eventCollection.removeAll();$('fireCount').textContent='0';$('activityIndex').textContent='—';$('timelineDate').textContent='—';return;}
  frameIndex=Math.max(0,Math.min(frameIndex,frames.length-1));const frame=frames[frameIndex];const fires=frame.fires||[],cells=frame.cells||[],summary=frame.summary||{};
  fireCollection.show=viewMode==='hotspots';heatCollection.show=viewMode==='heat';eventCollection.show=viewMode==='events'||viewMode==='evolution';eventDataSource.show=viewMode==='events';trailDataSource.show=viewMode==='evolution';
  let visible=0;
  if(viewMode==='hotspots')visible=renderHotspots(fires);
  else if(viewMode==='heat')visible=renderHeat(cells);
  else if(viewMode==='evolution')visible=renderEvolutionFrame(frame.date);
  else visible=renderEvents(candidateEvents,frame.date);
  if(Object.keys(envLayers).length)setTimeout(refreshEnvLayers,60);
  $('fireCount').textContent=visible.toLocaleString();$('countLabel').textContent=viewMode==='hotspots'?'VISIBLE DETECTIONS':viewMode==='heat'?'VISIBLE FUSION CELLS':viewMode==='evolution'?'TRACKED FIRE EVENTS':'ACTIVE CANDIDATE EVENTS';const fam=countFamilies(fires);$('modisCount').textContent=fam.modis.toLocaleString();$('viirsCount').textContent=fam.viirs.toLocaleString();$('agreementCount').textContent=(summary.agreement_cells||0).toLocaleString();$('activityIndex').textContent=Number(summary.activity_mean||0).toFixed(1);$('activityMeter').style.width=`${Math.min(100,summary.activity_mean||0)}%`;$('timelineDate').textContent=frame.date||'—';$('frameSlider').max=Math.max(0,frames.length-1);$('frameSlider').value=frameIndex;
}
function applyHarmonized(payload){
  lastPayload=payload;frames=payload.frames||[];candidateEvents=payload.events||[];frameIndex=Math.max(0,frames.length-1);lastMode=payload.mode||'harmonized';
  evolution=payload.evolution||null;evolutionTracks=evolution?.tracks||[];selectedTrack=null;
  renderEvolutionPanel();clearReticle();
  if(lastMode.includes('local-archive'))$('feedMode').textContent='LOCAL ARCHIVE';else if(lastMode.includes('demo'))$('feedMode').textContent='DEMO FUSION';else if(lastMode.includes('historical'))$('feedMode').textContent='NASA HISTORY';else $('feedMode').textContent='NASA FUSION';
  const src=(payload.available_sources||payload.sources||[]);$('sensorName').textContent=src.length?`${src.length} SOURCES`:'NO SIGNAL';renderEventList(candidateEvents);setStatus('ONLINE');renderFrame();
  if(payload.warnings?.length)showToast(`Partial sensor coverage: ${payload.warnings[0]}`,6500);else if(payload.warning)showToast(payload.warning,5200);
}

function applyArchiveStatus(status){
  archiveStatus=status||{};const n=Number(status?.observations||0);$('archiveTop').textContent=n?'READY':'EMPTY';$('archiveTop').classList.toggle('ok',!!n);$('archiveCount').textContent=n.toLocaleString();$('archiveCoverage').textContent=n?`${status.min_date} → ${status.max_date}`:'No historical files imported';
  $('archiveManagerCount').textContent=n.toLocaleString();$('archiveManagerImports').textContent=Number(status?.imports||0).toLocaleString();$('archiveManagerCoverage').textContent=n?`${status.min_date} → ${status.max_date}`:'—';
  const list=$('archiveSourceList');if(!list)return;list.innerHTML='';if(!(status?.sources||[]).length){list.innerHTML='<div class="source-empty">No files imported yet.</div>';return;}
  for(const src of status.sources){const row=document.createElement('div');row.className='source-row';row.innerHTML=`<div><strong>${src.label||src.id}</strong><span>${src.min_date} → ${src.max_date}</span></div><em>${Number(src.observations).toLocaleString()}</em>`;list.appendChild(row);}
}
async function loadArchiveStatus(){try{const res=await fetch('/api/archive/status');if(!res.ok)throw new Error(`HTTP ${res.status}`);applyArchiveStatus(await res.json());}catch(err){showToast(`Archive status warning: ${err.message}`,4800);}}
async function loadConfig(){try{const res=await fetch('/api/config');if(!res.ok)throw new Error(`HTTP ${res.status}`);config=await res.json();applyArchiveStatus(config.archive||{});if(!config.firms_key_configured){$('btnHarmonize').title='Configure FIRMS_MAP_KEY in .env to enable NASA data.';}}catch(err){showToast(`Configuration warning: ${err.message}`,5000);}}

async function loadAnalyticalDemo(){setStatus('LOADING');try{const res=await fetch('/api/harmonize/demo');if(!res.ok)throw new Error(`HTTP ${res.status}`);applyHarmonized(await res.json());lastArea=null;showToast('Analytical demo loaded. It is simulated and demonstrates the harmonization workflow.',5200);}catch(err){setStatus('ERROR',false);showToast(`Demo load failed: ${err.message}`,6000);}}
async function loadDemoPeriod(startDate,region){setStatus('LOADING');try{const url=`/api/harmonize/demo/date?region=${encodeURIComponent(region)}&start_date=${encodeURIComponent(startDate)}&days=${$('historyDays').value}`;const res=await fetch(url);if(!res.ok){const e=await res.json().catch(()=>({}));throw new Error(e.detail||`HTTP ${res.status}`);}applyHarmonized(await res.json());lastArea=REGIONS[region].area;showToast(`Demo period loaded: ${REGIONS[region].label} · ${startDate}. Synthetic data.`,5200);}catch(err){setStatus('ERROR',false);showToast(err.message,6500);}}
async function loadHarmonized(){const area=selectedArea();if(!area)return;const sources=selectedSources();if(!sources.length){showToast('Select at least one sensor source.');return;}setStatus('SYNCING');lastArea=area;try{const dateValue=$('historyDate').value;const today=new Date().toISOString().slice(0,10);const startDate=dateValue&&dateValue!==today?`&start_date=${encodeURIComponent(dateValue)}`:'';const url=`/api/harmonize?area=${encodeURIComponent(area)}${startDate}&days=${$('historyDays').value}&sources=${encodeURIComponent(sources.join(','))}&grid_deg=${$('gridSize').value}`;const res=await fetch(url);if(!res.ok){const e=await res.json().catch(()=>({}));throw new Error(e.detail||`HTTP ${res.status}`);}applyHarmonized(await res.json());showToast('NASA observations harmonized on a common grid.');}catch(err){setStatus('ERROR',false);showToast(err.message,6500);}}
function archiveSelectedSources(){const available=new Set((archiveStatus?.sources||[]).map(x=>x.id));let chosen=selectedSources().filter(x=>available.has(x));if(!chosen.length)chosen=[...(archiveStatus?.sources||[])].map(x=>x.id);return chosen;}
async function loadArchivePeriod(startDate,days){const area=selectedArea();if(!area)return;if(!archiveStatus?.ready){showToast('Import FIRMS archive data first. Open Local Archive Manager.',5200);return;}const sources=archiveSelectedSources();setStatus('LOCAL DB');lastArea=area;try{const url=`/api/archive/harmonize?area=${encodeURIComponent(area)}&start_date=${encodeURIComponent(startDate)}&days=${days}&sources=${encodeURIComponent(sources.join(','))}&grid_deg=${$('gridSize').value}&max_points_per_frame=1600`;const res=await fetch(url);if(!res.ok){const e=await res.json().catch(()=>({}));throw new Error(e.detail||`HTTP ${res.status}`);}const data=await res.json();applyHarmonized(data);showToast(`Loaded ${days} day(s) from the local DuckDB archive. No NASA API request used.`,5200);}catch(err){setStatus('ERROR',false);showToast(err.message,6500);}}

function renderAnomaly(data,labelPrefix='MODIS baseline'){const sign=data.percent_change>0?'+':'';$('anomalyValue').textContent=`${sign}${Number(data.percent_change).toFixed(0)}%`;$('anomalyLabel').textContent=(data.anomaly_label||'typical').toUpperCase();$('anomalyNote').textContent=`${labelPrefix} ${data.historical_mean} detections · z=${data.z_score}`;const color=data.z_score>=2?'#ff4e36':data.z_score>=1?'#ff9e42':data.z_score<=-1?'#46ffd2':'#a6ff77';$('anomalyValue').style.color=color;}
async function loadBaseline(){const area=lastArea||selectedArea();if(!area)return;const target=frames[frameIndex]?.date||$('historyDate').value;if(!target){showToast('Load a timeline frame first.');return;}setStatus('ANALYZING');try{let url,label;if(lastMode.includes('local-archive')){const d=new Date(`${target}T00:00:00Z`);url=`/api/archive/anomaly?area=${encodeURIComponent(area)}&target_year=${d.getUTCFullYear()}&target_month=${d.getUTCMonth()+1}&years=10&source=MODIS_SP`;label='LOCAL FULL-MONTH';}else{if(!config?.firms_key_configured){showToast('NASA FIRMS MAP_KEY is required for a live baseline, or use Local Archive mode.',5600);setStatus('ONLINE');return;}url=`/api/analytics/baseline?area=${encodeURIComponent(area)}&target_date=${target}&years=5&days=1`;label='MODIS API';}const res=await fetch(url);if(!res.ok){const e=await res.json().catch(()=>({}));throw new Error(e.detail||`HTTP ${res.status}`);}renderAnomaly(await res.json(),label);setStatus('ONLINE');}catch(err){setStatus('ERROR',false);showToast(err.message,6500);}}

function hideEvolutionBlocks(){['evoDetail','evoIntel'].forEach(id=>$(id)?.classList.add('hidden'));selectedTrack=null;clearReticle();renderTrackingBanner();renderEvolutionPanel();}
function openFire(fire){hideEvolutionBlocks();
  loadEnvironmentIntelligence(fire.lat,fire.lon,(fire.date||'').slice(0,10));$('detailEmpty').classList.add('hidden');$('detailCard').classList.remove('hidden');$('detailKicker').textContent='HOTSPOT INTELLIGENCE';$('detailSeverity').textContent=(fire.severity||'signal').toUpperCase();$('detailSeverity').style.color=fire.severity==='critical'?'#ff4e36':fire.severity==='high'?'#ff9e42':'#ffdc6a';$('detailCoords').textContent=`${Number(fire.lat).toFixed(4)}, ${Number(fire.lon).toFixed(4)}`;$('detailFrp').textContent=`${fire.frp??0} MW`;$('detailConfidence').textContent=`${fire.confidence??0}%`;$('detailTime').textContent=`${fire.date||'—'} ${fire.time||''} UTC`;$('detailSatellite').textContent=`${fire.source||fire.satellite||'—'}`;}
function openCell(cell){hideEvolutionBlocks();$('detailEmpty').classList.add('hidden');$('detailCard').classList.remove('hidden');$('detailKicker').textContent='HARMONIZED GRID CELL';$('detailSeverity').textContent=(cell.activity_level||'signal').toUpperCase();$('detailSeverity').style.color=heatColor(cell.activity_score).toCssColorString();$('detailCoords').textContent=`${Number(cell.lat).toFixed(4)}, ${Number(cell.lon).toFixed(4)}`;$('detailFrp').textContent=`ACT ${cell.activity_score} · ${cell.mean_frp} MW`;$('detailConfidence').textContent=`${cell.mean_confidence}% · agree ${Math.round((cell.sensor_agreement||0)*100)}%`;$('detailTime').textContent=frames[frameIndex]?.date||'—';$('detailSatellite').textContent=(cell.families||[]).join(' + ')||'—';}
function resetContext(message='SELECT A FIRE EVENT'){$('contextPlaceholder').classList.remove('hidden');$('contextPlaceholder').innerHTML=`${message}<br><small>Weather, dryness and recent air-quality context will appear here.</small>`;$('contextContent').classList.add('hidden');}
function fmtValue(value,suffix=''){return value==null||Number.isNaN(Number(value))?'—':`${Number(value).toFixed(1)}${suffix}`;}
function renderContext(data,demo=false){const w=data.weather||{},a=data.air_quality||{},dry=w.dryness_context||{};$('contextPlaceholder').classList.add('hidden');$('contextContent').classList.remove('hidden');$('drynessScore').textContent=fmtValue(dry.score,' / 100');$('drynessLabel').textContent=(dry.label||'unknown').toUpperCase();$('ctxTemp').textContent=fmtValue(w.temperature_max_c,'°C');$('ctxHumidity').textContent=fmtValue(w.relative_humidity_min_pct,'%');$('ctxWind').textContent=fmtValue(w.wind_speed_max_kmh,' km/h');$('ctxRain').textContent=fmtValue(w.precipitation_sum_mm,' mm');$('ctxSoil').textContent=fmtValue(w.soil_moisture_mean,' m³/m³');$('ctxPm25').textContent=a.available===false?'N/A':fmtValue(a.pm2_5_mean_ugm3,' µg/m³');$('ctxAod').textContent=a.available===false?'N/A':fmtValue(a.aerosol_optical_depth_mean,'');$('ctxWindDir').textContent=fmtValue(w.wind_direction_mean_deg,'°');$('contextSource').textContent=demo?'SIMULATED CONTEXT · demonstration only':`${w.provider||'weather unavailable'} · ${a.provider||'air quality unavailable'}`;}
function demoContext(event){const seed=Math.abs(Math.sin((event.lat||0)*1.73+(event.lon||0)*.61+(event.event_score||0)));const temp=22+16*seed,humidity=58-35*seed,wind=10+32*(1-seed/2),rain=Math.max(0,6-8*seed),soil=.12+.23*(1-seed),score=Math.min(96,35+58*seed);return{weather:{provider:'IGNIS synthetic demo',temperature_max_c:temp,relative_humidity_min_pct:humidity,wind_speed_max_kmh:wind,wind_direction_mean_deg:(event.event_score*3.6)%360,precipitation_sum_mm:rain,soil_moisture_mean:soil,dryness_context:{score,label:score>75?'very dry':score>55?'dry':'mixed'}},air_quality:{available:true,provider:'IGNIS synthetic demo',pm2_5_mean_ugm3:12+48*seed,aerosol_optical_depth_mean:.08+.42*seed}};}
async function loadEventContext(event){if(lastMode.includes('demo')){renderContext(demoContext(event),true);return;}resetContext('LOADING ENVIRONMENTAL CONTEXT…');try{const date=(event.start||frames[frameIndex]?.date||'').slice(0,10);const url=`/api/context/environment?lat=${encodeURIComponent(event.lat)}&lon=${encodeURIComponent(event.lon)}&event_date=${encodeURIComponent(date)}`;const res=await fetch(url);if(!res.ok){const e=await res.json().catch(()=>({}));throw new Error(e.detail||`HTTP ${res.status}`);}renderContext(await res.json());}catch(err){resetContext('CONTEXT UNAVAILABLE');showToast(`Environmental context: ${err.message}`,6200);}}
function openEvent(event){hideEvolutionBlocks();$('detailEmpty').classList.add('hidden');$('detailCard').classList.remove('hidden');$('detailKicker').textContent=`CANDIDATE FIRE EVENT · ${event.id}`;$('detailSeverity').textContent=(event.severity||'signal').toUpperCase();$('detailSeverity').style.color=event.severity==='critical'?'#ff4e36':event.severity==='high'?'#ff9e42':'#ffdc6a';$('detailCoords').textContent=`${Number(event.lat).toFixed(4)}, ${Number(event.lon).toFixed(4)}`;$('detailFrp').textContent=`Σ ${event.total_frp||0} MW · score ${event.event_score||0}`;$('detailConfidence').textContent=`${event.mean_confidence||0}% · ${event.detections||0} detections`;$('detailTime').textContent=`${(event.start||'—').slice(0,16)} → ${(event.end||'—').slice(0,16)}`;$('detailSatellite').textContent=(event.families||[]).join(' + ')||'—';loadEventContext(event);}
function exportSnapshot(){if(!lastPayload){showToast('Load an analytical dataset first.');return;}const frame=frames[frameIndex]||null;
  const evolutionOut=evolution?{engine:'fire-evolution',session:evolution.session,status_counts:evolution.status_counts,tracks_total:evolution.tracks_total,tracks_multi_frame:evolution.tracks_multi_frame,selected_track:selectedTrack?{id:selectedTrack.id,status:selectedTrack.status,confidence:selectedTrack.confidence,trajectory:selectedTrack.trajectory,timeline:selectedTrack.timeline}:null,method:evolution.method,caveat:evolution.caveat}:null;
  const out={ignis_version:'0.7.0',generated_at:new Date().toISOString(),mode:lastMode,region:$('regionName').textContent,frame,events:candidateEvents,evolution:evolutionOut,method:lastPayload.method||null,caveat:'Satellite thermal anomalies, candidate clusters and persistent tracks are analytical signals, not confirmed wildfire incidents or official perimeters.'};const blob=new Blob([JSON.stringify(out,null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=`IGNIS_snapshot_${(frame?.date||'current')}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1200);showToast('Intelligence snapshot exported as JSON.');}
function setViewMode(mode){viewMode=mode;document.querySelectorAll('#viewMode .seg').forEach(b=>b.classList.toggle('active',b.dataset.mode===mode));renderFrame();renderTrackingBanner();if(mode==='evolution'&&!evolutionTracks.length)showToast('No evolution tracks loaded yet. Press LOAD FIRE EVOLUTION (v0.7).',5200);}
function stepFrame(delta){if(!frames.length)return;frameIndex=(frameIndex+delta+frames.length)%frames.length;renderFrame();}
function togglePlay(){if(playTimer){clearInterval(playTimer);playTimer=null;$('btnPlay').textContent='PLAY';return;}if(frames.length<2){showToast('Load a multi-day timeline first.');return;}$('btnPlay').textContent='STOP';playTimer=setInterval(()=>stepFrame(1),900);}

function openCalendar(){$('calendarPanel').classList.remove('hidden');loadCalendar();}
function closeCalendar(){$('calendarPanel').classList.add('hidden');}
function setCalendarMode(mode){
  calendarMode=mode;document.querySelectorAll('#calendarMode .seg').forEach(b=>b.classList.toggle('active',b.dataset.calendarMode===mode));const now=new Date().getFullYear();
  if(mode==='demo'){$('calendarStartYear').value=2003;$('calendarEndYear').value=now;$('calendarNote').textContent='Synthetic full-history demo for interface exploration. Not NASA observations.';}
  else if(mode==='archive'){const min=archiveStatus?.min_date?Number(archiveStatus.min_date.slice(0,4)):2003;const max=archiveStatus?.max_date?Number(archiveStatus.max_date.slice(0,4)):now;$('calendarStartYear').value=Math.max(2000,min);$('calendarEndYear').value=Math.min(now,max);$('calendarNote').textContent='LOCAL ARCHIVE: complete imported monthly observations. Works without NASA API calls.';}
  else{$('calendarStartYear').value=Math.max(2003,now-3);$('calendarEndYear').value=now;$('calendarNote').textContent='NASA sampled mode: equal-length MODIS windows for seasonal comparison; not complete monthly totals.';}
}
function calendarRegionForDemo(){const key=selectedRegion();return key||'mexico';}
function calendarCellDate(year,month,item){if(item?.date)return item.date;const day=calendarMode==='archive'?1:10;return `${year}-${String(month).padStart(2,'0')}-${String(day).padStart(2,'0')}`;}
function renderCalendar(payload){calendarPayload=payload;const grid=$('calendarGrid');grid.innerHTML='';const corner=document.createElement('div');corner.className='cal-header year';corner.textContent='YEAR';grid.appendChild(corner);MONTHS.forEach(m=>{const h=document.createElement('div');h.className='cal-header';h.textContent=m;grid.appendChild(h);});for(const row of payload.rows||[]){const y=document.createElement('div');y.className='cal-year';y.textContent=row.year;grid.appendChild(y);for(const item of row.months||[]){const b=document.createElement('button');b.className=`cal-cell level-${item.level||'future'}`;b.disabled=!item.available;b.dataset.year=row.year;b.dataset.month=item.month;const score=item.score==null?'—':Math.round(item.score);b.innerHTML=`<strong>${score}</strong><span>${item.detections!=null?Number(item.detections).toLocaleString():' '}</span>`;const dateLabel=`${MONTHS[item.month-1]} ${row.year}`;b.title=item.available?`${dateLabel} · score ${score}${item.detections!=null?` · ${Number(item.detections).toLocaleString()} detections`:''}`:`${dateLabel} unavailable`;if(item.available)b.addEventListener('click',()=>selectCalendarCell(row.year,item));grid.appendChild(b);}}$('calendarSubtitle').textContent=`${payload.region_label||REGIONS[selectedRegion()]?.label||'Selected area'} · ${payload.start_year}–${payload.end_year}`;if(payload.sampling_note)$('calendarNote').textContent=payload.sampling_note;if(payload.warning)$('calendarNote').textContent=payload.warning;}
async function loadCalendar(){
  const start=Number($('calendarStartYear').value),end=Number($('calendarEndYear').value);if(start>end){showToast('Calendar FROM year must be before TO year.');return;}setStatus('CALENDAR');
  try{let url;if(calendarMode==='demo'){const region=calendarRegionForDemo();if(!selectedRegion())showToast('Full demo needs a preset region; using Mexico.',3800);url=`/api/analytics/calendar/demo?region=${encodeURIComponent(region)}&start_year=${start}&end_year=${end}`;}
    else if(calendarMode==='archive'){if(!archiveStatus?.ready){showToast('Your local archive is empty. Import FIRMS files first.',5200);openArchive();setStatus('ONLINE');return;}const area=selectedArea();if(!area)return;const available=new Set((archiveStatus.sources||[]).map(x=>x.id));const baselineSource=available.has('MODIS_SP')?'MODIS_SP':(archiveStatus.sources?.[0]?.id||'');url=`/api/archive/calendar?area=${encodeURIComponent(area)}&start_year=${start}&end_year=${end}&sources=${encodeURIComponent(baselineSource)}`;}
    else{if(!config?.firms_key_configured){showToast('NASA sampled calendar requires FIRMS_MAP_KEY in .env.',5200);setStatus('ONLINE');return;}const area=selectedArea();if(!area)return;url=`/api/analytics/calendar/sample?area=${encodeURIComponent(area)}&start_year=${start}&end_year=${end}&sample_days=3&anchor_day=10`;}
    $('calendarGrid').innerHTML='<div class="calendar-loading">BUILDING TEMPORAL MATRIX…</div>';const res=await fetch(url);if(!res.ok){const e=await res.json().catch(()=>({}));throw new Error(e.detail||`HTTP ${res.status}`);}renderCalendar(await res.json());setStatus('ONLINE');
  }catch(err){setStatus('ERROR',false);$('calendarGrid').innerHTML='<div class="calendar-loading error">CALENDAR FAILED</div>';showToast(err.message,6500);}
}
async function selectCalendarCell(year,item){const month=item.month;const startDate=calendarCellDate(year,month,item);$('historyDate').value=startDate;$('selectedPeriod').textContent=`${MONTHS[month-1]} ${year}`;const qualifier=calendarMode==='archive'?'complete local detections':calendarMode==='nasa'?'sampled detections':'demo detections';$('selectedPeriodScore').textContent=`ACTIVITY ${Math.round(item.score||0)} / 100${item.detections!=null?` · ${Number(item.detections).toLocaleString()} ${qualifier}`:''}`;const region=selectedRegion()||calendarRegionForDemo();if(REGIONS[region])flyRegion(region);closeCalendar();if(calendarMode==='demo')await loadDemoPeriod(startDate,region);else if(calendarMode==='archive')await loadArchivePeriod(startDate,daysInMonth(year,month));else await loadHarmonized();}

function openArchive(){$('archivePanel').classList.remove('hidden');loadArchiveStatus();}
function closeArchive(){$('archivePanel').classList.add('hidden');}
async function importArchive(){const input=$('archiveFile'),file=input.files?.[0];if(!file){showToast('Select a FIRMS CSV, TXT or ZIP file first.');return;}const fd=new FormData();fd.append('file',file);fd.append('source',$('archiveSource').value);$('archiveProgress').classList.remove('hidden');$('btnImportArchive').disabled=true;setStatus('IMPORTING');try{const res=await fetch('/api/archive/import',{method:'POST',body:fd});if(!res.ok){const e=await res.json().catch(()=>({}));throw new Error(e.detail||`HTTP ${res.status}`);}const data=await res.json();applyArchiveStatus(data.archive);const inserted=(data.results||[]).reduce((a,x)=>a+Number(x.rows_inserted||0),0);showToast(`Archive import complete: ${inserted.toLocaleString()} new observations.`,6500);input.value='';setStatus('ONLINE');}catch(err){setStatus('ERROR',false);showToast(err.message,7000);}finally{$('archiveProgress').classList.add('hidden');$('btnImportArchive').disabled=false;}}

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
  if(e.target.tagName==='INPUT'||e.target.tagName==='SELECT')return;
  if(e.key===' '){e.preventDefault();togglePlay();}
  if(e.key==='e'||e.key==='E')setViewMode('evolution');
  if(e.key==='h'||e.key==='H')setViewMode('hotspots');
  if(e.key==='r'||e.key==='R')replayTrack();
});
['moderate','high','critical'].forEach(id=>$(id).addEventListener('change',renderFrame));
document.querySelectorAll('#viewMode .seg').forEach(btn=>btn.addEventListener('click',()=>setViewMode(btn.dataset.mode)));
document.querySelectorAll('#calendarMode .seg').forEach(btn=>btn.addEventListener('click',()=>{setCalendarMode(btn.dataset.calendarMode);loadCalendar();}));
$('btnHarmonizedDemo').addEventListener('click',loadAnalyticalDemo);$('btnHarmonize').addEventListener('click',loadHarmonized);$('btnBaseline').addEventListener('click',loadBaseline);$('frameSlider').addEventListener('input',e=>{frameIndex=Number(e.target.value);renderFrame();});$('btnPrev').addEventListener('click',()=>stepFrame(-1));$('btnNext').addEventListener('click',()=>stepFrame(1));$('btnPlay').addEventListener('click',togglePlay);
$('regionPreset').addEventListener('change',()=>{updateRegionLabel();const key=selectedRegion();if(key)flyRegion(key);});$('btnFlyRegion').addEventListener('click',()=>{const key=selectedRegion();if(key)flyRegion(key);else showToast('Current viewport is already your active area.');});
$('btnCalendar').addEventListener('click',openCalendar);$('btnCloseCalendar').addEventListener('click',closeCalendar);$('btnLoadCalendar').addEventListener('click',loadCalendar);
$('btnArchive').addEventListener('click',openArchive);$('btnCloseArchive').addEventListener('click',closeArchive);$('btnImportArchive').addEventListener('click',importArchive);$('btnExport').addEventListener('click',exportSnapshot);
/* --- v0.7 --- */
$('btnEvolutionDemo').addEventListener('click',loadEvolutionDemo);
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
  await loadEvolutionDemo();                          // v0.7: arranca en modo evolución con pistas persistentes
})();

/* ==========================================================================
   IGNIS v0.7 — Fire Evolution Engine · UI
   Persistent tracks, lifecycle states, trail rendering, HUD cinematográfico.
   ========================================================================== */
const STATE_CLASS={EMERGING:'emerging',EXPANDING:'expanding',STABLE:'stable',DECLINING:'declining',EXTINCT:'extinct'};
const STATE_COLOR={EMERGING:'#ffdc6a',EXPANDING:'#ff9e42',STABLE:'#a6ff77',DECLINING:'#46ffd2',EXTINCT:'#789184'};
const trackColor=track=>Cesium.Color.fromCssColorString(STATE_COLOR[track.status]||'#a6ff77');

function frameIndexOf(date){return frames.findIndex(f=>(f.date||'')===(date||''));}

/* --- panel --- */
function renderEvolutionPanel(){
  const list=$('evoList'),summary=$('evoSummary');if(!list||!summary)return;
  if(!evolutionTracks.length){
    summary.innerHTML='<span class="chip">NO TRACKS</span><small>Load the evolution demo or a multi-day dataset.</small>';
    list.innerHTML='<div class="source-empty">Persistent event identities will appear here.</div>';
    return;
  }
  const counts=evolution?.status_counts||{};
  summary.innerHTML=['EXPANDING','DECLINING','STABLE','EMERGING','EXTINCT']
    .filter(s=>counts[s]).map(s=>`<span class="chip ${STATE_CLASS[s]}">${s} ${counts[s]}</span>`).join('')
    +`<small>${evolutionTracks.length} persistent track(s) · ${evolution?.tracks_multi_frame||0} multi-frame · link radius ${evolution?.method?.link_radius_km||'—'} km</small>`;
  list.innerHTML='';
  for(const track of evolutionTracks.slice(0,12)){
    const row=document.createElement('button');row.className='evo-row'+(selectedTrack?.id===track.id?' active':'');
    row.innerHTML=`<strong>${track.id}</strong>`
      +`<span class="row-state" style="color:${STATE_COLOR[track.status]||'#a6ff77'}">${track.status}</span>`
      +`<span>${track.frames_observed} frames · ${track.detections_total} det · ${track.duration_hours} h${track.trajectory?.bearing_compass?` · drift ${track.trajectory.bearing_compass}`:''}</span>`
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
  $('evoDetail').classList.remove('hidden');$('evoIntel').classList.remove('hidden');
  const chip=$('evoStatus');chip.textContent=track.status;chip.className=`status-chip ${STATE_CLASS[track.status]||''}`;
  $('evoIdentity').textContent=`${track.identity==='reused'?'IDENTITY REUSED':'NEW IDENTITY'} · ${track.sources?.join(' + ')||'—'}`;
  $('evoBasis').textContent=track.status_basis||'—';
  $('evoDuration').textContent=`${track.duration_hours} h`;
  $('evoFrames').textContent=`${track.frames_observed} / ${track.frames_in_dataset}`;
  $('evoPeak').textContent=`${track.peak?.date?.slice(5)||'—'} · ${track.peak?.total_frp||0} MW`;
  const tr=track.trajectory||{};
  $('evoDrift').textContent=tr.bearing_compass?`${tr.bearing_compass} · ${tr.net_displacement_km} km`:'—';
  $('evoConfidence').textContent=`${Math.round(track.confidence?.score||0)}% · ${track.confidence?.level||'—'}`;
  const bars=$('evoBars');bars.innerHTML='';
  const labels={detections:'DETECTIONS',persistence:'PERSISTENCE',sensor_independence:'SENSORS',frp:'PEAK FRP',declared_confidence:'DECLARED CONF.'};
  for(const [key,val] of Object.entries(track.confidence?.components||{})){
    const row=document.createElement('div');row.className='cb';
    row.innerHTML=`<span>${labels[key]||key.toUpperCase()}</span><span class="cb-track"><span class="cb-fill" style="width:${Math.min(100,val)}%;display:block"></span></span><span class="cb-val">${Math.round(val)}</span>`;
    bars.appendChild(row);
  }
  const ev=$('evoEvidence');ev.innerHTML='';
  for(const line of (track.confidence?.explanations||[])){const s=document.createElement('span');s.textContent=line;ev.appendChild(s);}
  const sp=document.createElement('span');
  sp.textContent=tr.interpretation||'Apparent centroid drift, not a propagation model.';
  ev.appendChild(sp);
  $('evoCaveat').textContent=track.caveat||'Analytical label — not an official incident record.';
  drawLifecycleChart(track);
}
function openTrack(track){
  selectedTrack=track;
  $('detailEmpty').classList.add('hidden');$('detailCard').classList.remove('hidden');
  $('detailKicker').textContent=`PERSISTENT FIRE EVENT · ${track.id}`;
  $('detailSeverity').textContent=track.status;
  $('detailSeverity').style.color=STATE_COLOR[track.status]||'#a6ff77';
  $('detailCoords').textContent=`${Number(track.lat).toFixed(4)}, ${Number(track.lon).toFixed(4)}`;
  $('detailFrp').textContent=`Σ ${track.total_frp} MW · peak ${track.max_frp} MW`;
  $('detailConfidence').textContent=`${track.mean_confidence}% · ${track.detections_total} detections`;
  $('detailTime').textContent=`${(track.first_seen||'').slice(0,10)} → ${(track.last_seen||'').slice(0,10)}`;
  $('detailSatellite').textContent=(track.families||[]).join(' + ')||'—';
  renderTrackDetail(track);renderEvolutionPanel();renderFrame();renderTrackingBanner();
  loadEnvironmentIntelligence(track.lat,track.lon,(track.last_seen||'').slice(0,10));
  const card=$('detailCard');if(card)card.scrollTop=0;
}

/* --- banner de seguimiento + reticle + línea guía --- */
function renderTrackingBanner(){
  const banner=$('trackingBanner');if(!banner)return;
  if(!selectedTrack||viewMode!=='evolution'){banner.classList.add('hidden');return;}
  banner.classList.remove('hidden');
  $('trackingId').textContent=selectedTrack.id;
  $('trackingState').textContent=`${selectedTrack.status} · ${Math.round(selectedTrack.confidence?.score||0)}% CONF · ${selectedTrack.detections_total} DET`;
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
      <text class="reticle-label" style="fill:${col}" x="${r+40}" y="${-r-4}">${selectedTrack.id} · ${selectedTrack.status}</text>
    </g>`;
}
function videoR(pos){const px=window.devicePixelRatio||1;return 24*px;}

/* --- animación: pulso + HUD --- */
viewer.scene.preRender.addEventListener(()=>{
  const time=performance.now()/1000;
  for(const item of pulsePrimitives){
    const k=0.5+0.5*Math.sin(time*2.2+item.phase);
    try{item.prim.pixelSize=item.base*(0.85+0.55*k);}catch(e){}
  }
  drawHud();
});

/* --- carga de datos de evolución --- */
async function loadEvolutionDemo(){
  setStatus('TRACKING');
  try{
    const region=selectedRegion()==='amazon'?'amazon':'mexico';
    const res=await fetch(`/api/evolution/demo?region=${region}&days=5`);
    if(!res.ok)throw new Error(`HTTP ${res.status}`);
    const payload=await res.json();
    applyHarmonized(payload);
    setViewMode('evolution');
    const best=evolutionTracks.find(t=>t.status==='EXPANDING')||evolutionTracks.find(t=>t.status!=='EXTINCT')||evolutionTracks[0];
    if(best){openTrack(best);flyToTrack(best);}
    else if(payload.camera)viewer.camera.flyTo({destination:Cesium.Cartesian3.fromDegrees(payload.camera[0],payload.camera[1],payload.camera[2]),duration:2.2});
    showToast(`Fire Evolution Engine: ${payload.evolution.tracks_total} persistent tracks (${payload.evolution.tracks_multi_frame} multi-frame). Synthetic scenario.`,6800);
  }catch(err){setStatus('ERROR',false);showToast(`Evolution demo failed: ${err.message}`,6500);}
}
async function loadEvolutionArchive(){
  const area=lastArea||selectedArea();if(!area)return;
  if(!archiveStatus?.ready){showToast('Import FIRMS archive data first (Local Archive Manager).',5600);return;}
  const start=archiveStatus.min_date||$('historyDate').value;
  const end=archiveStatus.max_date||start;
  const days=Math.min(10,Math.max(2,Math.round((new Date(end)-new Date(start))/86400000)+1));
  setStatus('TRACKING');
  try{
    const res=await fetch(`/api/evolution/archive?area=${encodeURIComponent(area)}&start_date=${encodeURIComponent(start)}&days=${days}`);
    if(!res.ok){const e=await res.json().catch(()=>({}));throw new Error(e.detail||`HTTP ${res.status}`);}
    const payload=await res.json();applyHarmonized(payload);setViewMode('evolution');
    const best=evolutionTracks.find(t=>t.status==='EXPANDING')||evolutionTracks[0];
    if(best){openTrack(best);flyToTrack(best);}
    showToast(`NASA REAL DATA · ${payload.evolution.tracks_total} persistent tracks (${payload.evolution.tracks_multi_frame} multi-frame) from the local archive.`,7000);
  }catch(err){setStatus('ERROR',false);showToast(err.message,6500);}
}

/* --- replay del ciclo de vida --- */
function stopReplay(){replayToken++;$('btnReplayTrack')?.classList.remove('playing');const b=$('btnReplayTrack');if(b)b.textContent='▶ REPLAY LIFECYCLE';}
function replayTrack(){
  if(!selectedTrack){showToast('Select a tracked event first.');return;}
  const token=++replayToken;const btn=$('btnReplayTrack');
  if(btn)btn.textContent='● REPLAYING';
  const steps=(selectedTrack.timeline||[]).map(s=>({index:frameIndexOf(s.date),lat:s.lat,lon:s.lon,det:s.detections}))
    .filter(s=>s.index>=0).sort((a,b)=>a.index-b.index);
  if(steps.length<2){showToast('This track has a single observed frame.');return;}
  let i=0;
  const advance=()=>{
    if(token!==replayToken)return;
    if(i>=steps.length){stopReplay();showToast(`Lifecycle replay complete: ${selectedTrack.id} — ${selectedTrack.status}.`,5200);return;}
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
  else if(env.workerMode==='none')parts.push('SIN-WORKERS');
  if(env.sandboxed)parts.push('SANDBOX');
  const label=parts.join(' · ');
  const el=$('rendererStatus');
  if(el){el.textContent=label;el.classList.add(gl&&!software?'ok':'degraded');}
  try{viewer.scene.renderError.addEventListener((sc,e)=>{window.IGNIS_ENV.renderErrorReal=String((e&&e.message)||e).slice(0,200);});}catch(e){}
if(!gl){showRenderAlert('SIN ACELERACIÓN 3D','Este navegador no expone WebGL, así que Cesium no puede dibujar el planeta. Prueba en Chrome/Edge/Firefox actualizados o activa la aceleración por hardware.');}
  console.info('[IGNIS] renderer:',label,'· sandboxed:',!!env.sandboxed,'· workers:',env.workerMode);
})();

function showRenderAlert(title,body){
  const box=$('renderAlert');if(!box)return;
  $('renderAlertTitle').textContent=title;$('renderAlertBody').textContent=body;box.classList.remove('hidden');
}
function hideRenderAlert(){const box=$('renderAlert');if(box)box.classList.add('hidden');}

/* Vigilante de render: si Cesium detiene el render, se degrada en vez de morir. */
(function renderWatchdog(){
  /* v0.8.1 — El watchdog anterior daba FALSOS POSITIVOS: `scene.renderError` es un
     Event de Cesium y basta que tenga un suscriptor interno para parecer un error.
     Ahora se mide lo único que importa: ¿el globo sigue dibujando cuadros? */
  let historial=[],aplicado=false;
  setInterval(()=>{
    try{
      if(!viewer||!viewer.scene)return;
      const f=(viewer.scene.frameState&&viewer.scene.frameState.frameNumber)||0;
      historial.push(f);if(historial.length>6)historial.shift();
      const congelado=historial.length>=6&&historial[0]===historial[historial.length-1];
      if(!congelado){
        if(aplicado){aplicado=false;hideRenderAlert();setStatus('ONLINE',true);}
        return;
      }
      // Congelado en 3 lecturas (~7,5 s): primer intento = aligerar efectos.
      if(!aplicado){
        aplicado=true;
        try{
          viewer.scene.postProcessStages.bloom.enabled=false;
          viewer.scene.highDynamicRange=false;
          viewer.scene.skyBox.show=false;
          viewer.scene.globe.enableLighting=false;
          viewer.resize();
        }catch(e){}
        setStatus('RENDER SEGURO',false);
        showToast('Render simplificado para mantener el planeta operativo.',4200);
        setTimeout(()=>{ // si aún así no dibuja, entonces sí avisamos
          if(!viewer||!viewer.scene)return;
          const g=(viewer.scene.frameState&&viewer.scene.frameState.frameNumber)||0;
          if(g===historial[historial.length-1]){
            const detalle=(window.IGNIS_ENV&&window.IGNIS_ENV.renderErrorReal)||'sin detalle del motor';
            showRenderAlert('MAPA 3D DETENIDO','El visor dejó de dibujar cuadros. Detalle del motor: '+detalle+'\n\nSe desactivaron los efectos pesados; la analítica y las APIs siguen funcionando.');
          }
        },9000);
      }
    }catch(e){}
  },2500);
})();

/* Reintento manual: recarga limpia del visor conservando el estado. */
$('btnRetryRender')?.addEventListener('click',()=>{
  hideRenderAlert();
  try{
    viewer.scene.renderError=undefined;
    viewer.scene.postProcessStages.bloom.enabled=true;
    viewer.scene.highDynamicRange=true;
    viewer.scene.skyBox.show=true;
    viewer.scene.globe.enableLighting=IGNIS_TERMINATOR;
    viewer.resize();
    tuneImagery();
    renderFrame();drawHud();
    showToast('Render reintentado con efectos completos.',4200);
  }catch(e){showToast('No se pudo reiniciar el render: '+e.message,6000);}
});

/* ==========================================================================
   IGNIS v0.8 — Environmental Intelligence (UI)
   1) Capas NASA GIBS conmutables sobre el globo, sincronizadas con el timeline.
   2) Bloque ENTORNO en el dossier: sequía, vegetación y humo por evento.
   Nota GIBS: el orden del REST es {TileMatrix}/{TileRow}/{TileCol}.
   ========================================================================== */
const GIBS_BASE='https://gibs.earthdata.nasa.gov/wmts/epsg4326/best';
const ENV_CATALOG={
  aerosol:{id:'MODIS_Terra_Aerosol',tms:'2km',matrix:['0','1','2','3','4','5'],maxLevel:5,ext:'png',alpha:.72,lagDays:1,label:'AEROSOLES (AOD)'},
  ndvi:{id:'MODIS_Terra_NDVI_8Day',tms:'250m',matrix:['0','1','2','3','4','5','6','7'],maxLevel:6,ext:'png',alpha:.82,lagDays:1,label:'VEGETACIÓN (NDVI)'},
  truecolor:{id:'MODIS_Terra_CorrectedReflectance_TrueColor',tms:'250m',matrix:['0','1','2','3','4','5','6','7'],maxLevel:6,ext:'jpg',alpha:.92,lagDays:1,label:'COLOR REAL'},
  pyro:{id:'OMPS_Aerosol_Index_PyroCumuloNimbus',tms:'2km',matrix:['0','1','2','3','4','5'],maxLevel:5,ext:'png',alpha:.42,lagDays:1,label:'PIRO-CUMULONIMBOS (OMPS)'},
};
let envLayers={};           // key -> Cesium.ImageryLayer activa
function currentEnvDate(){return frames[frameIndex]?.date||new Date().toISOString().slice(0,10);}
function removeEnvLayer(key){
  const layer=envLayers[key];
  if(!layer)return;
  try{viewer.imageryLayers.remove(layer,true);}catch(e){}
  delete envLayers[key];
  const chip=document.querySelector(`.env-chip[data-env="${key}"]`);
  if(chip){chip.classList.remove('active','loading','failed');}
}
function envDateOffset(date,days){const d=new Date(date+'T00:00:00Z');d.setUTCDate(d.getUTCDate()-days);return d.toISOString().slice(0,10);}
function addEnvLayer(key,attempt=0){
  const cfg=ENV_CATALOG[key];if(!cfg)return;
  const chip=document.querySelector(`.env-chip[data-env="${key}"]`);
  /* La fecha va literal en la URL: Cesium no sustituye {Time} con customTags de forma
     fiable y las peticiones salían con "%7BTime%7D" (HTTP 400). */
  const date=envDateOffset(currentEnvDate(),(cfg.lagDays||1)+attempt);
  try{
    const provider=new Cesium.WebMapTileServiceImageryProvider({
      url:`${GIBS_BASE}/${cfg.id}/default/${date}/${cfg.tms}/{TileMatrix}/{TileRow}/{TileCol}.${cfg.ext}`,
      layer:cfg.id,style:'default',format:`image/${cfg.ext==='jpg'?'jpeg':'png'}`,
      tileMatrixSetID:cfg.tms,tileMatrixLabels:cfg.matrix,maximumLevel:cfg.maxLevel,
      tilingScheme:new Cesium.GeographicTilingScheme(),
      customTags:{Time:date},
      credit:new Cesium.Credit('NASA GIBS · '+cfg.label),
    });
    const layer=viewer.imageryLayers.addImageryProvider(provider);
    layer.alpha=cfg.alpha;
    envLayers[key]=layer;
    chip?.classList.add('active');chip?.classList.remove('loading','failed');
    // Si algún tile falla (sin internet), se marca el chip como no disponible.
    let failures=0;
    provider.errorEvent.addEventListener(()=>{
      failures++;
      if(failures>4){
        removeEnvLayer(key);
        // El compuesto de GIBS puede no existir para hoy: se prueba con días anteriores.
        if(attempt<3){addEnvLayer(key,attempt+1);}
        else if(chip){chip.classList.add('failed');chip.title='NASA GIBS no respondió (¿sin internet?)';}
      }
    });
    showToast(`Capa ${cfg.label} · ${date} (NASA GIBS)`+(attempt?` · compuesto de ${attempt} día(s) antes`:''),3600);
  }catch(err){
    chip?.classList.add('failed');
    showToast(`No se pudo añadir ${cfg.label}: ${err.message}`,5000);
  }
}
function toggleEnvLayer(key){
  if(envLayers[key]){removeEnvLayer(key);showToast(`Capa ${ENV_CATALOG[key].label} desactivada.`,2600);}
  else addEnvLayer(key);
}
function refreshEnvLayers(){ // al cambiar de frame se recrean con la nueva fecha
  for(const key of Object.keys(envLayers)){removeEnvLayer(key);addEnvLayer(key);}
}

/* --- ENTORNO en el dossier --- */
function resetEnvBlock(){
  $('envDate').textContent='—';
  ['envDrought','envFuel','envSmoke'].forEach(id=>$(id).textContent='—');
  $('envEvidence').innerHTML='<span class="env-loading">consulta pendiente</span>';
}
async function loadEnvironmentIntelligence(lat,lon,date){
  if(!$('envBlock'))return;
  resetEnvBlock();
  $('envDate').textContent=date||'—';
  $('envEvidence').innerHTML='<span class="env-loading">consultando NASA GIBS + ERA5…</span>';
  try{
    const res=await fetch(`/api/environment/intelligence?lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}&event_date=${encodeURIComponent(date)}`);
    if(!res.ok)throw new Error(`HTTP ${res.status}`);
    const d=await res.json();
    $('envDrought').textContent=d.drought?.available?`${d.drought.category_label} · ${d.drought.percentile}%`: 'sin dato';
    $('envFuel').textContent=d.fuel?.available?`${d.fuel.fuel_label} (NDVI ${d.fuel.ndvi})`:'sin dato';
    $('envSmoke').textContent=d.smoke?.available?`${d.smoke.smoke_label} (AOD ${d.smoke.aod})`:'sin dato';
    const lines=[...(d.drought?.evidence||[]),...(d.fuel?.evidence?[d.fuel.evidence]:[]),...(d.smoke?.evidence||[])];
    $('envEvidence').innerHTML=lines.length?lines.map(l=>`<span>${l}</span>`).join(''):'<span class="env-loading">sin evidencia disponible (¿sin internet?)</span>';
  }catch(err){
    $('envEvidence').innerHTML=`<span class="env-loading">entorno no disponible (${err.message})</span>`;
  }
}
