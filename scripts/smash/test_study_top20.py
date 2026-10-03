import json
from pathlib import Path
from deploy import validate_top20_study
import copy
import unittest
from publish_ranking import export
from rank import compute
from study_top20 import activity_bonus, rerank, study, verify_baseline
from test_rank import fixture


class Top20StudyTests(unittest.TestCase):
    def test_bonuses_have_a_floor_and_cap_and_do_not_mutate_ratings(self):
        self.assertEqual([activity_bonus(n, 1, 'events') for n in (1, 2, 3, 8, 100)], [0, 0, 5, 30, 30])
        self.assertEqual([activity_bonus(20, n, 'months') for n in (1, 2, 3, 5, 12)], [0, 0, 10, 30, 30])
        rows = [{'id': 'a', 'rank': 1, 'rating': 1500, 'events': 2, 'wins': 4, 'tag': 'A'},
                {'id': 'b', 'rank': 2, 'rating': 1499, 'events': 8, 'wins': 4, 'tag': 'B'}]
        original = copy.deepcopy(rows)
        self.assertEqual(rerank(rows, {'a': 2, 'b': 6}, 'events')[0]['id'], 'b')
        self.assertEqual(rerank(rows, {'a': 2, 'b': 6}, 'none')[0]['id'], 'a')
        self.assertEqual(rows, original)

    def test_study_requires_exact_published_cut_and_keeps_eligibility_losses(self):
        snapshot = fixture()
        curation = {'playerOverrides': {'1': 'fixture'}}
        points = 'Category,Note,Player,Start.gg Hex ID,Start.gg Num ID,Points,Start Date,End Date,Midpt Date,Source\n'
        ranking = compute(snapshot, player_overrides=curation['playerOverrides'], points_table=points)
        published = export(snapshot, ranking)
        result = study(snapshot, curation, points, published)
        p = result['profiles'][0]
        self.assertEqual(p['months'], ['2026-01'])
        self.assertEqual(p['sensitivity']['unrankedScenarios'], 2)
        self.assertIsNone(p['sensitivity']['bestRank'])
        self.assertEqual(sum(e['wins']+e['losses'] for e in p['eventLedger']), p['sets'])
        altered = copy.deepcopy(published)
        altered['players'][0]['rating'] += 1
        with self.assertRaisesRegex(ValueError, 'no reproduce'):
            verify_baseline(ranking, altered)
        altered = copy.deepcopy(published)
        altered['generatedAt'] = 'otro corte'
        with self.assertRaisesRegex(ValueError, 'no reproduce'):
            verify_baseline(ranking, altered)

    def test_published_study_cannot_drop_players_or_overstate_a_bonus(self):
        source = Path(__file__).resolve().parents[2] / 'ranking-smash-ultimate/data/analisis-top20.json'
        original = json.loads(source.read_text())
        validate_top20_study(original)
        for corruption in ('missing_player', 'excess_bonus', 'different_profile'):
            data = copy.deepcopy(original)
            if corruption == 'missing_player':
                data['scenarios']['months']['players'].pop()
            elif corruption == 'excess_bonus':
                data['scenarios']['events']['players'][0]['bonus'] = 31
            else:
                data['profiles'][0]['id'] = 'other'
            with self.assertRaisesRegex(ValueError, 'incompleto'):
                validate_top20_study(data)

    def test_private_diagnostics_do_not_change_production_results(self):
        snapshot = fixture()
        usual = compute(snapshot)
        diagnostic = compute(snapshot, diagnostics=True)
        evidence = diagnostic.pop('diagnostics')
        self.assertEqual(usual, diagnostic)
        self.assertTrue(evidence['converged'])
        self.assertLess(evidence['maxStep'], 1e-7)
        self.assertNotIn('diagnostics', export(snapshot, compute(snapshot, diagnostics=True)))


if __name__ == '__main__':
    unittest.main()
