const test = require('node:test');
const assert = require('node:assert/strict');
const m = require('../../ranking-smash-ultimate/panel-model.js');

const report = {
  updatedAt:'2026-10-21T15:30-06:00', counterStartedAt:'2026-10-18',
  today:{date:'2026-10-21',visitors:5,pageviews:9,registrations:1},
  daily:[{date:'2026-10-18',visitors:3,pageviews:4,registrations:0},{date:'2026-10-19',visitors:0,pageviews:0,registrations:0},{date:'2026-10-20',visitors:7,pageviews:12,registrations:2}],
  periods:{'7':{from:'2026-10-14',to:'2026-10-20',days:7,daysWithData:3,visitors:8,previous:null,pages:{home:10,metodologia:0,cuenta:4,top20:2,torneos:0}},
    '90':{from:'2026-07-23',to:'2026-10-20',days:90,daysWithData:3}},
  weekly:{'90':[{from:'2026-10-18',to:'2026-10-20',visitors:8,pageviews:16,registrations:2,partial:true}]}
};
test('dates stay in the Guatemala calendar and cross months and years',()=>{
  assert.equal(m.dmy('2026-10-07'),'07/10/2026');
  assert.equal(m.shift('2026-12-31',1),'2027-01-01');
  assert.equal(m.shift('2026-03-01',-1),'2026-02-28');
  assert.equal(m.DOW[m.parts('2026-10-07').dow],'miércoles');
  assert.equal(m.span('2026-10-18','2026-10-20'),3);
});
test('daily bars: no data before the counter, real zeros after, today last and partial',()=>{
  const items=m.items(report,'7');
  assert.equal(items.length,8);
  assert.deepEqual(items.slice(0,4).map(i=>!!i.none),[true,true,true,true]);
  assert.equal(items[4].label,'domingo 18/10'); assert.equal(items[5].visitors,0); assert.equal(items[5].none,undefined);
  assert.deepEqual([items[7].short,items[7].partial,items[7].visitors],['Hoy',true,5]);
  assert.match(items[7].label,/en curso hasta 15:30/);
  assert.equal(m.defaultIndex(items),6);
  assert.equal(m.defaultIndex([{none:true},{partial:true,visitors:1}]),1);
  assert.equal(m.defaultIndex([{none:true}]),-1);
});
test('weekly bars come from the server and mark the clipped week',()=>{
  const items=m.items(report,'90');
  assert.equal(items.length,1); assert.equal(items[0].partial,true); assert.equal(items[0].weekly,true);
  assert.equal(items[0].label,'Semana 18/10 – 20/10 · 3 días (empieza el contador)');
  assert.match(m.reading(items[0]),/^8 visitantes \(semana\) · 16 vistas · 2 registros nuevos · parcial$/);
  assert.equal(m.reading({visitors:1,pageviews:1,registrations:1}),'1 visitante · 1 vista · 1 registro nuevo');
});
test('keyboard skips days without data and stops at the ends',()=>{
  const items=m.items(report,'7');
  assert.equal(m.step(items,6,'ArrowLeft'),5); assert.equal(m.step(items,4,'ArrowLeft'),4);
  assert.equal(m.step(items,7,'ArrowRight'),7); assert.equal(m.step(items,6,'Home'),4); assert.equal(m.step(items,4,'End'),7);
  assert.equal(m.step(items,6,'Enter'),6);
});
test('comparison is always worded and never invented',()=>{
  assert.equal(m.change('7',{visitors:8,previous:null}).text,'Sin periodo anterior completo para comparar');
  assert.equal(m.change('season',{visitors:8,previous:{visitors:4}}).text,'Primera temporada medida: sin comparación');
  assert.deepEqual(m.change('30',{visitors:112,previous:{visitors:100}}),{kind:'up',text:'▲ 12% más que los 30 días anteriores (100)'});
  assert.deepEqual(m.change('7',{visitors:50,previous:{visitors:100}}),{kind:'down',text:'▼ 50% menos que los 7 días anteriores (100)'});
  assert.equal(m.change('7',{visitors:100,previous:{visitors:100}}).kind,'none');
  assert.deepEqual(m.change('7',{visitors:3,previous:{visitors:0}}),{kind:'up',text:'▲ Más que los 7 días anteriores (0)'});
  assert.equal(m.change('7',{visitors:0,previous:{visitors:0}}).kind,'none');
});
test('short history notice, axis and page ranking',()=>{
  assert.match(m.shortNotice(report,report.periods['7']),/empezó el 18\/10\/2026: este periodo solo tiene 3 días completos/);
  assert.equal(m.shortNotice(report,{days:7,daysWithData:7}),''); assert.equal(m.shortNotice(report,{days:7,daysWithData:0}),'');
  assert.deepEqual([m.axisMax([]),m.axisMax([3]),m.axisMax([7]),m.axisMax([18]),m.axisMax([120]),m.axisMax([260]),m.axisMax([1000])],[4,4,10,20,200,500,1000]);
  const pages=m.pages(report.periods['7']);
  assert.deepEqual(pages.map(p=>[p.position,p.name,p.views,p.percent,p.width]).slice(0,3),[[1,'Inicio / ranking',10,63,100],[2,'Cuenta',4,25,40],[3,'Análisis del top 20',2,13,20]]);
  assert.deepEqual(m.pages({pages:{home:0,cuenta:0}}).map(p=>[p.percent,p.width]),[[0,0],[0,0]]);
});
test('agenda adds a distinct label and historical torneos keeps its meaning and share',()=>{
  const old={pages:{home:10,torneos:2}};
  const saved=JSON.stringify(old);
  assert.equal(m.pages(old).find(p=>p.key==='torneos').name,'Análisis de torneos');
  assert.equal(m.pages(old).find(p=>p.key==='torneos').percent,17);
  assert.equal(JSON.stringify(old),saved);
  const pages=m.pages({pages:{home:10,torneos:2,agendaTorneos:8}});
  assert.deepEqual(pages.map(p=>[p.key,p.name,p.views,p.percent,p.width]),[
    ['home','Inicio / ranking',10,50,100], ['agendaTorneos','Agenda de torneos',8,40,80],
    ['torneos','Análisis de torneos',2,10,20]
  ]);
  assert.equal(pages.reduce((n,p)=>n+p.views,0),20);
});

test('registration disclosures retain server day/week scopes and Guatemala time',()=>{
  const items=m.items(report,'7');
  assert.equal(items[4].scope,'2026-10-18_2026-10-18');
  assert.equal(items.at(-1).scope,'today');
  assert.equal(m.items(report,'90')[0].scope,'2026-10-18_2026-10-20');
  assert.equal(m.registrationTime('2026-10-15T23:59:59-06:00'),'15/10/2026 · 23:59:59 (Guatemala)');
});

// Execute the actual controller in a minimal DOM. Only the startup call is replaced;
// network/body timing and rendering remain the real panel code.
function registrationController(fetch) {
  const fs=require('node:fs'), vm=require('node:vm');
  const nodes=new Map(), listeners=new Map(); let reloads=0;
  const node=id=>{if(!nodes.has(id))nodes.set(id,{innerHTML:'',hidden:true,attrs:{},setAttribute(k,v){this.attrs[k]=v;},replaceChildren(){this.innerHTML='';},append(){},querySelector(){return {focus(){}};},addEventListener(){}});return nodes.get(id);};
  const source=fs.readFileSync(require.resolve('../../ranking-smash-ultimate/panel.js'),'utf8');
  const end='  load();\n})();'; assert.ok(source.endsWith(end+'\n'));
  const code=source.slice(0,source.lastIndexOf(end))+`  module.exports={
    open(scope){closeRegistrations(false);registrationScope=scope;registrationSnapshot='opaque-report-token';report={today:{date:'2026-10-10'}};return fetchRegistrations();},
    more(){return fetchRegistrations(true);},close(){closeRegistrations(false);},
    state(){return {items:registrationData,next:registrationNext,total:registrationTotal};}
  };
})();`;
  const context={PanelModel:m,document:{getElementById:node,querySelectorAll:()=>[],addEventListener:(k,v)=>listeners.set(k,v)},localStorage:{getItem:()=>null},
    fetch,AbortController,URLSearchParams,setTimeout,clearTimeout,module:{exports:{}},location:{reload(){reloads++;}}};
  vm.runInNewContext(code,context);
  return {api:context.module.exports,panel:node('registration-list'),reloads:()=>reloads};
}
const row=tag=>({tag,registeredAt:'2026-10-10T14:00:00-06:00',linked:true});
const reply=(items,total=items.length,nextOffset=null)=>({status:200,ok:true,json:async()=>({ok:true,registrations:{items,total,nextOffset}})});

test('closing/changing scope ignores a late JSON body even after headers arrived',{timeout:2000},async()=>{
  let resolveBody, notifyBody, calls=0, firstSignal;
  const bodyStarted=new Promise(resolve=>{notifyBody=resolve;});
  const body=new Promise(resolve=>{resolveBody=resolve;});
  const h=registrationController(async(url,options)=>{
    if(++calls===1){firstSignal=options.signal;return {status:200,ok:true,json(){notifyBody();return body;}};}
    return reply([row('Nuevo periodo')]);
  });
  const first=h.api.open('7'); await bodyStarted;
  await h.api.open('30'); assert.equal(firstSignal.aborted,true);
  resolveBody({ok:true,registrations:{items:[row('Respuesta antigua')],total:1,nextOffset:null}}); await first;
  assert.equal(h.api.state().items[0].tag,'Nuevo periodo');
  assert.match(h.panel.innerHTML,/Nuevo periodo/); assert.doesNotMatch(h.panel.innerHTML,/Respuesta antigua/);
});
test('loading-more errors preserve total/rows and retry the same bounded offset',async()=>{
  const urls=[]; let calls=0;
  const h=registrationController(async url=>{urls.push(url);calls++;
    if(calls===1)return reply(Array.from({length:50},(_,i)=>row(i===0?'<Jugador QA>':`Fila ${i}`)),55,50);
    if(calls===2)return {status:503,ok:false,json:async()=>({ok:false})};
    return reply(Array.from({length:5},(_,i)=>row(`Segundo lote ${i}`)),55,null);
  });
  await h.api.open('all'); await h.api.more();
  assert.equal(h.api.state().items.length,50); assert.equal(h.api.state().total,55); assert.equal(h.api.state().next,50);
  assert.match(h.panel.innerHTML,/55 cuentas/); assert.match(h.panel.innerHTML,/Reintentar/); assert.match(h.panel.innerHTML,/&lt;Jugador QA&gt;/);
  await h.api.more(); assert.equal(h.api.state().items.length,55); assert.equal(h.api.state().next,null);
  for(const url of urls.slice(1)) {const q=new URL(url,'https://test.invalid').searchParams;assert.equal(q.get('offset'),'50');assert.equal(q.get('snapshot'),'opaque-report-token');}
});
test('access loss clears rows; expired report offers to refresh instead of looping',async()=>{
  for(const status of [401,403]) {
    const h=registrationController(async()=>({status})); await h.api.open('all');
    assert.equal(h.reloads(),1); assert.equal(h.api.state().items.length,0); assert.equal(h.panel.hidden,true);
  }
  const h=registrationController(async()=>({status:400,ok:false,json:async()=>({ok:false,reason:'registration_snapshot_expired'})}));
  await h.api.open('all'); assert.match(h.panel.innerHTML,/Actualizar datos/); assert.doesNotMatch(h.panel.innerHTML,/data-registration-retry/);
});
