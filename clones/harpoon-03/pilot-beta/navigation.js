/* Instruments and return guidance only. This module never POSTs control commands. */
(()=>{'use strict';
 const $=s=>document.querySelector(s),num=x=>typeof x==='number'&&Number.isFinite(x);
 const el=(tag,cls,html)=>{const e=document.createElement(tag);e.className=cls;e.innerHTML=html;return e;};
 const stage=$('.camera-stage');if(!stage)return;
 const compass=el('section','nav-gauge nav-compass',`<svg viewBox="0 0 160 160" aria-label="Морський компас"><circle cx="80" cy="80" r="74" class="bezel"/><g class="rose-dial"></g><path d="M80 17L74 29H86Z" fill="#ff606a"/><circle cx="80" cy="80" r="28" class="hub"/><text x="80" y="86" class="course">—</text></svg><small>КУРС · НЕМАЄ ДАНИХ</small>`);
 const dial=compass.querySelector('.rose-dial');let ticks='';
 for(let a=0;a<360;a+=5){const major=a%30===0;ticks+=`<path d="M80 11V${major?22:16}" transform="rotate(${a} 80 80)" class="tick"/>`;}
 for(const [a,t] of [[0,'N'],[90,'E'],[180,'S'],[270,'W']])ticks+=`<g transform="rotate(${a} 80 80)"><text x="80" y="37" transform="rotate(${-a} 80 33)" class="cardinal">${t}</text></g>`;
 dial.innerHTML=ticks+'<path d="M80 44L87 80L80 116L73 80Z" fill="#6fe1c7" opacity=".4"/>';
 const horizon=el('section','nav-gauge nav-horizon',`<svg viewBox="0 0 160 160" aria-label="Авіагоризонт"><defs><clipPath id="nav-att-clip"><circle cx="80" cy="80" r="66"/></clipPath></defs><circle cx="80" cy="80" r="74" class="bezel"/><g clip-path="url(#nav-att-clip)"><g class="bank"><g class="pitch"><rect x="-150" y="-250" width="460" height="330" fill="#396979"/><rect x="-150" y="80" width="460" height="330" fill="#735943"/><path d="M-150 80H310" stroke="white" stroke-width="2"/><g stroke="white" opacity=".65">${[-30,-20,-10,10,20,30].map(a=>`<path d="M${a%20?65:55} ${80-a*2}H${a%20?95:105}"/>`).join('')}</g></g></g></g><path d="M35 80H66L72 85H88L94 80H125M80 14L75 24H85Z" fill="none" stroke="#ffdc78" stroke-width="3"/><text x="80" y="122" class="att-values">— / —</text></svg><small>КРЕН / ТАНГАЖ · FC</small>`);
 stage.append(compass,horizon);
 const trip=el('div','beta-metric','<small>ЧАС ПЛАВАННЯ</small><b>00:00:00</b>');$('.beta-extra').append(trip);
 // Keep the old canonical ID alive but hidden: no duplicate distance displayed.
 const old=$('#tmDistance');const km=el('b','voyage-distance','—');old.hidden=true;old.after(km);km.title='Шлях після підтвердженого руху; сесія від ввімкнення Raspberry';
 const box=el('section','nav-return','<button type="button">↶ Назад по треку</button><span role="status">Підказки · без автокерування</span>');$('.beta-map-slot').append(box);
 const button=box.querySelector('button'),hint=box.querySelector('span');
 let data=null,route=null,index=0,poly=null,target=null,home=null,boot=null;
 const meters=(a,b)=>{const r=Math.PI/180,p=a[0]*r,q=b[0]*r;return 12742000*Math.asin(Math.min(1,Math.sqrt(Math.sin((q-p)/2)**2+Math.cos(p)*Math.cos(q)*Math.sin((b[1]-a[1])*r/2)**2)));};
 const bearing=(a,b)=>{const r=Math.PI/180,d=(b[1]-a[1])*r,p=a[0]*r,q=b[0]*r;return (Math.atan2(Math.sin(d)*Math.cos(q),Math.cos(p)*Math.sin(q)-Math.sin(p)*Math.cos(q)*Math.cos(d))/r+360)%360;};
 function clear(){route=null;button.textContent='↶ Назад по треку';poly?.remove();target?.remove();poly=target=null;}
 button.onclick=()=>{if(route){clear();hint.textContent='Підказки вимкнено';return;}if(!data?.fresh||data.points.length<2)return;route=data.points.map(p=>[...p]);index=route.length-1;button.textContent='× Завершити підказки';guide();};
 function guide(){
   if(!route)return;
   const g=data?.gps||{};
   if(!data?.fresh||!g.position_valid||!num(g.position_age_s)||g.position_age_s>=3){hint.textContent='Повернення призупинено: немає GPS';target?.remove();target=null;return;}
   const pos=[g.latitude,g.longitude];
   while(index>0&&meters(pos,route[index])<4){if(route[index][3]){hint.textContent='Розрив GPS-треку — далі вести вручну';return;}index--;}
   const d=meters(pos,route[index]);
   if(index===0&&d<4){hint.textContent='Початкова точка досягнута';target?.remove();target=null;return;}
   if(d>30){hint.textContent='Далеко від наступної точки ('+Math.round(d)+' м). Повернись до треку вручну';return;}
   const course=g.heading_valid&&num(g.heading_deg)?g.heading_deg:null;
   const aim=bearing(pos,route[index]),delta=course===null?null:((aim-course+540)%360)-180;
   let remaining=d;for(let i=index;i>0;i--){if(route[i][3])break;remaining+=meters(route[i],route[i-1]);}
   let offset=d;
   if(index+1<route.length&&!route[index+1][3]){const a=route[index],b=route[index+1],r=Math.PI/180,scale=111195,cos=Math.cos(a[0]*r),bx=(b[1]-a[1])*scale*cos,by=(b[0]-a[0])*scale,px=(pos[1]-a[1])*scale*cos,py=(pos[0]-a[0])*scale,t=Math.max(0,Math.min(1,(px*bx+py*by)/(bx*bx+by*by||1)));offset=Math.hypot(px-t*bx,py-t*by);}
   hint.textContent=(delta===null?'Немає курсу носа':Math.abs(delta)<8?'Тримай курс':(delta<0?'← Лівіше ':'Правіше → ')+Math.round(Math.abs(delta))+'°')+' · ціль '+Math.round(aim)+'° · від треку '+Math.round(offset)+' м · '+(remaining/1000).toFixed(2)+' км'+(route.slice(0,index+1).some(p=>p[3])?' до розриву':' до дому');
   try{if(typeof map!=='undefined'&&map&&window.L){
     const segments=[];let s=[];for(let i=0;i<=index;i++){if(route[i][3]){if(s.length)segments.push(s);s=[];}s.push(route[i].slice(0,2));}if(s.length)segments.push(s);
     if(!poly)poly=L.polyline(segments,{color:'#ffd279',weight:4,opacity:.85,dashArray:'7 6'}).addTo(map);else poly.setLatLngs(segments);
     if(!target)target=L.circleMarker(route[index].slice(0,2),{radius:7,color:'#ffd279'}).addTo(map);else target.setLatLng(route[index].slice(0,2));
   }}catch{}
 }
 function instruments(g,a){
   const h=g?.heading_valid&&num(g.heading_deg)?g.heading_deg:null;
   compass.classList.toggle('unavailable',h===null);dial.style.transform=h===null?'':`rotate(${-h}deg)`;
   compass.querySelector('.course').textContent=h===null?'—':String(Math.round(h)%360).padStart(3,'0')+'°';compass.querySelector('small').textContent=h===null?'КУРС · НЕМАЄ ДАНИХ':'КУРС НОСА · GPS';
   const valid=a&&num(a.roll_deg)&&num(a.pitch_deg);horizon.classList.toggle('unavailable',!valid);
   horizon.querySelector('.bank').setAttribute('transform',`rotate(${valid?-a.roll_deg:0} 80 80)`);
   horizon.querySelector('.pitch').setAttribute('transform',`translate(0 ${valid?a.pitch_deg*2:0})`);
   horizon.querySelector('.att-values').textContent=valid?a.roll_deg.toFixed(1)+'° / '+a.pitch_deg.toFixed(1)+'°':'— / —';
   horizon.querySelector('small').textContent=valid?'КРЕН / ТАНГАЖ · FC':'НЕМАЄ ATTITUDE';
 }
 let freshAt=0,lastG={},lastA=null;
 async function poll(){
   try{const [v,c]=await Promise.all(['/voyage?after='+(data?.points.length||0)+'&boot='+encodeURIComponent(boot||''),'/control/status'].map(async u=>{const r=await fetch(u,{cache:'no-store',signal:AbortSignal.timeout(1800)});if(!r.ok)throw Error('HTTP');return r.json();}));
     if(boot===v.boot&&data)v.points=data.points.concat(v.points);
     if(boot!==v.boot){clear();home?.remove();home=null;boot=v.boot;}data=v;freshAt=Date.now();lastG=v.fresh?v.gps:{};lastA=c.attitude;
     instruments(lastG,lastA);km.textContent=(v.distance_m/1000).toFixed(2)+' км';const sec=Math.floor(v.elapsed_s);trip.querySelector('b').textContent=[Math.floor(sec/3600),Math.floor(sec/60)%60,sec%60].map(n=>String(n).padStart(2,'0')).join(':');
     button.disabled=!route&&(!v.fresh||!v.gps.position_valid||v.points.length<2);if(v.error&&!route)hint.textContent=v.error;
     try{if(!home&&v.points.length&&typeof map!=='undefined'&&map&&window.L)home=L.circleMarker(v.points[0].slice(0,2),{radius:6,color:'#6fe1c7'}).bindTooltip('Дім · перший GPS-фікс').addTo(map);}catch{}
     guide();
   }catch{instruments({},null);hint.textContent='Немає свіжої телеметрії';button.disabled=!route;km.textContent='—';trip.querySelector('b').textContent='—';}
   setTimeout(poll,700);
 }
 setInterval(()=>{if(Date.now()-freshAt>2500)instruments({},null);},500);poll();
})();
