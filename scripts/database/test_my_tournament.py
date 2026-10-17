"""Invented pools only; no production credentials, network capture or writes."""
import copy,gzip,json,os,subprocess,tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone
from unittest import mock
import my_tournament_sync as sync
import test_accounts_http as account_tests
ROOT=Path(__file__).resolve().parents[2];SITE=ROOT/'ranking-smash-ultimate'
NOW=1792274400


def sample():
    entrants=[dict(id=str(100+i),playerId=str(pid),tag=tag,initialSeed=i) for i,(pid,tag) in enumerate([(184005,'Yo'),(8999002,'Rival fuerte'),(8999003,'Rival seed'),(8999004,'Otro rival'),(8999005,'PRIVADO OTRO POOL')],1)]
    def slot(i,en=None,seed=None,prior=None):return dict(index=i,entrantId=en,seedId=seed,prereqId=prior,prereqType='set' if prior else None,prereqPlacement=1 if prior else None)
    group=dict(id='301',phaseId='201',phaseName='Pools',phaseOrder=1,identifier='B4',state=1,bracketType='DOUBLE_ELIMINATION',startAt=None,timeSource=None,dataAvailable=True,setsAvailable=True,
        seeds=[dict(id=str(400+i),entrantId=str(100+i),seed=i,groupSeed=i,isBye=False) for i in range(1,5)],
        sets=[dict(id='preview_1',round=1,roundText='Winners Round 1',startAt=None,state=1,winnerId=None,slots=[slot(0,'101','401'),slot(1,'104','404')]),dict(id='preview_2',round=1,roundText='Winners Round 1',startAt=None,state=1,winnerId=None,slots=[slot(0,'102','402'),slot(1,'103','403')]),dict(id='preview_3',round=2,roundText='Winners Final',startAt=None,state=1,winnerId=None,slots=[slot(0,prior='preview_1'),slot(1,prior='preview_2')])])
    other=copy.deepcopy(group);other.update(id='302',identifier='C7',seeds=[dict(id='405',entrantId='105',seed=5,groupSeed=1,isBye=False)],sets=[])
    return dict(schemaVersion=1,kind='my_tournament_bracket',capturedAt=datetime.fromtimestamp(NOW,timezone.utc).isoformat(),event=dict(id='1687524',tournamentId='942547',name='ULTIMATE Singles',tournamentName='LEGENDS7',slug='tournament/legends7/event/ultimate-singles',country='SV',startAt=1792857600,endAt=1792987200,timezone='America/El_Salvador'),registrationState='published',entrants=entrants,groups=[group,other],audit=dict(requests=2,batches=1,elapsedMilliseconds=1000))


def bridge(value):
    code="require 'ranking-smash-ultimate/mi-torneo.php';$v=json_decode(stream_get_contents(STDIN),true);try{if($v['mode']==='validate'){mt_validate($v['p']);$r=['valid'=>true];}elseif($v['mode']==='response'){$r=mt_response($v['p'],$v['player'],$v['public'],"+str(NOW)+");}else{$r=mt_receive($v['site'],base64_decode($v['body']),"+str(NOW)+");}echo json_encode(['ok'=>true,'result'=>$r]);}catch(Throwable $e){echo json_encode(['ok'=>false]);}"
    run=subprocess.run(['php','-d','memory_limit=512M','-r',code],input=json.dumps(value),capture_output=True,text=True,cwd=ROOT,timeout=15)
    if run.stderr:raise AssertionError(run.stderr)
    return json.loads(run.stdout)


class Source:
    def __init__(self,hidden=False,fail=False):self.calls=0;self.hidden=hidden;self.fail=fail
    def query(self,q,v):
        self.calls+=1;p=sample();groups=p['groups']
        def connection(rows):return dict(nodes=rows,pageInfo=dict(total=len(rows),totalPages=1 if rows else 0))
        if q==sync.META:
            e=dict(id=1687524,name='ULTIMATE Singles',slug=p['event']['slug'],startAt=1792857600,type=1,isOnline=False,videogame=dict(id=1386),tournament=dict(id=942547,name='LEGENDS7',countryCode='SV',startAt=1792854000,endAt=1792987200,timezone='America/El_Salvador'),phases=[])
            e['entrants']=None if self.hidden else connection([dict(id=x['id'],name=x['tag'],initialSeedNum=x['initialSeed'],participants=[dict(player=dict(id=x['playerId'],gamerTag=x['tag']))]) for x in p['entrants']])
            e['phaseGroups']=[dict(id=g['id'],displayIdentifier=g['identifier'],phase=dict(id=g['phaseId'],name=g['phaseName'],phaseOrder=1),state=1,bracketType='DOUBLE_ELIMINATION',startAt=None,firstRoundTime=None,wave=None) for g in groups]
            return dict(event=e)
        if self.fail:raise sync.APIError('NEVER PRINT PERSON OR TOKEN')
        out={}
        for i in range(3):
            if 'id'+str(i) not in v:continue
            g=next(g for g in groups if g['id']==v['id'+str(i)])
            out['g'+str(i)]=dict(id=g['id'],seeds=connection([dict(id=s['id'],seedNum=s['seed'],groupSeedNum=s['groupSeed'],isBye=s['isBye'],entrant=dict(id=s['entrantId'])) for s in g['seeds']]),sets=connection([dict(id=s['id'],round=s['round'],fullRoundText=s['roundText'],startAt=s['startAt'],state=s['state'],winnerId=None,slots=[dict(entrant=dict(id=x['entrantId']) if x['entrantId'] else None,seed=dict(id=x['seedId']) if x['seedId'] else None,prereqId=x['prereqId'],prereqType=x['prereqType'],prereqPlacement=x['prereqPlacement']) for x in s['slots']]) for s in g['sets']]))
        return out


class Contracts(unittest.TestCase):
    def test_capture_actual_schema_list_groups_and_bounded_hidden_roster(self):
        from graphql import parse
        parse(sync.META);parse(sync.ROSTER)
        c=Source();p=sync.capture(c,1687524);self.assertEqual((c.calls,len(p['groups'])),(2,2));self.assertTrue(bridge(dict(mode='validate',p=p))['ok'])
        c=Source(hidden=True);p=sync.capture(c,1687524);self.assertEqual(c.calls,1);self.assertEqual(p['registrationState'],'unavailable');self.assertEqual(p['groups'],[])
        with self.assertRaises(sync.APIError):sync.capture(Source(fail=True),1687524)
    def test_independent_pagination_ignores_exhausted_connection_without_losing_rows(self):
        class Pages(Source):
            def query(self,q,v):
                d=super().query(q,v)
                if q==sync.META:return d
                for i in range(3):
                    k='g'+str(i)
                    if k not in d or v['id'+str(i)]!='301':continue
                    if v['page'+str(i)]==1:
                        d[k]['sets']['pageInfo']=dict(total=3,totalPages=2)
                        d[k]['sets']['nodes']=d[k]['sets']['nodes'][:2]
                    else:
                        d[k]['seeds']=dict(pageInfo=dict(total=0,totalPages=0),nodes=[])
                        d[k]['sets']['pageInfo']=dict(total=3,totalPages=2)
                        d[k]['sets']['nodes']=d[k]['sets']['nodes'][2:]
                return d
        p=sync.capture(Pages(),1687524);self.assertEqual((len(p['groups'][0]['seeds']),len(p['groups'][0]['sets'])),(4,3))
    def test_signed_receiver_stores_private_file_without_database_configuration(self):
        import socket,shutil,time,urllib.request,urllib.error
        from publish_sql import signature
        with tempfile.TemporaryDirectory() as d:
            home=Path(d);site=home/'site';site.mkdir();private=home/'private-smash';private.mkdir()
            for name in ('database.php','ranking-import.php','rival-import.php','rival-sync-lib.php','ranking-sync-lib.php','ranking-sync.php','bracket-store.php','characters.js'):shutil.copyfile(SITE/name,site/name)
            (private/'sync.local.php').write_text("<?php return ['enabled'=>true,'key'=>'"+'1'*64+"'];")
            # Future-proof ONLY the disposable fixture: production deadlines remain fixed.
            f=site/'bracket-store.php';f.write_text(f.read_text().replace('const MT_END=1792987200','const MT_END=4102444800').replace('^2026-',r'^\d{4}-'))
            with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            server=subprocess.Popen(['php','-d','display_errors=0','-S',f'127.0.0.1:{port}','-t',str(site)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            try:
                url=f'http://127.0.0.1:{port}/ranking-sync.php'
                for _ in range(60):
                    try:urllib.request.urlopen(url,timeout=.2)
                    except urllib.error.HTTPError:break
                    except OSError:time.sleep(.05)
                p=sample();p['capturedAt']=datetime.now(timezone.utc).isoformat();body=gzip.compress(json.dumps(p).encode());stamp=str(int(time.time()))
                def send(nonce,signed=True):
                    headers={'Content-Type':'application/vnd.smash.bracket+gzip','X-Smash-Timestamp':stamp,'X-Smash-Nonce':nonce,'X-Smash-Signature':signature('1'*64,stamp,nonce,body) if signed else '0'*64}
                    try:r=urllib.request.urlopen(urllib.request.Request(url,data=body,headers=headers),timeout=10)
                    except urllib.error.HTTPError as error:r=error
                    return r.status,json.loads(r.read())
                self.assertEqual(send('a'*32,False)[0],401)
                self.assertEqual(send('b'*32)[1]['status'],'stored');path=private/'brackets/1687524.json';before=path.read_bytes()
                self.assertEqual(send('c'*32)[1]['status'],'already_stored');self.assertEqual(send('b'*32)[0],409);self.assertEqual(path.read_bytes(),before)
                self.assertFalse((private/'config.local.php').exists());self.assertFalse((site/'data/public.json').exists())
            finally:server.terminate();server.wait(timeout=5)
    def test_workflow_limited_main_flag_and_no_public_or_sql_transport(self):
        text=(ROOT/'.github/workflows/smash-my-tournament.yml').read_text()
        for expected in ('19,49 * * * *','SMASH_MY_TOURNAMENT_ENABLED','SMASH_MY_TOURNAMENT_EVENT_ID','refs/heads/main','smash-gt-publication'):self.assertIn(expected,text)
        for forbidden in ('secrets.FTP','MYSQL','upload-artifact','actions/cache'):self.assertNotIn(forbidden,text)
        for f in ('bracket-store.php','mi-torneo.php'):
            text=(SITE/f).read_text()
            for forbidden in ('curl_','UPDATE ','INSERT ','DELETE ','start.gg/gql'):self.assertNotIn(forbidden,text)

    def test_two_validators_reject_foreign_relations_and_unknown_fields(self):
        for mutation in (lambda p:p.update(secret='private'),lambda p:p['groups'][0]['sets'][0]['slots'][1].update(entrantId='105'),lambda p:p['groups'][0]['seeds'][0].update(seed=-1),lambda p:p['groups'][0]['sets'][0]['slots'][0].update(seedId='405'),lambda p:p['audit'].update(requests=61)):
            p=sample();mutation(p)
            with self.assertRaises(ValueError):sync.validate(p)
            self.assertFalse(bridge(dict(mode='validate',p=p))['ok'])
    def test_own_pool_only_first_opponent_path_and_strongest(self):
        p=sample();r=bridge(dict(mode='response',p=p,player='184005',public=dict(players=[dict(id='8999003',rank=3),dict(id='8999002',rank=10)])))['result']
        self.assertEqual(r['status'],'ready');self.assertEqual(len(r['pools']),1);g=r['pools'][0];self.assertEqual(g['group'],'B4');self.assertEqual(g['firstSet']['opponent']['tag'],'Otro rival');self.assertEqual(g['probablePath'][0]['opponent']['tag'],'Rival fuerte');self.assertEqual(g['strongest']['tag'],'Rival seed');self.assertEqual(g['strongestBasis'],'rank');self.assertIsNone(g['start']['timestamp']);self.assertNotIn('PRIVADO',json.dumps(r))
        r=bridge(dict(mode='response',p=p,player='184005',public={}))['result'];self.assertEqual(r['pools'][0]['strongest']['tag'],'Rival fuerte');self.assertEqual(r['pools'][0]['strongestBasis'],'seed')
    def test_pool_time_fallback_bye_and_confirmed_versus_predicted_first_opponent(self):
        p=sample();g=p['groups'][0];g.update(startAt=1792857600,timeSource='wave')
        r=bridge(dict(mode='response',p=p,player='184005',public={}))['result']['pools'][0]
        self.assertEqual(r['firstSet']['time']['source'],'wave');self.assertEqual(r['firstSet']['time']['guatemala'],'24/10/2026 10:00');self.assertEqual(r['firstSet']['time']['local'],'24/10/2026 10:00');self.assertTrue(r['firstSet']['opponentConfirmed'])
        # Verified bye advances the player; an unfilled slot alone never does.
        g['seeds'].append(dict(id='406',entrantId=None,seed=None,groupSeed=None,isBye=True));g['sets'][0]['slots'][1].update(entrantId=None,seedId='406')
        r=bridge(dict(mode='response',p=p,player='184005',public={}))['result']['pools'][0]
        self.assertEqual(r['firstSet']['id'],'preview_3');self.assertFalse(r['firstSet']['opponentConfirmed']);self.assertEqual(r['firstSet']['opponent']['tag'],'Rival fuerte')
        g['seeds'][-1]['isBye']=False
        r=bridge(dict(mode='response',p=p,player='184005',public={}))['result']['pools'][0]
        self.assertEqual(r['firstSet']['id'],'preview_1');self.assertIsNone(r['firstSet']['opponent'])
    def test_cycles_and_missing_seeds_do_not_invent_a_path_or_hang(self):
        p=sample();g=p['groups'][0];g['sets'][1]['slots'][0].update(entrantId=None,seedId=None,prereqId='preview_3',prereqType='set',prereqPlacement=1)
        r=bridge(dict(mode='response',p=p,player='184005',public={}))['result'];self.assertEqual(r['status'],'ready')
        for s in g['seeds']:s['seed']=None
        for en in p['entrants']:en['initialSeed']=None
        r=bridge(dict(mode='response',p=p,player='184005',public={}))['result']['pools'][0];self.assertIsNone(r['strongest']);self.assertIsNone(r['probablePath'][0]['opponent'])

    def test_unknown_registration_unassigned_and_null_times(self):
        for player,status in ((None,'not_registered'),('999','not_registered')):self.assertEqual(bridge(dict(mode='response',p=sample(),player=player,public={}))['result']['status'],status)
        p=sample();p['groups']=[];self.assertEqual(bridge(dict(mode='response',p=p,player='184005',public={}))['result']['status'],'pools_unpublished')
        p.update(registrationState='unavailable',entrants=[]);self.assertEqual(bridge(dict(mode='response',p=p,player='184005',public={}))['result']['status'],'registrations_unavailable')
    def test_atomic_repeat_stale_rejection_and_previous_snapshot_survives(self):
        import base64
        with tempfile.TemporaryDirectory() as d:
            home=Path(d);(home/'site').mkdir();(home/'private-smash').mkdir();p=sample()
            def deliver(p):return bridge(dict(mode='store',p=None,site=str(home/'site'),body=base64.b64encode(gzip.compress(json.dumps(p).encode())).decode()))
            self.assertEqual(deliver(p)['result']['status'],'stored');path=home/'private-smash/brackets/1687524.json';before=path.read_bytes();self.assertEqual(deliver(p)['result']['status'],'already_stored');self.assertEqual(path.read_bytes(),before)
            p['capturedAt']=datetime.fromtimestamp(NOW-10,timezone.utc).isoformat();self.assertFalse(deliver(p)['ok']);self.assertEqual(path.read_bytes(),before)
            p=sample();p['entrants'][0]['playerId']='bad';self.assertFalse(deliver(p)['ok']);self.assertEqual(path.read_bytes(),before)
    def test_schedule_hard_deadline_and_budget(self):
        self.assertEqual(sync.schedule(1687524,1792987200,True),'ended');self.assertEqual(sync.schedule(1687524,1792994400,True),'ended')
        self.assertEqual(sync.schedule(1687524,datetime(2026,10,23,9,19,tzinfo=timezone.utc).timestamp(),False),'due')
        self.assertEqual(sync.schedule(1687524,datetime(2026,10,23,9,49,tzinfo=timezone.utc).timestamp(),False),'not_due')
        self.assertEqual(sync.schedule(1687524,1792857600,False),'due')
        c=Source();b=sync.Budget(c)
        # Direct harmless metadata queries to exercise hard cap, not actual network.
        for _ in range(56):b.query(sync.META,{})
        with self.assertRaises(ValueError):b.query(sync.META,{})
        self.assertEqual(c.calls,56)


@unittest.skipUnless(os.getenv('SMASH_SCHEMA_TEST_DB'),'Disposable SQL service required')
class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        account_tests.AccountHttpTests.setUpClass.__func__(cls)
        for f in ('bracket-store.php','mi-torneo.php','mi-torneo-api.php'):__import__('shutil').copyfile(SITE/f,cls.site/f)
        (cls.private/'brackets').mkdir();cls.path=cls.private/'brackets/1687524.json'
    @classmethod
    def tearDownClass(cls):account_tests.AccountHttpTests.tearDownClass.__func__(cls)
    def setUp(self):
        account_tests.AccountHttpTests.setUp(self);self.path.write_text(json.dumps(sample()))
    def request(self,path='/mi-torneo-api.php',**kw):return account_tests.AccountHttpTests.request(self,path,**kw)
    def test_anonymous_and_methods_get_no_pool(self):
        self.assertEqual(self.request()[0],401);self.assertEqual(self.request(method='POST')[0],405);self.assertNotIn('Pools',json.dumps(self.request()[2]))
    def test_live_session_free_account_owns_pool_and_cannot_choose_another(self):
        self.request('/fixture-login.php');status,headers,r=self.request();self.assertEqual(status,200);self.assertEqual(r['status'],'ready');self.assertEqual(r['pools'][0]['group'],'B4');self.assertNotIn('PRIVADO',json.dumps(r));self.assertIn('no-store',headers['Cache-Control']);self.assertIn('private',headers['Cache-Control'])
        for query in ('?playerId=8999005','?pool=302','?event=1687524'):self.assertEqual(self.request('/mi-torneo-api.php'+query)[0],400)
        raw=json.dumps(r)
        for field in ('startggId','email','oauth','session','payment','cookie','entrantId','seedId','prereqId'):self.assertNotIn('"'+field+'"',raw)
        # Change real DB linkage: API must not keep trusting an old session identity.
        with self.db.cursor() as q:q.execute('UPDATE users SET player_id=NULL WHERE startgg_user_id=8999101')
        self.assertEqual(self.request()[2]['status'],'not_registered')
        self.request('/fixture-login.php')
        with self.db.cursor() as q:q.execute('UPDATE oauth_connections SET revoked_at=UTC_TIMESTAMP() WHERE user_id=(SELECT id FROM users WHERE startgg_user_id=8999101)')
        self.assertEqual(self.request()[0],401)
    def test_missing_snapshot_is_honest_and_no_file_is_created(self):
        self.request('/fixture-login.php');self.path.unlink();self.assertEqual(self.request()[2]['status'],'snapshot_unavailable');self.assertFalse(self.path.exists())

if __name__=='__main__':unittest.main(verbosity=2)
