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
