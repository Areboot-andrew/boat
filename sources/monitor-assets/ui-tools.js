// Runs in the detached document; intentionally has no dependency on its opener.
function mapWindowApp(base, seed) {
  const status=document.getElementById('status');
  if(!window.L){status.textContent='Не вдалося завантажити карту. Закрийте й відкрийте вікно ще раз.';document.getElementById('return').onclick=()=>window.close();return}
  const m=L.map('map').setView(seed.center,seed.zoom);
  let tileError=false,boat=null,following=true,last=null,lastSeq=-1;
  let lines=seed.session?[]:seed.segments;
  const trail=L.polyline(lines,{color:'#43e6bb',weight:3,opacity:.9}).addTo(m);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'}).on('tileerror',()=>{tileError=true}).on('tileload',()=>{tileError=false}).addTo(m);
  m.on('dragstart',()=>{following=false});
  document.getElementById('follow').onclick=()=>{following=true;if(boat)m.panTo(boat.getLatLng())};
  document.getElementById('return').onclick=()=>window.close();
  new ResizeObserver(()=>m.invalidateSize()).observe(document.getElementById('map'));
  function point(p){
    if(!p.gps_valid||!Number.isFinite(p.latitude)||!Number.isFinite(p.longitude)||!(p.speed_kmh>=1)){last=null;return}
    const ll=L.latLng(p.latitude,p.longitude),t=Date.parse(p.utc);
    if(last){const d=ll.distanceTo(last.ll),dt=(t-last.t)/1000;if(dt<=0||dt>8||d>Math.max(15,dt*150/3.6))last=null;else if(d<2)return}
    if(!last)lines.push([]);lines[lines.length-1].push([p.latitude,p.longitude]);last={ll,t};
    while(lines.reduce((n,s)=>n+s.length,0)>12000){if(lines[0].length>1)lines[0].shift();else lines.shift()}
    trail.setLatLngs(lines);
  }
  const number=v=>typeof v==='number'&&Number.isFinite(v);
  async function json(path){const r=await fetch(base+path,{cache:'no-store',signal:AbortSignal.timeout(5000)});if(!r.ok)throw Error('HTTP '+r.status);return r.json()}
  async function poll(){
    try{
      const data=await json('/telemetry'),g=data.gps||{};
      if(!g.position_valid||!number(g.latitude)||!number(g.longitude)){
        status.textContent='Очікування достовірної GPS-позиції';if(boat){boat.remove();boat=null}last=null;
      }else{
        const h=g.heading_valid?g.heading_deg:(g.speed_kmh>=1?g.course_deg:null);
        const heading=number(h)?h:null;
        const html=heading===null?'●':'<svg width="28" height="36" viewBox="0 0 28 36" style="transform:rotate('+heading+'deg);filter:drop-shadow(0 1px 2px #000)"><path d="M10 18H18V33H10Z" fill="#28dd83" stroke="white" stroke-width="1.2"/><path d="M14 2L26 18H18V22H10V18H2Z" fill="#ff454f" stroke="white" stroke-width="1.2"/></svg>';
        const icon=L.divIcon({className:'boat-marker',html,iconSize:[28,36],iconAnchor:[14,18]});
        if(!boat)boat=L.marker([g.latitude,g.longitude],{icon}).addTo(m);else boat.setLatLng([g.latitude,g.longitude]).setIcon(icon);
        if(following){if(m.getZoom()<10)m.setView(boat.getLatLng(),16);else m.panTo(boat.getLatLng(),{animate:false})}
        status.textContent=(number(g.speed_kmh)?g.speed_kmh.toFixed(1):'—')+' км/год · курс '+(heading===null?'—':heading.toFixed(0)+'°')+(tileError?' · немає тайлів карти':'');
        if(!seed.session)point({gps_valid:true,latitude:g.latitude,longitude:g.longitude,speed_kmh:g.speed_kmh,utc:new Date().toISOString()});
      }
      if(seed.session){
        try{const d=await json('/track?id='+encodeURIComponent(seed.session)+'&after='+lastSeq);for(const p of d.points){point(p);lastSeq=p.seq}}
        catch(e){status.textContent+=' · трек сесії недоступний'}
      }
    }catch(e){status.textContent='Немає зв’язку з Raspberry · повторюємо';if(boat){boat.remove();boat=null}last=null}
    finally{setTimeout(poll,1000)}
  }
  poll();
}

(() => {
  const panel=document.getElementById('mapPanel'), stage=panel.parentElement;
  const drag=document.getElementById('mapDrag'), resize=document.getElementById('mapResize');
  let rect=null, expanded=false, restore=null, floating=false, dockRect=null, popup=null;
  const home=document.createComment('map-home');panel.before(home);
  const toolbar=panel.querySelector('.map-toolbar>div');
  function button(id,text,title){const b=document.createElement('button');b.id=id;b.textContent=text;b.title=title;b.setAttribute('aria-label',title);toolbar.append(b);return b}
  const floatButton=button('mapFloat','↗','Відкріпити карту від камери');
  const windowButton=button('mapWindow','▣','Карта в окремому вікні / на іншому моніторі');
  const returnButton=document.createElement('button');returnButton.textContent='↙ Повернути карту';returnButton.hidden=true;returnButton.className='lock';
  document.querySelector('.camera-head').append(returnButton);
  returnButton.onclick=()=>{if(popup&&!popup.closed)popup.close();popup=null;panel.hidden=false;returnButton.hidden=true;if(map)map.invalidateSize()};
  const style=document.createElement('style');
  style.textContent='.map-pip.map-floating{position:fixed!important;z-index:10000;min-width:0;transition:none;background:#10252e}.map-toolbar>div{display:flex;gap:3px;flex-shrink:0}.map-toolbar button{padding:4px 6px}.map-pip{min-width:0!important}.map-pip[hidden]{display:none!important}.map-moving{user-select:none}.map-moving iframe{pointer-events:none}';
  document.head.append(style);
  const size=()=>floating?{w:document.documentElement.clientWidth,h:window.innerHeight}:{w:stage.clientWidth,h:stage.clientHeight};
  function bounds(r){
    const {w,h}=size();
    const width=Math.max(Math.min(180,w),Math.min(r.width,w)),height=Math.max(Math.min(130,h),Math.min(r.height,h));
    return {left:Math.max(0,Math.min(r.left,w-width)),top:Math.max(0,Math.min(r.top,h-height)),width,height};
  }
  function apply(r){rect=bounds(r);Object.assign(panel.style,{left:rect.left+'px',top:rect.top+'px',width:rect.width+'px',height:rect.height+'px',right:'auto',bottom:'auto'});if(map)map.invalidateSize()}
  function save(){try{const {w,h}=size();localStorage.setItem(floating?'harpoonMapFloatingRect':'harpoonMapRect',JSON.stringify({x:rect.left/w,y:rect.top/h,w:rect.width/w,h:rect.height/h}));localStorage.setItem('harpoonMapFloating',String(floating))}catch(e){}}
  function setFloating(value,persist=true){
    const a=panel.getBoundingClientRect();expanded=false;restore=null;
    document.getElementById('mapExpand').setAttribute('aria-expanded','false');
    if(value){dockRect={...rect};document.body.append(panel)}else home.after(panel);
    floating=value;panel.classList.toggle('map-floating',value);
    floatButton.textContent=value?'↙':'↗';floatButton.title=value?'Повернути карту в камеру':'Відкріпити карту від камери';floatButton.setAttribute('aria-label',floatButton.title);floatButton.setAttribute('aria-pressed',String(value));
    apply(value?{left:a.left,top:a.top,width:a.width,height:a.height}:(dockRect||{left:8,top:8,width:300,height:220}));
    if(persist)save();
  }
  floatButton.onclick=()=>setFloating(!floating);
  function initial(){
    const a=panel.getBoundingClientRect(),b=stage.getBoundingClientRect();
    let r={left:a.left-b.left,top:a.top-b.top,width:a.width,height:a.height};
    try{const s=JSON.parse(localStorage.getItem('harpoonMapRect'));if(s&&[s.x,s.y,s.w,s.h].every(Number.isFinite))r={left:s.x*stage.clientWidth,top:s.y*stage.clientHeight,width:s.w*stage.clientWidth,height:s.h*stage.clientHeight}}catch(e){}
    apply(r);
  }
  for(const [element,mode] of [[drag,'move'],[resize,'resize']]){
    let origin=null;
    element.addEventListener('pointerdown',e=>{if(e.button!==0)return;e.preventDefault();expanded=false;document.getElementById('mapExpand').setAttribute('aria-expanded','false');origin={...rect,x:e.clientX,y:e.clientY};element.setPointerCapture(e.pointerId);stage.classList.add('map-editing');document.body.classList.add('map-moving')});
    element.addEventListener('pointermove',e=>{if(!origin)return;const dx=e.clientX-origin.x,dy=e.clientY-origin.y,{w,h}=size();apply(mode==='move'?{...origin,left:origin.left+dx,top:origin.top+dy}:{...origin,width:Math.min(origin.width+dx,w-origin.left),height:Math.min(origin.height+dy,h-origin.top)})});
    const finish=()=>{if(origin){origin=null;stage.classList.remove('map-editing');document.body.classList.remove('map-moving');save()}};
    element.addEventListener('pointerup',finish);element.addEventListener('pointercancel',finish);element.addEventListener('lostpointercapture',finish);
    element.addEventListener('keydown',e=>{const delta={ArrowLeft:[-10,0],ArrowRight:[10,0],ArrowUp:[0,-10],ArrowDown:[0,10]}[e.key];if(!delta)return;e.preventDefault();apply(mode==='move'?{...rect,left:rect.left+delta[0],top:rect.top+delta[1]}:{...rect,width:rect.width+delta[0],height:rect.height+delta[1]});save()});
  }
  document.getElementById('mapExpand').onclick=()=>{expanded=!expanded;if(expanded){restore={...rect};const {w,h}=size();apply({left:8,top:8,width:w-16,height:h-16})}else{apply(restore||rect);save()}document.getElementById('mapExpand').setAttribute('aria-expanded',String(expanded))};
  initial();new ResizeObserver(()=>{if(rect)apply(rect)}).observe(stage);
  window.addEventListener('resize',()=>{if(rect)apply(rect)});
  try{if(localStorage.getItem('harpoonMapFloating')==='true'){setFloating(true,false);const s=JSON.parse(localStorage.getItem('harpoonMapFloatingRect'));if(s&&[s.x,s.y,s.w,s.h].every(Number.isFinite)){const {w,h}=size();apply({left:s.x*w,top:s.y*h,width:s.w*w,height:s.h*h})}}}catch(e){}
  windowButton.onclick=()=>{
    if(popup&&!popup.closed){popup.focus();return}
    popup=window.open('','harpoon-map-'+location.host,'popup,width=1000,height=750,resizable=yes,scrollbars=no');
    if(!popup){alert('Дозвольте спливні вікна для цього сайту, потім натисніть ▣ ще раз.');return}
    // A separate same-origin document: no video connection or recording controls.
    const base=location.origin;
    const seed={center:map?[map.getCenter().lat,map.getCenter().lng]:[0,0],zoom:map?map.getZoom():2,segments:JSON.parse(JSON.stringify(segments)),session:selected};
    popup.document.open();
    popup.document.write('<!doctype html><html lang="uk"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>HARPOON — карта</title><link rel="stylesheet" href="'+base+'/leaflet.css"><style>html,body{height:100%;margin:0;background:#10252e;color:#dceeed;font:14px Arial}body{display:flex;flex-direction:column}header{display:flex;align-items:center;gap:12px;padding:10px;flex-wrap:wrap}button{background:#254751;color:white;border:0;border-radius:6px;padding:8px;cursor:pointer}#status{flex:1}#map{flex:1;min-height:0}.boat-marker{color:white;text-align:center}</style></head><body><header><b>HARPOON · КАРТА</b><span id="status">З’єднання…</span><button id="follow">◎ До човна</button><button id="return">Повернути в інтерфейс</button></header><div id="map"></div><script src="'+base+'/leaflet.js"></script><script>('+mapWindowApp.toString()+')('+JSON.stringify(base)+','+JSON.stringify(seed)+');</script></body></html>');
    popup.document.close();popup.focus();panel.hidden=true;returnButton.hidden=false;
    const timer=setInterval(()=>{if(!popup||popup.closed){clearInterval(timer);popup=null;panel.hidden=false;returnButton.hidden=true;if(map)map.invalidateSize()}},500);
  };

  let selected='',active=null,lastSeq=-1,trackBusy=false,segments=[],lastPoint=null,trail=null;
  const select=document.getElementById('sessionSelect'),start=document.getElementById('sessionStart'),stop=document.getElementById('sessionStop'),status=document.getElementById('sessionStatus'),download=document.getElementById('sessionDownload');
  const remove=document.getElementById('sessionDelete'),clear=document.getElementById('sessionClear');
  function clearTrail(){segments=[];lastPoint=null;lastSeq=-1;if(trail){trail.remove();trail=null}}
  function addPoint(p){
    if(!map)return;
    const t=Date.parse(p.utc),lat=p.latitude,lon=p.longitude;
    if(!p.gps_valid||!Number.isFinite(lat)||!Number.isFinite(lon)||!(p.speed_kmh>=1)){lastPoint=null;return}
    const point=L.latLng(lat,lon);
    if(lastPoint){const meters=point.distanceTo(lastPoint.point),dt=(t-lastPoint.t)/1000;if(meters<2)return;if(dt<=0||dt>8||meters>Math.max(15,dt*150/3.6))lastPoint=null}
    if(!lastPoint)segments.push([]);
    segments[segments.length-1].push([lat,lon]);lastPoint={point,t};
    // Keep the on-screen trail bounded. Full-resolution data remains in SQLite/CSV.
    if(segments.reduce((n,s)=>n+s.length,0)>12000){if(segments[0].length>1)segments[0].shift();else segments.shift()}
    if(!trail)trail=L.polyline(segments,{color:'#43e6bb',weight:3,opacity:.9}).addTo(map);else trail.setLatLngs(segments);
  }
  window.liveTrack=g=>{if(!selected)addPoint({utc:new Date().toISOString(),latitude:g.latitude,longitude:g.longitude,speed_kmh:g.speed_kmh,gps_valid:g.position_valid})};
  function selection(){selected=select.value;clearTrail();download.hidden=!selected;remove.disabled=active!=null||!selected;if(selected)download.href='/sessions.csv?id='+encodeURIComponent(selected);loadTrack()}
  select.onchange=selection;
  async function loadTrack(){
    if(!selected||!map||trackBusy)return;
    trackBusy=true;const id=selected;
    try{const r=await fetch('/track?id='+encodeURIComponent(id)+'&after='+lastSeq,{cache:'no-store',signal:AbortSignal.timeout(5000)});if(!r.ok)throw Error();const d=await r.json();if(selected!==id)return;for(const p of d.points){addPoint(p);lastSeq=p.seq}}
    catch(e){status.textContent='Не вдалося завантажити трек · повторюємо'}finally{trackBusy=false}
  }
  function render(s){
    const changed=active!==s.active_id;
    active=s.active_id;
    start.disabled=active!=null;stop.disabled=active==null;
    clear.disabled=active!=null||!s.sessions.length;
    status.textContent=s.error?'Помилка запису: '+s.error:active!=null?'● Запис сесії #'+active+' · кожні 0,5 с':'Запис зупинений · дані збережено';
    const wanted=changed&&active!=null?String(active):s.sessions.some(row=>String(row.id)===selected)?selected:String(active||s.sessions[0]?.id||'');
    select.replaceChildren();
    if(!s.sessions.length)select.add(new Option('Ще немає сесій',''));
    for(const row of s.sessions)select.add(new Option('#'+row.id+' · '+new Date(row.started).toLocaleString('uk-UA')+' · '+({recording:'запис',saved:'збережено',interrupted:'перервано'}[row.status]||row.status),String(row.id)));
    select.value=wanted;
    if(selected!==select.value)selection();
    remove.disabled=active!=null||!selected;
  }
  async function command(action){start.disabled=stop.disabled=true;try{const r=await fetch('/sessions/'+action,{method:'POST',headers:{'X-Harpoon-Session':'1'},signal:AbortSignal.timeout(8000)});const s=await r.json();if(!r.ok)throw Error(s.error||'Помилка');if(action==='start'){selected='';clearTrail()}render(s)}catch(e){status.textContent='Не підтверджено: '+e.message;start.disabled=stop.disabled=true}}
  start.onclick=()=>command('start');stop.onclick=()=>command('stop');
  async function erase(all){
    if(active!=null)return;
    const id=selected;
    if(!confirm(all?'Видалити ВСІ сесії та їхні треки з Raspberry для всіх ПК? Спочатку завантажте потрібні CSV. Скасувати видалення неможливо.':'Видалити сесію #'+id+' та її трек для всіх ПК? Скасувати видалення неможливо.'))return;
    remove.disabled=clear.disabled=true;
    try{const r=await fetch('/sessions/delete',{method:'POST',headers:{'X-Harpoon-Session':'1','Content-Type':'application/json'},body:JSON.stringify({confirm:'DELETE',all,id}),signal:AbortSignal.timeout(15000)});const s=await r.json();if(!r.ok)throw Error(s.error||'Помилка видалення');selected='';clearTrail();render(s)}catch(e){status.textContent=e.message}
  }
  remove.onclick=()=>erase(false);clear.onclick=()=>erase(true);
  async function poll(){try{const r=await fetch('/sessions',{cache:'no-store',signal:AbortSignal.timeout(5000)});if(!r.ok)throw Error();render(await r.json());await loadTrack()}catch(e){status.textContent='Журнал недоступний';start.disabled=stop.disabled=remove.disabled=clear.disabled=true}finally{setTimeout(poll,2000)}}
  poll();
})();
