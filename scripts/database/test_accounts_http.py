"""Account HTTP contracts against a temporary site and local disposable database only.

The synthetic login helper is written ONLY to that temporary site. It is never a
production endpoint, deploy file, browser mock, or alternative OAuth implementation.
"""
import hashlib
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
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / 'ranking-smash-ultimate'
DATABASE = os.environ.get('SMASH_SCHEMA_TEST_DB', '')


@unittest.skipUnless(DATABASE, 'Requires local disposable database')
class AccountHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import pymysql
        if not DATABASE.startswith('smash_schema_test') or os.environ.get('SMASH_SCHEMA_TEST_HOST', '127.0.0.1') not in ('127.0.0.1', 'localhost'):
            raise RuntimeError('Local disposable database required')
        cls.db = pymysql.connect(host='127.0.0.1', port=int(os.environ.get('SMASH_SCHEMA_TEST_PORT', '3306')),
                                user='root', password=os.environ['SMASH_SCHEMA_TEST_PASSWORD'], database=DATABASE, autocommit=True)
        cls.temp = tempfile.TemporaryDirectory(prefix='smash-accounts-http-')
        home = Path(cls.temp.name)
        cls.site, cls.private, cls.sessions = home/'site', home/'private-smash', home/'sessions'
        for path in (cls.site/'data', cls.private, cls.sessions):
            path.mkdir(parents=True)
        for filename in ('accounts.php', 'database.php', 'stats.php', 'account-api.php', 'oauth.php', 'cuenta.html', 'cuenta.css', 'cuenta.js', 'account-model.js', 'characters.js'):
            shutil.copyfile(SITE/filename, cls.site/filename)
        shutil.copyfile(SITE/'data/public.json', cls.site/'data/public.json')
        shutil.copytree(SITE/'assets', cls.site/'assets')
        config = dict(database=dict(host='127.0.0.1', port=int(os.environ.get('SMASH_SCHEMA_TEST_PORT', '3306')),
                                    name=DATABASE, user='root', password=os.environ['SMASH_SCHEMA_TEST_PASSWORD']))
        # Only invented credentials for a local disposable instance.
        (cls.private/'config.local.php').write_text('<?php return json_decode('+json.dumps(json.dumps(config))+', true);')
        (cls.site/'fixture-login.php').write_text('''<?php
        require __DIR__.'/database.php'; require __DIR__.'/accounts.php';
        smash_account_session_start(); $pdo=smash_account_connect(__DIR__);
        $id=smash_account_login($pdo,['startggId'=>'8999101','playerId'=>'184005','tag'=>'Jugador QA','url'=>null],time());
        $user=smash_account_user($pdo,$id);
        $_SESSION['smash_account']=['id'=>$id,'at'=>time()-(isset($_GET['expired'])?28800:0),'version'=>$user['connectionVersion'],
            'url'=>'https://www.start.gg/user/fixture','avatarUrl'=>'https://images.start.gg/fixture.png'];
        if (isset($_GET['remember'])) smash_account_remember_set(smash_account_remember_create($pdo,$_SESSION['smash_account'],time()),time());
        session_regenerate_id(true); header('Location: ./cuenta.html',true,303);
        ''')
        (cls.site/'fixture-state.php').write_text('''<?php require __DIR__.'/accounts.php'; smash_account_session_start(); $_SESSION['smash_oauth_pending']=['state'=>'fixture-state','at'=>time()]; echo '{}';''')
        cls.log = home/'php-error.log'
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
        cls.base = f'http://127.0.0.1:{port}'
        cls.process = subprocess.Popen(['php','-d',f'session.save_path={cls.sessions}','-d','date.timezone=America/Guatemala',
                                        '-d','display_errors=1','-d','log_errors=1','-d',f'error_log={cls.log}',
                                        '-S',f'127.0.0.1:{port}','-t',str(cls.site)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                urllib.request.urlopen(cls.base+'/account-api.php',timeout=1).close(); break
            except OSError:
                time.sleep(.05)
        else:
            raise RuntimeError('Local PHP test server did not start')

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate(); cls.process.wait(timeout=10)
        with cls.db.cursor() as q:
            q.execute('SELECT id FROM users WHERE startgg_user_id=8999101'); row=q.fetchone()
            if row:
                for table in ('user_characters','user_roles','oauth_connections'):
                    q.execute(f'DELETE FROM {table} WHERE user_id=%s',(row[0],))
                q.execute('DELETE FROM users WHERE id=%s',(row[0],))
            q.execute('DELETE FROM players WHERE id=184005')
        cls.db.close(); cls.temp.cleanup()

    def setUp(self):
        self.cookies = http.cookiejar.CookieJar()
        self.client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))

    def request(self, path='/account-api.php', body=None, csrf=None, method=None):
        headers = {'Accept':'application/json'}
        if body is not None: headers['Content-Type']='application/json'
        if csrf is not None: headers['X-CSRF-Token']=csrf
        req=urllib.request.Request(self.base+path, data=json.dumps(body).encode() if body is not None else None, headers=headers, method=method)
        try: response=self.client.open(req,timeout=10)
        except urllib.error.HTTPError as error: response=error
        raw=response.read().decode()
        return response.status, response.headers, json.loads(raw) if raw.startswith('{') else raw

    def cookie(self, name):
        return next((c for c in self.cookies if c.name == name), None)

    def drop_browser_session(self):
        # Closing the browser, or the hosting clearing idle PHP sessions: only the long cookie is left.
        session = next(c for c in self.cookies if c.name != 'smash_recordar')
        self.cookies.clear(session.domain, session.path, session.name)

    def with_cookie(self, token, body=None, csrf=None):
        headers = {'Accept':'application/json', 'Cookie':'smash_recordar='+token}
        if body is not None: headers.update({'Content-Type':'application/json','X-CSRF-Token':csrf or ''})
        req=urllib.request.Request(self.base+'/account-api.php', data=json.dumps(body).encode() if body is not None else None, headers=headers)
        try: response=urllib.request.build_opener().open(req,timeout=10)
        except urllib.error.HTTPError as error: response=error
        return response.status, response.headers, json.loads(response.read().decode())

    def stored(self, token):
        with self.db.cursor() as q:
            q.execute('SELECT COUNT(*) FROM user_sessions WHERE token_hash=%s',(hashlib.sha256(token.encode()).hexdigest(),))
            return q.fetchone()[0]

    def login(self, remember=False):
        self.request('/fixture-login.php'+('?remember=1' if remember else ''))
        status, _, data=self.request()
        self.assertEqual(status,200)
        self.assertTrue(data['authenticated'])
        return data

    def test_anonymous_methods_csrf_and_credentials(self):
        status, headers, data=self.request()
        self.assertEqual(status,200); self.assertFalse(data['authenticated']); self.assertFalse(data['oauthReady'])
        self.assertNotIn('user',data); self.assertNotIn('profile',data)
        self.assertIn('no-store',headers['Cache-Control']); self.assertIn('HttpOnly',headers['Set-Cookie']); self.assertIn('SameSite=Lax',headers['Set-Cookie'])
        self.assertEqual(self.request(body={'action':'roles','roles':['admin']})[0],403)
        self.assertEqual(self.request(body={'action':'logout'},csrf=data['csrf'])[0],401)
        self.assertEqual(self.request(method='PUT')[0],405)
        raw=json.dumps(data); self.assertNotIn('client_secret',raw); self.assertNotIn('database',raw)

    def test_expired_session_and_oversized_body(self):
        self.request('/fixture-login.php?expired=1')
        self.assertFalse(self.request()[2]['authenticated'])
        data=self.login()
        self.assertEqual(self.request(body={'action':'roles','padding':'x'*5000},csrf=data['csrf'])[0],413)

    def test_verified_profile_and_scope_parity(self):
        data=self.login(); public=json.loads((SITE/'data/public.json').read_text())
        self.assertEqual(data['user']['tag'],'Jugador QA')
        for scope, view in [('combined',public),('guatemala',public['localRanking'])]:
            expected=next(p for p in view['players'] if p['id']=='184005')
            profile=data['profile']['views'][scope]
            self.assertEqual((profile['rank'],profile['points'],profile['wins'],profile['losses']),
                             (expected['rank'],expected['rating'],expected['wins'],expected['losses']))
        self.assertTrue(any(not e['counts'] for e in data['profile']['views']['guatemala']['events']))
        self.assertNotIn('connectionVersion',data['user'])
        # Ordinary accounts never learn that a private panel exists.
        self.assertNotIn('panel',data); self.assertNotIn('panel',json.dumps(data['user']))

    def test_small_tournament_shows_as_activity_with_its_reason_and_never_counts(self):
        before=self.login()
        with self.db.cursor() as q:
            q.execute("SHOW TABLES LIKE 'organizer_event_context'")
            if not q.fetchone(): self.skipTest('Migration 006 not installed')
        base=8999200; year=before['profile']['seasonYear']; clean=[
            f'DELETE FROM organizer_event_context WHERE event_id={base}', f'DELETE FROM set_slots WHERE event_id={base}',
            f'DELETE FROM sets WHERE event_id={base}', f'DELETE FROM entrant_players WHERE entrant_id IN ({base+1},{base+2})',
            f'DELETE FROM entrants WHERE event_id={base}', f'DELETE FROM events WHERE id={base}', f'DELETE FROM tournaments WHERE id={base}',
            f"DELETE FROM cuts WHERE source_hash='{'a'*64}'", f'DELETE FROM players WHERE id={base+9}']
        def wipe():
            with self.db.cursor() as q:
                for sql in clean: q.execute(sql)
        wipe(); self.addCleanup(wipe)
        with self.db.cursor() as q:
            q.execute(f"INSERT INTO players (id, tag) VALUES ({base+9}, 'Rival QA')")
            q.execute(f"INSERT INTO tournaments (id, name, starts_at, country_code, url) VALUES ({base}, 'Torneo chico QA', '{year}-08-23 18:00:00', 'GT', 'https://www.start.gg/tournament/chico-qa')")
            q.execute(f"INSERT INTO events (id, tournament_id, name) VALUES ({base}, {base}, 'Singles QA')")
            q.execute(f"INSERT INTO entrants (id, event_id, name) VALUES ({base+1}, {base}, 'Jugador QA'), ({base+2}, {base}, 'Rival QA')")
            q.execute(f"INSERT INTO entrant_players (entrant_id, player_id) VALUES ({base+1}, 184005), ({base+2}, {base+9})")
            for n, (winner, kind) in enumerate([(base+1,'competitive'),(base+2,'competitive'),(base+1,'competitive'),(base+1,'dq')]):
                q.execute(f"INSERT INTO sets (id, event_id, status, outcome_type, winner_entrant_id) VALUES ({base+10+n}, {base}, 'completed', '{kind}', {winner})")
                q.execute(f"INSERT INTO set_slots (set_id, slot_index, event_id, entrant_id) VALUES ({base+10+n}, 0, {base}, {base+1}), ({base+10+n}, 1, {base}, {base+2})")
            q.execute("INSERT INTO cuts (generated_at, season_year, season_label, method_version, schema_version, public_snapshot, source_hash, status) "
                      f"VALUES ('{year}-08-24 00:00:00', {year}, 'QA', 'QA-SMALL', 3, '{{}}', '{'a'*64}', 'published')")
            q.execute(f"INSERT INTO organizer_event_context (event_id, cut_id, captured_at, active_players, valid_sets, context_hash) VALUES ({base}, LAST_INSERT_ID(), '{year}-08-24 00:00:00', 13, 3, '{'b'*64}')")
        data=self.login()
        for scope in ('combined','guatemala'):
            view=data['profile']['views'][scope]; old=before['profile']['views'][scope]
            event=next(e for e in view['events'] if e['id']==str(base))
            self.assertEqual((event['counts'],event['wins'],event['losses'],event['date'],event['name']),(False,2,1,f'{year}-08-23','Torneo chico QA'))
            self.assertIn('13 jugadores activos',event['reason']); self.assertIn('20',event['reason'])
            # Ranking figures and every other event are exactly what they were.
            self.assertEqual({k:v for k,v in view.items() if k!='events'},{k:v for k,v in old.items() if k!='events'})
            self.assertEqual([e for e in view['events'] if e['id']!=str(base)],old['events'])
            self.assertEqual([e['date'] for e in view['events']],sorted((e['date'] for e in view['events']),reverse=True))

    def test_preferences_identity_is_server_bound(self):
        data=self.login(); csrf=data['csrf']
        self.assertEqual(self.request(body={'action':'roles','roles':['player','organizer'],'userId':'999'},csrf=csrf)[0],200)
        self.assertEqual(self.request(body={'action':'characters','characters':['1766','1319'],'userId':'999'},csrf=csrf)[0],200)
        self.assertEqual(self.request()[2]['user']['chosen'],['1766','1319'])
        self.assertEqual(self.request(body={'action':'characters','characters':['1766','1766']},csrf=csrf)[0],400)
        self.assertEqual(self.request()[2]['user']['chosen'],['1766','1319'])
        self.assertEqual(self.request(body={'action':'roles','roles':['admin']},csrf=csrf)[0],400)
        with self.db.cursor() as q:
            q.execute('SELECT COUNT(*) FROM tournament_staff'); self.assertEqual(q.fetchone()[0],0)
        self.assertEqual(self.request(body={'action':'characters','characters':['1766']},csrf='forged')[0],403)

    def test_logout_rotates_session_and_disconnect_rejects_other_sessions(self):
        data=self.login(); self.request(body={'action':'characters','characters':['1766','1319']},csrf=data['csrf'])
        first_cookie=next(iter(self.cookies)).value
        self.assertEqual(self.request(body={'action':'logout'},csrf=data['csrf'])[0],200)
        self.assertFalse(self.request()[2]['authenticated']); self.assertNotEqual(next(iter(self.cookies)).value,first_cookie)
        data=self.login(remember=True)
        # Signing in on a second device keeps the first one signed in.
        old_client, old_cookies=self.client, self.cookies; old_token=self.cookie('smash_recordar').value
        self.setUp(); newer=self.login(remember=True)
        new_client, new_cookies=self.client, self.cookies; new_token=self.cookie('smash_recordar').value
        self.client=old_client
        self.assertTrue(self.request()[2]['authenticated'])
        self.client, self.cookies=new_client, new_cookies
        self.assertEqual(self.request(body={'action':'disconnect'},csrf=newer['csrf'])[0],200)
        self.assertFalse(self.request()[2]['authenticated']); self.assertIsNone(self.cookie('smash_recordar'))
        # Disconnecting ends every browser of the account: live sessions and long cookies alike.
        self.assertEqual((self.stored(old_token),self.stored(new_token)),(0,0))
        self.client, self.cookies=old_client, old_cookies
        self.assertEqual(self.request()[0],401); self.assertIsNone(self.cookie('smash_recordar'))
        self.assertFalse(self.with_cookie(old_token)[2]['authenticated'])
        self.client, self.cookies=new_client, new_cookies
        # Re-linking preserves the user's choices without retaining provider tokens.
        self.assertEqual(self.login()['user']['chosen'],['1766','1319'])

    def test_remembered_browser_resumes_without_start_gg(self):
        data=self.login(remember=True); remembered=self.cookie('smash_recordar'); token=remembered.value
        self.assertRegex(token,r'^[0-9a-f]{64}$'); self.assertTrue(remembered.has_nonstandard_attr('HttpOnly'))
        self.assertEqual(remembered.get_nonstandard_attr('SameSite'),'Lax'); self.assertEqual(remembered.path,'/')
        self.assertGreater(remembered.expires,time.time()+89*86400); self.assertEqual(self.stored(token),1)
        with self.db.cursor() as q:
            q.execute('SELECT COUNT(*) FROM user_sessions WHERE token_hash=%s',(token,)); self.assertEqual(q.fetchone()[0],0)
        self.assertNotIn(token,json.dumps(data))
        self.drop_browser_session()
        status, headers, resumed=self.request()
        self.assertEqual(status,200); self.assertTrue(resumed['authenticated']); self.assertEqual(resumed['user']['tag'],'Jugador QA')
        self.assertEqual((resumed['user']['avatarUrl'],resumed['user']['url']),('https://images.start.gg/fixture.png','https://www.start.gg/user/fixture'))
        self.assertIn('no-store',headers['Cache-Control'])
        # The resumed browser can save with the CSRF token of its new session.
        self.assertEqual(self.request(body={'action':'roles','roles':['player']},csrf=resumed['csrf'])[0],200)
        # A session past its eight hours resumes too, also when the first request is a write.
        self.setUp(); self.request('/fixture-login.php?remember=1&expired=1')
        self.assertTrue(self.request()[2]['authenticated'])
        self.setUp(); csrf=self.login()['csrf']; self.request('/fixture-login.php?remember=1&expired=1')
        self.assertEqual(self.request(body={'action':'roles','roles':['player']},csrf=csrf)[0],200)
        self.assertTrue(self.request()[2]['authenticated'])

    def test_remembered_cookie_rejections_and_logout(self):
        self.login(remember=True); token=self.cookie('smash_recordar').value
        status, headers, data=self.with_cookie('f'*64)
        self.assertEqual(status,200); self.assertFalse(data['authenticated']); self.assertIn('smash_recordar=deleted',' '.join(headers.get_all('Set-Cookie')))
        for malformed in ('F'*64, token+'0', 'x'):
            self.assertFalse(self.with_cookie(malformed)[2]['authenticated'])
        self.assertEqual(self.stored(token),1)
        # A copied cookie cannot write without the CSRF token of its own session.
        self.assertEqual(self.with_cookie(token,body={'action':'characters','characters':['1766']},csrf='forged')[0],403)
        with self.db.cursor() as q:
            q.execute("UPDATE user_sessions SET expires_at='2026-01-01 00:00:00' WHERE token_hash=%s",(hashlib.sha256(token.encode()).hexdigest(),))
        self.assertFalse(self.with_cookie(token)[2]['authenticated'])
        data=self.login(remember=True); token=self.cookie('smash_recordar').value
        self.assertTrue(self.with_cookie(token)[2]['authenticated'])
        self.assertEqual(self.request(body={'action':'logout'},csrf=data['csrf'])[0],200)
        self.assertIsNone(self.cookie('smash_recordar')); self.assertEqual(self.stored(token),0)
        self.assertFalse(self.request()[2]['authenticated']); self.assertFalse(self.with_cookie(token)[2]['authenticated'])
        # Without the long cookie nothing changes: the session still ends after eight hours.
        self.setUp(); self.request('/fixture-login.php?expired=1')
        self.assertFalse(self.request()[2]['authenticated'])

    def test_oauth_rejects_unsigned_callbacks_and_missing_csrf(self):
        # No test ever contacts start.gg; unsigned callbacks fail before the transport.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,*args): return None
        self.client=urllib.request.build_opener(NoRedirect(),urllib.request.HTTPCookieProcessor(self.cookies))
        for path in ('/oauth.php?code=fixture&state=forged','/oauth.php?error=access_denied&state=forged'):
            status, headers, _=self.request(path)
            self.assertEqual(status,303); self.assertEqual(headers['Location'],'./cuenta.html#error')
        self.request('/fixture-state.php')
        status, headers, _=self.request('/oauth.php?error=access_denied&state=fixture-state')
        self.assertEqual(status,303); self.assertEqual(headers['Location'],'./cuenta.html#cancelado')
        self.assertEqual(self.request('/oauth.php?error=access_denied&state=fixture-state')[1]['Location'],'./cuenta.html#error')
        self.assertEqual(self.request('/oauth.php',method='PUT')[0],405)
        status, headers, _=self.request('/oauth.php',body={})
        self.assertEqual(status,303); self.assertEqual(headers['Location'],'./cuenta.html#error')


if __name__ == '__main__': unittest.main(verbosity=2)
