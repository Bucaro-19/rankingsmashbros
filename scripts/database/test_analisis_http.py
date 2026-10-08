"""Rival API contracts: synthetic data, disposable local MySQL/MariaDB, no provider traffic.

The login helper lives ONLY in a temporary site. Every SQL fixture write is local.
"""
import copy
from datetime import datetime, timezone
import http.cookiejar
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from test_import_ranking import fixture
from ranking_package import build_package
from import_ranking import import_package

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT/'ranking-smash-ultimate'
DATABASE = os.environ.get('SMASH_SCHEMA_TEST_DB', '')
PAID = {'h2h', 'streak', 'rivalForm', 'rivalTiers', 'meVsChar', 'himVsChar', 'gameMatrix', 'recommendations', 'probability', 'gameDataStatus'}


class AnalysisStaticTests(unittest.TestCase):
    def test_library_is_denied_and_published_before_endpoint(self):
        self.assertIn('<Files "analisis.php">', (SITE/'.htaccess').read_text())
        deploy = (ROOT/'scripts/smash/deploy.py').read_text()
        self.assertLess(deploy.index('"analisis.php"'), deploy.index('"analisis-api.php"'))
        text = (SITE/'analisis.php').read_text() + (SITE/'analisis-api.php').read_text()
        for forbidden in ('curl_', 'smash_premium_refresh(', 'file_get_contents("http', 'support.js'):
            self.assertNotIn(forbidden, text)
        self.assertIn('SET TRANSACTION READ ONLY', text)

    def test_score_matches_actual_account_model(self):
        sets = [dict(playerIds=['1','2'], score=x) for x in ('Juan 3 - Lukas 0', 'Alias 22 0 - Otro 3', '3 - Otro 2', 'W/O', 'Juan 2 - Otro 2', 'sin marcador', 'Juan 10 - Otro 1')]
        php = 'require '+json.dumps(str(SITE/'analisis.php'))+'; $sets=json_decode(stream_get_contents(STDIN),true); echo json_encode(array_map(static fn($s)=>[smash_analisis_score($s,"1"),smash_analisis_score($s,"2")],$sets));'
        actual = json.loads(subprocess.check_output(['php','-r',php], input=json.dumps(sets).encode()))
        js = "const model=require(process.argv[1]); const fs=require('node:fs'); const sets=JSON.parse(fs.readFileSync(0,'utf8')); console.log(JSON.stringify(sets.map(s=>['1','2'].map(id=>{const t=model.setScore(s,id).text;return t==='—'?[null,null]:t.split('–').map(Number)}))));"
        expected = json.loads(subprocess.check_output(['node','-e',js,str(SITE/'account-model.js')], input=json.dumps(sets).encode()))
        self.assertEqual(actual, expected)


@unittest.skipUnless(DATABASE, 'Requires local disposable database')
class AnalysisHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import pymysql
        from pymysql.constants import CLIENT
        if not DATABASE.startswith('smash_schema_test') or os.environ.get('SMASH_SCHEMA_TEST_HOST','127.0.0.1') not in ('127.0.0.1','localhost'):
            raise RuntimeError('Only local disposable database allowed')
        port = int(os.environ.get('SMASH_SCHEMA_TEST_PORT','3306'))
        cls.db = pymysql.connect(host='127.0.0.1',port=port,user='root',password=os.environ['SMASH_SCHEMA_TEST_PASSWORD'],database=DATABASE,charset='utf8mb4',autocommit=True,client_flag=CLIENT.MULTI_STATEMENTS)
        for file in [ROOT/'docs/smash/schema.sql',ROOT/'docs/smash/seed-characters.sql',*sorted((ROOT/'docs/smash/migrations').glob('*.sql'))]:
            with cls.db.cursor() as q:
                q.execute(file.read_text())
                while q.nextset(): pass
        cls.temp = tempfile.TemporaryDirectory(prefix='smash-analysis-http-')
        home = Path(cls.temp.name); cls.site=home/'site'; cls.private=home/'private-smash'; sessions=home/'sessions'
        for path in (cls.site/'data',cls.private,sessions): path.mkdir(parents=True)
        for name in ('database.php','accounts.php','stats.php','premium.php','analisis.php','analisis-api.php'):
            shutil.copyfile(SITE/name,cls.site/name)
        config = dict(database=dict(host='127.0.0.1',port=port,name=DATABASE,user='root',password=os.environ['SMASH_SCHEMA_TEST_PASSWORD']))
        (cls.private/'config.local.php').write_text('<?php return json_decode('+json.dumps(json.dumps(config))+',true);')
        (cls.private/'recurrente.local.php').write_text("<?php return ['enabled'=>true,'secret_key'=>'sk_test_"+'a'*40+"','webhook_secret'=>'whsec_a2tra2tra2tra2tra2tra2tra2tra2tr'];")
        (cls.site/'fixture-login.php').write_text('''<?php
        require __DIR__.'/database.php'; require __DIR__.'/accounts.php';
        smash_account_session_start(); $db=smash_account_connect(__DIR__);
        $type=$_GET['type']??'free'; $types=['free'=>8999201,'paid'=>8999202,'admin'=>8999203,'unlinked'=>8999204];
        $id=smash_account_login($db,['startggId'=>(string)$types[$type],'playerId'=>$type==='unlinked'?null:'1','tag'=>'Yo QA','url'=>null],time());
        if ($type==='admin') $db->exec("INSERT IGNORE INTO user_roles(user_id,role) VALUES ($id,'admin')");
        $user=smash_account_user($db,$id);
        $_SESSION['smash_account']=['id'=>$id,'at'=>time(),'version'=>$user['connectionVersion'],'url'=>null,'avatarUrl'=>null];
        if (isset($_GET['remember'])) smash_account_remember_set(smash_account_remember_create($db,$_SESSION['smash_account'],time()),time());
        session_regenerate_id(true); echo 'ok';
        ''')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0)); cls.port=sock.getsockname()[1]
        cls.base=f'http://127.0.0.1:{cls.port}'; cls.log=home/'errors.log'
        cls.process=subprocess.Popen(['php','-d','memory_limit=512M','-d',f'session.save_path={sessions}','-d','log_errors=1','-d',f'error_log={cls.log}','-S',f'127.0.0.1:{cls.port}','-t',str(cls.site)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for _ in range(100):
            try: urllib.request.urlopen(cls.base+'/analisis-api.php',timeout=1).close(); break
            except urllib.error.HTTPError: break
            except OSError: time.sleep(.05)
        else: raise RuntimeError('PHP server failed')

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate(); cls.process.wait(timeout=10); cls.db.close(); cls.temp.cleanup()

    def sql(self, query, args=None):
        with self.db.cursor() as q: q.execute(query,args); return q.fetchall()

    def setUp(self):
        self.cookies=http.cookiejar.CookieJar(); self.client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))
        raw,self.public=fixture()
        self.cut=import_package(self.db,build_package(raw,self.public),apply=True)['cutId']
        # Baseline empty tables, even when the shared importer fixture carries game context.
        self.sql('DELETE FROM game_selections'); self.sql('DELETE FROM games')
        for v in (self.public,self.public['localRanking']):
            for p in v['players']:
                cid,name=('1302','Mario') if p['id']=='1' else ('1296','Link')
                p['mains']=[dict(characterId=cid,name=name,games=1)]
            v['players'][1]['rank']=101  # Additional API-only synthetic case: a real place outside the top 100.
        self.sql("INSERT INTO players(id,tag,country_code) VALUES (3,'Sin puesto','GT'),(4,'Sin actividad','MX')")
        self.publish(self.public)

    def tearDown(self):
        self.db.rollback()
        self.sql('DELETE FROM users WHERE startgg_user_id BETWEEN 8999201 AND 8999204')
        self.sql('UPDATE rankings SET previous_cut_id=NULL')
        for table in ('game_selections','games','player_characters','rankings','cut_set_results','cut_events','cuts','set_slots','sets','entrant_players','entrants','events','tournaments','players'):
            self.sql('DELETE FROM `'+table+'`')

    def publish(self, public):
        (self.site/'data/public.json').write_text(json.dumps(public,ensure_ascii=False))
        self.sql('UPDATE cuts SET public_snapshot=%s WHERE id=%s',(json.dumps(public,ensure_ascii=False),self.cut))

    def call(self, query='',method='GET',endpoint='analisis-api.php'):
        req=urllib.request.Request(self.base+'/'+endpoint+('?' + query if query else ''),method=method)
        try: answer=self.client.open(req,timeout=10)
        except urllib.error.HTTPError as error: answer=error
        text=answer.read().decode()
        return answer.status,answer.headers,json.loads(text) if endpoint=='analisis-api.php' else text

    def login(self, kind='free',remember=False):
        # Reuse player 1 for successive account-state fixtures without violating uq_users_player.
        external=dict(free=8999201,paid=8999202,admin=8999203,unlinked=8999204)[kind]
        self.sql('UPDATE users SET player_id=NULL WHERE startgg_user_id BETWEEN 8999201 AND 8999204 AND startgg_user_id<>%s',(external,))
        self.cookies.clear()
        self.assertEqual(self.call('type='+kind+('&remember=1' if remember else ''),endpoint='fixture-login.php')[0],200)
        uid=self.sql('SELECT id FROM users WHERE startgg_user_id=%s',(external,))[0][0]
        self.sql('INSERT IGNORE INTO user_characters(user_id,position,character_id) VALUES (%s,1,1302)',(uid,))
        return uid

    def premium(self, uid, end='2099-01-01 00:00:00', live=0, status='active'):
        self.sql('DELETE FROM premium_subscriptions WHERE user_id=%s',(uid,))
        self.sql("INSERT INTO premium_subscriptions(user_id,plan,live_mode,provider_checkout_id,status,current_period_end,created_at,updated_at) VALUES (%s,'monthly',%s,%s,%s,%s,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))",(uid,live,f'qa_analysis_{uid}',status,end))

    def games(self):
        # Two games for each 2-0 set, all real FK relationships, not a source/API call.
        for sid,winner in self.sql('SELECT id,winner_entrant_id FROM sets ORDER BY id'):
            entrants=[r[0] for r in self.sql('SELECT entrant_id FROM set_slots WHERE set_id=%s ORDER BY slot_index',(sid,))]
            for n in (1,2):
                gid=sid*10+n
                self.sql("INSERT INTO games(id,set_id,game_number,winner_entrant_id,synced_at) VALUES (%s,%s,%s,%s,'2026-10-04 11:43:18.348499')",(gid,sid,n,winner))
                for en,char in zip(entrants,(1302,1296)):
                    self.sql('INSERT INTO game_selections(game_id,set_id,entrant_id,character_id) VALUES (%s,%s,%s,%s)',(gid,sid,en,char))

    def assert_free(self, data):
        self.assertFalse(PAID.intersection(data))
        for key in ('me','rival'):
            self.assertFalse({'chosen','detected','coverage'}.intersection(data[key]))
        body=json.dumps(data)
        for private in ('sk_test_','whsec_','provider_checkout_id','user_id','connectionVersion','899920','qa_analysis_'):
            self.assertNotIn(private,body)

    def test_auth_methods_free_gate_and_forged_identity(self):
        status,headers,data=self.call('rival=2'); self.assertEqual(status,401); self.assertIn('no-store',headers['Cache-Control'])
        self.assertEqual(self.call('rival=2',method='POST')[0],405)
        self.login(); status,headers,data=self.call('rival=2')
        self.assertEqual(status,200); self.assertEqual(data['state'],'bloqueado'); self.assert_free(data)
        self.assertEqual(data['record'],dict(wins=2,losses=3,sets=5)); self.assertEqual(data['me']['playerId'],'1')
        for query in ('rival=1','rival=2&me=2','rival=2&active=true','rival=2&userId=1','rival[]=2','rival=2&buscar=Lu','rival=1%20OR%201=1','rival=2&scope[]=gt'):
            self.assertEqual(self.call(query)[0],400,query)
        self.assertEqual(self.call('rival=999')[0],404)

    def test_empty_games_premium_and_null_unobserved_fields(self):
        uid=self.login('paid'); self.premium(uid)
        status,_,data=self.call('rival=2'); self.assertEqual(status,200); self.assertEqual(data['state'],'listo')
        self.assertTrue(data['premium']['active']); self.assertEqual(data['gameDataStatus'],'empty')
        self.assertEqual(data['me']['chosen'],['mario']); self.assertEqual(data['me']['coverage']['registered'],1)
        self.assertEqual(data['me']['detected'][0]['games'],1); self.assertNotIn('share',data['me']['detected'][0])
        self.assertEqual(data['gameMatrix']['mario|link']['scene'],[0,0]); self.assertEqual(data['recommendations'],[])
        self.assertEqual(data['meVsChar'],{}); self.assertIsNone(data['streak'])
        self.assertEqual(len(data['rivalForm']),3)
        for item in data['rivalForm']: self.assertIsNone(item['placement']); self.assertIsNone(item['entrants'])
        self.assertTrue(all(x['myChar'] is None for x in data['h2h']))
        self.assertEqual(data['rivalTiers']['intl']['outsideTop100'],[3,2]); self.assertEqual(data['rivalTiers']['intl']['unranked'],[0,0])

    def test_expiry_mode_other_account_and_admin_revocation(self):
        uid=self.login('paid'); self.premium(uid,end='2026-01-01 00:00:00')
        data=self.call('rival=2')[2]; self.assertEqual(data['state'],'vencido'); self.assert_free(data)
        self.premium(uid,live=1); self.assert_free(self.call('rival=2')[2])
        self.premium(uid); self.login('free'); self.assert_free(self.call('rival=2')[2])
        admin=self.login('admin'); data=self.call('rival=2')[2]
        self.assertEqual(data['access'],dict(full=True,reason='admin')); self.assertFalse(data['premium']['active']); self.assertIn('h2h',data)
        self.sql("DELETE FROM user_roles WHERE user_id=%s AND role='admin'",(admin,)); self.assert_free(self.call('rival=2')[2])
        self.sql('UPDATE oauth_connections SET revoked_at=UTC_TIMESTAMP(6) WHERE user_id=%s',(admin,))
        self.assertEqual(self.call('rival=2')[0],401)

    def test_scope_game_matrix_scores_and_read_only_tables(self):
        self.login('admin'); self.games()
        before={t:self.sql('SELECT * FROM `'+t+'` ORDER BY 1') for t in ('games','game_selections','cuts','rankings','users','user_characters','premium_subscriptions')}
        intl=self.call('rival=2')[2]; gt=self.call('rival=2&scope=gt')[2]
        self.assertEqual(intl['gameDataStatus'],'available'); self.assertEqual(intl['gameMatrix']['mario|link']['me'],[4,6])
        self.assertEqual(intl['gameMatrix']['mario|link']['him'],[6,4]); self.assertEqual(intl['meVsChar'],{'link':[2,3]})
        self.assertEqual(intl['himVsChar'],{'mario':[3,2]}); self.assertEqual(intl['recommendations'][0]['confidence'],'media')
        self.assertEqual(gt['record'],dict(wins=2,losses=2,sets=4)); self.assertEqual(len(gt['h2h']),4)
        for key in ('gameMatrix','recommendations','meVsChar','himVsChar'): self.assertEqual(gt[key],intl[key])
        self.assertNotEqual(gt['probability']['p'],intl['probability']['p'])
        self.assertEqual(intl['h2h'][0]['myGames'],0); self.assertEqual(intl['h2h'][0]['theirGames'],2)
        self.assertEqual(intl['h2h'][0]['myChar'],'mario'); self.assertEqual(len(gt['rivalForm']),2)
        after={t:self.sql('SELECT * FROM `'+t+'` ORDER BY 1') for t in before}; self.assertEqual(before,after)
        # Games updated after character capture cannot silently enter this published cut.
        self.sql("UPDATE games SET synced_at='2026-10-05 00:00:00' WHERE set_id=500")
        data=self.call('rival=2')[2]; self.assertEqual(data['gameMatrix']['mario|link']['sceneGames'],8)
        self.assertEqual(data['meVsChar'],{'link':[1,3]})

    def test_no_rank_no_characters_no_h2h_and_unlinked(self):
        self.login('admin'); status,_,data=self.call('rival=4'); self.assertEqual(status,200)
        self.assertIsNone(data['rival']['rank']['intl']); self.assertIsNone(data['rival']['points']['gt'])
        self.assertIsNone(data['probability']['p']); self.assertEqual(data['record']['sets'],0)
        self.assertEqual(data['rival']['detected'],[]); self.assertIsNone(data['rival']['coverage']['registered'])
        self.assertEqual(data['rivalForm'],[]); self.assertEqual(data['gameMatrix'],{}); self.assertEqual(data['recommendations'],[])
        self.login('unlinked'); data=self.call('rival=2')[2]; self.assertEqual(data['state'],'sinJugador'); self.assertIsNone(data['me']); self.assertFalse(PAID.intersection(data))

    def test_partial_cut_and_switching_do_not_invent_set_characters(self):
        self.login('admin'); self.games()
        self.sql('DELETE FROM game_selections WHERE game_id=5002 AND entrant_id=1001')
        data=self.call('rival=2')[2]; row=next(x for x in data['h2h'] if x['setId']=='500')
        self.assertIsNone(row['myChar']); self.assertEqual(row['theirChar'],'link')
        self.sql('INSERT INTO game_selections(game_id,set_id,entrant_id,character_id) VALUES (5002,500,1001,1296)')
        self.assertIsNone(next(x for x in self.call('rival=2')[2]['h2h'] if x['setId']=='500')['myChar'])
        self.sql("UPDATE cuts SET public_snapshot='{}'")
        data=self.call('rival=2')[2]; self.assertEqual(data['gameDataStatus'],'cut_not_synced'); self.assertEqual(data['gameMatrix']['mario|link']['sceneGames'],0)

    def test_no_chosen_fallback_no_detected_and_provable_streak(self):
        uid=self.login('admin'); self.games()
        self.sql('DELETE FROM user_characters WHERE user_id=%s',(uid,))
        data=self.call('rival=2')[2]
        self.assertEqual(data['me']['chosen'],[]); self.assertIn('mario|link',data['gameMatrix'])
        self.assertEqual(data['recommendations'],[])  # Detected characters do not become account preferences.
        self.sql("UPDATE sets SET completed_at='2026-01-03 00:00:01' WHERE id=503")
        self.sql("UPDATE sets SET completed_at='2026-01-02 00:00:01' WHERE id=501")
        self.assertEqual(self.call('rival=2')[2]['streak'],dict(won=False,sets=2))
        self.sql('UPDATE sets SET completed_at=NULL WHERE id=500')
        self.assertIsNone(self.call('rival=2')[2]['streak'])
        public=copy.deepcopy(self.public)
        for v in (public,public['localRanking']):
            p=next(x for x in v['players'] if x['id']=='2')
            p['mains']=[]; p['mainCoverage'].update(setsWithSelections=0,gamesWithSelections=0)
        self.publish(public)
        data=self.call('rival=2')[2]
        self.assertEqual(data['rival']['coverage']['registered'],0)
        self.assertEqual(data['rival']['detected'],[]); self.assertEqual(data['gameMatrix'],{})

    def test_unranked_foreign_opponent_is_searchable_and_not_weak(self):
        public=copy.deepcopy(self.public)
        for v in (public,public['localRanking']):
            v['results'].append(dict(id='990',eventId='100',playerIds=['3','1'],playerTags=['Sin puesto','Yo'],score='Sin puesto 3 - Yo 0'))
        self.publish(public); self.login('admin')
        data=self.call('rival=3')[2]
        self.assertEqual(data['record'],dict(wins=0,losses=1,sets=1))
        self.assertIsNone(data['rival']['rank']['intl']); self.assertIsNone(data['probability']['p'])
        self.assertIsNone(data['rival']['coverage']['registered'])
        self.assertEqual(data['rivalTiers']['intl']['outsideTop100'],[1,0])
        found=self.call('buscar=Sin')[2]['results']
        self.assertEqual([x['playerId'] for x in found],['3']); self.assertIsNone(found[0]['rank']['gt'])

    def test_search_unicode_limits_and_rate(self):
        self.login(); status,_,data=self.call('buscar=jugador%20a2'); self.assertEqual(status,200)
        self.assertEqual([x['playerId'] for x in data['results']],['2']); self.assertEqual(data['results'][0]['record']['sets'],5)
        self.assertFalse(PAID.intersection(data)); self.assertEqual(len(self.call('buscar=')[2]['results']),1)
        for query in ('buscar=a','buscar='+ 'a'*81,'buscar[]=Lu'): self.assertEqual(self.call(query)[0],400)
        many=copy.deepcopy(self.public)
        for i in range(30):
            p=copy.deepcopy(many['players'][0]); p['id']=str(10000+i); p['tag']=f'Jugador ficticio {i}'; many['players'].append(p)
        self.publish(many); data=self.call('buscar=Jugador')[2]; self.assertEqual(len(data['results']),20); self.assertTrue(data['truncated'])
        self.login()  # Fresh session, preserving account.
        for _ in range(30): self.assertEqual(self.call('buscar=xx')[0],200)
        status,headers,data=self.call('buscar=xx'); self.assertEqual(status,429); self.assertEqual(headers['Retry-After'],'60')

    def test_remembered_session_and_missing_premium_config(self):
        self.login('admin',remember=True)
        cookie=next(x for x in self.cookies if x.name!='smash_recordar'); self.cookies.clear(cookie.domain,cookie.path,cookie.name)
        self.assertEqual(self.call('rival=2')[2]['state'],'listo')
        path=self.private/'recurrente.local.php'; config=path.read_text(); path.unlink()
        try:
            self.assertEqual(self.call('rival=2')[2]['access']['reason'],'admin')
            self.login('paid'); self.assert_free(self.call('rival=2')[2])
        finally: path.write_text(config)

    def test_scene_limit_returns_no_partial_paid_analysis(self):
        self.login('admin')
        # 25,001 games, two entrant observations each: exceeds the 50,000-row SQL budget.
        with self.db.cursor() as q:
            q.executemany("INSERT INTO games(id,set_id,game_number,winner_entrant_id,synced_at) VALUES (%s,500,%s,1001,'2026-10-04 11:43:18.348499')",[(100000+i,i+1) for i in range(25001)])
        status,_,data=self.call('rival=2')
        self.assertEqual((status,data),(503,dict(ok=False,reason='game_limit_exceeded')))


if __name__=='__main__': unittest.main(verbosity=2)
