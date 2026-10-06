"""Enrich admitted competitive sets with recorded character selections; never infer mains."""
import argparse
import hashlib
import json
import os
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from collect import APIError, Client
from rank import competitive_set

FIELDS = 'id state winnerId displayScore games { id winnerId selections { entrant { id } character { id name } } }'
CACHE_MAX_AGE = 7 * 24 * 3600


def fingerprint(match):
    fields = {k: match.get(k) for k in ('id', 'state', 'winnerId', 'displayScore', 'updatedAt', 'slots')}
    return hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False))
    temp.replace(path)


def enrich(client, snapshot, player_ids, event_ids, cache, save_cache=lambda: None):
    wanted = {sid: m for sid, m in snapshot['sets'].items()
              if str((m.get('event') or {}).get('id')) in event_ids
              and (pair := competitive_set(m)) and player_ids.intersection(pair)}
    pending = []
    now = time.time()
    for sid, match in wanted.items():
        old = cache.get(sid, {})
        if (old.get('fingerprint') == fingerprint(match) and 0 <= now - old.get('fetchedAt', 0) < CACHE_MAX_AGE
                and 'games' in old):
            continue
        pending.append(sid)
    # Five sets per request keeps normal singles brackets well below object limits.
    for offset in range(0, len(pending), 5):
        batch = pending[offset:offset+5]
        variables = {f'id{i}': sid for i, sid in enumerate(batch)}
        query = 'query(' + ','.join(f'$id{i}:ID!' for i in range(len(batch))) + '){' + ' '.join(
            f's{i}:set(id:$id{i}){{{FIELDS}}}' for i in range(len(batch))) + '}'
        response = client.query(query, variables)
        for i, sid in enumerate(batch):
            row = response.get(f's{i}')
            match = wanted[sid]
            if (not row or str(row.get('id')) != sid or row.get('state') != match.get('state')
                    or str(row.get('winnerId')) != str(match.get('winnerId'))
                    or row.get('displayScore') != match.get('displayScore')):
                raise APIError('Un resultado cambió desde el corte; se requiere una captura nueva antes de publicar personajes.')
            games = row.get('games')
            if games is not None and not isinstance(games, list):
                raise APIError('Formato de partidas inválido; no publicar una cobertura parcial.')
            cache[sid] = {'fingerprint': fingerprint(match), 'fetchedAt': time.time(), 'games': games or []}
        save_cache()
        if offset % 100 == 0 or offset + 5 >= len(pending):
            print(f'Personajes: {min(offset+5,len(pending))}/{len(pending)} sets consultados; {len(wanted)-len(pending)} en caché.', flush=True)
    result = {**snapshot, 'sets': {sid: ({**match, 'games': cache[sid]['games']} if sid in wanted else dict(match))
                                  for sid, match in snapshot['sets'].items()},
              'characterDataComplete': True, 'characterCapturedAt': datetime.now(timezone.utc).isoformat(),
              'characterPlayerIds': sorted(player_ids), 'characterEventIds': sorted(event_ids)}
    return result


def player_mains(snapshot, event_ids, player_ids):
    usage = defaultdict(Counter)
    names = {}
    coverage = {pid: {'setsQueried': 0, 'setsWithSelections': 0, 'gamesWithSelections': 0,
                      'ambiguousGames': 0} for pid in player_ids}
    for match in snapshot['sets'].values():
        pair = competitive_set(match)
        if str((match.get('event') or {}).get('id')) not in event_ids or not pair:
            continue
        participants = player_ids.intersection(pair)
        if not participants:
            continue
        entrants = {str(slot['entrant']['id']): str(slot['entrant']['participants'][0]['player']['id'])
                    for slot in match['slots']}
        for pid in participants:
            coverage[pid]['setsQueried'] += 1
        seen_games, in_set = set(), set()
        for game in match.get('games') or []:
            gid = game.get('id')
            if gid is None or str(gid) in seen_games or str(game.get('winnerId')) not in entrants:
                continue
            seen_games.add(str(gid))
            picks = defaultdict(set)
            for selection in game.get('selections') or []:
                pid = entrants.get(str((selection.get('entrant') or {}).get('id')))
                char = selection.get('character') or {}
                cid, name = char.get('id'), char.get('name')
                if pid not in participants or cid is None or not isinstance(name, str) or not name.strip():
                    continue
                cid = str(cid)
                names[cid] = name.strip()
                picks[pid].add(cid)
            for pid, chars in picks.items():
                if len(chars) != 1:
                    coverage[pid]['ambiguousGames'] += 1
                    continue
                usage[pid][next(iter(chars))] += 1
                coverage[pid]['gamesWithSelections'] += 1
                in_set.add(pid)
        for pid in in_set:
            coverage[pid]['setsWithSelections'] += 1
    return {pid: {'mains': sorted([{'characterId': cid, 'name': names[cid], 'games': n}
                                   for cid, n in usage[pid].items()], key=lambda m: (-m['games'], m['characterId'])),
                  'mainCoverage': coverage[pid]} for pid in player_ids}


def add_to_public(snapshot, public):
    """Backfill only character fields in a verified, already published cut."""
    if snapshot.get('generatedAt') != public.get('generatedAt') or not snapshot.get('characterDataComplete'):
        raise ValueError('La captura de personajes no corresponde al corte público.')
    result = {**public}
    scopes = [result]
    if 'localRanking' in public:
        result['localRanking'] = dict(public['localRanking'])
        scopes.append(result['localRanking'])
    for view in scopes:
        ids = {p['id'] for p in view['players']}
        events = {e['id'] for e in view['events']}
        if not ids.issubset(set(snapshot['characterPlayerIds'])) or not events.issubset(set(snapshot['characterEventIds'])):
            raise ValueError('Cobertura de personajes incompleta para esta vista.')
        data = player_mains(snapshot, events, ids)
        view['players'] = [{**p, **data[p['id']]} for p in view['players']]
        view['results'] = [{**m, 'playerTags': [(snapshot['players'].get(pid) or {}).get('gamerTag') or f'Rival #{pid}' for pid in m['playerIds']]} for m in view['results']]
        view['schemaVersion'] = 3
        view['characterCapturedAt'] = snapshot['characterCapturedAt']
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path)
    parser.add_argument('public', type=Path)
    parser.add_argument('--cache', type=Path, default=Path('scripts/smash/data/characters-cache.json'))
    parser.add_argument('--output-snapshot', type=Path)
    parser.add_argument('--output-public', type=Path)
    args = parser.parse_args()
    token = os.environ.get('STARTGG_TOKEN', '')
    if not token:
        parser.exit(1, 'Falta STARTGG_TOKEN en el entorno privado.\n')
    snapshot = json.loads(args.snapshot.read_text())
    public = json.loads(args.public.read_text())
    if snapshot['generatedAt'] != public['generatedAt']:
        parser.exit(1, 'La captura y el corte público no coinciden.\n')
    cache = json.loads(args.cache.read_text()) if args.cache.exists() else {}
    ids = {p['id'] for p in public['players']}
    events = {e['id'] for e in public['events']}
    if 'localRanking' in public:
        ids.update(p['id'] for p in public['localRanking']['players'])
    try:
        result = enrich(Client(token), snapshot, ids, events, cache, lambda: atomic_json(args.cache, cache))
        enriched = add_to_public(result, public)
        if args.output_snapshot: atomic_json(args.output_snapshot, result)
        if args.output_public: atomic_json(args.output_public, enriched)
        print('Jugadores con personaje registrado:',sum(bool(p['mains']) for p in enriched['players']), '/',len(enriched['players']))
    except (APIError, ValueError) as error:
        parser.exit(1, str(error)+'\n')


if __name__ == '__main__':
    main()
