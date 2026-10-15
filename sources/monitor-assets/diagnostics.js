(()=>{
const $=id=>document.getElementById(id);
const labels={
POWER_UNDERVOLTAGE:['Низька напруга живлення','Перевірте джерело живлення, кабель і роз’єми.',true],
CPU_THROTTLED:['Продуктивність Raspberry обмежена','Можливі затримки відео. Перевірте живлення й температуру.',true],
TEMPERATURE_HIGH:['Висока температура','Перевірте охолодження.',true],MEMORY_LOW:['Мало вільної RAM','Можливі зависання сервісів.',true],
DISK_LOW:['Мало місця на SD','Перевірте обсяг записів.',true],ROOT_READONLY:['SD доступна лише для читання','Потрібна перевірка файлової системи.',true],
ETHERNET_NO_CARRIER:['Немає Ethernet-з’єднання','Перевірте кабель і роутер.',true],NO_DEFAULT_GATEWAY:['Не заданий шлюз','Доступ до інтернету може бути відсутній.',true],
INTERNET_PROBES_FAILED:['Перевірки інтернету не проходять','Обидві контрольні TCP-адреси недоступні; це не доводить повну відсутність інтернету.'],
DNS_FAILED:['Не працює перевірка DNS','Не вдалося визначити адресу контрольного домену.'],
TAILSCALE_NOT_RUNNING:['Tailscale не готовий','Перевірте сервіс і авторизацію.'],TAILSCALE_OFFLINE:['Tailscale offline','Тунель зараз недоступний.'],
GROUNDSTATION_OFFLINE:['Наземка offline','ПК 100.64.139.75 не онлайн у Tailscale.'],CAMERA2_NO_UDP:['Немає потоку камери 2','На UDP 5600 давно не було пакетів.'],
UDP_OBSERVER_ERROR:['Помилка спостереження за UDP','Стан потоку не підтверджено.'],WEB_TELEMETRY_UNAVAILABLE:['Телеметрія недоступна','Перевірте сервіс моніторингу.'],
GPS_LINK_DOWN:['GPS від’єднаний / немає даних','Перевірте USB-приймач і кабель.'],GPS_NO_FIX:['GPS без фікса','Координати не визначені. Потрібний огляд неба.'],
BMS_LINK_DOWN:['Немає зв’язку з BMS','Дані батареї можуть бути застарілими.']};
function issue(text,detail,cls=''){const li=document.createElement('li');li.className=cls;li.textContent=text;if(detail){const small=document.createElement('small');small.textContent=detail;li.append(small)}return li}
function metric(name,value){const d=document.createElement('div');d.className='diag-metric';d.textContent=name;const b=document.createElement('strong');b.textContent=value;d.append(b);return d}
function networkDetails(d){
 let box=$('diag-network');if(!box){box=document.createElement('details');box.id='diag-network';box.open=true;$('diag-metrics').after(box)}
 const title=document.createElement('summary');title.textContent='Інтернет і параметри зв’язку';const grid=document.createElement('div');grid.className='diag-metrics';
 const n=d.network||{},i=d.interfaces||{},status=v=>v===true?'ОК':v===false?'Немає відповіді':'Невідомо',num=(v,suffix)=>v!=null&&v!==''&&Number.isFinite(Number(v))?`${Number(v).toFixed(1)} ${suffix}`:'—';
 const age=d.uptime_s-n.checked_uptime_s,fresh=Number.isFinite(age)&&age>=0&&age<60;
 grid.append(metric('Шлюз',n.gateway||'—'),metric('Ping шлюзу',fresh?`${status(n.gateway_ping)} · ${num(n.gateway_ping_ms,'мс')}`:'Дані застарілі'));
 for(const ip of ['1.1.1.1','8.8.8.8'])grid.append(metric(`${ip}:443 · TCP`,fresh?`${status(n.internet_tcp_443?.[ip])} · ${num(n.tcp_connect_ms?.[ip],'мс')}`:'Дані застарілі'));
 grid.append(metric('DNS · example.com',fresh?status(n.dns_ok):'Дані застарілі'),metric('Tailscale',fresh?`${n.tailscale?.state||'—'} · ${status(n.tailscale?.self_online)}`:'Дані застарілі'),metric('Наземка · 100.64.139.75',fresh?status(n.groundstation_online):'Дані застарілі'),metric('Ethernet · лінк',i.eth0?.carrier==='1'?num(Number(i.eth0.link_mbps)>0?i.eth0.link_mbps:null,'Мбіт/с'):'Немає / невідомо'));
 for(const [key,label] of [['eth0','LAN'],['tailscale0','Tailscale']]){const v=i[key]||{};grid.append(metric(`${label} · ↓ прийом / ↑ передача`,`${num(v.rx_mbps,'Мбіт/с')} / ${num(v.tx_mbps,'Мбіт/с')}`),metric(`${label} · RX/TX помилки · відкинуто`,`${v.rx_errors||'0'}/${v.tx_errors||'0'} · ${v.rx_dropped||'0'}/${v.tx_dropped||'0'}`))}
 grid.append(metric('SD вільно',num(d.disk_free_mib/1024,'ГБ')),metric('CPU load · 1 хв',num(d.load?.[0],'')),metric('Прапорці живлення',d.power_flags||'—'));
 const note=document.createElement('p');note.className='diag-foot';note.textContent=`Мережеві проби ≈30 с; вік: ${Number.isFinite(age)?Math.max(0,Math.round(age)):'—'} с. Мбіт/с — поточний трафік, не швидкість тарифу. LAN включає камери; Tailscale — тунель, не сумуйте їх. TCP — час встановлення з’єднання, не ping. Лічильники помилок — від запуску інтерфейсу.`;
 box.replaceChildren(title,grid,note);
}
function render(d){
 const list=$('diag-issues'),summary=$('diag-summary'),metrics=$('diag-metrics');list.replaceChildren();metrics.replaceChildren();
 if(d.stale){$('diag-network')?.remove();summary.textContent='Дані застарілі';summary.className='diag-tag error';list.append(issue('Монітор діагностики не оновлюється','Поточний стан борта невідомий.','critical'));$('diag-updated').textContent='Немає свіжого знімка';return}
 const codes=Array.isArray(d.problems)?d.problems:[],critical=codes.some(k=>labels[k]?.[2]);
 summary.textContent=codes.length?`Попереджень: ${codes.length}`:'Основні перевірки ОК';summary.className='diag-tag '+(codes.length?(critical?'error':'warn'):'good');
 networkDetails(d);
 const net=d.network||{},temp=Number(d.temperature_c),mem=d.memory_kib||{};
 metrics.append(metric('Живлення',d.undervoltage_now===true?'Просідання':d.undervoltage_now===false?'Норма зараз':'Невідомо'),metric('Температура',d.temperature_c!=null&&Number.isFinite(temp)?`${temp.toFixed(1)} °C`:'—'),metric('RAM вільно',mem.MemAvailable!=null?`${(mem.MemAvailable/1048576).toFixed(1)} ГБ`:'—'),metric('Інтернет / Tailscale',`${Object.values(net.internet_tcp_443||{}).some(Boolean)?'ОК':'—'} / ${net.tailscale?.state==='Running'&&net.tailscale?.self_online!==false?'ОК':'—'}`));
 for(const code of codes){const v=labels[code]||[code.startsWith('SERVICE_NOT_ACTIVE:')?'Сервіс не працює: '+code.split(':')[1]:code,'Перевірте системний журнал.',true];list.append(issue(v[0],v[1],v[2]?'critical':''))}
 if(!codes.length)list.append(issue('Активних проблем за основними перевірками не виявлено','Це не гарантує доставку відео й телеметрії до QGC.','good'));
 const flags=parseInt(d.power_flags,16);if(!d.undervoltage_now&&(flags&0x10000))list.append(issue('Раніше в цьому запуску було просідання живлення','Зараз напруга нормальна; подія збережена в журналі.'));
 const time=new Date(d.utc);$('diag-updated').textContent=`Знімок: ${Number.isNaN(time.valueOf())?'—':time.toLocaleTimeString()} · перевірка ≈10 с`;
}
async function poll(){try{const r=await fetch('/diagnostics',{cache:'no-store',signal:AbortSignal.timeout(5000)});if(!r.ok)throw Error(r.status);render(await r.json())}catch(e){$('diag-network')?.remove();$('diag-summary').textContent='Немає даних';$('diag-summary').className='diag-tag error';$('diag-metrics').replaceChildren();$('diag-issues').replaceChildren(issue('Не вдалося отримати діагностику','Зв’язок із Raspberry або монітор недоступний.','critical'));$('diag-updated').textContent='Актуальний стан невідомий'}finally{setTimeout(poll,5000)}}
poll();
})();
