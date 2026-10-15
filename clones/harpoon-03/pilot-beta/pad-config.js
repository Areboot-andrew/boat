'use strict';
// Local browser preferences only. This module never sends control requests.
window.harpoonPadConfig=({panel,buttonHost=panel,onOpen})=>{
 const key='harpoon.pi03.gamepad.v1';let selected='',profiles={};
 try{const d=JSON.parse(localStorage.getItem(key)||'{}');selected=String(d.selected||'');profiles=d.profiles||{};}catch{}
 const defaults={steer:2,throttle:1,invertSteer:false,invertThrottle:false,deadzone:.06};
 const txid='Radiomaster TX12 Joystick (Vendor: 1209 Product: 4f54)';
 const tx={steer:0,throttle:2,invertSteer:false,invertThrottle:true,deadzone:.06,low:-.710,high:.011,modeAxis:6,caps:[50,60,70]};
 const config=p=>profiles[p?.id]||(p?.id===txid?tx:defaults);
 const range=c=>[c.low??-1,c.high??1];
 const extended=c=>{const [lo,hi]=range(c);return Number.isFinite(lo)&&Number.isFinite(hi)&&lo>=-1&&hi<=1&&hi-lo>=.2&&Number.isInteger(c.modeAxis??6)&&(c.modeAxis??6)>=0&&(c.modeAxis??6)<32&&![4,5,c.steer,c.throttle].includes(c.modeAxis??6)&&![4,5].includes(c.steer)&&![4,5].includes(c.throttle)&&(c.caps??[50,60,70]).length===3&&(c.caps??[50,60,70]).every((n,i)=>Number.isFinite(n)&&n>=0&&n<=[50,60,70][i]);};
 const valid=c=>c&&Number.isInteger(c.steer)&&Number.isInteger(c.throttle)&&c.steer>=0&&c.throttle>=0&&c.steer!==c.throttle&&c.steer<32&&c.throttle<32&&Number.isFinite(c.deadzone)&&c.deadzone>=0&&c.deadzone<=.3&&typeof c.invertSteer==='boolean'&&typeof c.invertThrottle==='boolean';
 const pads=()=>{try{return Array.from(navigator.getGamepads?.()||[]).filter(p=>p?.connected);}catch{return [];}};
 function getPad(index=null){return pads().find(p=>(index===null||p.index===index)&&(selected?p.id===selected:p.id===txid||p.mapping==='standard'));}
 function axes(p,c=config(p)){
  if(!valid(c)||!extended(c)||(!profiles[p?.id]&&p?.mapping!=='standard'&&p?.id!==txid))throw Error('Налаштуй і збережи осі цього джойстика');
  let s=p?.axes?.[c.steer],t=p?.axes?.[c.throttle];
  if(!Number.isFinite(s)||!Number.isFinite(t)||Math.abs(s)>1||Math.abs(t)>1)throw Error('Некоректні осі джойстика');
  const [lo,hi]=range(c);t=Math.max(0,Math.min(1,(t-lo)/(hi-lo)));
  if(c.invertSteer)s=-s;if(!c.invertThrottle)t=1-t;
  return [Math.abs(s)<=c.deadzone?0:Math.sign(s)*(Math.abs(s)-c.deadzone)/(1-c.deadzone),t];
 }
 let modeState=null;
 function mode(p){
  const c=config(p);if(!valid(c)||!extended(c))throw Error('Некоректний профіль TX12');
  const v=p?.axes?.[c.modeAxis??6],now=Date.now(),caps=c.caps??[50,60,70];
  if(!Number.isFinite(v)||Math.abs(v)>1)throw Error('Некоректна вісь перемикача ліміту');
  const id=JSON.stringify([p.id,p.index,c.modeAxis,caps]);
  if(modeState?.id!==id)modeState={id,candidate:null,since:now,cap:Math.min(...caps)/100};
  const index=[-1,0,1].findIndex(n=>Math.abs(v-n)<=.1);
  if(index<0){
   if(modeState.candidate!==null){modeState.candidate=null;modeState.since=now;}
   modeState.cap=Math.min(modeState.cap,Math.min(...caps)/100);
   if(now-modeState.since>300)modeState.cap=0;
   return {value:-1,cap:modeState.cap,settling:true};
  }
  if(modeState.candidate!==index){modeState.candidate=index;modeState.since=now;}
  const wanted=caps[index]/100;
  // Decrease immediately; an increase requires 200 ms in a stable detent.
  modeState.cap=now-modeState.since>=200?wanted:Math.min(modeState.cap,wanted);
  return {value:index-1,cap:modeState.cap,settling:modeState.cap!==wanted};
 }
 const button=document.createElement('button');button.textContent='⚙ Джойстик';button.title='Пристрій, осі та перевірка без руху';buttonHost.append(button);
 const box=document.createElement('dialog');box.style.cssText='background:#10262c;color:#d8edef;border:1px solid #38535c;border-radius:12px;max-width:540px;width:90%;padding:20px';
 box.innerHTML='<h3>Налаштування джойстика</h3><p data-status></p><label>Пристрій <select data-device></select></label><p><label>Поворот · вісь <select data-steer></select></label> <label><input type="checkbox" data-is> Інверсія</label></p><p><label>Газ · вісь <select data-throttle></select></label> <label><input type="checkbox" data-it> Інверсія</label></p><p><label>Мертва зона керма <input data-dz type="number" min="0" max="30" step="1" value="6" style="width:60px"> %</label></p><pre data-values style="white-space:pre-wrap"></pre><p>Газ: унизу 0%, угорі 100%. Пружинний центр означає 50%. Ліміт тяги в нижній панелі зберігається. Перед увімкненням — газ у нуль, кермо в центр.</p><p>Це тільки перевірка вводу: відкриття панелі припиняє керування. Збереження — у цьому браузері для цього пристрою.</p><button data-save>Зберегти</button> <button data-close>Закрити</button>';
 document.body.append(box);const q=s=>box.querySelector(s),device=q('[data-device]'),steer=q('[data-steer]'),throttle=q('[data-throttle]');let inventory='',draftPad=null;
 const extra=document.createElement('section');extra.innerHTML='<p>Калібрування сирої осі газу</p><label>Мінімум <input data-low type="number" min="-1" max="1" step="0.001"></label> <label>Максимум <input data-high type="number" min="-1" max="1" step="0.001"></label><p><label>Вісь перемикача ліміту <input data-mode type="number" min="0" max="31" step="1"></label></p><p><label>−1: <input data-c0 type="number" min="0" max="50">%</label> <label>0: <input data-c1 type="number" min="0" max="60">%</label> <label>+1: <input data-c2 type="number" min="0" max="70">%</label></p><p>Джойстик використовує ліміт перемикача замість повзунка клавіатури. Axis 4 і 5 — обов’язковий дозвіл. Для TX12 вже задані виміряні осі й калібрування. Після зміни моделі/мікшера пульта перевір калібрування знову.</p>';
 box.insertBefore(extra,q('[data-values]'));for(const input of extra.querySelectorAll('input'))input.style.width='75px';
 const option=(parent,value,label)=>{const e=document.createElement('option');e.value=value;e.textContent=label;parent.append(e);};
 function load(){draftPad=pads().find(p=>String(p.index)===device.value);for(const s of [steer,throttle]){s.replaceChildren();for(let i=0;i<(draftPad?.axes.length||0);i++)option(s,String(i),'Axis '+i);}const c=config(draftPad);steer.value=String(c.steer);throttle.value=String(c.throttle);q('[data-is]').checked=c.invertSteer;q('[data-it]').checked=c.invertThrottle;q('[data-dz]').value=String(c.deadzone*100);q('[data-low]').value=String(c.low??-1);q('[data-high]').value=String(c.high??1);q('[data-mode]').value=String(c.modeAxis??6);for(let i=0;i<3;i++)q('[data-c'+i+']').value=String((c.caps??[50,60,70])[i]);}
 const draft=()=>({steer:steer.value===''?-1:Number(steer.value),throttle:throttle.value===''?-1:Number(throttle.value),invertSteer:q('[data-is]').checked,invertThrottle:q('[data-it]').checked,deadzone:Number(q('[data-dz]').value)/100,low:Number(q('[data-low]').value),high:Number(q('[data-high]').value),modeAxis:Number(q('[data-mode]').value),caps:[0,1,2].map(i=>Number(q('[data-c'+i+']').value))});
 function refresh(){if(!box.open)return;const list=pads(),sig=JSON.stringify(list.map(p=>[p.index,p.id,p.axes.length]));if(sig!==inventory){inventory=sig;const previous=device.value;device.replaceChildren();for(const p of list)option(device,String(p.index),p.id);device.value=String(list.find(p=>String(p.index)===previous)?.index??list.find(p=>p.id===selected)?.index??list[0]?.index??'');load();}
  q('[data-status]').textContent=list.length?'TX12: у режимі Джойстик перехід Axis 4 І 5 у +1 запускає MANUAL → ARM (газ 0, кермо центр). OFF → STOP. Після відкриття сторінки/втрати зв’язку потрібен новий OFF → ON.':!window.isSecureContext?'Браузер може блокувати Gamepad API на HTTP. Відкрий через HTTPS або localhost (SSH-тунель).':!navigator.getGamepads?'Gamepad API недоступний у цьому браузері.':'Натисни кнопку на джойстику, залишаючи цю вкладку активною.';
  const p=list.find(p=>String(p.index)===device.value);q('[data-save]').disabled=!p;
  q('[data-values]').textContent=p?p.axes.map((v,i)=>'Axis '+i+': '+v.toFixed(3)).join('  ')+'\nКнопок: '+p.buttons.length:'Пристроїв: 0';
  if(p){try{const [s,t]=axes(p,draft()),m=mode(p);q('[data-values]').textContent+='\nКермо '+Math.round(s*100)+'% · Газ '+Math.round(t*100)+'% · Ліміт '+Math.round(m.cap*100)+'%';}catch{}}
 }
 button.onclick=()=>{onOpen();inventory='';box.showModal();refresh();};device.onchange=load;
 q('[data-close]').onclick=()=>box.close();q('[data-save]').onclick=()=>{const p=pads().find(p=>String(p.index)===device.value),c=draft();if(!p||!valid(c)||!extended(c)||c.steer>=p.axes.length||c.throttle>=p.axes.length||c.modeAxis>=p.axes.length){q('[data-status]').textContent='Перевір осі, калібрування (діапазон ≥0,2), ліміти 50/60/70%. Осі не повинні збігатися з перемикачами.';return;}try{const next={...profiles,[p.id]:c};localStorage.setItem(key,JSON.stringify({selected:p.id,profiles:next}));profiles=next;selected=p.id;box.close();}catch{q('[data-status]').textContent='Браузер не дозволив зберегти налаштування.';}};
 setInterval(refresh,200);return {getPad,axes,mode,isOpen:()=>box.open};
};
