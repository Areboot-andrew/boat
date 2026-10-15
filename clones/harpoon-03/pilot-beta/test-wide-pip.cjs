const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const code=fs.readFileSync(__dirname+'/beta.js','utf8');
const handlers={},style={};let saved,full=null;
const tile={hidden:false,style,getBoundingClientRect:()=>({left:20,top:30,width:200,height:120})};
const handle={closest:s=>s==='.camera-mini'?tile:handle,matches:()=>false};
const visual={querySelector:()=>tile,getBoundingClientRect:()=>({left:0,top:0,width:1200,height:500}),addEventListener:(k,f)=>handlers[k]=f,setPointerCapture(){},hasPointerCapture:()=>false};
const context={visual,stage:{getBoundingClientRect:()=>({left:0,top:0})},localStorage:{getItem:()=>null,setItem:(k,v)=>saved=JSON.parse(v)},document:{get fullscreenElement(){return full},addEventListener(){}},MutationObserver:class{observe(){}},ResizeObserver:class{observe(){}},requestAnimationFrame:()=>1};
vm.runInNewContext(code.slice(code.indexOf(' const pipKey='),code.indexOf(" const extra=make")),context);
function event(x,y){return {target:handle,button:0,pointerId:1,clientX:x,clientY:y,preventDefault(){},stopImmediatePropagation(){}};}
handlers.pointerdown(event(20,30));handlers.pointermove(event(950,250));
assert.equal(style.left,'950px');assert.equal(style.top,'250px'); // beyond 800px video: on map
handlers.pointermove(event(1500,800));assert.equal(style.left,'1000px');assert.equal(style.top,'380px');
handlers.pointerup(event(1500,800));assert.ok(saved);
full=tile;handlers.pointerdown(event(0,0));handlers.pointermove(event(10,10));assert.equal(style.left,'1000px');
assert.match(code,/cameraWidth\*8\/16/);
console.log('PASS: PiP crosses video boundary, clamps to whole visual, persists; fullscreen ignored; 16:8');
