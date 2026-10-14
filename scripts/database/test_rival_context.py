"""Invented roster/history; database tests require a disposable local service."""
import copy
import json
import os
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'smash'))
from rival_context import package,validate,load,read_private_json
from rival_history import new_state,capture_batch,roster,HISTORY,META,ENTRANTS,REGISTRATIONS
from ranking_package import digest,canonical,build_package
from import_ranking import import_package,sql
from test_import_ranking import fixture
ROOT=Path(__file__).resolve().parents[2]


def sample():
    raw,public=fixture(); m=copy.deepcopy(raw['sets']['500']);e=copy.deepcopy(raw['events'][0]);e.update(id=777,type=1,slug='tournament/test77/event/singles',tournament=dict(id=77,name='Otro evento de análisis',slug='tournament/test77',countryCode='SV'))
    a=copy.deepcopy(raw['players']['1']);b=dict(id=9,gamerTag='Rival solo contexto',user=dict(slug='user/context9',location=dict(country='El Salvador')))
    m.update(id=7777,event=e,tournament=e['tournament'],winnerId=7772,displayScore='Rival solo contexto 2 - Jugador 0',slots=[dict(entrant=dict(id=7771,participants=[dict(player=a)])),dict(entrant=dict(id=7772,participants=[dict(player=b)]))])
    m['games']=[dict(id=77770+i,orderNum=i,winnerId=7772,entrant1Score=0,entrant2Score=2,stage=None,selections=[dict(entrant=dict(id=en),character=dict(id=cid,name=name)) for en,cid,name in ((7771,1302,'Mario'),(7772,1296,'Link'))]) for i in (1,2)]
    ro=dict(kind='analysis_roster',schemaVersion=1,capturedAt=raw['generatedAt'],players={'9':b},event=dict(id=8888),tournament=dict(id=888),registrations=1)
    data=dict(kind='analysis_history',schemaVersion=1,capturedAt=raw['generatedAt'],seasonYear=2026,roster=ro,sets={'7777':m},coverage={'9':dict(nextPage=2,totalPages=1,complete=True)},audit=dict(requests=1,seconds=1,playersQueried=1,registered=1,known=0,missing=1,complete=1,sets=1))
    return data,public


class Contracts(unittest.TestCase):
    def test_package_is_analysis_only_and_preserves_public(self):
        data,public=sample(); before=canonical(public);p=package(data);validate(json.loads(canonical(p)))
        self.assertEqual(before,canonical(public));self.assertNotIn('public',p['content']);self.assertEqual(p['content']['gameScores'][0]['entrant2_score'],2)
        self.assertEqual(len(p['content']['entities']['game_selections']),4)
        for forbidden in ('cuts','cut_events','cut_set_results','rankings','player_characters'):self.assertNotIn(forbidden,p['content']['entities'])
    def test_corrupt_relation_rejected(self):
        data,_=sample();p=package(data);p['content']['entities']['games'][0]['winner_entrant_id']=999999;p['sha256']=digest(p['content'])
        with self.assertRaises(ValueError):validate(p)
    def test_unpublished_roster_is_not_zero(self):
        class Fake:
            calls=0
            def query(self,q,v):
                self.calls+=1
                if q==META:return {'tournament':dict(slug='tournament/legends7',events=[dict(id=88,type=1,videogame=dict(id=1386),numEntrants=None)])}
                empty=dict(pageInfo=dict(total=0,totalPages=0),nodes=[])
                return {'event':dict(entrants=empty)} if q==ENTRANTS else {'tournament':dict(participants=empty)}
        from collect import APIError
        with self.assertRaisesRegex(APIError,'registrations_unavailable'):roster(Fake(),'legends7')
    def test_private_files_never_overwrite_published_data(self):
        import tempfile
        from rival_history import save
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'a.json';save(p,{'kind':'test'})
            self.assertEqual(read_private_json(p),{'kind':'test'})
            with self.assertRaises(ValueError):save(p,{'bad':True})
            link=Path(tmp)/'link.json';link.symlink_to(p)
            with self.assertRaises(ValueError):read_private_json(link)
        with self.assertRaises(ValueError):save(ROOT/'ranking-smash-ultimate/data/public.json',{})
    def test_budget_and_resume_cache(self):
        data,_=sample();state=new_state(data['roster'],[],2026)
        class Fake:
            calls=0
            def query(self,q,v):
                self.calls+=1
                return {'player':dict(sets=dict(pageInfo=dict(total=500,totalPages=100),nodes=[dict(data['sets']['7777'])]))}
        c=Fake();got,state=capture_batch(c,state);self.assertEqual(c.calls,28);self.assertEqual(state['coverage']['9']['nextPage'],29)
        got,state=capture_batch(Fake(),state);self.assertEqual(state['coverage']['9']['nextPage'],57)
        self.assertLessEqual(got['audit']['requests'],30)


@unittest.skipUnless(os.getenv('SMASH_SCHEMA_TEST_DB'),'Disposable SQL required')
class SqlTests(unittest.TestCase):
    def setUp(self):
        import pymysql
        from pymysql.constants import CLIENT
        db=os.environ['SMASH_SCHEMA_TEST_DB'];self.assertTrue(db.startswith('smash_schema_test'))
        self.assertIn(os.getenv('SMASH_SCHEMA_TEST_HOST','127.0.0.1'),('localhost','127.0.0.1'))
        self.db=pymysql.connect(host='127.0.0.1',port=int(os.getenv('SMASH_SCHEMA_TEST_PORT','3306')),user='root',password=os.environ['SMASH_SCHEMA_TEST_PASSWORD'],database=db,autocommit=True,client_flag=CLIENT.MULTI_STATEMENTS)
        self.clean();raw,self.public=fixture();import_package(self.db,build_package(raw,self.public),apply=True)
    def clean(self):
        sql(self.db,'DELETE FROM analysis_context_players');sql(self.db,'DELETE FROM analysis_context_batches');sql(self.db,'DELETE FROM analysis_game_scores')
        sql(self.db,'UPDATE rankings SET previous_cut_id=NULL')
        for t in ('game_selections','games','player_characters','rankings','cut_set_results','cut_events','cuts','set_slots','sets','entrant_players','entrants','events','tournaments','players'):sql(self.db,'DELETE FROM '+t)
    def tearDown(self):self.db.rollback();self.clean();self.db.close()
    def protected(self):return {t:sql(self.db,'SELECT * FROM '+t+' ORDER BY 1') for t in ('cuts','rankings','cut_events','cut_set_results','player_characters')}
    def test_missing_migration_is_read_only_and_relation_conflict_rolls_back(self):
        p=package(sample()[0]);before=self.protected()
        sql(self.db,"DELETE FROM schema_migrations WHERE version='007_analysis_context'")
        try:
            self.assertEqual(load(self.db,p)['status'],'migration_required_no_writes')
            with self.assertRaises(ValueError):load(self.db,p,apply=True)
            self.assertEqual(sql(self.db,'SELECT id FROM players WHERE id=9'),())
        finally:sql(self.db,"INSERT INTO schema_migrations(version) VALUES ('007_analysis_context')")
        load(self.db,p,apply=True)
        for row in p['content']['entities']['entrant_players']:
            row['player_id']=9 if row['player_id']==1 else 1
        p['sha256']=digest(p['content'])
        with self.assertRaises(ValueError):load(self.db,p,apply=True)
        self.assertEqual(self.protected(),before)
    def test_dry_apply_repeat_and_frozen_ranking(self):
        p=package(sample()[0]);before=self.protected();r=load(self.db,p);self.assertEqual(r['status'],'validated_no_writes');self.assertEqual(sql(self.db,'SELECT id FROM players WHERE id=9'),())
        self.assertEqual(load(self.db,p,apply=True)['status'],'imported');self.assertEqual(load(self.db,p,apply=True)['status'],'already_imported')
        self.assertEqual(self.protected(),before);self.assertEqual(sql(self.db,'SELECT COUNT(*) FROM analysis_game_scores')[0][0],2)
        php='''require $argv[1].'/database.php';require $argv[1].'/accounts.php';require $argv[1].'/stats.php';require $argv[1].'/premium.php';require $argv[1].'/analisis.php';$cfg=json_decode(stream_get_contents(STDIN),true);$db=smash_database_connect($cfg['database']);$p=$cfg['public'];$u=['id'=>'1','playerId'=>'1','tag'=>'Yo','url'=>null,'country'=>'GT','chosen'=>[]];$r=smash_analisis_response($db,$p,$u,$cfg['input']??['rival'=>'9'],null,time());echo json_encode($r);'''
        # An invented admin row authorizes the paid projection; no real accounts/providers.
        sql(self.db,'INSERT INTO users(id,startgg_user_id,player_id) VALUES (1,8999901,1)');sql(self.db,"INSERT INTO user_roles(user_id,role) VALUES (1,'admin')")
        import subprocess
        cfg=dict(database=dict(host='127.0.0.1',port=int(os.getenv('SMASH_SCHEMA_TEST_PORT','3306')),name=os.environ['SMASH_SCHEMA_TEST_DB'],user='root',password=os.environ['SMASH_SCHEMA_TEST_PASSWORD']),public=self.public)
        try:
            r=json.loads(subprocess.check_output(['php','-r',php,str(ROOT/'ranking-smash-ultimate')],input=json.dumps(cfg).encode()))
            self.assertIsNone(r['rival']['rank']['intl']);self.assertEqual(r['record']['losses'],1);self.assertEqual(r['rival']['detected'][0]['slug'],'link');self.assertEqual(r['deep']['rival']['main'],'link')
            self.assertEqual(self.protected(),before)
            cfg['input']={'rival':'9','scope':'gt'}
            empty=json.loads(subprocess.check_output(['php','-r',php,str(ROOT/'ranking-smash-ultimate')],input=json.dumps(cfg).encode()))
            self.assertEqual(empty['record']['sets'],0)
            sql(self.db,"DELETE FROM user_roles WHERE user_id=1 AND role='admin'")
            cfg['input']={'rival':'9'}
            free=json.loads(subprocess.check_output(['php','-r',php,str(ROOT/'ranking-smash-ultimate')],input=json.dumps(cfg).encode()))
            self.assertNotIn('deep',free);self.assertNotIn('detected',free['rival']);self.assertEqual(free['record']['sets'],1)
            cfg['input']={'buscar':'solo contexto'}
            found=json.loads(subprocess.check_output(['php','-r',php,str(ROOT/'ranking-smash-ultimate')],input=json.dumps(cfg).encode()))
            self.assertEqual(found['results'][0]['playerId'],'9');self.assertIsNone(found['results'][0]['rank']['intl'])
            # A later correction is not reverted by replaying the already applied package.
            sql(self.db,"UPDATE sets SET display_score='Corrección posterior' WHERE id=7777")
            self.assertEqual(load(self.db,p,apply=True)['status'],'already_imported')
            self.assertEqual(sql(self.db,'SELECT display_score FROM sets WHERE id=7777')[0][0],'Corrección posterior')
        finally:sql(self.db,'DELETE FROM users WHERE id=1')

if __name__=='__main__':unittest.main(verbosity=2)
