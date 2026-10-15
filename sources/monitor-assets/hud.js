let map, marker, follow=true;
const fmt=(v,d=1)=>v==null||!Number.isFinite(Number(v))?'—':Number(v).toFixed(d);
window.renderGPS=function(g={}){
  const heading=g.heading_valid?g.heading_deg:(g.position_valid&&g.speed_kmh>=1?g.course_deg:null);
  document.getElementById('navLink').textContent=g.link_ok?'Зв’язок є':'Немає даних';
  document.getElementById('navPosition').textContent=g.position_valid?'Фікс · '+g.fix_quality:'Немає фікса';
  document.getElementById('navSatellites').textContent=g.link_ok?(g.satellites??'—'):'—';
  document.getElementById('navHeading').textContent=heading!=null?fmt(heading,1)+'° · '+(g.heading_valid?'ніс':'рух'):'Немає рішення';
  document.getElementById('gpsSpeed').textContent=fmt(g.speed_kmh);
  document.getElementById('gpsHeading').textContent=heading!=null?fmt(heading,0)+'°':'—';
  document.getElementById('gpsFix').textContent=g.position_valid?'GPS · ПОЗИЦІЯ ВИЗНАЧЕНА':g.link_ok?'GPS · ПОШУК СУПУТНИКІВ':'GPS · НЕМАЄ ДАНИХ';
  document.getElementById('gpsDetail').textContent=g.link_ok?'Супутників у рішенні: '+(g.satellites??'—'):'Підключіть UM982 до USB Raspberry';
  document.getElementById('gpsCoords').textContent=g.position_valid?fmt(g.latitude,6)+', '+fmt(g.longitude,6):'Координати очікуються';
  document.getElementById('headingState').textContent=g.heading_valid?'КУРС КОРПУСУ':heading!=null?'НАПРЯМОК РУХУ':'КУРС НЕ ВИЗНАЧЕНО';
  const empty=document.getElementById('mapEmpty');
  if(!g.position_valid){empty.hidden=false;empty.textContent='Очікування достовірної GPS-позиції';if(marker){marker.remove();marker=null}return}
  if(!window.L){empty.hidden=false;empty.textContent='Бібліотека карти недоступна';return}
  if(!map){map=L.map('gpsMap',{zoomControl:false}).setView([g.latitude,g.longitude],16);L.control.zoom({position:'bottomright'}).addTo(map);L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'}).on('tileerror',()=>{empty.hidden=false;empty.textContent='Немає доступу до карти · координати доступні'}).on('tileload',()=>{empty.hidden=true}).addTo(map);map.on('dragstart',()=>{follow=false});new ResizeObserver(()=>map.invalidateSize()).observe(document.getElementById('gpsMap'))}
  empty.hidden=true;
  const icon=L.divIcon({className:'boat-marker',html:heading!=null?'<svg width="28" height="36" viewBox="0 0 28 36" role="img" aria-label="Напрямок борта" style="display:block;transform:rotate('+Number(heading)+'deg);filter:drop-shadow(0 1px 2px #000)"><path d="M10 18H18V33H10Z" fill="#28dd83" stroke="white" stroke-width="1.2"/><path d="M14 2L26 18H18V22H10V18H2Z" fill="#ff454f" stroke="white" stroke-width="1.2"/></svg>':'●',iconSize:[28,36],iconAnchor:[14,18]});
  if(!marker)marker=L.marker([g.latitude,g.longitude],{icon}).addTo(map);else marker.setLatLng([g.latitude,g.longitude]).setIcon(icon);
  if(follow)map.panTo([g.latitude,g.longitude],{animate:false});
  if(window.liveTrack)window.liveTrack(g);
};
document.getElementById('mapFollow').onclick=()=>{follow=true;if(map&&marker)map.panTo(marker.getLatLng())};
window.refreshMonitor=async function(){
  const el=document.getElementById('connection');
  try{const response=await fetch('/telemetry',{cache:'no-store',signal:AbortSignal.timeout(5000)});if(!response.ok)throw Error('HTTP');const data=await response.json();renderPlatform(data.system);renderEconomy(data);renderBattery(data);try{renderGPS(data.gps)}catch(error){console.error('Map render:',error)}el.textContent='PI 5 · ЗВ’ЯЗОК ОК';el.className='badge ok'}
  catch(e){renderPlatform();renderGPS({});renderEconomy({});renderBattery({});el.textContent='PI НЕДОСТУПНА';el.className='badge bad'}
  finally{setTimeout(refreshMonitor,1000)}
};
function renderEconomy(d){const e=d.energy||{};document.getElementById('ecoInstant').textContent=fmt(e.instant_wh_km);document.getElementById('ecoAverage').textContent=fmt(e.average_wh_km);document.getElementById('ecoRange').textContent=fmt(e.range_km);document.getElementById('ecoStatus').textContent=e.log_error?'Помилка запису журналу':e.status||'Немає даних';document.getElementById('tmDistance').textContent=fmt(e.distance_km,2)+' км';document.getElementById('tmAverage').textContent=fmt(e.average_wh_km)+' Wh/км';document.getElementById('tmRange').textContent=fmt(e.range_km)+' км'}
function renderBattery(d){
  const b=d.bms?.bms_link_ok?d.bms:{},e=d.energy||{};
  const fields={bmSoc:['battery_soc',0,'%'],bmVoltage:['battery_voltage',2,'V'],bmCurrent:['battery_current_a',2,'A'],bmPower:['battery_power_w',0,'W'],bmRemaining:['battery_remaining_ah',2,'Ah'],bmFull:['battery_full_ah',2,'Ah'],bmCells:['cell_count',0,''],bmMin:['cell_min_v',3,'V'],bmMax:['cell_max_v',3,'V'],bmDelta:['cell_delta_mv',1,'mV'],bmMos:['bms_mos_temp_c',1,'°C'],bmT1:['bms_t1_c',1,'°C'],bmT2:['bms_t2_c',1,'°C']};
  for(const [id,[key,decimals,unit]] of Object.entries(fields)){const value=fmt(b[key],decimals);document.getElementById(id).textContent=value==='—'?value:value+' '+unit}
  document.getElementById('bmLink').textContent=b.bms_link_ok?'Зв’язок є':'BMS не підключена';
  document.getElementById('bmLink').className=b.bms_link_ok?'ok':'bad';
  document.getElementById('bmAh').textContent=e.consumed_ah==null?'—':fmt(e.consumed_ah,3)+' Ah';
  document.getElementById('bmWh').textContent=e.consumed_wh==null?'—':fmt(e.consumed_wh,1)+' Wh';
}
function renderPlatform(s={}){document.getElementById('platformStatus').textContent='LAN '+(s.link_up===true?'OK':s.link_up===false?'OFF':'—')+' · RX '+fmt(s.rx_mbps,2)+' / TX '+fmt(s.tx_mbps,2)+' Мбіт/с · Pi '+fmt(s.temperature_c,1)+' °C'}
refreshMonitor();
