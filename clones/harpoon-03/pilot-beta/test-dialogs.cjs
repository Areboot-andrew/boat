const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(__dirname+'/beta.js','utf8');
const calls=[];
const ctx={dialog:{close:()=>calls.push('telemetry.close'),showModal:()=>calls.push('telemetry.open')},logsDialog:{close:()=>calls.push('logs.close'),showModal:()=>calls.push('logs.open')},pages:[{b:{click:()=>calls.push('nav.select')}}],reset:()=>calls.push('reset')};
for(const [button,expected] of [['telemetry',['logs.close','nav.select','telemetry.open','reset']],['log',['telemetry.close','logs.open','reset']]]){
 const line=source.split('\n').find(s=>s.includes("panel.querySelector('[data-"+button+"]').onclick="));
 assert.ok(line);const fn=line.slice(line.indexOf('=')+1).trim().replace(/;$/,'');
 calls.length=0;vm.runInNewContext('('+fn+')()',ctx);assert.deepEqual(calls,expected);
}
assert.ok(!source.includes("tab('Консоль',consolePage)"));
assert.ok(!source.includes("tab('Сесії',sessions)"));
console.log('PASS: independent log/telemetry dialog handlers; no log tabs in telemetry');
