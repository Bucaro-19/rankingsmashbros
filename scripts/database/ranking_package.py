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
from characters import player_mains


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


CATALOG_COLUMNS = 'tournament_id event_id owner_startgg_user_id tournament_name slug starts_at city event_name entrants reason captured_at'
CATALOG_REASONS = {None, 'not_singles', 'online_or_unknown', 'unfinished_event', 'under_20_entrants', 'outside_window'}


def catalog_id(value):
    # Match the signed integer transport supported by PHP (the SQL column is unsigned).
    value = identifier(value)
    require(value <= 9223372036854775807, 'ID de catálogo fuera del contrato de transporte.')
    return value


def tournament_catalog(raw):
    source = raw.get('tournamentCatalog')
    if source is None:
        return None
    require(type(source) is list, 'Catálogo inválido.')
    rows, tournaments = [], set()
    for tournament in source:
        tid = catalog_id(tournament['id'])
        require(tid not in tournaments and type(tournament['events']) is list, 'Torneo de catálogo repetido/inválido.')
        tournaments.add(tid)
        slug = tournament.get('slug')
        if not isinstance(slug, str) or not slug.startswith('tournament/'):
            slug = None
        for event in tournament['events']:
            rows.append(dict(tournament_id=tid, event_id=catalog_id(event['id']),
                owner_startgg_user_id=catalog_id(tournament['ownerId']) if tournament.get('ownerId') is not None else None,
                tournament_name=text(tournament['name'], 255), slug=slug,
                starts_at=epoch(tournament.get('startAt')), city=text(tournament.get('city'), 120, optional=True),
                event_name=text(event.get('name'), 255, optional=True),
                entrants=integer(event['numEntrants']) if event.get('numEntrants') is not None else None,
                reason=event.get('reason'), captured_at=instant(raw['generatedAt'])))
    rows.sort(key=lambda r: (r['tournament_id'], r['event_id']))
    validate_tournament_catalog(rows, raw['generatedAt'])
    return rows


def validate_tournament_catalog(rows, captured_at):
    require(type(rows) is list, 'Catálogo inválido.')
    events, tournaments = set(), {}
    columns = set(CATALOG_COLUMNS.split())
    for row in rows:
        require(type(row) is dict and set(row) == columns, 'Columnas de catálogo inválidas.')
        for key in ('tournament_id', 'event_id', 'owner_startgg_user_id'):
            if key == 'owner_startgg_user_id' and row[key] is None:
                continue
            require(type(row[key]) is int and catalog_id(row[key]) == row[key], 'ID de catálogo inválido.')
        require(row['event_id'] not in events, 'Evento de catálogo repetido.')
        events.add(row['event_id'])
        text(row['tournament_name'], 255)
        text(row['city'], 120, optional=True); text(row['event_name'], 255, optional=True)
        slug = row['slug']
        require(slug is None or (isinstance(slug, str) and len(slug) <= 255
                and slug.startswith('tournament/') and re.fullmatch(r'[\x20-\x7e]+', slug)), 'Slug de catálogo inválido.')
        if row['entrants'] is not None:
            integer(row['entrants'])
        require(row['reason'] is None or (isinstance(row['reason'], str) and row['reason'] in CATALOG_REASONS), 'Motivo de catálogo inválido.')
        for key in ('starts_at', 'captured_at'):
            value = row[key]
            if key == 'starts_at' and value is None:
                continue
            require(isinstance(value, str) and re.fullmatch(r'\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{6}', value)
                    and instant(value.replace(' ', 'T') + 'Z') == value, 'Fecha de catálogo inválida.')
        require(row['captured_at'] == instant(captured_at), 'Catálogo de otra captura.')
        identity = tuple(row[key] for key in ('owner_startgg_user_id', 'tournament_name', 'slug', 'starts_at', 'city'))
        require(row['tournament_id'] not in tournaments or tournaments[row['tournament_id']] == identity, 'Torneo de catálogo inconsistente.')
        tournaments[row['tournament_id']] = identity


def character_ids():
    """Same versioned catalog installed by seed-characters.sql; Random is a real API ID."""
    catalog = Path(__file__).resolve().parents[2] / 'ranking-smash-ultimate/characters.js'
    return {int(v) for v in re.findall(r'"characterId":\s*"([0-9]+)"', catalog.read_text())} | {1746}


def context_set_ids(public, tables):
    """Captured competitive ledger plus invalidated sets, which must lose old game context."""
    admitted = {identifier(e['id']) for e in public['events']}
    ranked = {identifier(p['id']) for v in (public, public['localRanking']) for p in v['players']}
    entrants = {r['entrant_id'] for r in tables['entrant_players'] if r['player_id'] in ranked}
    relevant = {r['set_id'] for r in tables['set_slots'] if r['entrant_id'] in entrants}
    return sorted(s['id'] for s in tables['sets'] if s['outcome_type'] != 'competitive'
        or (s['event_id'] in admitted and s['id'] in relevant))


def game_context(raw, public, tables):
    require(raw.get('characterDataComplete') is True and raw.get('characterCapturedAt') == public['characterCapturedAt'],
            'Falta la captura privada de personajes del corte.')
    for view in (public, public['localRanking']):
        players = {p['id'] for p in view['players']}; events = {e['id'] for e in view['events']}
        require(players <= set(raw.get('characterPlayerIds', [])) and events <= set(raw.get('characterEventIds', [])),
                'Cobertura privada de personajes incompleta.')
        expected = player_mains(raw, events, players)
        require(all(p['mains'] == expected[p['id']]['mains'] and p['mainCoverage'] == expected[p['id']]['mainCoverage']
                    for p in view['players']), 'Los games no reproducen los mains publicados.')
    covered = context_set_ids(public, tables)
    competitive = {s['id'] for s in tables['sets'] if s['outcome_type'] == 'competitive'}
    games, selections = {}, []
    for sid in covered:
        if sid not in competitive:
            continue  # DQ/invalidated sets clear prior context without querying characters.
        match = raw['sets'][str(sid)]
        require(isinstance(match.get('games'), list), 'Set admitido sin captura de games.')
        entrants = {str(slot['entrant']['id']) for slot in match['slots']}
        seen = set()
        for number, game in enumerate(match['games'], 1):
            gid = game.get('id')
            if gid is None or str(gid) in seen or str(game.get('winnerId')) not in entrants:
                continue
            seen.add(str(gid))
            gid = identifier(gid)
            require(gid not in games, 'ID de game repetido entre sets.')
            games[gid] = dict(id=gid, set_id=sid, game_number=integer(number, minimum=1, maximum=65535),
                winner_entrant_id=identifier(game['winnerId']), stage_id=None, synced_at=instant(raw['characterCapturedAt']))
            picks = defaultdict(set)
            for selection in game.get('selections') or []:
                en = str((selection.get('entrant') or {}).get('id'))
                char = selection.get('character') or {}; name = char.get('name'); cid = char.get('id')
                if en in entrants and cid is not None and isinstance(name, str) and name.strip():
                    picks[identifier(en)].add(str(cid))
            for en, chars in picks.items():
                if len(chars) == 1:
                    selections.append(dict(game_id=gid, set_id=sid, entrant_id=en, character_id=identifier(next(iter(chars)))))
    tables['games'] = [games[k] for k in sorted(games)]
    tables['game_selections'] = sorted(selections, key=lambda r: (r['game_id'], r['entrant_id'], r['character_id']))
    return covered


def validate_game_context(c, ids, smap, links):
    tables = c['entities']; known = character_ids()
    covered = c.get('gameContextSetIds')
    require(covered == context_set_ids(c['public'], tables), 'Cobertura de games inválida.')
    game_ids = {identifier(r['id']): r for r in tables['games']}
    require(len(game_ids) == len(tables['games']), 'Game duplicado.')
    covered = set(covered)
    numbers = set()
    for g in tables['games']:
        require(set(g) == {'id','set_id','game_number','winner_entrant_id','stage_id','synced_at'}, 'Campos de game inválidos.')
        sid = identifier(g['set_id']); winner = identifier(g['winner_entrant_id'])
        require(sid in covered and ids['sets'][sid]['outcome_type'] == 'competitive', 'Game fuera de sets admitidos.')
        require(winner in [smap[(sid,i)]['entrant_id'] for i in range(2)], 'Ganador del game ajeno al set.')
        number = integer(g['game_number'], minimum=1, maximum=65535)
        require((sid,number) not in numbers, 'Número de game duplicado.'); numbers.add((sid,number))
        require(g['stage_id'] is None and g['synced_at'] == instant(c['public']['characterCapturedAt']), 'Metadatos del game inválidos.')
    seen = set()
    for r in tables['game_selections']:
        require(set(r) == {'game_id','set_id','entrant_id','character_id'}, 'Campos de selección inválidos.')
        gid,sid,en,cid = (identifier(r[k]) for k in ('game_id','set_id','entrant_id','character_id'))
        require(gid in game_ids and game_ids[gid]['set_id'] == sid, 'Selección de otro game/set.')
        require(en in [smap[(sid,i)]['entrant_id'] for i in range(2)] and cid in known, 'Selección ajena al set/catálogo.')
        require((gid,en) not in seen, 'Selección duplicada o ambigua.'); seen.add((gid,en))
    for view in (c['public'], c['public']['localRanking']):
        event_ids = {identifier(e['id']) for e in view['events']}; counts = Counter()
        players_by_entrant = {en:pid for en,pid in links}
        for r in tables['game_selections']:
            if ids['sets'][r['set_id']]['event_id'] in event_ids:
                counts[(players_by_entrant[r['entrant_id']], r['character_id'])] += 1
        for p in view['players']:
            pid = identifier(p['id'])
            require({cid:n for (player,cid),n in counts.items() if player == pid}
                    == {identifier(m['characterId']):m['games'] for m in p['mains']}, 'Games y mains publicados difieren.')


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
    covered = game_context(raw, public, data)
    content = dict(packageVersion=2, capturedAt=raw['generatedAt'], public=public, entities=data, gameContextSetIds=covered,
        limitations=['Entrants observed in set slots; not a complete registration roster.',
                     'Numeric scores are NULL: source stored displayScore without typed scores.',
                     'Games cover admitted ranked-player sets and both entrants; missing/ambiguous picks are omitted.',
                     'game_number is capture array position, not an API order field; stage_id is NULL.',
                     'Invalidated sets clear prior game context; published cut snapshots remain immutable.'])
    catalog = tournament_catalog(raw)
    if catalog is not None:
        content['packageVersion'] = 3
        content['tournamentCatalog'] = catalog
    return dict(content=content, sha256=digest(content))


def validate_package(package):
    """Validate normalized identities and published relationships before SQL writes."""
    require(set(package) == {'content', 'sha256'} and package['sha256'] == digest(package['content']), 'Hash de paquete inválido.')
    if package['content'].get('packageVersion') == 4:
        from organizer_context import national_package, validate_context
        core = national_package(package)
        validate_package(core)
        validate_context(package['content']['organizerContext'], core)
        return package['content']
    c = package['content']; public = c['public']; tables = c['entities']
    require(type(c['packageVersion']) is int and c['packageVersion'] in (1,2,3) and c['capturedAt'] == public['generatedAt'], 'Versión/captura del paquete inválida.')
    instant(c['capturedAt'])
    validate_public_data(public)
    require(public['schemaVersion'] == 3 and 'localRanking' in public, 'Se requieren mains y ambas vistas.')
    expected_tables = {'players','tournaments','events','entrants','sets','entrant_players','set_slots'}
    if c['packageVersion'] >= 2: expected_tables |= {'games','game_selections'}
    if c['packageVersion'] == 3:
        validate_tournament_catalog(c.get('tournamentCatalog'), c['capturedAt'])
    else:
        require('tournamentCatalog' not in c, 'Catálogo requiere paquete versión 3.')
    require(set(tables) == expected_tables, 'Tablas de paquete inválidas.')
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
    if c['packageVersion'] >= 2: validate_game_context(c, ids, smap, links)
    return c


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path); parser.add_argument('public', type=Path); parser.add_argument('output', type=Path)
    parser.add_argument('--organizer-context', type=Path, help='Complemento opcional; cualquier fallo conserva el paquete nacional V1–V3')
    args = parser.parse_args()
    try:
        raw = json.loads(args.capture.read_text())
        result = build_package(raw, json.loads(args.public.read_text()))
        validate_package(result)
        if args.organizer_context and args.organizer_context.exists():
            try:
                from organizer_context import extend_package
                extended = extend_package(result, raw, json.loads(args.organizer_context.read_text()))
                validate_package(extended)
                result = extended
            except (ValueError, KeyError, TypeError, OSError, OverflowError):
                print('Complemento de organizador omitido; paquete nacional intacto.')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(canonical(result), encoding='utf-8')
        args.output.chmod(0o600)
        print(json.dumps(dict(sha256=result['sha256'], counts={k:len(v) for k,v in result['content']['entities'].items()})))
    except (ValueError, KeyError, TypeError, OSError):
        parser.exit(1, 'Paquete rechazado: revisar captura completa, IDs, formato y coherencia con el corte.\n')


if __name__ == '__main__':
    main()
