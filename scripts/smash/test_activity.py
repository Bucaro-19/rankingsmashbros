import copy
import unittest
from datetime import datetime

from deploy import validate_public_data
from publish_ranking import export_views
from rank import compute
from test_scope import world, POINTS
from test_rank import match


def bundle():
    data = world()
    # UTC March 1 is still February in Guatemala. The event calendar is local.
    dates = {10: '2026-01-15T12:00:00+00:00', 11: '2026-03-01T01:00:00+00:00',
             12: '2026-05-12T12:00:00+00:00'}
    for event in data['events']:
        event['startAt'] = int(datetime.fromisoformat(dates[event['id']]).timestamp())
    for row in data['sets'].values():
        row['event']['startAt'] = int(datetime.fromisoformat(dates[row['event']['id']]).timestamp())
    data['sets']['dq'] = match('dq', 10, '1', '2', 'P1 2 - P2 DQ')
    data['sets']['pending'] = match('pending', 10, '1', '2')
    data['sets']['pending']['state'] = 1
    curation = {'playerOverrides': {'1': 'test'}}
    ranking = compute(data, player_overrides=curation['playerOverrides'], points_table=POINTS)
    return export_views(data, ranking, curation, POINTS)


class ActivityTests(unittest.TestCase):
    def test_months_use_local_event_date_and_follow_scope(self):
        data = bundle()
        validate_public_data(data)
        combined = next(p for p in data['players'] if p['id'] == '1')
        local = next(p for p in data['localRanking']['players'] if p['id'] == '1')
        self.assertEqual(combined['activity']['months'], ['2026-01', '2026-02', '2026-05'])
        self.assertEqual(local['activity']['months'], ['2026-01', '2026-02'])
        self.assertEqual(len(combined['activity']['events']), 3)
        self.assertEqual(len(local['activity']['events']), 2)
        self.assertNotIn('dq', [m['id'] for m in data['results']])
        self.assertNotIn('pending', [m['id'] for m in data['results']])
        self.assertEqual(sum(e['wins'] for e in local['activity']['events']), local['wins'])

    def test_bad_ledgers_cannot_be_deployed(self):
        original = bundle()
        for corrupt in ('duplicate', 'unknown', 'wins', 'months', 'missing', 'set_event', 'duplicate_set'):
            data = copy.deepcopy(original)
            p = data['players'][0]
            ledger = p['activity']['events']
            if corrupt == 'duplicate': ledger.append(ledger[0])
            if corrupt == 'unknown': ledger[0]['id'] = 'missing'
            if corrupt == 'wins': ledger[0]['wins'] += 1
            if corrupt == 'months': p['activity']['months'].append('2026-12')
            if corrupt == 'missing': del p['activity']
            if corrupt == 'set_event': data['results'][0]['eventId'] = 'missing'
            if corrupt == 'duplicate_set': data['results'].append(data['results'][0])
            with self.subTest(corrupt=corrupt), self.assertRaisesRegex(ValueError, 'actividad'):
                validate_public_data(data)

    def test_legacy_cut_can_still_be_deployed_during_rollout(self):
        data = bundle()
        for scope in (data, data['localRanking']):
            for p in scope['players']: del p['activity']
            for m in scope['results']: del m['eventId']
        validate_public_data(data)


if __name__ == '__main__':
    unittest.main()
