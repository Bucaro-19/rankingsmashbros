const test = require('node:test');
const assert = require('node:assert/strict');
const m = require('../../ranking-smash-ultimate/torneos-model.js');

// «Now» is Thursday 8 Oct 2026, 16:00 in Guatemala.
const now = Date.parse('2026-10-08T16:00:00-06:00');
const raw = (over) => ({id:'1',name:'Torneo',url:'https://www.start.gg/tournament/torneo-uno',startAt:'2026-10-10T14:00:00-06:00',attendanceType:'offline',
  city:'Quetzaltenango',department:'Quetzaltenango',venueName:'Arena',venueAddress:'Zona 1',latitude:14.83,longitude:-91.52,isRegistrationOpen:true,
  registrationClosesAt:'2026-10-20T12:00:00-06:00',numAttendees:12,isOfflineSingles:true,events:[{competitionType:'singles'},{competitionType:'doubles'}],...over});

test('dates are shown in Guatemala whatever offset the file uses', () => {
  const ms = Date.parse('2026-10-11T03:30:00+00:00');
  assert.equal(m.date(ms), '10/10/2026'); assert.equal(m.time(ms), '9:30 p. m.');
  assert.deepEqual(m.box(ms), {dow:'SÁB',day:10,month:'OCT'});
  assert.equal(m.time(Date.parse('2026-10-10T00:05:00-06:00')), '12:05 a. m.');
  assert.equal(m.fullDate(Date.parse('2026-10-10T14:00:00-06:00')), 'Sábado 10/10/2026 · 2:00 p. m. (hora de Guatemala)');
});

test('countdown by calendar day, weeks from fourteen days', () => {
  const c = iso => m.countdown(Date.parse(iso), now).text;
  assert.equal(c('2026-10-08T20:00:00-06:00'), 'Hoy'); assert.equal(c('2026-10-09T00:10:00-06:00'), 'Mañana');
  assert.equal(c('2026-10-11T10:00:00-06:00'), 'En 3 días'); assert.equal(c('2026-10-21T10:00:00-06:00'), 'En 13 días');
  assert.equal(c('2026-10-22T10:00:00-06:00'), 'En 2 semanas'); assert.equal(c('2026-11-13T10:00:00-06:00'), 'En 5 semanas');
  assert.equal(m.countdown(Date.parse('2026-10-11T10:00:00-06:00'), now).soon, true);
  assert.equal(m.countdown(Date.parse('2026-10-12T10:00:00-06:00'), now).soon, false);
});

test('null stays unknown: never zero, open or closed', () => {
  const t = m.normalize(raw({isRegistrationOpen:null,registrationClosesAt:null,numAttendees:null,venueName:null,venueAddress:null,latitude:null,longitude:-91,attendanceType:null,isOfflineSingles:null,events:[]}));
  assert.equal(t.registration, null); assert.equal(t.entrants, null); assert.equal(t.lat, null); assert.equal(t.lng, null);
  assert.equal(t.candidate, false); assert.equal(m.modeLabel(t), 'Modalidad no informada');
  assert.deepEqual(m.registration(t, now), {kind:'unknown',glyph:'?',text:'Inscripción no informada'});
  assert.equal(m.mapUrl(t), null); assert.equal(m.rankingNote(t), null);
  assert.equal(m.normalize(raw({numAttendees:0})).entrants, 0);
});

test('unsafe or unusable entries are dropped', () => {
  for (const bad of [raw({url:'https://evil.example/tournament/x'}), raw({url:'javascript:alert(1)'}), raw({startAt:'nunca'}), raw({name:' '}), null])
    assert.equal(m.normalize(bad), null);
  const agenda = {generatedAt:'2026-10-08T12:00:00-06:00',tournaments:[raw({id:'2',startAt:'2026-10-08T15:00:00-06:00'}),raw({id:'3'}),raw({id:'4',url:'http://www.start.gg/tournament/x'})]};
  assert.deepEqual(m.upcoming(agenda, now).map(t => t.id), ['3']);
  assert.deepEqual(m.upcoming({}, now), []);
});

test('stale after 48 hours or without a date', () => {
  assert.equal(m.stale({generatedAt:'2026-10-06T16:00:01-06:00'}, now), false);
  assert.equal(m.stale({generatedAt:'2026-10-06T15:59:59-06:00'}, now), true);
  assert.equal(m.stale({}, now), true);
});

test('registration states', () => {
  const r = over => m.registration(m.normalize(raw(over)), now);
  assert.deepEqual(r({}), {kind:'open',glyph:'●',text:'Inscripción abierta · cierra el 20/10/2026'});
  assert.equal(r({registrationClosesAt:null}).text, 'Inscripción abierta');
  assert.equal(r({registrationClosesAt:'2026-10-08T23:00:00-06:00'}).text, 'Abierta · cierra hoy');
  assert.equal(r({registrationClosesAt:'2026-10-09T10:00:00-06:00'}).text, 'Abierta · cierra mañana');
  assert.deepEqual(r({registrationClosesAt:'2026-10-11T10:00:00-06:00'}), {kind:'closing',glyph:'◐',text:'Abierta · cierra en 3 días'});
  assert.equal(r({isRegistrationOpen:false}).text, 'Inscripción cerrada');
});

test('groups by Guatemala calendar: week to Sunday, then month, then later', () => {
  const list = m.upcoming({tournaments:[raw({id:'a',startAt:'2026-10-11T22:00:00-06:00'}),raw({id:'b',startAt:'2026-10-12T00:30:00-06:00'}),
    raw({id:'c',startAt:'2026-10-31T23:00:00-06:00'}),raw({id:'d',startAt:'2026-11-01T00:30:00-06:00'})]}, now);
  assert.deepEqual(m.groups(list, now).map(g => [g.key, g.items.map(t => t.id)]), [['week',['a']],['month',['b','c']],['later',['d']]]);
  assert.deepEqual(m.groups([], now), []);
  // On a Sunday the week ends that same day.
  const sunday = Date.parse('2026-10-11T09:00:00-06:00');
  assert.deepEqual(m.groups(m.upcoming({tournaments:[raw({id:'a',startAt:'2026-10-11T22:00:00-06:00'}),raw({id:'b',startAt:'2026-10-12T10:00:00-06:00'})]}, sunday), sunday).map(g => g.key), ['week','month']);
});

test('filters add up and zones apply to in-person only', () => {
  const list = m.upcoming({tournaments:[raw({id:'x'}),raw({id:'g',city:'Guatemala',department:'Guatemala',events:[{competitionType:'doubles'}],isOfflineSingles:false}),
    raw({id:'o',attendanceType:'online',city:null,department:null,isOfflineSingles:false})]}, now);
  assert.deepEqual(m.zones(list), {departments:['Guatemala','Quetzaltenango'],cities:['Guatemala','Quetzaltenango']});
  const ids = f => m.filter(list, f).map(t => t.id).sort();
  assert.deepEqual(ids({}), ['g','o','x']); assert.deepEqual(ids({zone:'d:Guatemala'}), ['g']); assert.deepEqual(ids({zone:'c:Quetzaltenango'}), ['x']);
  assert.deepEqual(ids({mode:'online'}), ['o']); assert.deepEqual(ids({mode:'presencial'}), ['g','x']);
  assert.deepEqual(ids({ranking:true}), ['x']); assert.deepEqual(ids({zone:'d:Guatemala',ranking:true}), []);
  assert.deepEqual(m.rankingNote(list.find(t => t.id === 'g')), {ok:false,text:'No cuenta: el ranking solo usa singles.'});
  assert.equal(m.rankingNote(list.find(t => t.id === 'o')).text, 'No cuenta: el ranking solo usa torneos presenciales.');
  assert.equal(m.rankingNote(list.find(t => t.id === 'x')).ok, true);
});

test('near me: distance on the device, located first, online next, unlocated last', () => {
  assert.ok(Math.abs(m.distance(14.6349, -90.5069, 14.8347, -91.5180) - 111) < 3);
  const list = m.upcoming({tournaments:[raw({id:'far',latitude:15.5,longitude:-90.2}),raw({id:'near',startAt:'2026-10-10T18:00:00-06:00'}),
    raw({id:'online',attendanceType:'online'}),raw({id:'unknown',latitude:null,longitude:null})]}, now);
  const group = m.groups(list, now, {lat:14.84,lng:-91.52})[0].items;
  assert.deepEqual(group.map(t => t.id), ['near','far','online','unknown']);
  assert.ok(group[0].km < 2); assert.equal(group[2].km, null); assert.equal(group[3].km, null);
  assert.equal(m.groups(list, now)[0].items[0].km, null);
});

test('labels, map link and home block choice', () => {
  const t = m.normalize(raw({}));
  assert.equal(m.where(t), 'Arena · Quetzaltenango, Quetzaltenango'); assert.equal(m.kindsLabel(t), 'Singles · Dobles'); assert.equal(m.modeLabel(t), 'Presencial');
  assert.equal(m.mapUrl(t), 'https://www.google.com/maps/search/?api=1&query=14.83%2C-91.52');
  assert.equal(m.mapUrl(m.normalize(raw({latitude:null,longitude:null}))), 'https://www.google.com/maps/search/?api=1&query=Arena%2C%20Zona%201');
  assert.equal(m.where(m.normalize(raw({attendanceType:'online'}))), 'Online · desde cualquier lugar');
  assert.equal(m.where(m.normalize(raw({venueName:null,city:null,department:null}))), 'Lugar por anunciar');
  const list = m.upcoming({tournaments:[raw({id:'online',attendanceType:'online',startAt:'2026-10-09T10:00:00-06:00'}),raw({id:'closed',isRegistrationOpen:false,startAt:'2026-10-09T12:00:00-06:00'}),raw({id:'open'})]}, now);
  assert.equal(m.next(list).id, 'open'); assert.equal(m.next(list.slice(0, 2)).id, 'online'); assert.equal(m.next([]), null);
});
