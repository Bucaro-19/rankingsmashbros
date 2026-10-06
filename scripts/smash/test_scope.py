import copy
import unittest

from deploy import validate_public_data
from publish_ranking import export_views
from rank import compute
from test_rank import fixture, match, player


POINTS = 'Category,Note,Player,Start.gg Hex ID,Start.gg Num ID,Points,Start Date,End Date,Midpt Date,Source\n'


def world():
    data = fixture()
    data['internationalComplete'] = True
    # Player 2 has one local set and three foreign sets: eligible only combined.
    del data['sets']['1102']
    data['events'].append({'id': 12, 'name': 'Ultimate Singles', 'numEntrants': 64,
                           'startAt': 1768000000, 'placements': {},
                           'tournament': {'countryCode': 'MX', 'name': 'Foreign'}})
    for pid in range(1, 65):
        data['players'].setdefault(str(pid), player(str(pid), 'Mexico'))
    for pid in range(2, 65):
        m = match('f'+str(pid), 12, str(pid), '1')
        m['tournament'] = {'countryCode': 'MX', 'name': 'Foreign'}
        data['sets'][m['id']] = m
    for sid in ('extra-a', 'extra-b'):
        m = match(sid, 12, '2', '1')
        m['tournament'] = {'countryCode': 'MX', 'name': 'Foreign'}
        data['sets'][sid] = m
    return data


class ScopeTests(unittest.TestCase):
    def bundle(self, data=None, previous=None):
        data = data or world()
        curation = {'playerOverrides': {'1': 'test'}}
        ranking = compute(data, player_overrides=curation['playerOverrides'], points_table=POINTS)
        return export_views(data, ranking, curation, POINTS, previous)

    def test_local_view_refits_and_rechecks_eligibility_and_history(self):
        bundle = self.bundle()
        local = bundle['localRanking']
        self.assertIn('2', [p['id'] for p in bundle['players']])
        self.assertNotIn('2', [p['id'] for p in local['players']])
        self.assertEqual(local['counts']['events'], 2)
        self.assertEqual(bundle['counts']['events'], 3)
        p1 = next(p for p in bundle['players'] if p['id'] == '1')
        self.assertNotEqual(p1['rating'], local['players'][0]['rating'])
        self.assertTrue(all(m['country'] == 'GT' for m in local['results']))
        self.assertEqual(local['generatedAt'], bundle['generatedAt'])
        validate_public_data(bundle)

    def test_previous_positions_belong_to_the_same_scope(self):
        previous = self.bundle()
        data = world(); data['generatedAt'] = '2026-09-29T12:00:00+00:00'
        next_cut = self.bundle(data, previous)
        for scope in (next_cut, next_cut['localRanking']):
            self.assertEqual(scope['previousCutAt'], previous['generatedAt'])
        previous['localRanking'] = {k: v for k, v in previous.items() if k != 'localRanking'}
        mixed = self.bundle(data, previous)
        self.assertIsNone(mixed['localRanking']['previousCutAt'])
        del previous['localRanking']
        first_local = self.bundle(data, previous)
        self.assertIsNone(first_local['localRanking']['previousCutAt'])
        self.assertIsNotNone(first_local['previousCutAt'])

    def test_deployment_rejects_mixed_dates_and_foreign_results_in_local(self):
        original = self.bundle()
        for corrupt in ('date', 'foreign_event', 'foreign_set', 'method'):
            data = copy.deepcopy(original)
            local = data['localRanking']
            if corrupt == 'date': local['generatedAt'] = '2026-09-30T12:00:00+00:00'
            if corrupt == 'foreign_event': local['events'][0]['country'] = 'MX'
            if corrupt == 'foreign_set': local['results'][0]['country'] = 'MX'
            if corrupt == 'method': local['methodVersion'] = 'other'
            with self.assertRaises(ValueError): validate_public_data(data)


if __name__ == '__main__':
    unittest.main()
