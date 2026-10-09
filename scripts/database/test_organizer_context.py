"""Private small-event context: legacy hash preservation and Python/PHP/hosting parity."""
import copy
import json
import os
from pathlib import Path
import tempfile
import time
import unittest

from ranking_package import build_package, canonical, digest, validate_package
from organizer_context import extend_package, national_package
from import_ranking import import_package, sql
import test_import_ranking as fixtures
import test_hosting_sync as hosting
from test_tournament_catalog import catalog, package as catalog_package

MIGRATION=fixtures.ROOT/'docs/smash/migrations/006_organizer_event_context.sql'
FIRST='2026-10-04T11:43:18.348499+00:00'
SECOND='2026-10-11T06:00:00+00:00'


def captures(at=FIRST):
    raw,public=fixtures.fixture(at)
    raw['season']=dict(startInclusive=1767247200,endExclusive=1798783200)
    raw['tournamentCatalog']=catalog()
    people=copy.deepcopy(raw['players'])
    people['3']=dict(id=3,gamerTag='Tercero',user=dict(slug='user/test3',location=dict(country='Guatemala')))
    event=dict(id=200,name='Pequeño',slug='tournament/small/event/singles',type=1,state='COMPLETED',isOnline=False,
        numEntrants=3,startAt=1768000000,videogame=dict(id=1386),placements={'1':1,'2':2,'3':3},setsFetched=2,
        tournament=dict(id=20,name='Torneo chico',slug='tournament/small',countryCode='GT'))
    sets={}
    for sid,loser in ((700,2),(701,3)):
        sets[str(sid)]=dict(id=sid,state=3,winnerId=2001,displayScore=f'Jugador Á1 2 - Rival {loser} 0',
            completedAt=1768003600,updatedAt=1768003600,event=event,tournament=event['tournament'],
            slots=[dict(entrant=dict(id=2000+pid,participants=[dict(player=people[str(pid)])])) for pid in (1,loser)])
    context=dict(schemaVersion=1,kind='organizer_small_context',complete=True,nationalGeneratedAt=at,
        season=raw['season'],capturedAt=at,events=[event],players=people,sets=sets)
    return raw,public,context


def package(at=FIRST):
    raw,public,context=captures(at)
    return extend_package(build_package(raw,public),raw,context)


class OrganizerContracts(unittest.TestCase):
    def php(self,p):
        if not hosting.PHP:self.skipTest('PHP required')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'package.json';path.write_text(canonical(p));return hosting.bridge('validate',path)

    def test_national_package_hash_public_mains_and_legacy_versions_are_identical(self):
        raw,public,context=captures();original=copy.deepcopy((raw,public,context))
        base=build_package(raw,public);expanded=extend_package(base,raw,context)
        self.assertEqual((raw,public,context),original)
        self.assertEqual(national_package(expanded),base)
        self.assertEqual(digest(expanded['content']['public']),digest(public))
        self.assertNotEqual(expanded['sha256'],base['sha256'])
        self.assertEqual(self.php(expanded)['result']['sha256'],base['sha256'])
        for p in (fixtures.legacy_package(build_package(*fixtures.fixture())),build_package(*fixtures.fixture()),catalog_package()):
            before=canonical(p);validate_package(p);self.assertEqual(before,canonical(p))
            self.assertEqual(self.php(p)['result']['sha256'],p['sha256'])
        self.assertEqual(catalog_package()['sha256'],'3fde2db72ce6c9382d9d378466d9a9be4e181af0dd4854c46703ff2471e2df0e')
        self.assertEqual(build_package(*fixtures.fixture())['sha256'],'83d408314770e33bb7906bad9a71b1094fd9b69a970209025cbb4f10f2b922a7')
        self.assertEqual(fixtures.legacy_package(build_package(*fixtures.fixture()))['sha256'],'fe6396196b208f0e2bd01e0af72336b9a6566ead6761749f0637ec8bd6f029d2')

    def test_rehashed_invalid_extensions_rejected_in_both_languages(self):
        for kind in ('national_hash','national_version','boolean_version','duplicate','online','unfinished','doubles','large','active','country','slot','event','winner','timestamp','future','stray','duplicate_link'):
            p=package();c=p['content'];x=c['organizerContext'];t=x['entities']
            if kind=='national_hash':c['nationalSha256']='0'*64
            if kind=='national_version':c['nationalPackageVersion']=5
            if kind=='boolean_version':c['nationalPackageVersion']=True
            if kind=='duplicate':t['events'].append(copy.deepcopy(t['events'][0]))
            if kind=='online':x['eligibility'][0]['is_online']=True
            if kind=='unfinished':x['eligibility'][0]['state']='ACTIVE'
            if kind=='doubles':x['eligibility'][0]['entrant_size']=2
            if kind=='large':t['events'][0]['registered_entrants']=20
            if kind=='active':t['events'][0]['active_players']=20
            if kind=='country':t['tournaments'][0]['country_code']='MX'
            if kind=='slot':t['set_slots'][0]['event_id']=100
            if kind=='event':t['events'][0]['id']=100
            if kind=='winner':t['sets'][0]['winner_entrant_id']=999
            if kind=='timestamp':t['sets'][0]['synced_at']='2026-01-01 00:00:00.000000'
            if kind=='future':t['events'][0]['starts_at']='2027-01-01 00:00:00.000000'
            if kind=='stray':t['players'].append(dict(t['players'][0],id=99))
            if kind=='duplicate_link':t['entrant_players'].append(copy.deepcopy(t['entrant_players'][0]))
            p['sha256']=digest(c)
            with self.subTest(kind=kind):
                with self.assertRaises((ValueError,KeyError,TypeError)):validate_package(p)
                self.assertFalse(self.php(p)['ok'])

    def test_optional_invalid_or_missing_capture_exports_exact_base_package(self):
        import subprocess,sys
        raw,public,context=captures();base=build_package(raw,public)
        for kind in ('missing','bad_json','null','list','malformed_event','stale','online','unfinished','empty'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as folder:
                root=Path(folder)
                (root/'raw.json').write_text(canonical(raw));(root/'public.json').write_text(canonical(public))
                bad=copy.deepcopy(context)
                if kind=='null':bad=None
                if kind=='list':bad=[]
                if kind=='malformed_event':bad['events']=[None]
                if kind=='stale':bad['nationalGeneratedAt']='2026-10-01T00:00:00Z'
                if kind=='online':bad['events'][0]['isOnline']=True
                if kind=='unfinished':bad['events'][0]['state']='ACTIVE'
                if kind=='empty':bad['events']=[];bad['sets']={};bad['players']={}
                if kind!='missing':(root/'context.json').write_text('bad' if kind=='bad_json' else canonical(bad))
                run=subprocess.run([sys.executable,str(fixtures.ROOT/'scripts/database/ranking_package.py'),str(root/'raw.json'),str(root/'public.json'),str(root/'package.json'),'--organizer-context',str(root/'context.json')],capture_output=True,text=True)
                self.assertEqual(run.returncode,0,run.stderr)
                self.assertEqual((root/'package.json').read_text(),canonical(base))


@unittest.skipUnless(hosting.PHP and os.environ.get('SMASH_SCHEMA_TEST_DB'),'Disposable SQL required')
class OrganizerSQL(unittest.TestCase):
    @classmethod
    def install(cls):
        with cls.db.cursor() as q:
            q.execute(MIGRATION.read_text())
            while q.nextset():pass
    @classmethod
    def setUpClass(cls):
        fixtures.ImportTests.setUpClass.__func__(cls);cls.install()
    @classmethod
    def tearDownClass(cls):cls.db.close()
    clear_core=hosting.HostingSQLTests.clear
    snapshot=hosting.HostingSQLTests.snapshot
    run_package=hosting.HostingSQLTests.run_package
    queue=hosting.HostingSQLTests.queue
    def clear(self):
        self.db.rollback();sql(self.db,'DROP TRIGGER IF EXISTS small_fail_test');self.install();self.clear_core()
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.folder=Path(self.temp.name).resolve();self.path=self.folder/'package.json';self.clear()
    def tearDown(self):self.clear()
    def apply(self,who,p,apply=True):
        if who=='python':return import_package(self.db,p,apply=apply)
        report=self.run_package(p,'apply' if apply else 'dry');self.assertTrue(report['ok'],report);return report['result']
    def markers(self):return sql(self.db,'SELECT * FROM organizer_event_context ORDER BY event_id')
    def national(self):
        snap=self.snapshot(compare_importers=True)
        return {t:snap[t] for t in ('cuts','cut_events','cut_set_results','rankings','player_characters')}
    def test_python_php_table_parity_national_unchanged_repeat_and_refresh(self):
        snapshots=[]
        for who in ('python','php'):
            self.clear();base=national_package(package());self.apply(who,base);original=self.national()
            self.clear();p=package();dry=self.apply(who,p,False);self.assertEqual(dry['organizer']['status'],'ready');self.assertEqual(self.markers(),())
            report=self.apply(who,p);self.assertEqual(report['organizer']['status'],'imported');self.assertEqual(original,self.national())
            self.assertEqual(sql(self.db,'SELECT source_hash FROM cuts')[0][0],base['sha256'])
            self.assertEqual(sql(self.db,'SELECT event_id FROM cut_events WHERE event_id=200'),())
            before=(self.snapshot(),self.markers());self.assertEqual(self.apply(who,p)['status'],'already_imported');self.assertEqual(before,(self.snapshot(),self.markers()))
            # Old legacy transport for the same national core still sees already_imported.
            self.assertEqual(self.apply(who,base)['status'],'already_imported')
            raw,public,small=captures(SECOND);small['sets']['700']['winnerId']=2002;small['sets']['700']['displayScore']='Rival 2 2 - Jugador Á1 0'
            corrected=extend_package(build_package(raw,public),raw,small)
            self.assertEqual(self.apply(who,corrected)['organizer']['status'],'imported')
            self.assertEqual(sql(self.db,'SELECT winner_entrant_id,display_score FROM sets WHERE id=700')[0],(2002,'Rival 2 2 - Jugador Á1 0'))
            self.assertEqual(original['cuts'][0],self.national()['cuts'][0])
            snapshots.append((self.snapshot(compare_importers=True),self.markers()))
        self.assertEqual(*snapshots)
    def test_missing_or_broken_migration_and_context_error_do_not_block_national(self):
        for who in ('python','php'):
            for kind in ('missing','broken','write','parity','global_parity'):
                with self.subTest(who=who,kind=kind):
                    self.clear()
                    if kind in ('missing','broken'):sql(self.db,'DROP TABLE organizer_event_context')
                    if kind=='missing':sql(self.db,"DELETE FROM schema_migrations WHERE version='006_organizer_event_context'")
                    if kind=='write':sql(self.db,"CREATE TRIGGER small_fail_test BEFORE INSERT ON sets FOR EACH ROW BEGIN IF NEW.event_id=200 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='test'; END IF; END")
                    if kind=='parity':sql(self.db,"CREATE TRIGGER small_fail_test BEFORE INSERT ON set_slots FOR EACH ROW SET NEW.score=IF(NEW.event_id=200,7,NEW.score)")
                    if kind=='global_parity':sql(self.db,"CREATE TRIGGER small_fail_test BEFORE INSERT ON players FOR EACH ROW SET NEW.tag=IF(NEW.id=3,'corrupted',NEW.tag)")
                    p=package();report=self.apply(who,p)
                    self.assertEqual(report['status'],'imported');self.assertEqual(report['organizer']['status'],{'missing':'migration_missing','broken':'schema_unavailable','write':'skipped_context_error','parity':'skipped_context_error','global_parity':'skipped_context_error'}[kind])
                    self.assertEqual(sql(self.db,'SELECT id FROM events WHERE id=200'),())
                    self.assertEqual(sql(self.db,'SELECT source_hash FROM cuts')[0][0],national_package(p)['sha256'])
                    self.assertEqual(self.apply(who,p)['status'],'already_imported')
                    self.install();self.assertEqual(self.apply(who,p)['status'],'already_imported');self.assertEqual(self.markers(),())
    def test_real_receiver_deduplicates_v4_and_worker_imports_national_hash(self):
        import shutil,socket,subprocess,urllib.request,secrets
        import publish_sql as sender
        site=self.folder/'site';private=self.folder/'private-smash';site.mkdir();private.mkdir();(site/'data').mkdir()
        for name in ('database.php','ranking-import.php','ranking-sync-lib.php','ranking-sync.php','characters.js'):
            shutil.copy(fixtures.ROOT/'ranking-smash-ultimate'/name,site)
        key='1'*64
        (private/'sync.local.php').write_text("<?php return ['enabled'=>true,'key'=>'"+key+"'];")
        config=dict(database=dict(host='127.0.0.1',port=int(os.environ.get('SMASH_SCHEMA_TEST_PORT',3306)),name=os.environ['SMASH_SCHEMA_TEST_DB'],user='root',password=os.environ['SMASH_SCHEMA_TEST_PASSWORD']))
        (private/'config.local.php').write_text("<?php return json_decode('"+json.dumps(config)+"',true);")
        p=package();(site/'data/public.json').write_text(canonical(p['content']['public']))
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        process=subprocess.Popen([hosting.PHP,'-S',f'127.0.0.1:{port}','-t',str(site)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            for _ in range(100):
                try:
                    with socket.create_connection(('127.0.0.1',port),timeout=.1):break
                except OSError:time.sleep(.02)
            body=sender.transport(p)
            def send():
                at=str(int(time.time()));nonce=secrets.token_hex(16)
                headers={'Content-Type':'application/gzip','X-Smash-Timestamp':at,'X-Smash-Nonce':nonce,'X-Smash-Signature':sender.signature(key,at,nonce,body)}
                with urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:{port}/ranking-sync.php',data=body,headers=headers),timeout=5) as response:return json.loads(response.read())
            first=send();self.assertEqual(first['status'],'queued');self.assertEqual(send()['jobId'],first['jobId'])
            result=hosting.bridge('worker',site,private);self.assertTrue(result['ok'],result);self.assertEqual(result['result']['organizer']['status'],'imported')
            self.assertEqual(send()['status'],'succeeded');self.assertEqual(sql(self.db,'SELECT source_hash FROM cuts')[0][0],national_package(p)['sha256'])
        finally:process.terminate();process.wait(timeout=5)

    def test_large_v4_context_worker_memory_and_transport_limits(self):
        import publish_sql as sender
        def large(raw):
            template=raw['sets']['500']['games'][0]
            raw['sets']['500']['games']=[dict(template,id=10000+i) for i in range(5000)]
        raw,public=fixtures.fixture(mutate=large)
        _,_,context=captures();raw['season']=context['season'];raw['tournamentCatalog']=catalog()
        p=extend_package(build_package(raw,public),raw,context)
        data=self.folder/'data';data.mkdir();(data/'public.json').write_text(canonical(public));self.queue(p)
        start=time.monotonic();out=hosting.bridge('worker',self.folder,self.folder)
        self.assertTrue(out['ok'],out);self.assertEqual(out['result']['organizer']['status'],'imported')
        self.assertLess(out['result']['peakMemoryBytes'],512*1024*1024)
        print(json.dumps(dict(test='synthetic_large_v4_worker',games=5000,bytes=len(canonical(p).encode()),gzipBytes=len(sender.transport(p)),peakMemoryBytes=out['result']['peakMemoryBytes'],seconds=round(time.monotonic()-start,3))))

    def test_worker_v4_uses_live_national_public_and_preserves_transport_limits(self):
        import publish_sql as sender
        for installed in (True,False):
            with self.subTest(installed=installed):
                self.clear()
                if not installed:
                    sql(self.db,'DROP TABLE organizer_event_context');sql(self.db,"DELETE FROM schema_migrations WHERE version='006_organizer_event_context'")
                p=package();data=self.folder/'data';data.mkdir(exist_ok=True);(data/'public.json').write_text(canonical(p['content']['public']))
                size=len(canonical(p).encode());compressed=len(sender.transport(p));self.queue(p)
                started=time.monotonic();out=hosting.bridge('worker',self.folder,self.folder)
                self.assertTrue(out['ok'],out);r=out['result'];self.assertEqual(r['status'],'imported');self.assertEqual(r['organizer']['status'],'imported' if installed else 'migration_missing')
                self.assertLess(size,32*1024*1024);self.assertLess(compressed,4*1024*1024);self.assertLess(r['peakMemoryBytes'],512*1024*1024)
                self.assertEqual(sql(self.db,'SELECT status FROM sync_jobs'),(('succeeded',),))
                print(json.dumps(dict(test='organizer_v4_worker',schemaInstalled=installed,bytes=size,gzipBytes=compressed,peakMemoryBytes=r['peakMemoryBytes'],seconds=round(time.monotonic()-started,3))))

if __name__=='__main__':unittest.main(verbosity=2)
