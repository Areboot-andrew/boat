/* Pi03 preview: all drive values stay in this browser. No control POSTs. */
(() => {
 'use strict';
 const $=s=>document.querySelector(s), make=(tag,cls,html)=>{const e=document.createElement(tag);e.className=cls;e.innerHTML=html;return e};
 document.title='HARPOON · PILOT β · Pi03';
 $('header h1').innerHTML='HARPOON <small>PILOT β / 03</small>';
 $('.monitor-note').textContent='ПЕРЕГЛЯД БЕТИ · Живі камери / телеметрія. Служба керування ще не підключена. Керування нижче — лише тест вводу, команди не передаються.';
 const top=make('div','beta-top-actions','<span>Керування — preview</span><button disabled title="Бета не підключена до служби керування">MANUAL</button><button disabled>ARM</button><button disabled>DISARM</button><button class="beta-stop" title="Скинути лише локальний тест вводу">STOP · тест</button>');
 $('header').append(top);
 const dialog=make('dialog','beta-dialog','<div class="beta-dialog-head"><h2>Навігація та телеметрія</h2><button aria-label="Закрити">✕</button></div><div class="beta-tabs" role="tablist"></div><div class="beta-pages"></div>');document.body.append(dialog);
 dialog.querySelector('.beta-dialog-head button').onclick=()=>dialog.close();
 const telemetry=$('.telemetry-panel'), diagnostics=$('.diagnostic-panel');
 const cards=telemetry.querySelector('.unified-cards');
 const groups=[['Навігація',['tmDistance','navLink','navPosition','navSatellites','navHeading']],['АКБ',['bmPower','bmCurrent','bmSoc','bmLink','bmVoltage','bmRemaining','bmFull','bmCells','bmMin','bmMax','bmDelta','bmMos','bmT1','bmT2']],['Витрати',['bmWh','bmAh','tmAverage','tmRange']]];
 const pages=[];
 function tab(name,page){const b=make('button','','');b.textContent=name;b.setAttribute('role','tab');dialog.querySelector('.beta-tabs').append(b);dialog.querySelector('.beta-pages').append(page);pages.push({b,page});b.onclick=()=>pages.forEach(p=>{p.page.hidden=p!==pages.find(x=>x.b===b);p.b.setAttribute('aria-selected',String(p.b===b))});return b;}
 for(const [name,ids] of groups){const page=make('section','cards','');for(const id of ids){const node=cards.querySelector('#'+id);if(node)page.append(node.closest('.card'));}tab(name,page);}
 tab('Система',diagnostics);
 const sessions=telemetry.querySelector('.session-controls');sessions.inert=true;sessions.prepend(make('p','notice','У беті журнал доступний лише для перегляду. Запис / видалення — у старому інтерфейсі.'));
 const logsDialog=make('dialog','beta-dialog','<div class="beta-dialog-head"><h2>Логи</h2><button aria-label="Закрити логи">✕</button></div>');
 logsDialog.id='beta-logs-dialog';dialog.id='beta-telemetry-dialog';
 document.body.append(logsDialog);
 logsDialog.querySelector('button').onclick=()=>logsDialog.close();
 // Keep legacy IDs alive for the existing telemetry scripts, without duplicate visible blocks.
 telemetry.hidden=true;
 const consolePage=make('section','','<h3>Консоль тесту вводу</h3><p>Локальні події браузера, не відповіді польотника.</p><pre aria-live="polite"></pre>');
 logsDialog.append(consolePage,sessions);pages[0].b.click();
 const panel=make('section','beta-controls',`<select aria-label="Джерело вводу"><option value="keyboard">⌨ Клавіатура</option><option value="gamepad">◉ Джойстик</option></select><button data-test>Тест вводу</button><button data-left aria-label="Кермо ліворуч">←</button><button data-right aria-label="Кермо праворуч">→</button><button data-up aria-label="Тяга">↑</button><label>Ліміт <input type="range" min="0" max="50" value="25"><span data-cap>25%</span></label><button data-cruise>Круїз · тест</button><output>Кермо 0% · тяга 0%</output><span class="beta-spacer"></span><button data-telemetry>Навігація / телеметрія</button><button data-log>Логи</button><a data-old>Старий інтерфейс ↗</a><span class="beta-input-state">Ввід вимкнено. Space не викликає STOP.</span>`);
 const dock=make('section','beta-dock','');
 dock.setAttribute('aria-label','Показники та керування');
 $('.camera-panel').after(dock);
 dock.append($('.bottom-hud'));
 $('header').append(panel);
 const piStats=make('div','beta-pi-stats','');
 dock.querySelector('.bottom-hud').append(piStats);
 for(const id of ['connection','platformStatus']){const node=$('#'+id);if(node)piStats.append(node);}
 // Keep one live map instance, outside the video stage. Existing popup stays available.
 const stage=$('.camera-stage'),mapPanel=$('#mapPanel');
 const visual=make('div','beta-visual',''),mapSlot=make('aside','beta-map-slot','');
 stage.before(visual);visual.append(stage,mapSlot);mapSlot.append(mapPanel);
 mapPanel.classList.remove('map-floating');mapPanel.classList.add('beta-map-docked');
 for(const id of ['mapFloat','mapResize','mapExpand']){const b=$('#'+id);if(b)b.hidden=true;}
 const drag=$('#mapDrag');drag.textContent='КАРТА';drag.removeAttribute('role');drag.tabIndex=-1;
 for(const type of ['pointerdown','keydown'])drag.addEventListener(type,e=>e.stopImmediatePropagation(),true);
 function fitVisual(){const width=visual.clientWidth;const narrow=width<850;
   const available=innerHeight-$('header').getBoundingClientRect().height-dock.getBoundingClientRect().height-20;
   const cameraWidth=narrow?width:Math.min(width*.76,Math.max(180,available)*16/9);
   visual.style.setProperty('--camera-width',cameraWidth+'px');
   visual.style.setProperty('--camera-height',cameraWidth*9/16+'px');
 }
 const layoutObserver=new ResizeObserver(fitVisual);for(const node of [visual,$('header'),dock])layoutObserver.observe(node);window.addEventListener('resize',fitVisual);fitVisual();
 // Move the existing selector, retaining camera-player event handlers.
 function dockCameraModes(){const modes=$('.camera-mode'),tile=stage.querySelector('.camera-tile:not([hidden]):not(.camera-mini)'),bar=tile?.querySelector('.camera-tile-bar');if(bar&&modes&&modes.parentElement!==bar)bar.insertBefore(modes,bar.querySelector('button'));}
 const cameraBarObserver=new MutationObserver(dockCameraModes);cameraBarObserver.observe(stage,{subtree:true,childList:true,attributes:true,attributeFilter:['class','hidden']});cameraBarObserver.observe($('.camera-head'),{subtree:true,childList:true});dockCameraModes();
 // Beta-only PiP bounds: video + map. Capture before the legacy stage-only handlers.
 const pipKey='harpoonBetaWidePip';let pip=null,pipGesture=null,pipFrame=0;
 try{const p=JSON.parse(localStorage.getItem(pipKey));if(p&&['left','top','width','height'].every(k=>Number.isFinite(p[k])))pip=p;}catch{}
 function placeWidePip(){
   const tile=visual.querySelector('.camera-mini');if(!tile||tile.hidden||document.fullscreenElement||!pip)return;
   const box=visual.getBoundingClientRect(),base=stage.getBoundingClientRect();
   if(!box.width||!box.height)return;
   const width=Math.min(box.width,Math.max(170,pip.width)),height=Math.min(box.height,Math.max(120,pip.height));
   const left=Math.max(0,Math.min(pip.left,box.width-width)),top=Math.max(0,Math.min(pip.top,box.height-height));
   const styles={left:(left+box.left-base.left)+'px',top:(top+box.top-base.top)+'px',width:width+'px',height:height+'px',right:'auto',bottom:'auto'};
   for(const [k,v] of Object.entries(styles))if(tile.style[k]!==v)tile.style[k]=v;
 }
 function queuePip(){if(!pipFrame)pipFrame=requestAnimationFrame(()=>{pipFrame=0;placeWidePip();});}
 function savePip(){try{localStorage.setItem(pipKey,JSON.stringify(pip));}catch{}}
 visual.addEventListener('pointerdown',e=>{
   const handle=e.target.closest('.camera-tile-name,.camera-grip'),tile=handle?.closest('.camera-mini');
   if(!tile||tile.hidden||e.button!==0||document.fullscreenElement)return;
   e.preventDefault();e.stopImmediatePropagation();
   const a=tile.getBoundingClientRect(),b=visual.getBoundingClientRect();
   pip={left:a.left-b.left,top:a.top-b.top,width:a.width,height:a.height};
   pipGesture={id:e.pointerId,x:e.clientX,y:e.clientY,rect:{...pip},resize:handle.matches('.camera-grip')};
   visual.setPointerCapture(e.pointerId);
 },true);
 visual.addEventListener('pointermove',e=>{
   if(!pipGesture||e.pointerId!==pipGesture.id)return;e.preventDefault();e.stopImmediatePropagation();
   const g=pipGesture,dx=e.clientX-g.x,dy=e.clientY-g.y;
   pip=g.resize?{...g.rect,width:g.rect.width+dx,height:g.rect.height+dy}:{...g.rect,left:g.rect.left+dx,top:g.rect.top+dy};
   placeWidePip();
 },true);
 for(const type of ['pointerup','pointercancel','lostpointercapture'])visual.addEventListener(type,e=>{
   if(!pipGesture||e.pointerId!==pipGesture.id)return;e.stopImmediatePropagation();pipGesture=null;savePip();
   if(visual.hasPointerCapture(e.pointerId))visual.releasePointerCapture(e.pointerId);
 },true);
 // Arrow keys on a PiP handle must move the window, never reach steering controls.
 visual.addEventListener('keydown',e=>{
   const handle=e.target.closest('.camera-tile-name,.camera-grip'),tile=handle?.closest('.camera-mini');
   const d={ArrowLeft:[-10,0],ArrowRight:[10,0],ArrowUp:[0,-10],ArrowDown:[0,10]}[e.key];
   if(!tile||!d)return;e.preventDefault();e.stopImmediatePropagation();
   const a=tile.getBoundingClientRect(),b=visual.getBoundingClientRect();pip={left:a.left-b.left,top:a.top-b.top,width:a.width,height:a.height};
   if(handle.matches('.camera-grip')){pip.width+=d[0];pip.height+=d[1];}else{pip.left+=d[0];pip.top+=d[1];}
   placeWidePip();savePip();
 },true);
 new MutationObserver(queuePip).observe(stage,{subtree:true,childList:true,attributes:true,attributeFilter:['class','style','hidden']});
 new ResizeObserver(queuePip).observe(visual);document.addEventListener('fullscreenchange',queuePip);
 const extra=make('div','beta-extra','');dock.querySelector('.bottom-hud').append(extra,piStats);
 function metric(label){const e=make('div','beta-metric','<small></small><b>—</b>');e.querySelector('small').textContent=label;extra.append(e);return e.querySelector('b');}
 const distance=metric('ШЛЯХ'),soc=metric('АКБ'),gps=metric('GPS'),browserLink=metric('БРАУЗЕР ↔ PI'),internet=metric('ІНТЕРНЕТ БОРТА');
 // Move canonical values: existing telemetry updater continues to own these IDs.
 for(const [id,dest] of [['tmDistance',distance],['bmSoc',soc]]){const value=$('#'+id),card=value.closest('.card');dest.replaceWith(value);card.remove();}
 const num=x=>typeof x==='number'&&Number.isFinite(x);
 let linkHistory=[];
 async function refreshExtra(){
   const begin=performance.now();
   try{const r=await fetch('/telemetry',{cache:'no-store',signal:AbortSignal.timeout(2500)});if(!r.ok)throw Error('HTTP');const d=await r.json();
     const ms=Math.round(performance.now()-begin);linkHistory.push(true);linkHistory=linkHistory.slice(-30);
     browserLink.textContent=ms+' мс';browserLink.title='Час HTTP-запиту, не ping. Невдалі запити: '+linkHistory.filter(x=>!x).length+'/'+linkHistory.length;
     const g=d.gps||{};gps.textContent=!g.link_ok?'Немає зв’язку':(g.position_valid?'Фікс '+g.fix_quality:'Без фікса')+' · '+(num(g.satellites)?g.satellites:'—')+' суп.';
     gps.title='HDOP: '+(num(g.hdop)?g.hdop:'—');
   }catch{linkHistory.push(false);linkHistory=linkHistory.slice(-30);browserLink.textContent='Немає зв’язку';gps.textContent='—';$('#tmDistance').textContent=$('#bmSoc').textContent='—';}
   try{const r=await fetch('/diagnostics',{cache:'no-store',signal:AbortSignal.timeout(2500)});if(!r.ok)throw Error('HTTP');const d=await r.json(),n=d.network||{};
     const age=d.uptime_s-n.checked_uptime_s;
     if(d.stale||!num(age)||age<0||age>90)throw Error('Stale');
     const results=Object.values(n.internet_tcp_443||{}),times=Object.values(n.tcp_connect_ms||{}).filter(num);
     const ok=results.filter(x=>x===true).length;
     internet.textContent=!results.length?'—':ok===0?'Недоступний':ok<results.length?'Частковий доступ':'Доступ є';
     if(ok&&times.length)internet.textContent+=' · '+Math.round(Math.max(...times))+' мс';
     internet.title='TCP-з’єднання :443 до контрольних адрес, не швидкість каналу і не втрати пакетів. Вік перевірки '+Math.round(age)+' с. DNS: '+(n.dns_ok===true?'OK':n.dns_ok===false?'помилка':'—');
   }catch{internet.textContent='—';internet.title='Немає свіжої діагностики';}
   setTimeout(refreshExtra,3000);
 }
 refreshExtra();
 const old=new URL(location.href);old.port='8080';old.pathname='/';old.search='';panel.querySelector('[data-old]').href=old.href;
 const status=make('div','beta-status','Діагностика: очікування…');piStats.append(status);
 const ds=$('#diag-summary');if(ds)new MutationObserver(()=>{status.textContent='Стан борта: '+ds.textContent+' · докладніше в «Система»';}).observe(ds,{childList:true,subtree:true,characterData:true});
 panel.querySelector('[data-telemetry]').onclick=()=>{logsDialog.close();pages[0].b.click();dialog.showModal();reset('Відкрито телеметрію');};
 panel.querySelector('[data-log]').onclick=()=>{dialog.close();logsDialog.showModal();reset('Відкрито логи');};
 if(window.harpoonLiveControl){window.harpoonLiveControl({panel,top,dialog,logsDialog,consolePage,sessions,pages});return;}
 let enabled=false,cruise=null,keys=new Set(),last=performance.now(),applied=[0,0],target=[0,0],start=[0,0],since=last,selectedPad=null;
 const source=panel.querySelector('select'),limit=panel.querySelector('input'),out=panel.querySelector('output'),note=panel.querySelector('.beta-input-state'),logs=[];
 function log(t){logs.push(new Date().toLocaleTimeString()+' · '+t);consolePage.querySelector('pre').textContent=logs.slice(-60).join('\n');}
 function reset(why){enabled=false;cruise=null;keys.clear();applied=[0,0];target=[0,0];selectedPad=null;panel.querySelector('[data-test]').textContent='Тест вводу';panel.querySelector('[data-cruise]').textContent='Круїз · тест';out.textContent='Кермо 0% · тяга 0%';log(why);}
 function pad(){try{return Array.from(navigator.getGamepads?.()||[]).find(p=>p?.connected&&p.mapping==='standard');}catch{return null;}}
 const clamp=(x,a,b)=>Math.max(a,Math.min(b,x)), dead=x=>Math.abs(x)<.06?0:Math.sign(x)*(Math.abs(x)-.06)/.94;
 function axes(p){return [dead(clamp(p.axes[2],-1,1)),clamp((1-p.axes[1])/2,0,1)];}
 panel.querySelector('[data-test]').onclick=()=>{if(enabled){reset('Тест зупинено');return;}if(source.value==='gamepad'){const p=pad();if(!p||p.axes.length<4){note.textContent='Потрібен стандартний gamepad і доступ Gamepad API (HTTPS або localhost). Натисни кнопку на джойстику.';return;}const [s,t]=axes(p);if(!Number.isFinite(s)||!Number.isFinite(t)||Math.abs(s)>.05||t>.03){note.textContent='Перед тестом: лівий стік униз (0), правий у центр.';return;}selectedPad=p.index;}enabled=true;panel.querySelector('[data-test]').textContent='Завершити тест';note.textContent='Лише локальний тест · лівий низ 0 / центр 50 / верх 100; правий −100…+100. Без команд.';log('Локальний тест '+source.value);};
 top.querySelector('.beta-stop').onclick=()=>reset('STOP: локальний ввід скинуто; на польотник нічого не передано');
 source.onchange=()=>reset('Змінено джерело вводу');
 limit.oninput=()=>{panel.querySelector('[data-cap]').textContent=limit.value+'%';if(cruise!==null)cruise=Math.min(cruise,Number(limit.value)/100);applied[1]=Math.min(applied[1],Number(limit.value)/100);};
 panel.querySelector('[data-cruise]').onclick=()=>{if(!enabled||source.value!=='keyboard')return;cruise=cruise===null?Number(limit.value)/100:null;panel.querySelector('[data-cruise]').textContent=cruise===null?'Круїз · тест':'Утримання '+Math.round(cruise*100)+'% · тест';};
 for(const [attr,key] of [['left','ArrowLeft'],['right','ArrowRight'],['up','ArrowUp']]){const b=panel.querySelector('[data-'+attr+']');b.onpointerdown=e=>{if(enabled&&source.value==='keyboard'){keys.add(key);b.setPointerCapture(e.pointerId);}};for(const ev of ['pointerup','pointercancel','lostpointercapture'])b.addEventListener(ev,()=>keys.delete(key));}
 window.addEventListener('keydown',e=>{if(!enabled||source.value!=='keyboard'||dialog.open||logsDialog.open||e.target.matches('input,select,textarea,button'))return;if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.code)){e.preventDefault();keys.add(e.code);if(e.code==='ArrowDown')cruise=null;}});
 window.addEventListener('keyup',e=>keys.delete(e.code));
 window.addEventListener('blur',()=>reset('Втрачено фокус'));
 document.addEventListener('visibilitychange',()=>{if(document.hidden)reset('Вкладку приховано');});
 window.addEventListener('gamepaddisconnected',()=>{if(source.value==='gamepad')reset('Джойстик відключено');});
 function frame(now){const cap=Number(limit.value)/100;let next=[0,0];if(enabled){if(source.value==='gamepad'){const p=pad();if(!p||p.index!==selectedPad||p.axes.length<4){reset('Джойстик недоступний');}else{const [s,t]=axes(p);if(!Number.isFinite(s)||!Number.isFinite(t))reset('Невалідні осі');else next=[s*.6,t*cap];}}else next=[(keys.has('ArrowRight')?.6:0)-(keys.has('ArrowLeft')?.6:0),keys.has('ArrowDown')?0:Math.min(cap,cruise??(keys.has('ArrowUp')?cap:0))];}
 const f=Math.min(1,(now-since)/300);applied=applied.map((_,i)=>start[i]+(target[i]-start[i])*f);if(next.some((v,i)=>Math.abs(v-target[i])>.001)){start=[...applied];target=next;since=now;}applied[1]=Math.min(applied[1],cap);if(!enabled)applied=[0,0];out.textContent=`Кермо ${Math.round(applied[0]*100)}% · тяга ${Math.round(applied[1]*100)}%`;requestAnimationFrame(frame);}
 requestAnimationFrame(frame);
 log('Pi03 PILOT β: backend керування відсутній; усі кнопки вводу — тільки preview.');
})();
