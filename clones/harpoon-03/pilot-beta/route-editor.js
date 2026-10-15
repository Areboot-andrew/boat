(()=>{'use strict';
const api=window.harpoonAuto;if(!api)return;
const labels={cruise:'Крейсерська тяга, %',max_throttle:'Максимальна тяга, %',turn_throttle:'Тяга на дузі, % (до 25)',max_steer:'Максимальне кермо, %',turn_radius:'Радіус плавного повороту, м',radius:'Допуск проходження точки, м',corridor:'Макс. відхилення від лінії, м',lookahead:'Випередження на прямій, м',turn_distance:'Гальмування перед дугою, м',turn_angle:'Зменшення тяги: помилка курсу, °',kp:'Корекція курсу: % керма / °',ki:'Накопичення поправки сопла, % / ° / с',trim_limit:'Максимальна поправка сопла, %',steer_rate:'Перекладання керма, %/с',throttle_rate:'Наростання тяги, %/с',gps_age:'Максимальний вік GPS, с',heading_offset:'Поправка азимуту, °',steer_sign:'Напрям керма: 1 або −1'};
const bar=document.createElement('div');bar.className='auto-bar';bar.innerHTML='<button data-edit>✎ Точки</button><button data-settings title="Налаштування маршруту">⚙</button><button data-fit title="Показати весь маршрут">⌖</button><button data-start>▶ Маршрут</button><button data-return>↶ Автоповернення</button><button class="auto-stop">STOP · тяга</button><div class="route-edit-tools" hidden><button data-save>✓ Зберегти</button><button data-undo>↶ Останню</button><button data-cancel>Скасувати</button></div><span role="status"></span>';document.querySelector('.beta-map-slot').append(bar);
const modal=document.createElement('dialog');modal.className='beta-dialog auto-dialog';modal.innerHTML='<div class="beta-dialog-head"><h2>Маршрут і повороти · Pi03</h2><button data-close>✕</button></div><p>Бірюзова лінія — розрахована траєкторія керування. Дуги зрізають кути: перевір перешкоди. Радіус плану не гарантує фізичного радіуса човна. Зворотний записаний трек поки йде старим алгоритмом без цих дуг.</p><form><div class="auto-fields"></div><details><summary>Координати точок</summary><textarea rows="5" aria-label="Координати точок"></textarea></details><div class="auto-actions"><button type="button" data-pick>✎ Редагувати на карті</button><button type="submit">Зберегти налаштування й точки</button></div></form><p class="auto-message" role="status"></p>';document.body.append(modal);
const fields=modal.querySelector('.auto-fields');for(const [key,label] of Object.entries(labels)){const l=document.createElement('label');l.textContent=label;const i=document.createElement('input');i.type='number';i.step='any';i.name=key;l.append(i);fields.append(l);}
const status=bar.querySelector('span'),msg=modal.querySelector('.auto-message'),area=modal.querySelector('textarea'),tools=bar.querySelector('.route-edit-tools');
const launch=document.createElement('dialog');launch.className='beta-dialog auto-start-dialog';launch.innerHTML='<div class="beta-dialog-head"><h2>Початок автоходу</h2><button data-dismiss>✕</button></div><p data-summary></p><p>Маршрут зберігається автоматично до запуску. Якщо ще немає сесії: закрий це вікно, зверху ввімкни керування → MANUAL → ARM, тоді знову натисни «Маршрут».</p><label><input type="checkbox" data-test-consent> Кермо вільне, випробування безпечне; дозволяю тест ±10% сигналу з нульовою тягою.</label><div class="auto-actions"><button data-servo="-1" disabled>← Тест керма 10%</button><button data-servo="1" disabled>Тест керма 10% →</button><button data-servo="0" disabled>Центр</button></div><p>Кожен тест триває 0,6 с, потім запитується центр. Це команда, не доказ руху — перевір кермо фізично.</p><label><input type="checkbox" data-verified> Кермо перевірив: ліво / право правильні. Акваторія вільна, дозволяю рух.</label><div class="auto-actions"><button data-go disabled>Почати рух</button><button data-abort>Скасувати</button><button data-stop>STOP · тяга</button></div><p role="status" data-launch-message></p>';document.body.append(launch);
let launchBack=false;
const launchMessage=t=>launch.querySelector('[data-launch-message]').textContent=t;
launch.querySelector('[data-test-consent]').onchange=e=>{for(const b of [-1,0,1])launch.querySelector('[data-servo="'+b+'"]').disabled=!e.target.checked;};
for(const direction of [-1,0,1])launch.querySelector('[data-servo="'+direction+'"]').onclick=()=>{try{api.testSteer(direction);launchMessage('Тест '+direction*10+'% запитано; перевір фактичний рух керма. Тяга 0.');}catch(e){launchMessage(e.message);}};
launch.querySelector('[data-verified]').onchange=e=>launch.querySelector('[data-go]').disabled=!e.target.checked;
const dismiss=()=>{api.cancelTest?.();launch.close();};
launch.querySelector('[data-dismiss]').onclick=dismiss;launch.querySelector('[data-abort]').onclick=dismiss;launch.addEventListener('close',()=>api.cancelTest?.());
launch.querySelector('[data-stop]').onclick=()=>{api.stop();dismiss();};
launch.querySelector('[data-go]').onclick=async()=>{if(!launch.querySelector('[data-verified]').checked)return;const b=launch.querySelector('[data-go]');b.disabled=true;try{await api.start(launchBack);launch.close();message('Автохід запущено — STOP доступний зверху й на мапі');}catch(e){launchMessage(e.message);}finally{b.disabled=!launch.querySelector('[data-verified]').checked;}};
let draft=[],config=null,editing=false,layer=null,bound=null,loaded=false,version=0,timer=null,valid=false,confirmType=null,until=0,insertAfter=null,savedKey='',saving=false,pendingSaved=null,previewError='';
const routeKey=(c,r)=>JSON.stringify([Object.entries(c).sort(([a],[b])=>a.localeCompare(b)),r]);
const dirty=()=>routeKey(config,draft)!==savedKey;
function distanceText(){let d=0;for(let i=1;i<draft.length;i++){const a=draft[i-1],b=draft[i],r=Math.PI/180,h=Math.sin((b[0]-a[0])*r/2)**2+Math.cos(a[0]*r)*Math.cos(b[0]*r)*Math.sin((b[1]-a[1])*r/2)**2;d+=6371000*2*Math.asin(Math.sqrt(Math.min(1,h)));}return `${draft.length} точок · ламана ${d<1000?d.toFixed(1)+' м':(d/1000).toFixed(2)+' км'}`;}
const mapNow=()=>typeof map!=='undefined'?map:null;
function message(t){status.textContent=t;msg.textContent=t;}
function resetConfirm(){confirmType=null;bar.querySelector('[data-start]').textContent='▶ Маршрут';bar.querySelector('[data-return]').textContent='↶ Автоповернення';}
function syncText(){area.value=draft.map(p=>p.join(', ')).join('\n');}
function readFields(){const c={};for(const k of Object.keys(labels))c[k]=Number(fields.querySelector('[name='+k+']').value);return c;}
function fillFields(){for(const k of Object.keys(labels))fields.querySelector('[name='+k+']').value=config[k];syncText();}
function textPoints(){const r=area.value.trim()?area.value.trim().split(/\n+/).map(l=>l.trim().split(/[,;\s]+/).map(Number)):[];if(r.some(p=>p.length!==2||p.some(n=>!Number.isFinite(n))))throw Error('Кожен рядок: широта, довгота');return r;}
function loadSaved(){const n=pendingSaved||api.status()?.autonav;if(!n)throw Error('Немає стану контролера');config={...n.settings};draft=n.route.map(p=>[...p]);savedKey=routeKey(config,draft);loaded=true;fillFields();}
function ensureMap(){if(mapNow()||!window.L)return;map=L.map('gpsMap',{zoomControl:false}).setView(draft[0]||[0,0],draft.length?17:2);L.control.zoom({position:'bottomright'}).addTo(map);L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap'}).addTo(map);map.on('dragstart',()=>{follow=false;});new ResizeObserver(()=>map.invalidateSize()).observe(document.getElementById('gpsMap'));document.querySelector('.beta-map-slot').classList.add('route-planning-map');}
function begin(){if(editing)return;const n=api.status();if(n?.armed||n?.lease_active)throw Error('Редагування: спочатку DISARM і завершення керування');loadSaved();ensureMap();editing=true;tools.hidden=false;insertAfter=null;resetConfirm();try{follow=false;}catch{}paint();}
function end(){editing=false;tools.hidden=true;insertAfter=null;resetConfirm();}
function fit(){const m=mapNow();if(m&&draft.length){try{follow=false;}catch{}m.fitBounds(L.latLngBounds(draft),{paddingTopLeft:[45,145],paddingBottomRight:[45,80],maxZoom:19});}}
function paint(){
 const m=mapNow();if(!m||!window.L){message('Карта очікує GPS; координати можна задати через ⚙');return;}version++;const token=version;clearTimeout(timer);valid=false;previewError='';layer?.remove();layer=L.layerGroup().addTo(m);const targetLayer=layer;
 if(draft.length>1)L.polyline(draft,{color:'#c9d3d9',weight:3,opacity:.9,dashArray:'4 6',interactive:false}).addTo(layer);
 draft.forEach((p,i)=>{
  L.circle(p,{radius:config.radius,color:'#63ddc9',weight:1,opacity:.35,fillOpacity:.03,interactive:false}).addTo(layer);
  const marker=L.marker(p,{draggable:editing,keyboard:true,title:`Точка ${i+1}`,icon:L.divIcon({className:'route-waypoint',html:`<span>${i+1}</span>`,iconSize:[28,28],iconAnchor:[14,14]})}).addTo(layer);
  if(editing){marker.on('dragstart',()=>{version++;valid=false;resetConfirm();});marker.on('dragend',e=>{const ll=e.target.getLatLng();draft[i]=[+ll.lat.toFixed(7),+ll.lng.toFixed(7)];syncText();paint();});
   const popup=document.createElement('div');popup.className='route-point-popup';const title=document.createElement('b');title.textContent=`Точка ${i+1}`;popup.append(title);
   const del=document.createElement('button');del.textContent='Видалити';del.onclick=()=>{draft.splice(i,1);insertAfter=null;syncText();paint();};popup.append(del);
   const ins=document.createElement('button');ins.textContent='Додати після';ins.onclick=()=>{insertAfter=i;m.closePopup();message(`Клікни на карті: нова точка після ${i+1}`);};popup.append(ins);marker.bindPopup(popup);
  }
 });
 if(draft.length<2){message(editing?'Клікни на мапі: постав щонайменше дві точки. Перетягуй за номер.':'✎ Точки — створити маршрут на мапі');return;}
 message(distanceText()+' · розрахунок плавних поворотів…');timer=setTimeout(async()=>{try{const p=await api.preview(config,draft);if(token!==version)return;
  L.polyline(p.points,{color:'#0a242b',weight:8,opacity:.8,interactive:false}).addTo(targetLayer);L.polyline(p.points,{color:'#5ff1cf',weight:3,opacity:1,interactive:false}).addTo(targetLayer);valid=true;
  message(`${editing?'Редагування · ':''}${draft.length} точок · ${p.length_m} м · радіус ${p.turn_radius} м${editing?' · перетягни номер / клікни для видалення':''}`);
 }catch(e){if(token===version){valid=false;previewError=e.message;message(distanceText()+' · траєкторію не побудовано: '+previewError);}}},200);
}
bar.querySelector('[data-edit]').onclick=()=>{try{begin();}catch(e){message(e.message);}};
bar.querySelector('[data-settings]').onclick=()=>{try{begin();fillFields();modal.showModal();}catch(e){message(e.message);}};
bar.querySelector('[data-fit]').onclick=fit;
bar.querySelector('[data-undo]').onclick=()=>{draft.pop();insertAfter=null;syncText();paint();};
bar.querySelector('[data-cancel]').onclick=()=>{end();loadSaved();paint();};
async function save(){if(saving)throw Error('Збереження вже триває');if(draft.length===1)throw Error('Потрібно дві точки або порожній маршрут');const n=api.status();if(n?.armed||n?.lease_active)throw Error('Не збережено: спочатку DISARM і вимкни керування; точки залишились у редакторі');const c={...config},r=draft.map(p=>[...p]);saving=true;message('Збереження маршруту…');tools.inert=true;fields.inert=true;area.disabled=true;document.getElementById('gpsMap').inert=true;try{if(r.length)await api.preview(c,r);await api.save(c,r);config=c;draft=r;savedKey=routeKey(c,r);pendingSaved={settings:c,route:r};end();paint();message('Збережено на Pi03. Рух не запущено.');}finally{saving=false;tools.inert=false;fields.inert=false;area.disabled=false;document.getElementById('gpsMap').inert=false;}}
bar.querySelector('[data-save]').onclick=async()=>{try{await save();}catch(e){message(e.message);}};
modal.querySelector('[data-close]').onclick=()=>modal.close();
modal.querySelector('[data-pick]').onclick=()=>{try{draft=textPoints();config=readFields();syncText();paint();modal.close();}catch(e){message(e.message);}};
modal.querySelector('form').onsubmit=async e=>{e.preventDefault();try{draft=textPoints();config=readFields();await save();modal.close();}catch(e){message(e.message);}};
async function start(back,b){if(saving){message('Збереження ще триває');return;}try{
 if(!back){if(draft.length<2)throw Error('Постав щонайменше дві точки');await api.preview(config,draft);}
 if(editing&&dirty())await save();else if(editing)end();
 launchBack=back;resetConfirm();launch.querySelector('[data-test-consent]').checked=false;launch.querySelector('[data-verified]').checked=false;launch.querySelector('[data-go]').disabled=true;for(const d of [-1,0,1])launch.querySelector('[data-servo="'+d+'"]').disabled=true;
 launch.querySelector('[data-summary]').textContent=back?'Повернення записаним треком':distanceText()+` · крейсер ${config.cruise}% · максимум ${config.max_throttle}% · кермо ±${config.max_steer}%`;
 launchMessage('Перевір кермо, потім підтвердь початок руху. ARM автоматично не надсилається.');launch.showModal();
 }catch(e){message('Не запущено: '+e.message);}}
bar.querySelector('[data-start]').onclick=e=>start(false,e.currentTarget);bar.querySelector('[data-return]').onclick=e=>start(true,e.currentTarget);bar.querySelector('.auto-stop').onclick=()=>{resetConfirm();api.stop();};
setInterval(()=>{const m=mapNow(),n=api.status()?.autonav;
 if(confirmType!==null&&Date.now()>until)resetConfirm();
 if(m&&m!==bound){bound=m;L.DomEvent.disableClickPropagation(bar);L.DomEvent.disableScrollPropagation(bar);m.on('click',e=>{if(!editing||modal.open)return;if(draft.length>=100){message('Максимум 100 точок');return;}const p=[+e.latlng.lat.toFixed(7),+e.latlng.lng.toFixed(7)];if(insertAfter!==null){draft.splice(insertAfter+1,0,p);insertAfter=null;}else draft.push(p);syncText();paint();});if(loaded)paint();}
 if(pendingSaved&&n&&routeKey(n.settings,n.route)===savedKey)pendingSaved=null;
 if(n&&!editing&&!saving&&!pendingSaved&&(!loaded||savedKey!==routeKey(n.settings,n.route))){loadSaved();if(draft.length)ensureMap();paint();}
 if(n?.active){const p=n.progress;message(p?`АВТО · лишилось ${p.distance_m} м · відхилення ${p.cross_track_m} м${p.turn_slowdown?' · сповільнення':''}`:'АВТО: початок');}
},500);
})();
