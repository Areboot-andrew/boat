// No network, serial, or actuator access: full browser sequence in an isolated VM.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
function el(){const children=new Map();return {value:'25',checked:false,disabled:false,open:false,dataset:{},textContent:'',style:{},querySelector(s){if(!children.has(s))children.set(s,el());return children.get(s)},querySelectorAll(){return ['check','manual','arm','disarm'].map(a=>{const b=this.querySelector('[data-action='+a+']');b.dataset.action=a;return b})},append(){},remove(){},addEventListener(){},showModal(){this.open=true},close(){this.open=false},matches(){return false}}}
async function scenario(kind){
 const panel=el(),top=el(),dialog=el(),logsDialog=el(),consolePage=el(),sessions=el(),doc=el(),packets=[];
 panel.querySelector('select').value='gamepad';let focused=true,hidden=false,modal=false;
 let pad={id:'TX12',index:0,connected:true,mapping:'standard',axes:[0,1,0,0,1,1,-1]};
 const ready={connected:true,armed:false,mode:4,state:3,blocked:null,lease_active:false,events:[],applied:[0,0]};
 const window={addEventListener(){}};
 const ctx={window,document:{createElement:el,querySelector:s=>doc.querySelector(s),hasFocus:()=>focused,get hidden(){return hidden},addEventListener(){}},navigator:{getGamepads:()=>pad?[pad]:[]},setInterval(){},setTimeout(){},AbortSignal:{timeout(){}},Date,Math,Number,Set,
 fetch:async(url,o)=>{if(o?.method!=='POST')return {ok:true,json:async()=>url==='/diagnostics'?{problems:[]}:ready};const p=JSON.parse(o.body);packets.push(p);
 if(p.action==='manual'){if(kind==='manual-denied')return {ok:false,json:async()=>({error:'DENIED'})};window.test.update({mode:0});if(kind==='off-during-manual'){pad.axes[4]=0;window.test.watch();}}
 if(p.action==='arm')window.test.update({armed:true});
 return {ok:true,json:async()=>p.action==='claim'?{lease:'L'}:{nonce:'N'}};}};
 let src=fs.readFileSync(__dirname+'/live-control.js','utf8').replace(/\};\s*$/,`window.test={watch:watchSwitchStart,update:d=>{state={...state,...d};freshAt=Date.now()},stop,read:()=>({lease,switchReady,switchStarting})};};`);
 vm.runInNewContext(src,ctx);window.harpoonLiveControl({panel,top,dialog,logsDialog,consolePage,sessions,pages:[{b:{click(){}}}]});
 const flush=async()=>{for(let i=0;i<15;i++)await new Promise(r=>setImmediate(r))};await flush();const t=window.test;
 t.watch();await flush();assert.equal(packets.length,0,'ON at startup must never ARM');
 pad.axes[4]=0;t.watch();assert.equal(t.read().switchReady,true);
 if(kind==='high-throttle')pad.axes[1]=-1;
 if(kind==='modal')dialog.open=true;
 if(kind==='blur')focused=false;
 if(kind==='stale')t.update({connected:false});
 pad.axes[4]=1;t.watch();await flush();
 const actions=packets.map(p=>p.action);
 if(kind==='ok'){
  assert.deepEqual(actions,['claim','tick','manual','arm']);assert.equal(packets[1].throttle,0);assert.equal(packets[1].steer,0);assert.equal(packets[3].confirm,'ARM');assert.equal(t.read().lease,'L');
  t.stop('loss');t.update({armed:false,lease_active:false});t.watch();await flush();assert.equal(packets.filter(p=>p.action==='arm').length,1,'no automatic re-ARM after STOP');
 }else{assert.ok(!actions.includes('arm'),kind+' must not ARM');if(['manual-denied','off-during-manual'].includes(kind))assert.ok(actions.includes('stop'));}
 // Keyboard enable occupies PREARM position; legacy lower button is hidden.
 panel.querySelector('select').value='keyboard';panel.querySelector('select').onchange();t.update({armed:false,lease_active:false,connected:true});
 assert.equal(panel.querySelector('[data-test]').hidden,true);
 await top.querySelector('[data-action=check]').onclick();assert.equal(top.querySelector('[data-action=check]').textContent,'Підтверджую ввімкнення');
}
(async()=>{for(const kind of ['ok','high-throttle','modal','blur','stale','manual-denied','off-during-manual'])await scenario(kind);console.log('PASS: OFF→ON claim/MANUAL/ARM; no startup/reconnect auto-ARM; high throttle/focus/modal/stale/denial/OFF cancel; keyboard top enable')})().catch(e=>{console.error(e);process.exitCode=1});
