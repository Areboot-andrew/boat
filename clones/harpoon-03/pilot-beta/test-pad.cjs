const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
function el(){const children={};return {value:'',checked:false,style:{},append(){},insertBefore(){},querySelectorAll(){return []},replaceChildren(){},querySelector(s){return children[s]??=el()},showModal(){this.open=true},close(){this.open=false}}}
let pad={id:'TX12 HID',index:0,connected:true,mapping:'',axes:[0,1,0,0],buttons:[]};
const saved={selected:pad.id,profiles:{[pad.id]:{steer:0,throttle:1,invertSteer:false,invertThrottle:false,deadzone:.06}}};
let now=1000;
const ctx={Date:{now:()=>now},window:{},document:{createElement:el,body:el()},navigator:{getGamepads:()=>pad?[pad]:[]},localStorage:{getItem:()=>JSON.stringify(saved)},setInterval(){}};
vm.runInNewContext(fs.readFileSync(__dirname+'/pad-config.js','utf8'),ctx);
const api=ctx.window.harpoonPadConfig({panel:el(),onOpen(){}});
assert.equal(api.getPad().id,'TX12 HID');assert.deepEqual(Array.from(api.axes(pad)),[0,0]);
pad.axes=[1,-1];assert.deepEqual(Array.from(api.axes(pad)),[1,1]);
assert.deepEqual(Array.from(api.axes(pad,{...saved.profiles[pad.id],invertSteer:true,invertThrottle:true})),[-1,0]);
pad.axes=[.03,0];assert.deepEqual(Array.from(api.axes(pad)),[0,.5]);
assert.throws(()=>api.axes(pad,{...saved.profiles[pad.id],steer:1}));
assert.throws(()=>api.axes({...pad,axes:[NaN,0]}));
assert.equal(api.getPad(1),undefined);pad=null;assert.equal(api.getPad(),undefined);
pad={id:'Radiomaster TX12 Joystick (Vendor: 1209 Product: 4f54)',connected:true,mapping:'',axes:[0,0,-.710,0,1,1,-1]};
assert.deepEqual(Array.from(api.axes(pad)),[0,0]);pad.axes[2]=.011;assert.deepEqual(Array.from(api.axes(pad)),[0,1]);
pad.axes[2]=(-.710+.011)/2;assert.ok(Math.abs(api.axes(pad)[1]-.5)<1e-9);
for(const [v,c] of [[-1,.5],[0,.6],[1,.7]]){pad.axes[6]=v;assert.ok(api.mode(pad).cap<=c);now+=210;assert.equal(api.mode(pad).cap,c)}
pad.axes[6]=.5;assert.equal(api.mode(pad).cap,.5);now+=310;assert.equal(api.mode(pad).cap,0);
pad.axes[6]=1;assert.ok(api.mode(pad).cap<=.5);now+=210;assert.equal(api.mode(pad).cap,.7);
pad.axes[6]=-1;assert.equal(api.mode(pad).cap,.5);pad.axes[6]=NaN;assert.throws(()=>api.mode(pad));
console.log('PASS: TX12 nonstandard mapping; zero/full/center; inversion; deadzone; invalid axes; disconnect; no network');
