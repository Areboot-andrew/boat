// Isolated DOM/API: no network, vehicle commands or real route writes.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
function el(){const children=new Map();return {value:'',textContent:'',open:false,hidden:false,querySelector(s){if(!children.has(s))children.set(s,el());return children.get(s)},append(){},addEventListener(){},showModal(){this.open=true},close(){this.open=false}};}
const doc=el(),timeouts=new Map(),intervals=[],lines=[];let id=0,fail=false,starts=0,saves=0;
const state={armed:false,lease_active:false,autonav:{settings:{radius:4,turn_radius:8},route:[]}};
const api={status:()=>state,preview:async(c,r)=>{if(fail)throw Error('Points must be 2..2000 m apart');return {points:r,length_m:76.6,turn_radius:8}},save:async()=>{saves++},start:async()=>{starts++},stop(){throw Error('Unexpected hardware command')}};
const leaf=()=>({addTo(){return this},remove(){},on(){return this},bindPopup(){return this}});
const ctx={window:{harpoonAuto:api,L:{}},document:{createElement:el,querySelector:s=>doc.querySelector(s),getElementById:s=>doc.querySelector(s),body:el()},map:{on(){}},follow:false,L:{layerGroup:leaf,polyline:(p,o)=>{lines.push({p,o});return leaf()},circle:leaf,marker:leaf,divIcon:()=>({}),DomEvent:{disableClickPropagation(){},disableScrollPropagation(){}}},setTimeout:f=>{timeouts.set(++id,f);return id},clearTimeout:i=>timeouts.delete(i),setInterval:f=>intervals.push(f),Date,Math,Number,JSON};
const src=fs.readFileSync(__dirname+'/route-editor.js','utf8').replace(/\}\)\(\);\s*$/,`window.test={begin,save,start,paint,loadSaved,read:()=>({draft,editing,valid,pendingSaved,previewError,text:status.textContent}),set:r=>{draft=r;paint()},bar,launch};})();`);
vm.runInNewContext(src,ctx);const t=ctx.window.test;
const flush=async()=>{for(const [i,f]of [...timeouts]){timeouts.delete(i);await f()}};
(async()=>{
 t.begin();t.set([[50,30],[50,30.00056],[50.00036,30.00056]]);assert.match(t.read().text,/ламана/);await flush();assert.equal(t.read().valid,true);assert.match(t.read().text,/76.6 м/);assert.ok(lines.some(l=>l.o.color==='#5ff1cf'));
 await t.start(false,el());assert.equal(starts,0);assert.equal(t.launch.open,true);assert.equal(t.launch.querySelector('[data-go]').disabled,true);
 assert.equal(saves,1);assert.equal(t.read().editing,false);await flush();
 // Stale pre-save polling MUST NOT replace acknowledged route with empty route.
 intervals[0]();assert.equal(t.read().draft.length,3);assert.ok(t.read().pendingSaved);
 state.autonav={settings:{turn_radius:8,radius:4},route:[[50,30],[50,30.00056],[50.00036,30.00056]]};intervals[0]();assert.equal(t.read().pendingSaved,null);
 // Opening settings without changes no longer requires another save to exit edit.
 t.begin();await flush();await t.start(false,el());assert.equal(t.read().editing,false);assert.equal(starts,0);assert.equal(t.launch.open,true);assert.equal(saves,1);
 await t.launch.querySelector('[data-go]').onclick();assert.equal(starts,0,'unchecked confirmation never starts');
 t.launch.querySelector('[data-verified]').checked=true;await t.launch.querySelector('[data-go]').onclick();assert.equal(starts,1,'explicit confirmation invokes mocked start');
 t.begin();fail=true;t.set([[50,30],[51,31]]);await flush();assert.equal(t.read().valid,false);assert.match(t.read().text,/ламана.*Points/);await t.start(false,el());assert.match(t.read().text,/Points/);assert.equal(starts,1);
 state.armed=true;await assert.rejects(t.save(),/DISARM/);assert.equal(t.read().draft.length,2);assert.equal(saves,1);
 console.log('PASS: line/distance, preview error retained, stale save polling, key order, unchanged edit, armed save retains draft; no movement');
})().catch(e=>{console.error(e);process.exitCode=1});
