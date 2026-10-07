const {test}=require('node:test');
const assert=require('node:assert/strict');
const m=require('../../ranking-smash-ultimate/account-model.js');
test('movement needs a real previous cut, preserves new/up/down/tie',()=>{
  assert.equal(m.movement({rank:12,previousRank:1}).text,'Sin comparación previa');
  assert.equal(m.movement({rank:null,previousCutAt:'2026-10-01'}).kind,'none');
  assert.equal(m.movement({rank:10,previousRank:null,previousCutAt:'2026-10-01'}).kind,'new');
  assert.match(m.movement({rank:10,previousRank:12,previousCutAt:'2026-10-01'}).text,/▲ Subiste 2/);
  assert.match(m.movement({rank:12,previousRank:10,previousCutAt:'2026-10-01'}).text,/▼ Bajaste 2/);
  assert.equal(m.movement({rank:12,previousRank:12,previousCutAt:'2026-10-01'}).text,'= Mismo puesto');
  assert.equal(m.movement({rank:10,previousRank:12,previousCutAt:'2026-10-01'}).text,'▲ Subiste 2 puestos · antes #12');
  assert.equal(m.movement({rank:11,previousRank:10,previousCutAt:'2026-10-01'}).text,'▼ Bajaste 1 puesto · antes #10');
});
test('main assignment swaps duplicates and never mutates saved choices',()=>{
  const saved=['1','2','3'];
  assert.deepEqual(m.assign(saved,0,'3'),['3','2','1']);
  assert.deepEqual(m.assign(saved,1,'3'),['1','3','2']);
  assert.deepEqual(m.assign(saved,2,'4'),['1','2','4']);
  assert.deepEqual(saved,['1','2','3']);
  assert.deepEqual(m.assign([],2,'3'),[]);
  assert.deepEqual(m.assign(['1'],2,'3'),['1','3']);
});
test('secondary removal compacts slots; main remains required',()=>{
  assert.deepEqual(m.remove(['1','2','3'],1),['1','3']);
  assert.deepEqual(m.remove(['1','2','3'],0),['1','2','3']);
  assert.equal(m.dirty(['1','3'],['1','2']),true);
  assert.equal(m.dirty(['1'],['1']),false);
});
test('history distinguishes counted events from known excluded attendance',()=>{
  const view={events:[{id:'GT',counts:true},{id:'MX',counts:false}]};
  assert.deepEqual(m.history(view,'all'),view.events);
  assert.equal(m.history(view,'excluded')[0].id,'MX');
  assert.equal(m.history(view,'counted')[0].id,'GT');
  assert.equal(m.normalize('Pokémon'),'pokemon');
});

test('requirements show progress without exceeding the minimum',()=>{
  const rules={playerMinimumEvents:2,playerMinimumSets:4};
  assert.deepEqual(m.requirements({countedEvents:1,wins:2,losses:1},rules).map(r=>[r.shown,r.max,r.done,r.missing]),[[1,2,false,1],[3,4,false,1]]);
  assert.deepEqual(m.requirements({countedEvents:5,wins:9,losses:0},rules).map(r=>[r.shown,r.done,r.missing]),[[2,true,0],[4,true,0]]);
});
test('set score is read from the published text and never invented',()=>{
  const win={playerIds:['1','2'],playerTags:['Yo','Rival'],score:'CG/ML | Yo 3 - Salamandra | Rival 0'};
  assert.deepEqual(m.setScore(win,'1'),{won:true,text:'3–0'});
  assert.deepEqual(m.setScore(win,'2'),{won:false,text:'0–3'});
  // start.gg may name the loser first; the winner is always playerIds[0].
  assert.deepEqual(m.setScore({playerIds:['1','2'],score:'Rival 1 - Yo 2'},'1'),{won:true,text:'2–1'});
  assert.deepEqual(m.setScore({playerIds:['1','2'],score:'Krlos04 2 - Player7 0'},'2'),{won:false,text:'0–2'});
  for (const score of ['DQ','',null,'Yo 1 - Rival 1','Yo W - Rival L']) assert.equal(m.setScore({playerIds:['1','2'],score},'1').text,'—');
  assert.equal(m.setScore(win,'9'),null);
  assert.deepEqual(m.opponent(win,'2'),{id:'1',tag:'Yo',won:false});
  assert.equal(m.opponent({playerIds:['1','2']},'1').tag,'Rival sin alias');
});
test('head to head counts only sets between both players, newest first',()=>{
  const results=[{playerIds:['1','2'],date:'2026-01-01'},{playerIds:['2','1'],date:'2026-03-01'},{playerIds:['1','3'],date:'2026-02-01'},{playerIds:['2','3'],date:'2026-02-02'}];
  const h=m.headToHead(results,'1','2');
  assert.deepEqual([h.wins,h.losses,h.sets.map(s=>s.date)],[1,1,['2026-03-01','2026-01-01']]);
  assert.deepEqual([m.headToHead(results,'1','9').sets.length,m.headToHead(results,'1','1').sets.length],[0,0]);
});
