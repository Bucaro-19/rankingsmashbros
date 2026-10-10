const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../../ranking-smash-ultimate/organizador.js'),'utf8');
function controller(){const context=vm.createContext({URL,Blob,Uint8Array,AbortController,DOMException,setTimeout,clearTimeout});vm.runInContext(source+';globalThis.progress=SmashSlideProgress;',context);return context.progress;}
const data={organizer:{},players:[{rank:1},{rank:2}]};
function renderer(){return {prepare:async(d,{report})=>{report(1,1,3);report(1,2,3);report(1,3,3);report(2,0,2);report(2,1,2);report(2,2,2);return {images:new Map(),warnings:[]};},draw:()=>({canvas:{width:1920,height:1080}}),png:async()=>new Blob(['png']),filename:(d,p)=>p?`0${p.rank}.png`:'top.png',zip:files=>new Blob(files.map(f=>f.bytes)),abortable:async(promise,signal)=>{if(signal?.aborted)throw new DOMException('cancel','AbortError');return promise;}};}
test('no eager request; load only on demand, session module is reused',async()=>{
 const C=controller();let fetches=0,runs=0;const options={fetcher:async()=>{fetches++;return {ok:true,text:async()=>''};},run:async()=>{runs++;return renderer();}};
 assert.equal(fetches,0);await C.load(undefined,options);await C.load(undefined,options);assert.equal(fetches,1);assert.equal(runs,1);
});
test('generator fetch cancellation releases response and retries',async()=>{
 const C=controller(),controllerAbort=new AbortController();let active=0;
 const pending=C.load(controllerAbort.signal,{fetcher:(url,{signal})=>new Promise((resolve,reject)=>{active++;signal.addEventListener('abort',()=>{active--;reject(new DOMException('cancel','AbortError'));},{once:true});})});
 controllerAbort.abort();await assert.rejects(pending,{name:'AbortError'});assert.equal(active,0);
 await C.load(undefined,{fetcher:async()=>({ok:true,text:async()=>''}),run:async()=>renderer()});
});
test('four actual stages are monotonic and reach 100, PNG count equals top plus real players',async()=>{
 const C=controller(),events=[];const report=C.progress(v=>events.push(v));
 const result=await C.generate(data,{report,loader:async()=>renderer()});assert.equal(result.files.length,3);assert.equal(events.at(-1).percent,100);
 assert.equal(events[0].percent,0);assert.ok(events.every((e,i)=>!i||e.percent>=events[i-1].percent));
 assert.deepEqual([...new Set(events.map(e=>e.stage))],[0,1,2,3]);assert.ok(events.some(e=>e.text==='Cargando personajes (1 de 2)'));assert.ok(events.some(e=>e.text==='Dibujando láminas (2 de 3)'));
 const percent=[];const p=C.progress(e=>percent.push(e.percent));p(3,2,3);p(0,0,1);assert.ok(percent[1]>=percent[0]);
});
test('cancel after drawing one image prevents further drawings and archive',async()=>{
 const C=controller(),abort=new AbortController(),S=renderer();let drawings=0,archives=0;
 S.draw=()=>{drawings++;return {canvas:{}};};S.zip=()=>{archives++;};
 const report=C.progress(e=>{if(e.stage===3&&e.done===1)abort.abort();});
 await assert.rejects(C.generate(data,{signal:abort.signal,report,loader:async()=>S}),{name:'AbortError'});assert.equal(drawings,1);assert.equal(archives,0);
});
test('UI has real ARIA meter, polite step, cancellation, retry, escape and restoration',()=>{
 for(const text of ['role="progressbar"','aria-valuenow','aria-valuetext','aria-live="polite"','panel.focus()','job.opener.focus()',"event.key==='Escape'",'job.controller.abort()','Reintentar'])assert.ok(source.includes(text),text);
});
