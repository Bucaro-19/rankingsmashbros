"""Invented roster, source and hosting; SQL/HTTP only on a local disposable database."""
import contextlib
import copy
from datetime import datetime,timezone
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
from unittest import mock

import rival_automation as auto
import test_rival_context as fixtures
import publish_sql as sender
from ranking_package import canonical,digest,build_package
from rival_context import package,load,validate,COLUMNS as CONTEXT_COLUMNS
from import_ranking import sql,import_package
from test_import_ranking import fixture as national_fixture
ROOT=Path(__file__).resolve().parents[2];SITE=ROOT/'ranking-smash-ultimate'
NOW=datetime(2026,10,14,tzinfo=timezone.utc)


def source_player(pid):return dict(id=pid,gamerTag='Inventado '+str(pid),user=dict(slug='user/test'+str(pid),location=dict(country='El Salvador')))

def history(pid):
    d,_=fixtures.sample();m=copy.deepcopy(d['sets']['7777']);delta=pid-9;eid=777+delta;sid=7777+delta
    m['id']=sid;m['event'].update(id=eid,slug=f'tournament/test77/event/singles{eid}')
    m['winnerId']=eid*10+2;m['slots'][0]['entrant']['id']=eid*10+1;m['slots'][1]['entrant'].update(id=eid*10+2,participants=[dict(player=source_player(pid))])
    for i,g in enumerate(m['games'],1):
        g.update(id=sid*10+i,winnerId=m['winnerId'])
        for pick,en in zip(g['selections'],(eid*10+1,eid*10+2)):pick['entrant']['id']=en
    return m


class Source:
    def __init__(self,ids=(),pages=1):self.ids=list(ids);self.calls=0;self.history_ids=[];self.pages=pages
    def query(self,q,v):
        self.calls+=1
        if q==auto.EVENT_ROSTER:
            nodes=[dict(participants=[dict(player=source_player(pid))]) for pid in self.ids]
            return dict(event=dict(id=1687524,name='Ultimate Singles',slug='tournament/legends7/event/ultimate-singles',type=1,numEntrants=len(nodes) or None,startAt=1792857600,isOnline=False,videogame=dict(id=1386,name='Ultimate'),
                tournament=dict(id=942547,name='LEGENDS7',slug='tournament/legends7',countryCode='SV',timezone='America/El_Salvador'),
                entrants=dict(pageInfo=dict(total=len(nodes),totalPages=1 if nodes else 0),nodes=nodes)))
        self.history_ids.append(int(v['id']))
        return dict(player=dict(sets=dict(pageInfo=dict(total=self.pages,totalPages=self.pages),nodes=[history(int(v['id']))])) )


class DenseSource(Source):
    """Worst-case bounded batch: 28 pages, five sets/page, ten games/set."""
    def query(self,q,v):
        response=super().query(q,v)
        if q==auto.EVENT_ROSTER:return response
        rows=[]
        for j in range(5):
            m=history(int(v['id']));m['id']=900000+(v['page']-1)*5+j
            model=m['games'][0];m['games']=[]
            for i in range(1,11):
                game=copy.deepcopy(model);game.update(id=m['id']*10+i,orderNum=i);m['games'].append(game)
            rows.append(m)
        response['player']['sets']['nodes']=rows;return response


def quiet_run(*args,**kwargs):
    with contextlib.redirect_stdout(io.StringIO()) as out:result=auto.run(*args,**kwargs)
    return result,out.getvalue()


def php(mode,p):
    run=subprocess.run(['php','-d','memory_limit=512M',str(ROOT/'scripts/database/php_rival_bridge.php')],input=json.dumps(dict(mode=mode,raw=canonical(p))),text=True,capture_output=True,timeout=90)
    if run.stderr:raise AssertionError('Unexpected PHP diagnostic')
    return json.loads(run.stdout)


class Contracts(unittest.TestCase):
    def test_hidden_is_one_query_no_hosting_and_no_names_in_log(self):
        client=Source();host=mock.Mock();report,log=quiet_run(client,host,1687524,now=NOW)
        self.assertEqual(client.calls,1);host.inventory.assert_not_called();host.deliver.assert_not_called()
        self.assertEqual(report['status'],'registrations_unavailable');self.assertIsNone(report['registered']);self.assertEqual(report['added'],0)
        self.assertNotIn('Inventado',log)
    def test_expired_is_zero_queries(self):
        client=Source([9]);host=mock.Mock();report,_=quiet_run(client,host,1687524,now=auto.UNTIL)
        self.assertEqual(report['status'],'authorization_expired');self.assertEqual(client.calls,0);host.inventory.assert_not_called()
        self.assertTrue(auto.active(datetime(2026,10,26,5,59,59,tzinfo=timezone.utc)))
    def test_different_event_is_not_authorized_and_does_not_query(self):
        client=Source([9]);host=mock.Mock()
        with contextlib.redirect_stdout(io.StringIO()),self.assertRaisesRegex(sender.SyncStopped,'analysis_event_not_authorized'):auto.run(client,host,999,now=NOW)
        self.assertEqual(client.calls,0);host.inventory.assert_not_called()
    def test_bad_configuration_still_has_aggregate_summary(self):
        with mock.patch.dict(os.environ,{'SMASH_RIVAL_EVENT_ID':'invalid'}),contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(auto.main(),1)
        summary=json.loads(out.getvalue().splitlines()[0]);self.assertEqual(summary['status'],'configuration_invalid');self.assertEqual(summary['queries'],0)
    def test_workflow_off_main_only_no_artifacts_sql_ftp_or_unbounded_batches(self):
        text=(ROOT/'.github/workflows/smash-rival-context.yml').read_text()
        for needed in ('37 2,8,14,20 * * *','SMASH_RIVAL_SYNC_ENABLED','refs/heads/main','smash-gt-publication','SMASH_RIVAL_EVENT_ID'):self.assertIn(needed,text)
        for blocked in ('secrets.FTP','MYSQL','upload-artifact','actions/cache','--apply','workflow_run'):self.assertNotIn(blocked,text)
        self.assertEqual(auto.MAX_BATCHES,2)
    def test_php_python_same_context_contract_and_hash(self):
        p=package(fixtures.sample()[0]);p['content']['audit']['seconds']=1;p['sha256']=digest(p['content'])
        self.assertTrue(php('validate',p)['ok'])
        for kind in ('winner','slot','character','game_order','season','extra_table','score'):
            v=copy.deepcopy(p);c=v['content'];t=c['entities']
            if kind=='winner':t['games'][0]['winner_entrant_id']=999
            if kind=='slot':t['set_slots'][0]['event_id']=999
            if kind=='character':t['game_selections'][0]['character_id']=999
            if kind=='game_order':t['games'][0]['game_number']=0
            if kind=='season':c['seasonYear']=2025
            if kind=='extra_table':t['rankings']=[]
            if kind=='score':c['gameScores'][0]['entrant2_score']='bad'
            v['sha256']=digest(c)
            with self.subTest(kind=kind):
                with self.assertRaises((ValueError,KeyError)):validate(v)
                self.assertFalse(php('validate',v)['ok'])
    def test_auth_scope_stays_closed_without_owner_clarification(self):
        # Deliberately not assumed from a narrower authorization. Temporary SQL test copy enables it only in the fixture.
        self.assertIn('const RC_ENTITY_INSERTS_AUTHORIZED=false;',(SITE/'rival-sync-lib.php').read_text())


@unittest.skipUnless(os.getenv('SMASH_SCHEMA_TEST_DB'),'Disposable SQL service required')
class SqlTests(fixtures.SqlTests):
    def clean(self):
        sql(self.db,"DELETE FROM sync_jobs WHERE kind='player_history'")
        fixtures.SqlTests.clean(self)
    def setUp(self):
        super().setUp();self.temp=tempfile.TemporaryDirectory(prefix='smash-auto-');self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name).resolve();self.site=self.folder/'site';self.private=self.folder/'private-smash';self.site.mkdir();self.private.mkdir();(self.site/'data').mkdir()
        for filename in ('database.php','ranking-import.php','rival-import.php','rival-sync-lib.php','ranking-sync-lib.php','ranking-sync.php','ranking-worker.php','characters.js'):
            shutil.copyfile(SITE/filename,self.site/filename)
        # Test-only copy; production source remains closed pending the owner's response.
        lib=self.site/'rival-sync-lib.php';lib.write_text(lib.read_text().replace('RC_ENTITY_INSERTS_AUTHORIZED=false','RC_ENTITY_INSERTS_AUTHORIZED=true').replace("const RC_UNTIL='2026-10-26T06:00:00Z'","const RC_UNTIL='2099-10-26T06:00:00Z'"))
        config=dict(database=dict(host='127.0.0.1',port=int(os.getenv('SMASH_SCHEMA_TEST_PORT','3306')),name=os.environ['SMASH_SCHEMA_TEST_DB'],user='root',password=os.environ['SMASH_SCHEMA_TEST_PASSWORD']))
        (self.private/'config.local.php').write_text('<?php return json_decode('+json.dumps(json.dumps(config))+',true);')
        (self.private/'sync.local.php').write_text("<?php return ['enabled'=>true,'key'=>'"+'1'*64+"'];")
        (self.site/'data/public.json').write_text(canonical(self.public))
    @contextlib.contextmanager
    def serving(self):
        with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
        server=subprocess.Popen(['php','-d','display_errors=0','-S',f'127.0.0.1:{port}','-t',str(self.site)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        self.addCleanup(lambda:server.poll() is None and server.terminate())
        with mock.patch.object(sender,'URL',f'http://127.0.0.1:{port}/ranking-sync.php'):
            import urllib.request,urllib.error
            for _ in range(60):
                try:urllib.request.urlopen(sender.URL,timeout=.2)
                except urllib.error.HTTPError:break
                except OSError:time.sleep(.05)
            try:yield auto.Hosting('1'*64,pause=lambda seconds:self.worker())
            finally:server.terminate();server.wait(timeout=5)
    def worker(self):
        result=subprocess.run(['php','-d','memory_limit=512M',str(self.site/'ranking-worker.php')],text=True,capture_output=True,timeout=30)
        self.assertEqual(result.stderr,'');data=json.loads(result.stdout);self.assertTrue(data['ok'],data);self.last_peak=data['peakMemoryBytes'];return data
    def dump(self):
        out={}
        for table in tuple(CONTEXT_COLUMNS)+('analysis_context_batches','analysis_context_players','analysis_game_scores'):
            cols=[r[0] for r in sql(self.db,'SHOW COLUMNS FROM '+table) if r[0] not in ('updated_at','imported_at')]
            out[table]=sorted(sql(self.db,'SELECT '+','.join(cols)+' FROM '+table),key=repr)
        return out
    def test_import_once_new_registration_and_frozen_ranking_over_real_signed_http(self):
        before=self.protected();public=(self.site/'data/public.json').read_bytes()
        with self.serving() as host:
            c=Source([9]);first,log=quiet_run(c,host,1687524,now=NOW)
            self.assertEqual(first['registered'],1);self.assertEqual(first['added'],1);self.assertEqual(first['pending'],0);self.assertEqual(c.history_ids,[9]);self.assertNotIn('Inventado',log)
            state=self.dump();c=Source([9]);second,_=quiet_run(c,host,1687524,now=NOW)
            self.assertEqual(second['status'],'already_imported');self.assertEqual(c.calls,1);self.assertEqual(c.history_ids,[]);self.assertEqual(self.dump(),state)
            c=Source([9,10]);third,_=quiet_run(c,host,1687524,now=NOW);self.assertEqual(third['added'],1);self.assertEqual(c.history_ids,[10])
        self.assertEqual(sql(self.db,'SELECT COUNT(*) FROM analysis_context_batches')[0][0],2)
        self.assertEqual(sql(self.db,'SELECT COUNT(*) FROM sync_jobs WHERE kind="player_history"')[0][0],2)
        self.assertEqual(self.protected(),before);self.assertEqual((self.site/'data/public.json').read_bytes(),public);self.assertLess(self.last_peak,512*1024*1024)
    def test_missing_007_rejects_before_history_or_queue_write(self):
        sql(self.db,"DELETE FROM schema_migrations WHERE version='007_analysis_context'");before=self.dump();protected=self.protected()
        try:
            with self.serving() as host,contextlib.redirect_stdout(io.StringIO()):
                c=Source([9])
                with self.assertRaisesRegex(sender.SyncStopped,'analysis_migration_required'):auto.run(c,host,1687524,now=NOW)
                self.assertEqual(c.calls,1);self.assertEqual(c.history_ids,[])
            self.assertEqual(self.dump(),before);self.assertEqual(self.protected(),protected);self.assertEqual(sql(self.db,'SELECT COUNT(*) FROM sync_jobs')[0][0],0)
        finally:sql(self.db,"INSERT INTO schema_migrations(version) VALUES ('007_analysis_context')")
    def test_known_registrant_does_not_consume_history_queries(self):
        with self.serving() as host:
            c=Source([1]);result,_=quiet_run(c,host,1687524,now=NOW)
        self.assertEqual((result['known'],result['added'],result['pending'],c.calls),(1,0,0,1))
        self.assertEqual(sql(self.db,"SELECT COUNT(*) FROM sync_jobs WHERE kind='player_history'")[0][0],0)
    def test_two_bounded_batches_resume_next_run_without_restarting_pages(self):
        with self.serving() as host:
            c=Source([9],pages=60);report,_=quiet_run(c,host,1687524,now=NOW)
            self.assertEqual((report['pending'],report['queries'],report['added']),(1,57,1))
            inventory=host.inventory(auto.event_roster(Source([9]),1687524))
            self.assertEqual(inventory['checkpoint']['coverage']['9']['nextPage'],57)
            self.assertEqual(inventory['checkpoint']['pages'],[])
            c=Source([9],pages=60);report,_=quiet_run(c,host,1687524,now=NOW)
            self.assertEqual((report['pending'],report['queries'],report['added']),(0,5,0))
            self.assertEqual(host.inventory(auto.event_roster(Source([9]),1687524))['checkpoint']['coverage']['9']['nextPage'],61)
    def test_source_failure_does_not_queue_partial_capture(self):
        class Broken(Source):
            def query(self,q,v):
                if q!=auto.EVENT_ROSTER and v['page']==2:
                    self.calls+=1;raise auto.APIError('Invented upstream failure')
                return super().query(q,v)
        before=self.dump();protected=self.protected()
        with self.serving() as host,contextlib.redirect_stdout(io.StringIO()) as output:
            with self.assertRaises(auto.APIError):auto.run(Broken([9],pages=10),host,1687524,now=NOW)
        self.assertIn('"status": "failed"',output.getvalue());self.assertNotIn('upstream',output.getvalue())
        self.assertEqual(self.dump(),before);self.assertEqual(self.protected(),protected)
        self.assertEqual(sql(self.db,"SELECT COUNT(*) FROM sync_jobs WHERE kind='player_history'")[0][0],0)
    def test_expired_server_rejects_without_queue_or_graph_write(self):
        lib=self.site/'rival-sync-lib.php';lib.write_text(lib.read_text().replace('2099-10-26T06:00:00Z','2000-10-26T06:00:00Z'))
        before=self.dump()
        with self.serving() as host,contextlib.redirect_stdout(io.StringIO()):
            c=Source([9])
            with self.assertRaisesRegex(sender.SyncStopped,'analysis_authorization_expired'):auto.run(c,host,1687524,now=NOW)
        self.assertEqual(c.calls,1);self.assertEqual(self.dump(),before);self.assertEqual(sql(self.db,"SELECT COUNT(*) FROM sync_jobs WHERE kind='player_history'")[0][0],0)
    def test_unclarified_scope_rejects_without_history_queue_or_graph_write(self):
        lib=self.site/'rival-sync-lib.php';lib.write_text(lib.read_text().replace('RC_ENTITY_INSERTS_AUTHORIZED=true','RC_ENTITY_INSERTS_AUTHORIZED=false'))
        before=self.dump()
        with self.serving() as host,contextlib.redirect_stdout(io.StringIO()):
            c=Source([9])
            with self.assertRaisesRegex(sender.SyncStopped,'analysis_entity_authorization_required'):auto.run(c,host,1687524,now=NOW)
        self.assertEqual(c.calls,1);self.assertEqual(self.dump(),before);self.assertEqual(sql(self.db,"SELECT COUNT(*) FROM sync_jobs WHERE kind='player_history'")[0][0],0)
    def test_registrant_without_history_has_no_invented_sets(self):
        class NoHistory(Source):
            def query(self,q,v):
                result=super().query(q,v)
                if q!=auto.EVENT_ROSTER:result['player']['sets']=dict(pageInfo=dict(total=0,totalPages=0),nodes=[])
                return result
        before=sql(self.db,'SELECT COUNT(*) FROM sets')[0][0]
        with self.serving() as host:
            result,_=quiet_run(NoHistory([9]),host,1687524,now=NOW)
        self.assertEqual((result['added'],result['pending']),(1,0));self.assertEqual(sql(self.db,'SELECT COUNT(*) FROM sets')[0][0],before)
    def test_dense_bounded_batch_size_memory_and_existing_graph_unchanged(self):
        with self.serving() as host:
            client=DenseSource([9],pages=28);roster=auto.event_roster(client,1687524);initial=host.inventory(roster)
            began=time.monotonic();data,state=auto.capture_batch(client,auto.merge_state(roster,None,[]));data['audit']['seconds']=1
            state['pages']={};p=package(data);env=dict(operation='analysis_import',eventId=1687524,baseRevision=None,package=p,checkpoint=state)
            body=sender.encode_transport(env);raw=len(gzip.decompress(body));before=self.protected()
            self.assertEqual(data['audit']['requests'],28);self.assertEqual(len(p['content']['entities']['sets']),140)
            self.assertEqual(len(p['content']['entities']['games']),1400);self.assertLess(len(body),4*1024*1024);self.assertLess(raw,8*1024*1024)
            host.deliver(env);self.assertLess(self.last_peak,512*1024*1024);self.assertEqual(self.protected(),before)
            print(json.dumps(dict(syntheticBatch=dict(sets=140,games=1400,selections=2800,sourceQueries=28,compressedBytes=len(body),rawBytes=raw,workerPeakBytes=self.last_peak,seconds=round(time.monotonic()-began,3)))))
    def test_committed_batch_recovers_private_checkpoint_after_interrupted_worker(self):
        with self.serving() as host:
            roster=auto.event_roster(Source([9]),1687524);initial=host.inventory(roster)
            data,state=auto.capture_batch(Source([9]),auto.merge_state(roster,None,[]));data['audit']['seconds']=1
            p=package(data);state['pages']={}
            env=dict(operation='analysis_import',eventId=1687524,baseRevision=initial['revision'],package=p,checkpoint=state)
            body=sender.encode_transport(env);digest=hashlib.sha256(body).hexdigest();queued=host.call(env)
            dry=load(self.db,p);load(self.db,p,apply=True) # Simulated kill just after commit, before active checkpoint rename.
            candidate=self.private/'analysis-context'/f'1687524.json.{digest}.pending'
            candidate.write_text(canonical(dict(revision=digest,checkpoint=state,lastResult=dict(dry,status='imported'))))
            sql(self.db,"UPDATE sync_jobs SET status='running' WHERE deduplication_key=%s",(digest,))
            self.worker();saved=host.inventory(roster)
            self.assertEqual(saved['revision'],digest);self.assertEqual(saved['lastResult']['newRosterPlayers'],1);self.assertFalse(candidate.exists())
            self.assertEqual(sql(self.db,'SELECT COUNT(*) FROM analysis_context_batches')[0][0],1)
            c=Source([9]);result,_=quiet_run(c,host,1687524,now=NOW)
            self.assertEqual(result['status'],'already_imported');self.assertEqual(c.calls,1)
    def test_stale_checkpoint_or_rewind_is_rejected_before_queue_insert(self):
        with self.serving() as host:
            roster=auto.event_roster(Source([9]),1687524);initial=host.inventory(roster)
            data,state=auto.capture_batch(Source([9],pages=60),auto.merge_state(roster,None,[]));data['audit']['seconds']=1
            state['pages']={};p=package(data)
            env=dict(operation='analysis_import',eventId=1687524,baseRevision=initial['revision'],package=p,checkpoint=state)
            host.deliver(env)
            stale=copy.deepcopy(env);stale['package']['content']['audit']['seconds']=2;stale['package']['sha256']=digest(stale['package']['content'])
            with self.assertRaisesRegex(sender.SyncStopped,'analysis_checkpoint_conflict'):host.call(stale)
            saved=host.inventory(roster);stale['baseRevision']=saved['revision']
            with self.assertRaises(sender.SyncStopped):host.call(stale)
            self.assertEqual(sql(self.db,"SELECT COUNT(*) FROM sync_jobs WHERE kind='player_history'")[0][0],1)
    def test_python_php_identical_tables_and_rollback_on_failure(self):
        p=package(fixtures.sample()[0]);p['content']['audit']['seconds']=1;p['sha256']=digest(p['content']);before=self.protected()
        load(self.db,p,apply=True);expected=self.dump();self.assertEqual(self.protected(),before)
        self.clean();raw,public=national_fixture();import_package(self.db,build_package(raw,public),apply=True);before=self.protected()
        self.assertEqual(php('dry',p)['result']['status'],'validated_no_writes');self.assertEqual(php('apply',p)['result']['status'],'imported')
        self.assertEqual(self.dump(),expected);self.assertEqual(php('apply',p)['result']['status'],'already_imported');self.assertEqual(self.protected(),before)
        sql(self.db,'DELETE FROM analysis_context_players');sql(self.db,'DELETE FROM analysis_context_batches');sql(self.db,'DELETE FROM analysis_game_scores')
        # A late SQL exception after base-entity insertion must roll the entire new batch back.
        data,_=fixtures.sample();m=data['sets'].pop('7777');m['id']=8888;data['sets']['8888']=m
        for i,g in enumerate(m['games']):g['id']=88880+i
        p2=package(data);p2['content']['audit']['seconds']=1;p2['sha256']=digest(p2['content']);snapshot=self.dump()
        sql(self.db,"CREATE TRIGGER reject_analysis_score BEFORE INSERT ON analysis_game_scores FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='invented failure'")
        try:self.assertFalse(php('apply',p2)['ok']);self.assertEqual(self.dump(),snapshot)
        finally:sql(self.db,'DROP TRIGGER reject_analysis_score')

if __name__=='__main__':unittest.main(verbosity=2)
