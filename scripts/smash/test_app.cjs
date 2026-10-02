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
