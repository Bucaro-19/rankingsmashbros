const test = require('node:test');
const assert = require('node:assert/strict');
const m = require('../../ranking-smash-ultimate/analisis-model.js');

test('probability is worded, clamped for display and never invented',()=>{
  assert.equal(m.probability({p:null}),null); assert.equal(m.probability(undefined),null); assert.equal(m.probability({p:NaN}),null);
  assert.deepEqual(m.probability({p:0.5}),{text:'50%',word:'Set parejo',kind:'yellow',mine:50});
  assert.deepEqual([m.probability({p:0.65}).word,m.probability({p:0.66}).word],['Set parejo','Llegas favorito']);
  assert.deepEqual([m.probability({p:0.35}).word,m.probability({p:0.34}).word],['Set parejo','Él llega favorito']);
  assert.deepEqual([m.probability({p:0.97}).text,m.probability({p:0.97}).mine],['>90%',90]);
  assert.deepEqual([m.probability({p:0.02}).text,m.probability({p:0.02}).mine],['<10%',10]);
  assert.equal(m.probability({p:0.9}).text,'90%'); assert.equal(m.probability({p:0.1}).text,'10%');
});
test('records are counts; percentage only from ten on',()=>{
  assert.deepEqual(m.record([0,0]),{count:'0–0',total:0,percent:null,note:'Sin sets registrados',small:false,empty:true});
  assert.deepEqual(m.record([1,0]),{count:'1–0',total:1,percent:null,note:'Muestra pequeña · 1 set',small:true,empty:false});
  assert.equal(m.record([9,0]).percent,null);
  assert.deepEqual(m.record([7,3]),{count:'7–3',total:10,percent:70,note:'10 sets',small:false,empty:false});
  assert.equal(m.record([0,0],'games').note,'Sin games registrados');
  assert.equal(m.record([2,1],'games').note,'Muestra pequeña · 3 games');
  assert.equal(m.record(null).empty,true);
});
test('coverage and usage say what is known, not more',()=>{
  assert.equal(m.coverage({tag:'Brisa',coverage:{registered:31,total:45,source:'published'}}),'Personaje registrado en 31 de 45 sets de Brisa.');
  assert.match(m.coverage({tag:'Kiwi',coverage:{registered:0,total:12,source:'published'}}),/no registró personaje en ninguno de sus 12 sets/);
  assert.match(m.coverage({tag:'Lagarto',coverage:{registered:null,total:3,source:'unavailable'}}),/no está entre los clasificados/);
  assert.deepEqual(m.usage([{slug:'steve',games:3,totalGames:4},{slug:'x',games:0,totalGames:0}]).map(d=>d.percent),[75,0]);
});
test('recommendations read as advice with their sample',()=>{
  const good=m.recommendation({type:'good',confidence:'media',ownSets:4,sceneGames:90,reasonData:{own:[3,1],scene:[50,40],basis:'own_sets'}},'Pikachu','Steve');
  assert.deepEqual(good,{good:true,mark:'✓',title:'Pikachu te ha funcionado',reason:'Con Pikachu llevas 3–1 en sets contra él.',confidence:'Confianza media',sample:'4 sets tuyos · 90 games de escena'});
  const avoid=m.recommendation({type:'avoid',confidence:'baja',ownSets:0,sceneGames:160,reasonData:{own:[0,0],scene:[60,100],basis:'scene_games'}},'Ness','Steve');
  assert.deepEqual([avoid.mark,avoid.title,avoid.reason,avoid.sample],['!','Ness te ha costado','En la escena, Ness lleva 60–100 en games contra Steve.','0 sets tuyos · 160 games de escena']);
  const data={record:{sets:3},h2h:[{myChar:'pikachu',theirChar:null},{myChar:null,theirChar:null},{myChar:null,theirChar:'steve'}],rival:{detected:[{usableForMatchups:true}]}};
  assert.equal(m.noRecommendation(data,'Brisa'),'Hay 3 sets entre ustedes (2 con personaje registrado). Para recomendar necesitamos al menos 2 sets tuyos con personaje o 150 games de la escena en el cruce.');
  assert.equal(m.noRecommendation({rival:{detected:[]}},'Kiwi'),'Sin personajes detectados de Kiwi: no podemos cruzar personajes todavía.');
});
test('streak, score, tiers and matrix helpers',()=>{
  assert.equal(m.streak(null),''); assert.equal(m.streak({won:true,sets:1}),'');
  assert.equal(m.streak({won:true,sets:3}),'Llevas 3 seguidos ganados'); assert.equal(m.streak({won:false,sets:2}),'Llevas 2 seguidos perdidos');
  assert.equal(m.setScore({myGames:3,theirGames:1}),'3–1'); assert.equal(m.setScore({myGames:null,theirGames:null}),'—');
  assert.deepEqual(m.TIERS.map(t=>t[0]),['top10','t11_50','t51_100','outsideTop100','unranked']);
  assert.deepEqual(m.myMatrixCharacters({gameMatrix:{'pikachu|steve':{},'pikachu|ness':{},'pichu|steve':{}}}),{mine:['pikachu','pichu'],his:['steve','ness']});
  assert.deepEqual(m.myMatrixCharacters({}),{mine:[],his:[]});
  assert.match(m.gamesNote('cut_not_synced'),/sincronizando/); assert.match(m.gamesNote('empty'),/no hay games/); assert.equal(m.gamesNote('available'),'');
  assert.equal(m.date('2026-09-26'),'26/09/2026'); assert.equal(m.initials(' brisa'),'BR');
});
