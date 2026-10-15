// One reader per visible camera; the same player is used in standalone windows.
function harpoonVideo(video,state,url){
  let reader=null,generation=0;
  const stop=()=>{generation++;if(reader)reader.close();reader=null;video.pause();if(video.srcObject)video.srcObject.getTracks().forEach(t=>t.stop());video.srcObject=null;video.muted=true};
  const start=()=>{if(reader)return;if(!window.RTCPeerConnection||typeof MediaMTXWebRTCReader==='undefined'){state.textContent='WebRTC недоступний';return}const token=++generation;state.textContent='З’єднання…';reader=new MediaMTXWebRTCReader({url,onError:e=>{if(token!==generation)return;state.textContent='Немає відео · повторюємо';state.title=String(e);video.srcObject=null},onTrack:e=>{if(token!==generation)return;video.srcObject=e.streams[0]||new MediaStream([e.track]);video.play().catch(()=>{state.textContent='Натисніть відео для запуску'})}})};
  video.onplaying=()=>{state.textContent='● LIVE'};video.onwaiting=()=>{if(reader)state.textContent='Буферизація…'};
  return {start,stop};
}
function harpoonCameraWindow(base,id){
  const video=document.querySelector('video'),state=document.getElementById('state'),url=new URL(base);url.port='8889';url.pathname='/'+id+'web/whep';
  const player=harpoonVideo(video,state,url.href);
  document.getElementById('sound').onclick=()=>{video.muted=!video.muted;document.getElementById('sound').textContent=video.muted?'Звук: вимк.':'Звук: увімк.';video.play().catch(()=>{state.textContent='Відтворення заблоковано браузером'})};
  document.getElementById('full').onclick=()=>{const p=document.fullscreenElement?document.exitFullscreen():document.documentElement.requestFullscreen();p?.catch(()=>{state.textContent='Повний екран недоступний'})};
  document.getElementById('back').onclick=()=>window.close();video.onclick=()=>video.play().catch(()=>{});
  window.addEventListener('beforeunload',()=>player.stop(),{once:true});player.start();
}
window.startCameraPlayer=()=>{
  if(window.harpoonCamerasStarted)return;window.harpoonCamerasStarted=true;
  const stage=document.querySelector('.camera-stage'),head=document.querySelector('.camera-head'),controls=document.querySelector('.camera-buttons'),oldVideo=document.getElementById('cameraFrame');
  let active='cam1',mode='single';try{const s=localStorage.getItem('harpoonVideoSource');if(s==='cam2'||s==='camera1')active='cam2';if(localStorage.getItem('harpoonCameraMode')==='both')mode='both'}catch(e){}
  const style=document.createElement('style');style.textContent=`
  .camera-head h2{font-size:16px}.camera-buttons{gap:6px}.camera-mode{display:flex;padding:3px;border:1px solid #39525b;border-radius:9px;gap:2px}.camera-mode button{font-size:13px;padding:6px 10px!important;background:transparent;color:#bdd1d5;border-radius:6px}.camera-mode button[aria-pressed=true]{background:#236854;color:#fff}
  .camera-tile{position:absolute;inset:0;background:#020708;overflow:hidden;border-radius:8px;z-index:1}.camera-tile[hidden]{display:none!important}.camera-tile video{display:block;width:100%;height:100%;object-fit:contain;background:#020708}.camera-mini{inset:auto;left:12px;top:12px;width:29%;height:30%;min-width:170px;min-height:120px;z-index:5;border:1px solid #649087;box-shadow:0 4px 18px #0009}.camera-mini video{cursor:pointer}
  .camera-tile-bar{position:absolute;top:0;left:0;right:0;height:32px;display:flex;align-items:center;gap:5px;padding:3px 7px;background:linear-gradient(#071419dd,#07141988);color:#dceeed;font-size:12px;z-index:2}.camera-tile-name{white-space:nowrap}.camera-tile-status{margin-right:auto;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#a8c3bf;font-size:11px}.camera-tile-bar button{padding:3px 6px;font-size:14px;background:#19363dcc;color:white;border-radius:5px}.camera-tile-bar button:hover{background:#315963}.camera-mini .camera-tile-name{cursor:grab;touch-action:none;user-select:none;margin-right:auto}.camera-mini .camera-tile-status{display:none}.camera-grip{position:absolute;right:0;bottom:0;z-index:3;padding:2px 6px!important;font-size:17px;background:#19363d;color:#74ead0;touch-action:none;cursor:nwse-resize}.camera-placeholder{position:absolute;inset:32px 0 0;display:flex;align-items:center;justify-content:center;color:#b6cdca;background:#09191f;z-index:1}.camera-placeholder[hidden]{display:none}.camera-tile:fullscreen{width:100%!important;height:100%!important;inset:0!important;border:0}.camera-tile:fullscreen .camera-grip{display:none}.camera-tile button[hidden]{display:none!important}
  @media(max-width:600px){.camera-mini{width:44%;height:29%;min-width:150px}.camera-tile-status{max-width:95px}.camera-head h2{font-size:14px}}
  `;document.head.append(style);
  controls.replaceChildren();head.querySelector('h2').textContent='Камери';
  const group=document.createElement('div');group.className='camera-mode';group.setAttribute('role','group');group.setAttribute('aria-label','Режим камер');controls.append(group);
  function button(parent,text,label,fn){const b=document.createElement('button');b.type='button';b.textContent=text;b.title=label;b.setAttribute('aria-label',label);b.onclick=fn;parent.append(b);return b}
  const selectors={};for(const [key,label] of [['cam1','1'],['cam2','2'],['both','Обидві']])selectors[key]=button(group,label,key==='both'?'Обидві камери: основна та PiP':'Лише камера '+label,()=>{if(key==='both')mode='both';else{active=key;mode='single'}render()});
  const cams={};let pipRect=null;
  for(const [index,id] of ['cam1','cam2'].entries()){
    const tile=document.createElement('section');tile.className='camera-tile';tile.setAttribute('aria-label','Панель камери '+(index+1));
    const video=index===0?oldVideo:document.createElement('video');video.removeAttribute('style');video.autoplay=true;video.muted=true;video.playsInline=true;video.setAttribute('aria-label','Відео камери '+(index+1));tile.append(video);
    const bar=document.createElement('div');bar.className='camera-tile-bar';tile.append(bar);
    const name=document.createElement('span');name.className='camera-tile-name';name.textContent='Камера '+(index+1);name.tabIndex=0;name.title='Перетягнути малу камеру';bar.append(name);
    const state=document.createElement('span');state.className='camera-tile-status';bar.append(state);
    const c={id,tile,video,state,popup:null,detached:false,player:null};cams[id]=c;
    c.swap=button(bar,'⇄','Зробити камеру '+(index+1)+' основною',()=>{active=id;render()});
    c.sound=button(bar,'♪','Увімкнути / вимкнути звук камери '+(index+1),()=>{video.muted=!video.muted;c.sound.setAttribute('aria-pressed',String(!video.muted));video.play().catch(()=>{state.textContent='Відтворення заблоковано'})});
    c.full=button(bar,'⛶','Повний екран камери '+(index+1),()=>{const p=document.fullscreenElement?document.exitFullscreen():tile.requestFullscreen();p?.catch(()=>{state.textContent='Повний екран недоступний'})});
    c.out=button(bar,'↗','Винести камеру '+(index+1)+' в окреме вікно',()=>detach(c));
    const placeholder=document.createElement('div');placeholder.className='camera-placeholder';placeholder.hidden=true;tile.append(placeholder);c.placeholder=placeholder;
    button(placeholder,'↙ Повернути','Повернути камеру '+(index+1)+' в інтерфейс',()=>{if(c.popup&&!c.popup.closed)c.popup.close();c.popup=null;c.detached=false;render()});
    const grip=button(tile,'◢','Змінити розмір малої камери',()=>{});grip.className='camera-grip';c.grip=grip;
    video.onclick=()=>{if(mode==='both'&&active!==id){active=id;render()}else video.play().catch(()=>{})};
    c.player=harpoonVideo(video,state,location.protocol+'//'+location.hostname+':8889/'+id+'web/whep');stage.prepend(tile);
    for(const [el,resize] of [[name,false],[grip,true]]){
      let origin=null;
      el.addEventListener('pointerdown',e=>{if(active===id||mode!=='both'||e.button!==0)return;e.preventDefault();const a=tile.getBoundingClientRect(),b=stage.getBoundingClientRect();origin={x:e.clientX,y:e.clientY,left:a.left-b.left,top:a.top-b.top,width:a.width,height:a.height};el.setPointerCapture(e.pointerId)});
      el.addEventListener('pointermove',e=>{if(!origin)return;const dx=e.clientX-origin.x,dy=e.clientY-origin.y;pipRect=resize?{...origin,width:origin.width+dx,height:origin.height+dy}:{...origin,left:origin.left+dx,top:origin.top+dy};placePip(c)});
      const end=()=>{origin=null;try{if(pipRect)localStorage.setItem('harpoonCameraPipRect',JSON.stringify(pipRect))}catch(e){}};
      el.addEventListener('pointerup',end);el.addEventListener('pointercancel',end);el.addEventListener('lostpointercapture',end);
      el.addEventListener('keydown',e=>{const d={ArrowLeft:[-10,0],ArrowRight:[10,0],ArrowUp:[0,-10],ArrowDown:[0,10]}[e.key];if(!d||active===id||mode!=='both')return;e.preventDefault();const a=tile.getBoundingClientRect(),b=stage.getBoundingClientRect();pipRect={left:a.left-b.left,top:a.top-b.top,width:a.width,height:a.height};if(resize){pipRect.width+=d[0];pipRect.height+=d[1]}else{pipRect.left+=d[0];pipRect.top+=d[1]}placePip(c);end()});
    }
  }
  function placePip(c){if(!pipRect)return;const w=stage.clientWidth,h=stage.clientHeight,width=Math.min(w,Math.max(170,pipRect.width)),height=Math.min(h,Math.max(120,pipRect.height));pipRect={left:Math.max(0,Math.min(pipRect.left,w-width)),top:Math.max(0,Math.min(pipRect.top,h-height)),width,height};Object.assign(c.tile.style,{left:pipRect.left+'px',top:pipRect.top+'px',width:width+'px',height:height+'px',right:'auto',bottom:'auto'})}
  try{const r=JSON.parse(localStorage.getItem('harpoonCameraPipRect'));if(r&&['left','top','width','height'].every(k=>Number.isFinite(r[k])))pipRect=r}catch(e){}
  function render(){
    for(const [key,b] of Object.entries(selectors))b.setAttribute('aria-pressed',String(key===(mode==='both'?'both':active)));
    for(const c of Object.values(cams)){
      const mini=mode==='both'&&active!==c.id,visible=mode==='both'||active===c.id;
      c.tile.hidden=!visible;c.tile.classList.toggle('camera-mini',mini);c.tile.removeAttribute('style');c.swap.hidden=!mini;c.grip.hidden=!mini;c.placeholder.hidden=!c.detached;c.sound.disabled=c.detached;c.full.disabled=c.detached;
      if(mini)placePip(c);if(visible&&!c.detached)c.player.start();else c.player.stop();if(c.detached)c.state.textContent='В окремому вікні';c.sound.setAttribute('aria-pressed',String(!c.video.muted));
    }
    try{localStorage.setItem('harpoonVideoSource',active);localStorage.setItem('harpoonCameraMode',mode)}catch(e){}
  }
  function detach(c){
    if(c.popup&&!c.popup.closed){c.popup.focus();return}
    const p=window.open('','harpoon-'+c.id+'-'+location.host,'popup,width=1000,height=700,resizable=yes');if(!p){alert('Дозвольте спливні вікна для цього сайту й натисніть ↗ ще раз.');return}
    c.popup=p;c.detached=true;c.player.stop();render();const base=location.origin,label=c.id==='cam1'?'Камера 1':'Камера 2';
    p.document.open();p.document.write('<!doctype html><html lang="uk"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>HARPOON · '+label+'</title><style>html,body{margin:0;height:100%;background:#020708;color:#dceeed;font:14px Arial}body{display:flex;flex-direction:column}header{display:flex;align-items:center;gap:10px;padding:8px;background:#10252e;flex-wrap:wrap}#state{margin-right:auto;color:#a9c5bd}button{padding:7px 10px;background:#24444c;color:white;border:0;border-radius:6px;cursor:pointer}video{width:100%;flex:1;min-height:0;object-fit:contain}</style></head><body><header><b>'+label+'</b><span id="state">З’єднання…</span><button id="sound">Звук: вимк.</button><button id="full">⛶</button><button id="back">↙ Повернути</button></header><video autoplay muted playsinline></video><script src="'+base+'/reader.js"></script><script>'+harpoonVideo.toString()+';('+harpoonCameraWindow.toString()+')('+JSON.stringify(base)+','+JSON.stringify(c.id)+');</script></body></html>');p.document.close();p.focus();
  }
  const timer=setInterval(()=>{let changed=false;for(const c of Object.values(cams))if(c.detached&&(!c.popup||c.popup.closed)){c.detached=false;c.popup=null;changed=true}if(changed)render()},500);
  new ResizeObserver(()=>{for(const c of Object.values(cams))if(mode==='both'&&c.id!==active)placePip(c)}).observe(stage);
  window.addEventListener('beforeunload',()=>{clearInterval(timer);for(const c of Object.values(cams))c.player.stop()},{once:true});render();
};
