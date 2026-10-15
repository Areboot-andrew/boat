// Isolated state tests: fake DOM, USB/network never used.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
function el(){const children=new Map();return {value:'25',checked:false,disabled:false,open:false,dataset:{},textContent:'',style:{},querySelector(s){if(!children.has(s))children.set(s,el());return children.get(s)},querySelectorAll(){return ['check','manual','arm','disarm'].map(a=>{const b=this.querySelector('[data-action='+a+']');b.dataset.action=a;return b})},append(){},remove(){},addEventListener(){},showModal(){this.open=true},close(){this.open=false},matches(){return false}};}
const panel=el(),top=el(),dialog=el(),logsDialog=el(),consolePage=el(),sessions=el();panel.querySelector('select').value='keyboard';
const events={},packets=[],window={addEventListener(k,v){events[k]=v}},doc=el();
let focused=true;
const document={createElement:el,querySelector:s=>doc.querySelector(s),hasFocus:()=>focused,hidden:false,addEventListener:(k,v)=>events[k]=v};
let pad=null,failPoll=false,failTick=false,failStart=false,releaseStop=null,delayStop=false;
const ready={connected:true,armed:false,mode:4,state:3,blocked:null,claim_blocked:null,lease_active:false,events:[],parameters:{},applied:[0,0],connection_phase:'ready'};
const ctx={window,document,navigator:{getGamepads:()=>pad?[pad]:[]},setInterval(){},setTimeout(){},AbortSignal:{timeout(){}},Date,Math,Number,Set,
 fetch:async(url,o)=>{if(o?.method==='POST'){const p=JSON.parse(o.body);packets.push(p);if(failTick&&p.action==='tick'||failStart&&p.action==='auto_start')throw Error('lost reply');if(delayStop&&p.action==='emergency_stop')await new Promise(r=>releaseStop=r);return {ok:true,json:async()=>p.action==='claim'?{lease:'L'}:{nonce:'N'}}}if(failPoll&&url==='/control/status')throw Error('network gap');return {ok:true,json:async()=>url==='/diagnostics'?{problems:[]}:ready}}};
let src=fs.readFileSync(__dirname+'/live-control.js','utf8');
src=src.replace(/\};\s*$/,`window.test={setup(s={}){state={...${JSON.stringify(ready)},armed:true,mode:0,lease_active:true,...s};freshAt=Date.now();lease='L';nonce='N';confirmAction=null;cruise=null;linkRecovering=false;linkWarning=false;keys.clear();},expireTest(){servoTest.until=0},tick,poll,keys,stop,read:()=>({lease,cruise,linkRecovering}),setPadId:x=>padId=x};};`);
vm.runInNewContext(src,ctx);window.harpoonLiveControl({panel,top,dialog,logsDialog,consolePage,sessions,pages:[{b:{click(){}}}]});
(async()=>{
 await new Promise(r=>setImmediate(r));assert.equal(packets.length,0,'startup must be read only');
 assert.equal(top.querySelector('[data-action=disarm]').disabled,false,'DISARM is never disabled by UI');
 const t=window.test;assert.throws(()=>window.harpoonAuto.testSteer(1),/сесія/);
 t.setup();window.harpoonAuto.testSteer(1);await t.tick();assert.equal(packets.at(-1).steer,.1);assert.equal(packets.at(-1).throttle,0);
 t.expireTest();await t.tick();assert.equal(packets.at(-1).steer,0);assert.equal(packets.at(-1).throttle,0,'expired test returns neutral');
 window.harpoonAuto.testSteer(-1);window.harpoonAuto.cancelTest();await t.tick();assert.equal(packets.at(-1).steer,0);assert.equal(packets.at(-1).throttle,0);
 t.setup({applied:[0,.1]});assert.throws(()=>window.harpoonAuto.testSteer(-1),/зупини тягу/);
 t.setup({mode:4});assert.throws(()=>window.harpoonAuto.testSteer(-1),/сесія/);
 t.setup();doc.querySelector('.auto-start-dialog').open=true;events.keydown({code:'ArrowUp',target:el(),preventDefault(){}});assert.equal(t.keys.size,0);doc.querySelector('.auto-start-dialog').open=false;
 t.setup();t.keys.add('ArrowUp');await t.tick();assert.equal(packets.at(-1).throttle,.25);
 panel.querySelector('[data-cruise]').onclick();assert.equal(t.read().cruise,null);panel.querySelector('[data-cruise]').onclick();assert.equal(t.read().cruise,.25);
 t.keys.clear();panel.querySelector('input').value='50';panel.querySelector('input').oninput();await t.tick();assert.equal(packets.at(-1).throttle,.25,'raise cap must not raise cruise');
 t.setup();events.keydown({code:'Space',target:el()});assert.equal(t.read().lease,'L','Space is not STOP');
 t.keys.add('ArrowUp');focused=false;const beforeBlur=packets.length;events.blur();assert.equal(t.read().lease,'L');assert.equal(packets.length,beforeBlur,'blur sends no STOP or DISARM');assert.equal(t.keys.size,0);assert.equal(t.read().cruise,null);await t.tick();assert.equal(packets.at(-1).action,'tick');assert.equal(packets.at(-1).throttle,0,'unfocused keyboard does not latch throttle');focused=true;
 panel.querySelector('select').value='gamepad';t.setup();t.setPadId(0);pad={connected:true,mapping:'standard',index:0,axes:[0,0,1,0,1,1]};await t.tick();assert.equal(packets.at(-1).steer,.6);assert.equal(packets.at(-1).throttle,.25,'center = half cap');
 pad.axes[1]=1;await t.tick();assert.equal(packets.at(-1).throttle,0);
 pad.axes[1]=-1;await t.tick();assert.equal(packets.at(-1).throttle,.5);
 focused=false;events.blur();assert.equal(t.read().lease,'L','visible joystick session survives blur');await t.tick();assert.equal(packets.at(-1).action,'tick','joystick sends while unfocused');assert.equal(packets.at(-1).throttle,.5);
 document.hidden=true;events.visibilitychange();assert.equal(t.read().lease,'L','hidden page retains session');assert.equal(packets.at(-1).action,'tick');assert.equal(packets.at(-1).throttle,0);assert.equal(packets.at(-1).resync,true);const hiddenCount=packets.length;pad=null;await t.tick();assert.equal(packets.length,hiddenCount,'hidden page sends no motion and does not stop on unavailable gamepad');assert.equal(t.read().lease,'L');
 events.pagehide();assert.equal(t.read().lease,'L','pagehide never releases or disarms');assert.equal(packets.at(-1).action,'tick');assert.equal(packets.at(-1).throttle,0);
 document.hidden=false;pad={connected:true,mapping:'standard',index:0,axes:[0,-1,0,0,1,1]};await t.tick();assert.equal(packets.at(-1).throttle,0,'return with high stick remains neutral');assert.equal(t.read().linkRecovering,true);pad.axes[1]=1;await t.tick();assert.equal(t.read().linkRecovering,false,'neutral returns same session');
 t.setup();pad.axes[4]=0;await t.tick();assert.equal(t.read().lease,null,'OFF stops while unfocused');pad.axes[4]=1;
 focused=true;
 for(const values of [[0,1],[1,0],[-1,1],[1,NaN],[1,undefined]]){t.setup({mode:4,armed:false});pad.axes[4]=values[0];pad.axes[5]=values[1];await t.tick();assert.equal(t.read().lease,null,'gate stops even in HOLD/disarmed');assert.equal(packets.at(-1).action,'stop');}
 pad.axes[4]=pad.axes[5]=1;await t.tick();assert.equal(t.read().lease,null,'switches must not auto-claim');
 t.setup();pad=null;await t.tick();assert.equal(t.read().lease,null,'lost pad stops');
 t.setup();panel.querySelector('[data-log]').onclick();assert.equal(logsDialog.open,true);assert.equal(dialog.open,false);assert.equal(t.read().lease,'L');
 panel.querySelector('[data-telemetry]').onclick();assert.equal(dialog.open,true);assert.equal(t.read().lease,'L');dialog.close();
 panel.querySelector('select').value='keyboard';t.setup();failPoll=true;await t.poll();assert.equal(t.read().lease,'L','one poll failure preserves session');failPoll=false;
 t.keys.add('ArrowUp');failTick=true;await t.tick();assert.equal(t.read().lease,'L');assert.equal(t.read().linkRecovering,true);failTick=false;await t.tick();assert.equal(packets.at(-1).throttle,0,'lost ACK recovered with neutral');assert.equal(packets.at(-1).resync,true);assert.equal(t.read().linkRecovering,false);
 panel.querySelector('select').value='gamepad';pad={connected:true,mapping:'standard',index:0,axes:[0,-1,0,0,1,1]};t.setup();failTick=true;await t.tick();failTick=false;await t.tick();assert.equal(packets.at(-1).throttle,0);assert.equal(t.read().linkRecovering,true,'high stick cannot restart after loss');pad.axes[1]=1;await t.tick();assert.equal(t.read().linkRecovering,false,'physical neutral restores same session');
 panel.querySelector('select').value='keyboard';t.setup();failStart=true;
 await assert.rejects(window.harpoonAuto.start(false),/lost reply/);failStart=false;
 assert.equal(t.read().lease,'L');assert.equal(t.read().linkRecovering,true);await t.tick();
 assert.equal(packets.at(-1).resync,true);assert.equal(packets.at(-1).throttle,0,'lost auto_start ACK uses neutral resync, not manual takeover');
 t.setup();t.keys.add('ArrowUp');delayStop=true;const stopping=window.harpoonAuto.stop();
 assert.equal(t.read().lease,null,'STOP cancels locally before server reply');const count=packets.length;
 await t.tick();assert.equal(packets.length,count,'no new motion while STOP pending');releaseStop();await stopping;delayStop=false;
 assert.ok(!packets.some(p=>['arm','manual','disarm'].includes(p.action)));
 console.log('PASS: startup read-only; cruise/cap; Space; blur; joystick bottom/center/top; disconnect; separate logs; no hardware access');
})().catch(e=>{console.error(e);process.exitCode=1});
