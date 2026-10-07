const {test}=require('node:test');
const assert=require('node:assert/strict');
const m=require('../../ranking-smash-ultimate/account-model.js');
test('movement needs a real previous cut, preserves new/up/down/tie',()=>{
  assert.equal(m.movement({rank:12,previousRank:1}).text,'Sin comparación previa');
  assert.equal(m.movement({rank:null,previousCutAt:'2026-10-01'}).kind,'');
  assert.equal(m.movement({rank:10,previousRank:null,previousCutAt:'2026-10-01'}).kind,'new');
  assert.match(m.movement({rank:10,previousRank:12,previousCutAt:'2026-10-01'}).text,/▲ 2/);
  assert.match(m.movement({rank:12,previousRank:10,previousCutAt:'2026-10-01'}).text,/▼ 2/);
  assert.equal(m.movement({rank:12,previousRank:12,previousCutAt:'2026-10-01'}).text,'= Sin cambio');
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
