"""Private, deterministic database package. No API calls or rating calculations."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'smash'))
from deploy import validate_public_data
from rank import competitive_set


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def identifier(value):
    require(type(value) in (int, str) and re.fullmatch(r'[1-9][0-9]*', str(value))
            and int(value) <= 18446744073709551615, 'ID externo inválido.')
    return int(value)


def text(value, limit, *, optional=False):
    if optional and value is None:
        return None
    require(isinstance(value, str) and bool(value.strip()) and len(value) <= limit,
            'Texto ausente o demasiado largo para el esquema.')
    return value


def integer(value, *, minimum=0, maximum=4294967295):
    require(type(value) is int and minimum <= value <= maximum, 'Número fuera del contrato SQL.')
    return value


def instant(value):
    require(isinstance(value, str), 'Fecha ausente.')
    d = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(d.tzinfo is not None and d.year >= 1970, 'Fecha debe incluir zona horaria.')
    return d.astimezone(timezone.utc).replace(tzinfo=None).isoformat(sep=' ', timespec='microseconds')


def epoch(value):
    if value is None:
        return None
    integer(value, maximum=253402300799)
    return datetime.fromtimestamp(value, timezone.utc).replace(tzinfo=None).isoformat(sep=' ', timespec='microseconds')


def country(value):
    if isinstance(value, str) and re.fullmatch('[A-Z]{2}', value):
        return value
    return {'Guatemala': 'GT', 'Mexico': 'MX', 'México': 'MX', 'United States': 'US',
            'El Salvador': 'SV', 'Honduras': 'HN', 'Costa Rica': 'CR', 'Panama': 'PA',
            'Panamá': 'PA', 'Nicaragua': 'NI', 'Canada': 'CA', 'Japan': 'JP'}.get(value)


def build_package(raw, public):
    validate_public_data(public)
    require('localRanking' in public and public.get('rankingCoverage') == 'all_eligible',
            'Se requieren ambas vistas y todos los clasificados.')
    require(raw.get('catalogComplete') is True and raw.get('eventsComplete') is True
            and raw.get('internationalComplete') is True and raw.get('kind') == 'national_discovery',
            'Captura privada incompleta.')
    require(raw.get('generatedAt') == public['generatedAt'], 'Captura y corte no coinciden.')
    captured = instant(raw['generatedAt'])
    raw_events = {identifier(e['id']): e for e in raw['events']}
    require(len(raw_events) == len(raw['events']), 'Evento repetido.')
    entities = {k: {} for k in ('players', 'tournaments', 'events', 'entrants', 'sets')}
    ep, slots, observed, competitive_counts = {}, {}, defaultdict(set), Counter()
    set_counts, valid_counts, active = Counter(), Counter(), defaultdict(set)
    ranked = {identifier(p['id']): p for p in public['players']}

    for key, p in raw['players'].items():
        pid = identifier(key)
        require(identifier(p['id']) == pid, 'ID de jugador inconsistente.')
        location = ((p.get('user') or {}).get('location') or {}).get('country')
        user_slug = (p.get('user') or {}).get('slug')
        profile = 'https://www.start.gg/' + user_slug if isinstance(user_slug, str) and re.fullmatch(r'user/[\w-]+', user_slug) else None
        selected = ranked.get(pid, {})
        basis = selected.get('countryBasis') or ('país declarado en perfil start.gg: ' + location if location else None)
        entities['players'][pid] = dict(id=pid, tag=text(p['gamerTag'], 100),
            known_as=text(selected.get('knownAs'), 100, optional=True), country_code=country(location),
            country_basis=text(basis, 255, optional=True), profile_url=profile, synced_at=captured)

    for eid, e in raw_events.items():
        t = e['tournament']; tid = identifier(t['id'])
        trow = dict(id=tid, name=text(t['name'], 255), slug=text(t.get('slug'), 255, optional=True),
            country_code=country(t.get('countryCode')),
            url='https://www.start.gg/' + t['slug'] if re.fullmatch(r'tournament/[\w-]+', t.get('slug') or '') else None,
            synced_at=captured)
        require(tid not in entities['tournaments'] or entities['tournaments'][tid] == trow, 'Torneo contradictorio.')
        entities['tournaments'][tid] = trow
        require(identifier((e.get('videogame') or {})['id']) == 1386, 'Evento no es Ultimate.')
        entities['events'][eid] = dict(id=eid, tournament_id=tid, name=text(e['name'], 255),
            videogame_id=1386, entrant_size=1, starts_at=epoch(e.get('startAt')),
            registered_entrants=integer(e['numEntrants']), synced_at=captured,
            url='https://www.start.gg/' + e['slug'] if re.fullmatch(r'tournament/[\w-]+/event/[\w-]+', e.get('slug') or '') else None)

    for key, m in raw['sets'].items():
        sid = identifier(key); eid = identifier(m['event']['id'])
        require(identifier(m['id']) == sid and eid in raw_events and len(m.get('slots', [])) == 2,
                'Set sin evento o sin dos slots.')
        require(identifier(m['tournament']['id']) == entities['events'][eid]['tournament_id'], 'Torneo del set no coincide.')
        pair = competitive_set(m)
        set_counts[eid] += 1
        if pair:
            valid_counts[eid] += 1
            active[eid].update(identifier(p) for p in pair)
        entrant_ids = []
        for index, slot in enumerate(m['slots']):
            entrant = slot.get('entrant')
            if not entrant:
                slots[(sid, index)] = dict(set_id=sid, slot_index=index, event_id=eid, entrant_id=None, score=None, is_dq=0)
                continue
            enid = identifier(entrant['id']); entrant_ids.append(enid)
            participants = entrant.get('participants') or []
            require(len(participants) <= 1, 'No importar dobles como singles.')
            player = (participants[0].get('player') or {}) if participants else {}
            pid = identifier(player['id']) if player else None
            if pid is not None:
                require(pid in entities['players'], 'Participante ausente del catálogo de jugadores.')
                observed[(eid, pid)].add(enid)
                ep[(enid, pid)] = dict(entrant_id=enid, player_id=pid, registered_tag=text(player['gamerTag'], 100))
            erow = dict(id=enid, event_id=eid, name=text(entrant.get('name') or player.get('gamerTag') or f'Participante #{enid}', 255),
                        synced_at=captured)
            require(enid not in entities['entrants'] or entities['entrants'][enid] == erow, 'Entrant contradictorio.')
            entities['entrants'][enid] = erow
            if pair:
                competitive_counts[enid] += 1
            slots[(sid, index)] = dict(set_id=sid, slot_index=index, event_id=eid, entrant_id=enid, score=None, is_dq=0)
        require(len(set(entrant_ids)) == len(entrant_ids), 'Entrant duplicado en un set.')
        winner = identifier(m['winnerId']) if m.get('winnerId') is not None else None
        require(winner is None or winner in entrant_ids, 'Ganador no pertenece al set.')
        state = integer(m.get('state'), maximum=255)
        require(state == 3 or winner is None, 'Set no terminado con ganador.')
        display = text(m.get('displayScore'), 255, optional=True)
        row = dict(id=sid, event_id=eid, source_state=state,
            status={1:'pending', 2:'in_progress', 3:'completed'}.get(state, 'unknown'),
            outcome_type='competitive' if pair else 'dq' if display and 'DQ' in display.upper() else 'unknown',
            winner_entrant_id=winner, display_score=display, completed_at=epoch(m.get('completedAt')),
            source_updated_at=epoch(m.get('updatedAt')), synced_at=captured)
        row['source_hash'] = digest(dict(row=row, slots=[slots[(sid, i)] for i in range(2)]))
        entities['sets'][sid] = row

    for eid, e in raw_events.items():
        require(set_counts[eid] == e.get('setsFetched'), 'Captura de sets incompleta por evento.')
        entities['events'][eid]['active_players'] = len(active[eid])
    for enid, row in entities['entrants'].items():
        row['competitive_sets'] = competitive_counts[enid]
    for (eid, pid), ids in observed.items():
        require(len(ids) == 1, 'Más de un entrant para el mismo jugador/evento.')
        placement = (raw_events[eid].get('placements') or {}).get(str(pid))
        if placement is not None:
            entities['entrants'][next(iter(ids))]['final_placement'] = integer(placement, minimum=1)

    for scope in (public, public['localRanking']):
        require(scope['rankingCoverage'] == 'all_eligible', 'Vista incompleta.')
        ids = {identifier(e['id']) for e in scope['events']}
        ranked_ids = {identifier(p['id']) for p in scope['players']}
        require(ranked_ids <= entities['players'].keys(), 'Clasificado ausente de captura.')
        for e in scope['events']:
            eid = identifier(e['id']); source = raw_events.get(eid)
            require(source is not None and e['validSets'] == valid_counts[eid]
                    and e['activePlayers'] == len(active[eid]) and e['country'] == source['tournament'].get('countryCode'),
                    'Ledger de eventos distinto de la captura.')
            require(e['name'] == source['tournament']['name'] and e['eventName'] == source['name']
                    and e['date'] == datetime.fromtimestamp(source['startAt'], timezone.utc).astimezone(ZoneInfo('America/Guatemala')).date().isoformat(),
                    'Metadatos del evento no coinciden.')
        expected = {str(sid): pair for sid, match in raw['sets'].items()
                    if identifier(match['event']['id']) in ids and (pair := competitive_set(match))
                    and ranked_ids.intersection(identifier(p) for p in pair)}
        require({r['id'] for r in scope['results']} == expected.keys(), 'Resultados públicos incompletos o ajenos al corte.')
        for r in scope['results']:
            source = raw['sets'][r['id']]
            require(tuple(r['playerIds']) == expected[r['id']] and r['score'] == source['displayScore']
                    and identifier(r['eventId']) == identifier(source['event']['id']), 'Resultado distinto de la captura.')
        instant(scope['characterCapturedAt'])
        for p in scope['players']:
            identifier(p['id']); text(p['tag'], 100)
            integer(p['rating'], minimum=-2147483648, maximum=2147483647)
            for k in ('rank', 'wins', 'losses', 'events'):
                integer(p[k], minimum=1 if k == 'rank' else 0)
            if p.get('previousRank') is not None:
                integer(p['previousRank'], minimum=1)
                require(instant(scope['previousCutAt']) < captured, 'Corte anterior inválido.')
            for main in p['mains']:
                identifier(main['characterId']); integer(main['games'], minimum=1)

    data = {k: [rows[key] for key in sorted(rows)] for k, rows in entities.items()}
    data['entrant_players'] = [ep[k] for k in sorted(ep)]
    data['set_slots'] = [slots[k] for k in sorted(slots)]
    content = dict(packageVersion=1, capturedAt=raw['generatedAt'], public=public, entities=data,
        limitations=['Entrants observed in set slots; not a complete registration roster.',
                     'Numeric scores are NULL: source stored displayScore without typed scores.',
                     'No individual games/selections imported; mains preserve the published capture.'])
    return dict(content=content, sha256=digest(content))


def validate_package(package):
    """Validate normalized identities and published relationships before SQL writes."""
    require(set(package) == {'content', 'sha256'} and package['sha256'] == digest(package['content']), 'Hash de paquete inválido.')
    c = package['content']; public = c['public']; tables = c['entities']
    require(c['packageVersion'] == 1 and c['capturedAt'] == public['generatedAt'], 'Versión/captura del paquete inválida.')
    instant(c['capturedAt'])
    validate_public_data(public)
    require(public['schemaVersion'] == 3 and 'localRanking' in public, 'Se requieren mains y ambas vistas.')
    require(set(tables) == {'players','tournaments','events','entrants','sets','entrant_players','set_slots'}, 'Tablas de paquete inválidas.')
    ids = {}
    for table in ('players','tournaments','events','entrants','sets'):
        ids[table] = {identifier(r['id']): r for r in tables[table]}
        require(len(ids[table]) == len(tables[table]), 'ID repetido en paquete.')
    for p in tables['players']:
        text(p['tag'], 100); text(p.get('known_as'), 100, optional=True); text(p.get('country_basis'), 255, optional=True)
    links = {(identifier(r['entrant_id']), identifier(r['player_id'])) for r in tables['entrant_players']}
    require(len(links) == len(tables['entrant_players']), 'Vínculo repetido.')
    for enid, pid in links:
        require(enid in ids['entrants'] and pid in ids['players'], 'Vínculo a identidad ausente.')
    smap = {(identifier(r['set_id']), integer(r['slot_index'], maximum=1)): r for r in tables['set_slots']}
    require(len(smap) == len(tables['set_slots']), 'Slot repetido.')
    for e in tables['events']:
        require(identifier(e['tournament_id']) in ids['tournaments'], 'Torneo ausente.')
    for e in tables['entrants']:
        require(identifier(e['event_id']) in ids['events'], 'Evento del entrant ausente.')
    for s in tables['sets']:
        sid = s['id']; eid = identifier(s['event_id'])
        require(eid in ids['events'], 'Evento del set ausente.')
        values = [smap.get((sid, i)) for i in range(2)]
        require(all(v and v['event_id'] == eid and (v['entrant_id'] is None or
                    ids['entrants'].get(v['entrant_id'], {}).get('event_id') == eid) for v in values), 'Slots de otro evento.')
        require(s['winner_entrant_id'] is None or s['winner_entrant_id'] in [v['entrant_id'] for v in values], 'Ganador ajeno al set.')
    for scope in (public, public['localRanking']):
        require(scope['rankingCoverage'] == 'all_eligible', 'Vista incompleta.')
        for e in scope['events']:
            require(identifier(e['id']) in ids['events'], 'Evento público ausente.')
        for p in scope['players']:
            require(identifier(p['id']) in ids['players'], 'Jugador público ausente.')
            text(p['tag'], 100); integer(p['rating'], minimum=-2147483648, maximum=2147483647)
            if p.get('previousRank') is not None:
                require(instant(scope['previousCutAt']) < instant(public['generatedAt']), 'Corte anterior inválido.')
        for r in scope['results']:
            s = ids['sets'].get(identifier(r['id']))
            require(s is not None and s['event_id'] == identifier(r['eventId']) and s['display_score'] == r['score']
                    and s['outcome_type'] == 'competitive', 'Resultado no coincide con el set.')
            ws = [smap[(s['id'], i)] for i in range(2)]
            winner = next(v['entrant_id'] for v in ws if v['entrant_id'] == s['winner_entrant_id'])
            loser = next(v['entrant_id'] for v in ws if v['entrant_id'] != winner)
            require((winner, identifier(r['playerIds'][0])) in links and
                    (loser, identifier(r['playerIds'][1])) in links, 'Ganador/perdedor no coinciden con participantes.')
    return c


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path); parser.add_argument('public', type=Path); parser.add_argument('output', type=Path)
    args = parser.parse_args()
    try:
        result = build_package(json.loads(args.capture.read_text()), json.loads(args.public.read_text()))
        validate_package(result)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(canonical(result), encoding='utf-8')
        args.output.chmod(0o600)
        print(json.dumps(dict(sha256=result['sha256'], counts={k:len(v) for k,v in result['content']['entities'].items()})))
    except (ValueError, KeyError, TypeError, OSError):
        parser.exit(1, 'Paquete rechazado: revisar captura completa, IDs, formato y coherencia con el corte.\n')


if __name__ == '__main__':
    main()
