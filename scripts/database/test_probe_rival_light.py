"""Synthetic cases for the read-only paired comparison."""
import copy
import math
import unittest

from probe_rival_light import HISTORY, LIGHT, START, compare_window, sample_plan


def match(id_, current):
    return {'id':str(id_), 'state':3, 'updatedAt':START+10, 'winnerId':'2',
            'event':{'id':'1','startAt':START+1 if current else START-1,'type':1,'videogame':{'id':1386}},
            'slots':[{'entrant':{'id':'2','participants':[{'player':{'id':'77'}}]}}],
            'games':[{'id':'3','winnerId':'2','selections':[{'character':{'id':1302}}]}]}


class Source:
    def __init__(self, sets, *, divergent=False, wrong_detail=False):
        self.calls = 0
        self.sets = sets
        self.divergent = divergent
        self.wrong_detail = wrong_detail

    def query(self, document, params):
        self.calls += 1
        if document in (HISTORY,LIGHT):
            size = 5 if document == HISTORY else 50
            page = params['page']
            sets = list(reversed(self.sets)) if document == LIGHT and self.divergent else self.sets
            return {'player':{'sets':{'pageInfo':{'total':len(sets),'totalPages':math.ceil(len(sets)/size)},
                                      'nodes':sets[(page-1)*size:page*size]}}}
        self.assert_detail_query(document)
        out = {key:copy.deepcopy(next(item for item in self.sets if item['id']==id_)) for key,id_ in params.items()}
        if self.wrong_detail:
            next(iter(out.values()))['games'][0]['selections'][0]['character']['id'] = 1296
        return out

    def assert_detail_query(self, document):
        assert 'set(id:$id0)' in document
        assert 'displayScore' in document
        assert 'selections' in document


class ProbeTests(unittest.TestCase):
    def test_sparse_window_is_cheaper_and_keeps_its_detail(self):
        source = Source([match(i,51 <= i <= 55) for i in range(1,106)])
        report = compare_window(source,'long_later_window','77',105,2)
        self.assertEqual(report['status'],'matched')
        self.assertEqual((report['current']['requests'],report['light']['requests']),(10,2))
        self.assertEqual((report['seasonSets'],report['games'],report['selections']),(5,5,5))

    def test_short_dense_history_can_cost_more(self):
        report = compare_window(Source([match(i,True) for i in range(1,6)]),'short_complete','77',5,1)
        self.assertEqual(report['status'],'matched')
        self.assertEqual((report['current']['requests'],report['light']['requests']),(1,2))

    def test_disagreeing_windows_or_character_details_do_not_pass(self):
        source = Source([match(i,True) for i in range(1,106)],divergent=True)
        self.assertEqual(compare_window(source,'long_first_window','77',105,1)['status'],'window_mismatch')
        detail = Source([match(1,True)],wrong_detail=True)
        self.assertEqual(compare_window(detail,'short_complete','77',1,1)['status'],'detail_mismatch')

    def test_sample_is_bounded_and_uses_whole_windows(self):
        choices = [('1',10),('2',25),('3',31),('4',105),('5',219),('6',410)]
        self.assertEqual(sample_plan(choices),[('short_complete','1',10,1),('short_complete','2',25,1),
            ('long_first_window','4',105,1),('long_later_window','5',219,4)])


if __name__ == '__main__':
    unittest.main()
