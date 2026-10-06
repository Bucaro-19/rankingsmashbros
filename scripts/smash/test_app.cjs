const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

// Load validation without browser event bindings; use the real published-data contract.
const source = fs.readFileSync(path.join(__dirname, '../../ranking-smash-ultimate/app.js'), 'utf8');
const validate = vm.runInNewContext(source.split('const tabs =')[0] + '\nvalidate;');
function fixture() {
  return {
    schemaVersion: 2, status: 'international_pilot', rankingComputed: true,
    generatedAt: '2026-10-01T12:00:00Z', scope: 'Guatemala', seasonYear: 2026,
    rankingCoverage: 'all_eligible', results: [],
    counts: {players: 155, eligiblePlayers: 155, top100: 100, events: 2, sets: 310, countries: 1},
    players: Array.from({length: 155}, (_, i) => ({id: String(i + 1), tag: `Jugador ${i + 1}`,
      rank: i + 1, previousRank: i + 2, rating: 1500 - i, sets: 4, events: 2,
      wins: 2, losses: 2, countryBasis: 'país del perfil'})),
  };
}
test('all positions and movement beyond position 100 load successfully', () => {
  assert.equal(validate(fixture()).players[154].previousRank, 156);
});
test('a legacy top-100 cut still loads while deployment updates the data', () => {
  const data = fixture(); data.players = data.players.slice(0, 100); data.counts.players = 100;
  delete data.rankingCoverage; delete data.counts.top100; delete data.counts.eligiblePlayers;
  assert.equal(validate(data).players.length, 100);
});
test('truncated and inconsistent full rankings are rejected', () => {
  for (const change of ['truncated', 'gap', 'duplicate']) {
    const data = fixture();
    if (change === 'truncated') { data.players.pop(); data.counts.players--; }
    if (change === 'gap') data.players[154].rank = 157;
    if (change === 'duplicate') data.players[154].id = '1';
    assert.throws(() => validate(data));
  }
});

function dualFixture() {
  const data = fixture();
  data.rankingScope = 'combined';
  data.events = [{id:'gt',country:'GT'},{id:'mx',country:'MX'}];
  data.localRanking = structuredClone(data);
  data.localRanking.rankingScope = 'guatemala';
  data.localRanking.status = 'local_pilot';
  data.localRanking.events = [{id:'gt',country:'GT'}];
  return data;
}
test('both views must share a cut and local data excludes foreign events and results', () => {
  assert.equal(validate(dualFixture()).localRanking.rankingScope, 'guatemala');
  for (const corruption of ['date','method','event','set','missing']) {
    const data = dualFixture();
    if (corruption === 'date') data.localRanking.generatedAt = '2026-10-02T12:00:00Z';
    if (corruption === 'method') data.localRanking.methodVersion = 'other';
    if (corruption === 'event') data.localRanking.events[0].country = 'MX';
    if (corruption === 'set') data.localRanking.results.push({playerIds:['1','2'],tournament:'Foreign',date:'2026-01-01',score:'2-0',country:'MX'});
    if (corruption === 'missing') data.localRanking = null;
    assert.throws(()=>validate(data));
  }
});
test('selecting a view returns that calculation and never silently falls back', () => {
  const choose = vm.runInNewContext(source.split('const tabs =')[0] + '\nchooseSnapshot;');
  const data = dualFixture();
  data.localRanking.players.reverse(); // Deliberately distinguish returned lists.
  assert.equal(choose(data,true),data);
  assert.equal(choose(data,false),data.localRanking);
  assert.throws(()=>choose(fixture(),false));
});

const activityView = vm.runInNewContext(source.split('const tabs =')[0] + '\nactivityView;');
function activityFixture() {
  return {player:{id:'1',events:2,sets:5,wins:3,losses:2,activity:{months:['2026-01','2026-02'],events:[{id:'b',wins:1,losses:1},{id:'a',wins:2,losses:1}]}},
    data:{events:[{id:'a',date:'2026-01-15',name:'Enero'},{id:'b',date:'2026-02-28',name:'Febrero'}]}};
}
test('activity joins by event id and sorts the ledger without changing points', () => {
  const {player,data}=activityFixture(); const before=JSON.stringify(player);
  const view=activityView(player,data);
  assert.equal(view.ledger[0].name,'Febrero');
  assert.equal(view.months.length,2);
  assert.equal(JSON.stringify(player),before);
  assert.equal(activityView({id:'legacy'},data),null);
});
test('activity rejects invented months, duplicate events and inconsistent totals', () => {
  for(const corruption of ['months','duplicate','unknown','totals','negative']) {
    const {player,data}=activityFixture();
    if(corruption==='months')player.activity.months.push('2026-03');
    if(corruption==='duplicate')player.activity.events[0].id='a';
    if(corruption==='unknown')player.activity.events[0].id='other';
    if(corruption==='totals')player.sets++;
    if(corruption==='negative')player.activity.events[0].wins=-1;
    assert.throws(()=>activityView(player,data));
  }
});
test('the published combined and local player ledgers load under the browser contract', () => {
  const data=JSON.parse(fs.readFileSync(path.join(__dirname,'../../ranking-smash-ultimate/data/public.json'),'utf8'));
  assert.equal(validate(data),data);
  for(const scope of [data,data.localRanking]) for(const player of scope.players) assert.ok(activityView(player,scope));
});
