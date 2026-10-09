"""Invented API captures and disposable SQL only. Never uses production credentials/data."""
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import small_events_backfill as backfill
from ranking_package import canonical, digest, instant, build_package
from import_ranking import import_package, sql
from test_organizer_context import captures, MIGRATION
import test_import_ranking as fixtures
import test_hosting_sync as hosting

OBSERVED = '2026-10-09T12:00:00+00:00'
START = 1767247200
END = 1791525600


def fake_inventory(cut=1, source_hash='a'*64):
    return dict(inventoryVersion=1,anchor=dict(cutId=cut,generatedAt='2026-10-04T11:43:18.348499+00:00',
        seasonYear=2026,methodVersion='BT-PILOTO-3',sourceHash=source_hash),markedEventIds=[],protectedEventIds=[100,101,102])


def fake_catalog(count=8):
    e = captures()[2]['events'][0]
    events = [dict(e,id=200+i,startAt=1768000000+i*86400) for i in range(count)]
    return dict(generatedAt=OBSERVED,season=dict(startInclusive=START,endExclusive=END),organizerCandidates=list(reversed(events)))


def fake_fetch(client,event):
    for _ in range(3): client.query('fixture',{})
    _,_,raw=captures(); matches={}; eid=event['id']
    for j,m in enumerate(raw['sets'].values()):
        m=copy.deepcopy(m); m.update(id=eid*10+j,event=event,tournament=event['tournament'],winnerId=eid*100+1)
        for slot in m['slots']:
            p=slot['entrant']['participants'][0]['player']['id'];slot['entrant']['id']=eid*100+p
        matches[str(m['id'])]=m
    return dict(event,setsFetched=2),raw['players'],matches


class Client:
    def __init__(self): self.calls=0
    def query(self,q,v): self.calls+=1; return {}


def package(inv=None,count=2):
    with patch('organizer_small.fetch_event',side_effect=fake_fetch), patch('organizer_small.datetime') as clock:
        clock.now.return_value=datetime.fromisoformat(OBSERVED)
        return backfill.capture_batch(Client(),inv or fake_inventory(),START,END,limit=count,catalog=fake_catalog(count))[0]


class BackfillContracts(unittest.TestCase):
    def test_unplayed_sets_in_completed_event_do_not_invent_results_or_change_source(self):
        _,_,raw=captures();raw['capturedAt']=OBSERVED
        pending=copy.deepcopy(raw['sets']['700']);pending.update(id=799,state=1,winnerId=None,displayScore=None)
        raw['sets']['799']=pending;raw['events'][0]['setsFetched']+=1
        before=copy.deepcopy(raw)
        context=backfill.normalize_small(raw)
        self.assertEqual(len(context['entities']['sets']),2);self.assertEqual(raw,before)
        self.assertEqual(context['entities']['events'][0]['active_players'],3)
        raw['sets']['799']['winnerId']=2001
        with self.assertRaises(ValueError):backfill.normalize_small(raw)

    def test_oldest_missing_only_and_no_national_mutation_or_games(self):
        inv=fake_inventory();inv['markedEventIds']=[200,202];inv['protectedEventIds'] += [201]
        catalog=fake_catalog();before=copy.deepcopy((inv,catalog));client=Client()
        with patch('organizer_small.fetch_event',side_effect=fake_fetch),patch('organizer_small.datetime') as clock:
            clock.now.return_value=datetime.fromisoformat(OBSERVED)
            p,r=backfill.capture_batch(client,inv,START,END,limit=2,catalog=catalog)
        self.assertEqual((inv,catalog),before)
        self.assertEqual({e['id'] for e in p['content']['context']['entities']['events']},{203,204})
        self.assertEqual((r['missingEvents'],r['remainingEvents'],r['apiRequests']),(5,3,6))
        self.assertEqual(set(p['content']['context']['entities']),set(backfill.TABLES))
        self.assertNotIn('public',p['content']);self.assertNotIn('rankings',p['content']['context']['entities'])
        self.assertNotIn('games',p['content']['context']['entities'])

    def test_budget_includes_catalog_retries_time_and_never_writes_partial_output(self):
        inv=fake_inventory();client=Client()
        def catalog(budget,start,end):
            budget.query('catalog',{});budget.query('catalog',{});return fake_catalog()
        def expensive(client,event):
            for _ in range(35):client.query('sets',{})
        with patch('small_events_backfill.probe_catalog',side_effect=catalog),patch('organizer_small.fetch_event',side_effect=expensive):
            with self.assertRaises(backfill.APIError):backfill.capture_batch(client,inv,START,END)
        self.assertEqual(client.calls,28)  # Includes two catalog calls; reserves three attempts.
        for limit in (0,11,True):
            client=Client()
            with self.assertRaises(ValueError):backfill.capture_batch(client,inv,START,END,limit=limit)
            self.assertEqual(client.calls,0)
        client=Client(); times=iter([0,0,121])
        with patch('small_events_backfill.probe_catalog',side_effect=catalog),self.assertRaises(backfill.APIError):
            backfill.capture_batch(client,inv,START,END,clock=lambda:next(times))
        self.assertEqual(client.calls,0)
        inv['markedEventIds']=[e['id'] for e in fake_catalog()['organizerCandidates']]
        p,r=backfill.capture_batch(Client(),inv,START,END,catalog=fake_catalog());self.assertIsNone(p);self.assertEqual(r['apiRequests'],0)

    def test_rehashed_bad_relations_anchor_budget_window_and_extra_tables_rejected(self):
        for kind in ('hash','anchor','table','online','slot','winner','activity','budget','time','window','stray'):
            p=package();c=p['content'];t=c['context']['entities']
            if kind=='hash':p['sha256']='0'*64
            if kind=='anchor':c['anchor']['sourceHash']='bad'
            if kind=='table':t['cuts']=[]
            if kind=='online':c['context']['eligibility'][0]['is_online']=True
            if kind=='slot':t['set_slots'][0]['event_id']=999
            if kind=='winner':t['sets'][0]['winner_entrant_id']=999
            if kind=='activity':t['events'][0]['active_players']=19
            if kind=='budget':c['audit']['apiRequests']=31
            if kind=='time':c['audit']['elapsedMilliseconds']=120001
            if kind=='window':c['season']['endExclusive']=START+1
            if kind=='stray':t['players'].append(dict(t['players'][0],id=99999))
            if kind!='hash':p['sha256']=digest(c)
            with self.subTest(kind=kind),self.assertRaises((ValueError,KeyError,TypeError)):backfill.validate_batch(p)

    def test_private_output_never_replaces_input_or_existing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'package.json';backfill.write_private(p,package())
            self.assertEqual(p.stat().st_mode & 0o777,0o600);original=p.read_bytes()
            with self.assertRaises(ValueError):backfill.write_private(p,package())
            self.assertEqual(original,p.read_bytes())
            link=Path(folder)/'link.json';link.symlink_to(p)
            with self.assertRaises(ValueError):backfill.read_json(link)
        workflow=(fixtures.ROOT/'.github/workflows/smash-publish.yml').read_text()
        self.assertIn('national.json --limit 6',workflow)
        self.assertNotIn('small_events_backfill',workflow)


@unittest.skipUnless(os.environ.get('SMASH_SCHEMA_TEST_DB'),'Disposable SQL required')
class BackfillSQL(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.ImportTests.setUpClass.__func__(cls)
        with cls.db.cursor() as q:
            q.execute(MIGRATION.read_text())
            while q.nextset():pass
    @classmethod
    def tearDownClass(cls):cls.db.close()
    clear=hosting.HostingSQLTests.clear
    snapshot=hosting.HostingSQLTests.snapshot
    def setUp(self):
        self.clear();self.base=build_package(*fixtures.fixture());import_package(self.db,self.base,apply=True)
        self.inv=backfill.inventory(self.db,2026);self.p=package(self.inv)
    def tearDown(self):
        self.db.rollback();sql(self.db,'DROP TRIGGER IF EXISTS backfill_fail');self.clear()
    def immutable(self):
        return {t:sql(self.db,'SELECT * FROM '+t+' ORDER BY 1') for t in ('cuts','cut_events','cut_set_results','rankings','player_characters','games','game_selections')}
    def test_read_only_inventory_simulation_apply_repeat_and_multiple_batches(self):
        original=self.snapshot(compare_importers=True);frozen=self.immutable()
        self.assertEqual(backfill.load_batch(self.db,self.p)['status'],'validated_no_writes')
        self.assertEqual(self.snapshot(compare_importers=True),original)
        with patch('small_events_backfill.organizer_plan',side_effect=lambda db,c: (sql(db,"INSERT INTO organizer_event_context(event_id,cut_id,captured_at,active_players,valid_sets,context_hash) VALUES (100,1,'2026-10-09',2,1,REPEAT('f',64))"),{})):
            with self.assertRaises(Exception) as blocked:backfill.load_batch(self.db,self.p)
        self.assertEqual(blocked.exception.args[0],1792)  # SQL server enforces READ ONLY.
        self.assertEqual(self.snapshot(compare_importers=True),original)
        self.assertEqual(backfill.load_batch(self.db,self.p,apply=True)['status'],'context_imported')
        once=self.snapshot(compare_importers=True);markers=sql(self.db,'SELECT * FROM organizer_event_context ORDER BY event_id')
        # Changed source after capture does not refresh a marked event in this one-off tool.
        altered=copy.deepcopy(self.p);altered['content']['context']['entities']['sets'][0]['display_score']='correction';altered['sha256']=digest(altered['content'])
        self.assertEqual(backfill.load_batch(self.db,altered,apply=True)['status'],'already_imported')
        self.assertEqual(self.snapshot(compare_importers=True),once)
        self.assertEqual(sql(self.db,'SELECT * FROM organizer_event_context ORDER BY event_id'),markers)
        inv=backfill.inventory(self.db,2026)
        with patch('organizer_small.fetch_event',side_effect=fake_fetch),patch('organizer_small.datetime') as clock:
            clock.now.return_value=datetime.fromisoformat(OBSERVED)
            p,r=backfill.capture_batch(Client(),inv,START,END,limit=2,catalog=fake_catalog(4))
        self.assertEqual(r['selectedEvents'],2)
        self.assertEqual(backfill.load_batch(self.db,p,apply=True)['status'],'context_imported')
        self.assertEqual(sql(self.db,'SELECT COUNT(*) FROM organizer_event_context')[0][0],4)
        self.assertEqual(frozen,self.immutable())
        # The original live national graph remains exactly equal, including shared players.
        for name,rows in original.items():
            if rows:
                current=self.snapshot(compare_importers=True)[name]
                self.assertTrue(all(row in current for row in rows),name)

    def test_partial_repeat_skips_existing_markers_and_account_contract_stays_intact(self):
        first=copy.deepcopy(self.p);first['content']['context']=backfill.subset(first['content']['context'],{200})
        a=first['content']['audit'];a['selectedEvents']=1;a['remainingEvents']=1;first['sha256']=digest(first['content'])
        backfill.load_batch(self.db,first,apply=True)
        original=sql(self.db,'SELECT * FROM organizer_event_context WHERE event_id=200')
        r=backfill.load_batch(self.db,self.p,apply=True)
        self.assertEqual((r['selectedEvents'],r['alreadyMarkedEvents']),(1,1))
        self.assertEqual(original,sql(self.db,'SELECT * FROM organizer_event_context WHERE event_id=200'))
        if hosting.PHP:
            with tempfile.TemporaryDirectory() as folder:
                script=Path(folder)/'account.php'
                script.write_text("<?php require "+json.dumps(str(fixtures.ROOT/'ranking-smash-ultimate/accounts.php'))+"; $p=new PDO('mysql:host=127.0.0.1;port='.getenv('SMASH_SCHEMA_TEST_PORT').';dbname='.getenv('SMASH_SCHEMA_TEST_DB').';charset=utf8mb4','root',getenv('SMASH_SCHEMA_TEST_PASSWORD'),[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]); echo json_encode(smash_account_small_events($p,'1',2026));")
                out=subprocess.run([hosting.PHP,str(script)],capture_output=True,text=True,check=True)
                events=json.loads(out.stdout);self.assertEqual(len(events),2)
                for e in events:
                    self.assertFalse(e['counts']);self.assertEqual((e['wins'],e['losses']),(2,0))
                    self.assertIn('3 jugadores activos',e['reason']);self.assertIn('20 o más',e['reason'])

    def test_anchor_live_collision_sql_failure_and_import_lock_roll_back(self):
        original=self.snapshot(compare_importers=True)
        bad=copy.deepcopy(self.p);bad['content']['anchor']['sourceHash']='f'*64;bad['sha256']=digest(bad['content'])
        with self.assertRaises(ValueError):backfill.load_batch(self.db,bad,apply=True)
        # Existing unmarked live event, even outside cut_events, is protected.
        row=self.p['content']['context']['entities']['events'][0]
        from import_ranking import insert_rows,COLUMNS
        insert_rows(self.db,'tournaments',COLUMNS['tournaments'],self.p['content']['context']['entities']['tournaments'])
        insert_rows(self.db,'events',COLUMNS['events'],[row]);self.db.commit()
        before=self.snapshot(compare_importers=True)
        with self.assertRaises(ValueError):backfill.load_batch(self.db,self.p,apply=True)
        self.assertEqual(before,self.snapshot(compare_importers=True))
        self.clear();import_package(self.db,self.base,apply=True);self.p=package(backfill.inventory(self.db,2026))
        sql(self.db,"CREATE TRIGGER backfill_fail BEFORE INSERT ON organizer_event_context FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='fixture'")
        with self.assertRaises(ValueError):backfill.load_batch(self.db,self.p,apply=True)
        self.assertEqual(original,self.snapshot(compare_importers=True));self.assertEqual(sql(self.db,'SELECT COUNT(*) FROM organizer_event_context')[0][0],0)
        sql(self.db,'DROP TRIGGER backfill_fail')
        self.db.begin();sql(self.db,"UPDATE sets SET display_score='foreign transaction' WHERE id=500")
        with self.assertRaises(ValueError):backfill.load_batch(self.db,self.p)
        self.assertEqual(sql(self.db,'SELECT display_score FROM sets WHERE id=500')[0][0],'foreign transaction');self.db.rollback()
        import pymysql
        other=pymysql.connect(host='127.0.0.1',port=int(os.environ['SMASH_SCHEMA_TEST_PORT']),user='root',password=os.environ['SMASH_SCHEMA_TEST_PASSWORD'],database=os.environ['SMASH_SCHEMA_TEST_DB'])
        try:
            sql(other,'SELECT GET_LOCK(%s,0)',('smash-ranking-import-v1',))
            with self.assertRaises(ValueError):backfill.load_batch(self.db,self.p,apply=True)
        finally:other.close()
        self.assertEqual(original,self.snapshot(compare_importers=True))


if __name__ == '__main__': unittest.main(verbosity=2)
