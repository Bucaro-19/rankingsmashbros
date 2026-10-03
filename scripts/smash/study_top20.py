"""Dated diagnostic study; never changes the production ranking or its rules."""
import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from rank import competitive_set, compute
from publish_ranking import event_url


def activity_bonus(events, months, mode):
    if mode == 'events':
        return min(30, 5 * max(0, events - 2))
    if mode == 'months':
        return min(30, 10 * max(0, months - 2))
    if mode == 'none':
        return 0
    raise ValueError('Escenario desconocido')


def rerank(rows, months, mode):
    result = [{**p, 'baseRank': p['rank'], 'bonus': activity_bonus(p['events'], months[p['id']], mode)} for p in rows]
    result.sort(key=lambda p: (-(p['rating'] + p['bonus']), -p['wins'], -p['events'], p['tag'].casefold(), p['id']))
    return [{'id': p['id'], 'tag': p['tag'], 'baseRank': p['baseRank'], 'rank': i,
             'basePoints': p['rating'], 'bonus': p['bonus'], 'points': p['rating'] + p['bonus']}
            for i, p in enumerate(result, 1)]


def verify_baseline(baseline, published):
    fields = ('id', 'rank', 'rating', 'events', 'wins', 'losses')
    expected = [tuple(p[k] for k in fields) for p in published['players']]
    actual = [tuple(p[k] for k in fields) for p in baseline['fullRanking']]
    if (expected != actual or baseline['generatedAt'] != published['generatedAt']
            or baseline['methodVersion'] != published['methodVersion']
            or set(baseline['eventIds']) != {e['id'] for e in published['events']}
            or baseline['counts']['competitiveSets'] != published['counts']['sets']):
        raise ValueError('La base no reproduce el corte publicado; no generar un estudio con datos diferentes.')


def study(snapshot, curation, points, published):
    exclusions = set(curation.get('excludedEventIds', {})) | set(curation.get('excludedForeignEventIds', {}))
    kwargs = dict(player_overrides=curation.get('playerOverrides', {}), points_table=points,
                  player_aliases=curation.get('playerAliases', {}))
    baseline = compute(snapshot, exclusions, **kwargs, diagnostics=True)
    verify_baseline(baseline, published)
    rows = baseline['fullRanking']
    by_id = {p['id']: p for p in rows}
    top_ids = {p['id'] for p in rows[:20]}
    events = {str(e['id']): e for e in snapshot['events']}
    admitted = set(baseline['eventIds'])
    months = defaultdict(set)
    records = defaultdict(lambda: defaultdict(Counter))
    rivals = defaultdict(lambda: defaultdict(Counter))
    for match in snapshot['sets'].values():
        eid = str((match.get('event') or {}).get('id'))
        pair = competitive_set(match)
        if eid not in admitted or pair is None:
            continue
        win, loss = pair
        month = datetime.fromtimestamp(events[eid]['startAt'], ZoneInfo('America/Guatemala')).strftime('%Y-%m')
        for pid, rival, outcome in ((win, loss, 'wins'), (loss, win, 'losses')):
            months[pid].add(month)
            records[pid][eid][outcome] += 1
            rivals[pid][rival][outcome] += 1
    month_counts = {pid: len(months[pid]) for pid in by_id}
    scenarios = {}
    for mode in ('none', 'events', 'months'):
        ranked = rerank(rows, month_counts, mode)
        scenarios[mode] = {'players': ranked,
                          'movedPlayers': sum(p['rank'] != p['baseRank'] for p in ranked),
                          'maxMove': max(abs(p['rank'] - p['baseRank']) for p in ranked),
                          'newTop100': [p['tag'] for p in ranked if p['rank'] <= 100 < p['baseRank']],
                          'newTop20': [p['tag'] for p in ranked if p['rank'] <= 20 < p['baseRank']]}
    # Leave one whole event out and refit all rivals and eligibility each time.
    removed = []
    for i, eid in enumerate(sorted(admitted), 1):
        variant = compute(snapshot, exclusions | {eid}, **kwargs)
        positions = {p['id']: p for p in variant['fullRanking']}
        removed.append({'eventId': eid, 'name': events[eid]['tournament']['name'],
                        'positions': {pid: positions[pid]['rank'] if pid in positions else None for pid in top_ids}})
        print(f'Sensibilidad {i}/{len(admitted)}: {eid}', flush=True)
    profiles = []
    for p in rows[:20]:
        pid = p['id']
        ledger = []
        for eid, record in records[pid].items():
            e = events[eid]
            ledger.append({'id': eid, 'name': e['tournament']['name'], 'country': e['tournament']['countryCode'],
                           'date': datetime.fromtimestamp(e['startAt'], ZoneInfo('America/Guatemala')).strftime('%Y-%m-%d'),
                           'url': event_url(e.get('slug')), 'wins': record['wins'], 'losses': record['losses']})
        ledger.sort(key=lambda e: (e['date'], e['id']))
        opponent_rows = [{'id': rid, 'tag': (snapshot['players'].get(rid) or {}).get('gamerTag', 'Sin alias'),
                          'rank': by_id.get(rid, {}).get('rank'), 'wins': r['wins'], 'losses': r['losses']}
                         for rid, r in rivals[pid].items()]
        opponent_rows.sort(key=lambda r: (r['rank'] is None, r['rank'] or 0, r['tag'].casefold()))
        tested = [{'eventId': r['eventId'], 'event': r['name'], 'rank': r['positions'][pid]} for r in removed]
        positions = [r['rank'] for r in tested if r['rank'] is not None]
        foreign = [e for e in ledger if e['country'] != 'GT']
        peer = [r for r in opponent_rows if r['id'] in top_ids]
        profiles.append({**p, 'months': sorted(months[pid]), 'uniqueOpponents': len(opponent_rows),
                         'foreignEvents': len(foreign), 'foreignWins': sum(e['wins'] for e in foreign),
                         'foreignLosses': sum(e['losses'] for e in foreign),
                         'top20Wins': sum(r['wins'] for r in peer), 'top20Losses': sum(r['losses'] for r in peer),
                         'largestEventShare': round(max(e['wins'] + e['losses'] for e in ledger) / p['sets'], 4),
                         'eventLedger': ledger, 'opponents': opponent_rows,
                         'sensitivity': {'bestRank': min(positions, default=None), 'worstRank': max(positions, default=None),
                                         'unrankedScenarios': sum(r['rank'] is None for r in tested), 'scenarios': tested}})
    foreign_ids = {eid for eid in admitted if events[eid]['tournament']['countryCode'] != 'GT'}
    local_only = compute(snapshot, exclusions | foreign_ids, **kwargs, diagnostics=True)
    local_positions = {p['id']: p for p in local_only['fullRanking']}
    coverage = {'removedEvents': len(foreign_ids),
                'qualifiedPlayersWithForeignSets': sum(any(events[eid]['tournament']['countryCode'] != 'GT' for eid in records[p['id']]) for p in rows),
                'localOnlyTop20': [{'id': p['id'], 'tag': p['tag'], 'currentRank': p['rank'],
                                    'localOnlyRank': local_positions.get(p['id'], {}).get('rank')}
                                   for p in rows[:20]]}
    solver = {k: baseline['diagnostics'][k] for k in ('iterations', 'maxStep', 'converged')}
    return {'schemaVersion': 1, 'coverageSensitivity': coverage, 'solverCheck': solver, 'status': 'study_not_adopted', 'cut': published['generatedAt'],
            'seasonLabel': published['seasonLabel'], 'methodVersion': baseline['methodVersion'],
            'counts': published['counts'], 'pointsSourceSha256': hashlib.sha256(points.encode()).hexdigest(),
            'sensitivityEventCount': len(removed), 'profiles': profiles, 'scenarios': scenarios,
            'bonusLimit': 30, 'recommendation': 'Mantener puntos por resultados y mostrar constancia por separado. Los bonos son pruebas para debate, no reglas aprobadas.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ('snapshot', 'curation', 'points', 'published', 'output'):
        parser.add_argument(arg, type=Path)
    args = parser.parse_args()
    result = study(json.loads(args.snapshot.read_text()), json.loads(args.curation.read_text()),
                   args.points.read_text(), json.loads(args.published.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.output.with_suffix('.tmp')
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    tmp.replace(args.output)
    print(json.dumps({k: {n: v[n] for n in ('movedPlayers', 'maxMove', 'newTop100', 'newTop20')}
                      for k, v in result['scenarios'].items()}, ensure_ascii=False))


if __name__ == '__main__':
    main()
