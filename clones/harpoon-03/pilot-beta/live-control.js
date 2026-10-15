// Real control is operator-gated. Loading this file only reads status/diagnostics.
'use strict';
window.harpoonLiveControl=({panel,top,dialog,logsDialog,consolePage,sessions,pages})=>{
 const q=s=>panel.querySelector(s),keys=new Set(),lines=[];
 let lease=null,nonce=null,seq=0,state=null,freshAt=0,epoch=0,busy=false,eventId=0,cruise=null,confirmAction=null,confirmUntil=0,padId=null;
 let switchReady=false,switchStarting=false,switchPad=null;
 let autoMode=false,autoStarting=false,servoTest=null;
 let linkRecovering=false,linkWarning=false;
 const source=q('select'),limit=q('input'),claim=q('[data-test]'),note=q('.beta-input-state'),output=q('output'),cruiseBtn=q('[data-cruise]');
 document.querySelector('.monitor-note').textContent='Pi03 · Керування: сесія → MANUAL → ARM. Один активний пілот; не подавай команди з QGC одночасно.';
 top.innerHTML='<span role="status">Очікування USB…</span><button data-action="check">PREARM</button><button data-action="manual" disabled>MANUAL</button><button data-action="arm" disabled>ARM</button><button data-action="disarm" disabled>DISARM</button><button class="beta-stop">STOP</button>';
 consolePage.querySelector('h3').textContent='Зв’язок, команди та проблеми';
 consolePage.querySelector('p').textContent='ACK — підтвердження прийняття команди, не доказ фізичного руху. Журнал служби також зберігається в journald на Pi.';
 sessions.inert=false;sessions.querySelector('.notice')?.remove();
 const recover={checked:true,disabled:true}; // Restore the previous bounded DISARMED preparation path.
 const cap=()=>Math.max(0,Math.min(.5,Number(limit.value)/100));
 const drivingCap=()=>source.value==='gamepad'&&padConfig?padConfig.mode(requirePadGate(getPad())).cap:cap();
 const fresh=()=>state&&Date.now()-freshAt<3000;
 function recoverLink(why){
   if(!linkRecovering)log('LINK_PAUSE',why+' · сесія збережена; газ у нуль, кермо в центр');
   linkRecovering=true;nonce=null;keys.clear();cruise=null;servoTest=null;autoMode=false;
 }
 function log(kind,text){lines.push(new Date().toLocaleTimeString()+' ['+kind+'] '+text);while(lines.length>250)lines.shift();consolePage.querySelector('pre').textContent=lines.join('\n');}
 function cancelConfirm(){confirmAction=null;confirmUntil=0;}
 function confirmed(action){if(confirmAction===action&&Date.now()<confirmUntil){cancelConfirm();return true;}confirmAction=action;confirmUntil=Date.now()+10000;keys.clear();cruise=null;
   note.textContent=action==='arm'?'Підтверди ARM повторним натисканням. Рушій готовий до запуску?':action==='claim'?'Підтверди керування повторним натисканням. Інший пілот / QGC не керує?':'Підтверди утримання тяги повторним натисканням. Круїз потребує постійного зв’язку.';render();return false;}
 async function post(data){const r=await fetch('/control/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...data,lease}),signal:AbortSignal.timeout(2500)});const d=await r.json();if(!r.ok){const e=Error(d.error||'HTTP '+r.status);e.http=r.status;throw e;}return d;}
 function stop(why){autoMode=false;autoStarting=false;servoTest=null;const old=lease;lease=null;nonce=null;keys.clear();cruise=null;padId=null;switchReady=false;switchPad=null;epoch++;cancelConfirm();
   linkRecovering=false;linkWarning=false;
   if(old)fetch('/control/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'stop',lease:old,reason:why}),keepalive:true}).catch(()=>log('ERROR','STOP не підтверджено мережею; перевір фізичну зупинку'));
   note.textContent=why;output.textContent='Команди вимкнено';if(old)log('STOP',why);render();}
 function render(){
   if(confirmAction&&Date.now()>confirmUntil)cancelConfirm();
   const f=fresh(),block=state?.blocked,gate=recover.checked?state?.claim_blocked:block;
   const phase={waiting_usb:'Очікування USB',waiting_heartbeat:'Очікування HEARTBEAT',waiting_parameters:'Читання параметрів',blocked:'Не готовий',ready:'Зв’язок є'};
   top.querySelector('span').textContent=f?(phase[state.connection_phase]||'USB')+' · '+(state.connected?(state.armed?'ARMED':'DISARMED')+' / '+({0:'MANUAL',4:'HOLD'}[state.mode]??state.mode):'немає HEARTBEAT'):'Немає свіжого стану';
   claim.textContent=confirmAction==='claim'?'Підтверджую ввімкнення':lease?'Вимкнути керування':'Увімкнути керування';
   claim.disabled=!lease&&(!f||!state.connected||!!gate||state.armed||state.lease_active);
   for(const a of ['check','manual','arm','disarm']){const b=top.querySelector('[data-action='+a+']');b.disabled=a==='disarm'?false:!f||!state.connected||(['manual','arm'].includes(a)&&(!lease||!!block||state.armed||(a==='arm'&&state.mode!==0)));if(a==='arm')b.textContent=confirmAction==='arm'?'Підтверджую ARM':'ARM';}
   const armButton=top.querySelector('[data-action=arm]');
   if(!lease){armButton.textContent='Запит ARM';armButton.disabled=!f||!state.connected||state.armed||state.lease_active;}
   claim.hidden=true;
   const enable=top.querySelector('[data-action=check]');if(source.value==='keyboard'){enable.textContent=claim.textContent;enable.disabled=claim.disabled;}else{enable.textContent='PREARM';}
   if(switchStarting){top.querySelector('[data-action=manual]').disabled=true;top.querySelector('[data-action=arm]').disabled=true;}
   source.disabled=!!lease;recover.disabled=!!lease;limit.disabled=source.value==='gamepad';
   try{q('[data-cap]').textContent=source.value==='gamepad'?Math.round(drivingCap()*100)+'% · Axis':limit.value+'%';}catch{q('[data-cap]').textContent='Перевір TX12';}
   cruiseBtn.disabled=cruise===null&&(!lease||!f||!state.armed||state.mode!==0||!!block||cap()===0||source.value!=='keyboard');
   cruiseBtn.textContent=confirmAction==='cruise'?'Підтверджую круїз':cruise===null?'Круїз':'Утримання '+Math.round(cruise*100)+'% · вимк.';
   if(!confirmAction)note.textContent=!f?'Немає свіжого стану · DISARM доступна, доставку перевіряй у логах':state.error||block||(lease?'Керування активне · Space не STOP. Кнопка STOP завжди доступна.':state.armed?'Польотник уже ARMED. Натисни DISARM перед отриманням керування.':'Готовність перевірена; увімкнення тільки оператором.');
   if(source.value==='gamepad'&&!lease&&f&&!state.armed&&!block)note.textContent=switchReady?'TX12: газ 0, кермо центр; обидва перемикачі +1 → MANUAL → ARM':'TX12: спочатку вимкни один із перемикачів Axis 4/5; потім обидва +1';
   if(lease&&linkRecovering)note.textContent='Відновлення зв’язку · сесія збережена · газ у нуль, кермо в центр';
 }
 const padConfig=window.harpoonPadConfig?.({panel,buttonHost:top,onOpen:()=>stop('Налаштування джойстика: керування припинено')});
 function getPad(){if(padConfig)return padConfig.getPad(padId);try{return Array.from(navigator.getGamepads?.()||[]).find(p=>p?.connected&&p.mapping==='standard'&&(padId===null||p.index===padId));}catch{return null;}}
 function padAxes(p){if(padConfig)return padConfig.axes(p);const s=p?.axes?.[2],t=p?.axes?.[1];if(!Number.isFinite(s)||!Number.isFinite(t)||Math.abs(s)>1||Math.abs(t)>1)throw Error('Некоректні осі джойстика');return [Math.abs(s)<.06?0:Math.sign(s)*(Math.abs(s)-.06)/.94,(1-t)/2];}
 function requirePadGate(p){if(!p)throw Error('Джойстик відключено або не налаштовано');if(![4,5].every(i=>Number.isFinite(p.axes?.[i])&&p.axes[i]>=.95&&p.axes[i]<=1))throw Error('Дозвіл TX12 вимкнений: Axis 4 і Axis 5 мають бути +1');return p;}
 function neutralPad(){const p=requirePadGate(getPad());const [s,t]=padAxes(p);if(Math.abs(s)>.05||t>.03)throw Error('Лівий стік униз до 0; правий у центр');return p;}
 claim.onclick=async()=>{if(lease){stop('Вимкнено оператором');return;}try{
   if(source.value==='gamepad')neutralPad();if(!confirmed('claim'))return;
   if(source.value==='gamepad')padId=neutralPad().index;
   const requested=++epoch;claim.disabled=true;
   const r=await post({action:'claim',operator_confirmed:true});
   if(requested!==epoch||document.hidden||!document.hasFocus()){fetch('/control/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'stop',lease:r.lease}),keepalive:true});return;}
   lease=r.lease;nonce=null;seq=0;keys.clear();cruise=null;state={...state,lease_active:true};log('LOCAL','Сесію отримано; MANUAL та ARM окремо');await tick();
 }catch(e){log('ERROR',e.message);note.textContent=e.message;}render();};
 for(const b of top.querySelectorAll('[data-action]'))b.onclick=async()=>{const a=b.dataset.action;try{
   if(a==='arm'&&!lease){
     if(!window.confirm('Надіслати звичайний запит ARM польотнику Pi03? Якщо він прийме команду, рушій може стати активним. Переконайся, що випробування безпечне. Це не force ARM і не дозвіл керування при помилці.'))return;
     const r=await post({action:'arm_request',confirm:'REQUEST_NORMAL_ARM'});log('ARM_REQUEST',r.message);
     logsDialog.showModal();return;
   }
   if(a==='check'&&source.value==='keyboard'){await claim.onclick();return;}
   keys.clear();cruise=null;if(a==='arm'){if(source.value==='gamepad')neutralPad();if(!confirmed('arm'))return;}
   if(a==='disarm')stop('DISARM');
   await post({action:a,confirm:a==='arm'?'ARM':undefined});log('LOCAL',a+': сервер прийняв; чекаємо ACK та HEARTBEAT');
 }catch(e){log('ERROR',e.message);}render();};
 async function emergency(){stop('STOP: локальне керування вимкнено; очікування доставки');try{await post({action:'emergency_stop'});log('STOP','DISARM запитано; перевір стан польотника');}catch(e){log('ERROR','STOP не підтверджений: '+e.message+' · повтори STOP; перевір фізичну зупинку');}}
 top.querySelector('.beta-stop').onclick=emergency;
 const rebootBtn=document.createElement('button');rebootBtn.textContent='↻ Польотник';rebootBtn.title='Перезавантажити тільки польотник, без скидання параметрів';top.append(rebootBtn);
 rebootBtn.onclick=async()=>{
   if(!fresh()||!state.connected){log('ERROR','Перезавантаження: немає свіжого HEARTBEAT. Якщо польотник повністю завис, потрібне фізичне керування живленням.');note.textContent='Немає зв’язку для перезавантаження — дивись Логи';return;}
   if(state.armed||state.lease_active||lease){log('ERROR','Перезавантаження: спочатку DISARM і завершення керування');note.textContent='Спочатку DISARM і завершення керування';return;}
   if(!window.confirm('Перезавантажити польотник Pi03? Човен має бути зупинений, силове живлення двигуна вимкнене. Зв’язок тимчасово зникне. Параметри не змінюються. Raspberry не перезавантажується.'))return;
   rebootBtn.disabled=true;
   try{const r=await post({action:'reboot_fc',confirm:'REBOOT_FC'});log('REBOOT',r.message);note.textContent='Перезапуск запитано — перевір відновлення зв’язку в Логах';}
   catch(e){log('ERROR',e.message);note.textContent=e.message;}
   finally{setTimeout(()=>{rebootBtn.disabled=false},30000);}
 };
 window.harpoonAuto={status:()=>state,stop:emergency,prepare:()=>stop('Налаштування автомаршруту'),testSteer:direction=>{
   if(![-1,0,1].includes(direction))throw Error('Невірний напрям тесту');
   if(!lease||!fresh()||!state.armed||state.mode!==0||source.value!=='keyboard'||autoMode||autoStarting||confirmAction)throw Error('Для тесту: власна сесія Клавіатура → MANUAL → ARM');
   if((state.applied||[]).length!==2||Math.abs(state.applied[1])>.001||Math.abs(state.intent?.[1]||0)>.001||keys.size||cruise!==null)throw Error('Спочатку зупини тягу й відпусти клавіші');
   keys.clear();cruise=null;servoTest={steer:direction*.1,until:Date.now()+600};log('SERVO_TEST','Запит керма '+direction*10+'%, тяга 0; фізичний рух підтверджує оператор');
 },cancelTest:()=>{servoTest=null;keys.clear();cruise=null;},preview:async(settings,route)=>post({action:'auto_preview',settings,route}),save:async(settings,route)=>post({action:'auto_save',settings,route}),start:async(returnTrack)=>{
   if(!lease||!fresh()||!state.armed||state.mode!==0||source.value!=='keyboard')throw Error('Потрібна власна сесія: Клавіатура → MANUAL → ARM, ручні команди нуль');
   if(busy||autoStarting||autoMode||servoTest)throw Error('Зачекай завершення команди / тесту керма');
   const token=epoch;autoStarting=true;keys.clear();cruise=null;
   try{const d=await post({action:'auto_start',confirm:'START',return_track:returnTrack,seq:++seq,nonce});if(token!==epoch)return;if(d.network_paused){recoverLink('Запуск не виконано: зв’язок потребує відновлення');return;}nonce=d.nonce;autoMode=true;log('AUTO','Автоматичне ведення запущено');}
   catch(e){if(token===epoch&&lease)recoverLink('Запуск не підтверджено; нейтральна синхронізація, маршрут треба запустити повторно');throw e;}
   finally{autoStarting=false;}
 }};
 source.onchange=()=>stop('Джерело вводу змінено');recover.onchange=render;
 limit.oninput=()=>{q('[data-cap]').textContent=limit.value+'%';keys.clear();cancelConfirm();if(cruise!==null)cruise=Math.min(cruise,cap());render();};
 cruiseBtn.onclick=()=>{if(cruise!==null){cruise=null;keys.clear();cancelConfirm();render();return;}if(!lease||source.value!=='keyboard'||!state?.armed)return;if(!confirmed('cruise'))return;cruise=cap();log('CRUISE','Утримання '+Math.round(cruise*100)+'%');render();};
 function watchPadGate(){if(lease&&source.value==='gamepad'){try{requirePadGate(getPad());drivingCap();}catch(e){log('INTERLOCK',e.message);stop(e.message);}}}
 function switchContext(){return source.value==='gamepad'&&fresh()&&state.connected&&!(!state.armed&&'claim_blocked' in state?state.claim_blocked:state.blocked)&&!document.hidden&&document.hasFocus()&&!dialog.open&&!logsDialog.open&&!padConfig?.isOpen?.();}
 async function startBySwitch(){
   switchReady=false;switchStarting=true;const token=++epoch;
   const check=()=>{if(token!==epoch||!switchContext())throw Error('TX12: запуск скасовано');neutralPad();drivingCap();};
   const waitState=async(predicate)=>{const until=Date.now()+5000;while(Date.now()<until){check();if(predicate(state))return;await new Promise(resolve=>setTimeout(resolve,100));}throw Error('TX12: немає підтвердження стану польотника');};
   try{
     check();if(state.armed||state.lease_active)throw Error('TX12: потрібен DISARMED без іншого пілота');
     padId=neutralPad().index;confirmAction='switch-start';confirmUntil=Date.now()+20000;
     log('TX12','Перехід перемикачів OFF → ON: отримання керування');
     const r=await post({action:'claim',operator_confirmed:true});
     if(token!==epoch||!switchContext()){await fetch('/control/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'stop',lease:r.lease}),keepalive:true});throw Error('TX12: запит скасовано');}
     lease=r.lease;nonce=null;seq=0;state={...state,lease_active:true};check();await tick();
     check();await post({action:'manual'});log('TX12','MANUAL надіслано; чекаємо HEARTBEAT');
     await waitState(s=>s.mode===0&&!s.armed&&s.lease_active&&(s.applied||[0,0]).every(v=>Math.abs(v)<1e-6));
     check();await post({action:'arm',confirm:'ARM'});log('TX12','ARM надіслано; чекаємо HEARTBEAT');
     await waitState(s=>s.mode===0&&s.armed&&s.lease_active);
     check();cancelConfirm();log('TX12','ARMED/MANUAL підтверджено. Керування стіками активне.');
   }catch(e){log('TX12',e.message);if(token===epoch)stop(e.message);}
   finally{switchStarting=false;render();}
 }
 function watchSwitchStart(){
   if(switchStarting){try{if(!switchContext())throw Error('TX12: втрачено готовність під час запуску');neutralPad();drivingCap();}catch(e){stop(e.message);}return;}
   if(lease)return;
   if(!switchContext()||state.armed||state.lease_active){switchReady=false;switchPad=null;return;}
   const p=getPad();if(!p||![4,5].every(i=>Number.isFinite(p.axes?.[i])&&Math.abs(p.axes[i])<=1)){switchReady=false;switchPad=null;return;}
   const id=p.id+':'+p.index;if(id!==switchPad){switchReady=false;switchPad=id;}
   if([4,5].some(i=>p.axes[i]<.95)){switchReady=true;return;}
   if(switchReady){switchReady=false;void startBySwitch();}
 }
 async function tick(){watchPadGate();if(!lease||busy||autoStarting)return;if(document.hidden){stop('Вкладку приховано');return;}if(!fresh())recoverLink('Немає свіжої телеметрії');busy=true;const token=epoch;
   if(autoMode){try{if(keys.size){stop('Ручне перехоплення: автомаршрут зупинено');return;}const d=await post({action:'auto_tick',seq:++seq,nonce});if(token===epoch&&lease){if(d.network_paused){recoverLink('Автомаршрут призупинено через зв’язок');return;}if(d.finished){stop('Маршрут завершено');return;}nonce=d.nonce;output.textContent='АВТО · точка '+(state.autonav?.progress?.point||'—')+' · '+Math.round((state.applied?.[1]||0)*100)+'%';}}catch(e){if(token!==epoch)return;log('AUTO',e.message);if(!e.http||e.http>=500)recoverLink('Відповідь автомаршруту втрачено');else stop('Автомаршрут припинено: '+e.message);}finally{busy=false;}return;}
   try{let steer=0,throttle=0;const activeCap=drivingCap();if(nonce&&!confirmAction&&state.mode===0){if(source.value==='gamepad'){const p=getPad();if(!p)throw Error('Джойстик відключився');const [s,t]=padAxes(p);steer=s*.6;throttle=state.armed?(t<.03?0:t*activeCap):0;}else{steer=(keys.has('ArrowRight')?.6:0)-(keys.has('ArrowLeft')?.6:0);throttle=state.armed&&!keys.has('ArrowDown')?Math.min(cap(),cruise??(keys.has('ArrowUp')?cap():0)):0;}}
     if(servoTest){if(Date.now()>=servoTest.until||state.mode!==0||!state.armed||source.value!=='keyboard'||keys.size||confirmAction)servoTest=null;else steer=servoTest.steer;throttle=0;}
     let neutralReady=true;
     if(linkRecovering){
       if(source.value==='gamepad'){const [s,t]=padAxes(requirePadGate(getPad()));neutralReady=Math.abs(s)<=.05&&t<=.03;}else neutralReady=keys.size===0;
       steer=0;throttle=0;
     }
     const p=source.value==='gamepad'?getPad():null,meta=p&&padConfig?{input_source:'gamepad',pad_gate:[p.axes[4],p.axes[5]],pad_mode:padConfig.mode(p).value}:{};
     const d=await post({action:'tick',seq:++seq,nonce,steer,throttle,throttle_cap:activeCap,resync:linkRecovering,...meta});if(token===epoch&&lease){
       if(d.network_paused){recoverLink('Сервер очікує нейтраль');return;}
       nonce=d.nonce;
       if(linkRecovering&&neutralReady&&fresh()){linkRecovering=false;log('LINK_RECOVER','Зв’язок і нейтраль підтверджені; керування доступне');}
       output.textContent='Команда: '+Math.round((state?.applied?.[0]||0)*100)+'% / '+Math.round((state?.applied?.[1]||0)*100)+'%';}
   }catch(e){if(token!==epoch)return;log('ERROR',e.message);if(!e.http||e.http>=500)recoverLink('Відповідь на команду втрачено');else stop('Команда відхилена: '+e.message);}finally{busy=false;}}
 for(const [attr,key] of [['left','ArrowLeft'],['right','ArrowRight'],['up','ArrowUp']]){const b=q('[data-'+attr+']');b.onpointerdown=e=>{if(lease&&source.value==='keyboard'&&!confirmAction){keys.add(key);b.setPointerCapture(e.pointerId);}};for(const ev of ['pointerup','pointercancel','lostpointercapture'])b.addEventListener(ev,()=>keys.delete(key));}
 window.addEventListener('keydown',e=>{if(!lease||source.value!=='keyboard'||confirmAction||dialog.open||logsDialog.open||document.querySelector('.auto-start-dialog')?.open||e.target.matches('input,select,textarea'))return;if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.code)){e.preventDefault();keys.add(e.code);if(e.code==='ArrowDown')cruise=null;}});
 window.addEventListener('keyup',e=>keys.delete(e.code));
 window.addEventListener('blur',()=>{keys.clear();if(source.value!=='gamepad'){cruise=null;servoTest=null;}log('FOCUS','Фокус втрачено; сесію збережено, натиснуті клавіші скинуто');});window.addEventListener('pagehide',()=>stop('Сторінка закрита'));
 document.addEventListener('visibilitychange',()=>{if(document.hidden)stop('Вкладку приховано');});
 window.addEventListener('gamepaddisconnected',()=>{if(source.value==='gamepad')stop('Джойстик відключено');});
 q('[data-telemetry]').onclick=()=>{keys.clear();logsDialog.close();pages[0].b.click();dialog.showModal();};
 q('[data-log]').onclick=()=>{keys.clear();dialog.close();logsDialog.showModal();};
 let lastFault=null;
 async function poll(){const token=epoch;try{const r=await fetch('/control/status',{cache:'no-store',signal:AbortSignal.timeout(1500)});if(!r.ok)throw Error('USB service HTTP '+r.status);const d=await r.json();if(token!==epoch)return;
   state=d;freshAt=Date.now();if(linkWarning){linkWarning=false;log('LINK_RECOVER','Телеметрія знову надходить');}if(lease&&d.network_paused)recoverLink('Команди затримані; тяга обнулена');if(d.events?.length&&d.events.at(-1).id<eventId)eventId=0;for(const e of d.events||[])if(e.id>eventId){log(e.kind,e.text);eventId=e.id;}
   const fault=d.error||d.blocked||null;if(fault!==lastFault){log(fault?'BLOCK':'READY',fault||'Польотник готовий');lastFault=fault;}
   if(lease&&(!d.connected||!d.lease_active||(d.blocked&&!(recover.checked&&!d.armed&&d.state===5))))stop('Сервер припинив керування');
   if(cruise!==null&&(!d.armed||d.mode!==0))stop('Круїз: втрачено ARMED/MANUAL');
 }catch(e){if(token!==epoch)return;if(!linkWarning)log('LINK',e.message+' · повторюю запит');linkWarning=true;if(lease&&!fresh())recoverLink('Затримка телеметрії понад 3 с');}finally{render();setTimeout(poll,400);}}
 let issues=new Set(),diagFailed=false;
 async function diagnostics(){try{const r=await fetch('/diagnostics',{cache:'no-store',signal:AbortSignal.timeout(2500)});if(!r.ok)throw Error('HTTP '+r.status);const d=await r.json();if(d.stale)throw Error('Застаріла діагностика');if(diagFailed)log('RECOVER','Діагностика відновлена');diagFailed=false;
   const current=new Set(d.problems||[]);if(d.undervoltage_now)current.add('UNDERVOLTAGE_NOW');if(d.throttled_now)current.add('THROTTLED_NOW');
   for(const p of current)if(!issues.has(p))log('BOARD',p);for(const p of issues)if(!current.has(p))log('RECOVER',p);issues=current;
 }catch(e){if(!diagFailed)log('BOARD','Діагностика недоступна: '+e.message);diagFailed=true;}finally{setTimeout(diagnostics,5000);}}
 setInterval(()=>{watchPadGate();watchSwitchStart();},50);setInterval(tick,150);poll();diagnostics();render();
};
