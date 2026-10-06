import copy
import unittest
from unittest.mock import Mock

from characters import enrich, player_mains, add_to_public
from collect import APIError
from deploy import validate_public_data
from test_scope import world
import test_scope


def game(gid, selections):
    return {'id':gid, 'winnerId':'e1', 'selections':[
        {'entrant':{'id':entrant},'character':{'id':cid,'name':name}} for entrant,cid,name in selections]}


class CharacterTests(unittest.TestCase):
    def test_count_by_entrant_dedupe_and_skip_ambiguous_or_unfinished_games(self):
        data=world(); match=data['sets']['1002']
        a=game('g1',[('e1',1,'Mario'),('e2',2,'Pikachu'),('e1',1,'Mario')])
        ambiguous=game('g2',[('e1',1,'Mario'),('e1',3,'Luigi')])
        pending=game('g3',[('e1',1,'Mario')]);pending['winnerId']=None
        match['games']=[a,a,ambiguous,pending,game('g4',[('e1',3,'Luigi')])]
        result=player_mains(data,{'10','11'},{'1','2'})
        self.assertEqual(result['1']['mains'],[{'characterId':'1','name':'Mario','games':1},{'characterId':'3','name':'Luigi','games':1}])
        self.assertEqual(result['2']['mains'][0]['name'],'Pikachu')
        self.assertEqual(result['1']['mainCoverage']['ambiguousGames'],1)
        self.assertEqual(result['1']['mainCoverage']['setsWithSelections'],1)

    def test_foreign_characters_do_not_leak_into_local_view(self):
        data=world();data['sets']['f2']['games']=[game('f',[('e1',9,'Sora')])]
        self.assertEqual(player_mains(data,{'10','11'},{'1'})['1']['mains'],[])
        self.assertEqual(player_mains(data,{'12'},{'1'})['1']['mains'][0]['name'],'Sora')

    def test_cache_reuse_null_games_and_changed_results_fail_closed(self):
        data=world();data['sets']={'1002':data['sets']['1002']}
        original=data['sets']['1002']; row={k:original[k] for k in ('id','state','winnerId','displayScore')};row['games']=None
        client=Mock();client.query.return_value={'s0':row};cache={}
        result=enrich(client,data,{'1'},{'10'},cache)
        self.assertTrue(result['characterDataComplete']);self.assertEqual(result['sets']['1002']['games'],[])
        enrich(client,data,{'1'},{'10'},cache);self.assertEqual(client.query.call_count,1)
        wrong={**row,'winnerId':'e2'};client.query.return_value={'s0':wrong}
        with self.assertRaises(APIError): enrich(client,data,{'1'},{'10'}, {})
        self.assertNotIn('games',original)

    def test_public_enrichment_preserves_all_previous_fields_and_validates(self):
        data=world();public=test_scope.ScopeTests().bundle(data)
        data.update(characterDataComplete=True,characterCapturedAt='2026-10-06T00:00:00Z',
                    characterPlayerIds=[p['id'] for p in public['players']], characterEventIds=[e['id'] for e in public['events']])
        result=add_to_public(data,public);validate_public_data(result)
        old=copy.deepcopy(result)
        for view in (old,old['localRanking']):
            view['schemaVersion']=2;del view['characterCapturedAt']
            for p in view['players']: del p['mains'];del p['mainCoverage']
        self.assertEqual(old,public)
        broken=copy.deepcopy(result);broken['players'][0]['mainCoverage']['setsQueried']=0
        with self.assertRaises(ValueError): validate_public_data(broken)
        data['characterPlayerIds']=[]
        with self.assertRaises(ValueError): add_to_public(data,public)


if __name__=='__main__': unittest.main()
