"""Account HTTP contracts against a temporary site and local disposable database only.

The synthetic login helper is written ONLY to that temporary site. It is never a
production endpoint, deploy file, browser mock, or alternative OAuth implementation.
"""
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
        for filename in ('accounts.php', 'database.php', 'account-api.php', 'oauth.php', 'cuenta.html', 'cuenta.css', 'cuenta.js', 'account-model.js', 'characters.js'):
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
        $_SESSION['smash_account']=['id'=>$id,'at'=>time()-(isset($_GET['expired'])?28800:0),'version'=>$user['connectionVersion']];
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

    def login(self):
        self.request('/fixture-login.php')
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
        data=self.login()
        # Separate browser login changes the connection version: the first browser must reauthorize.
        old_client=self.client
        self.setUp(); newer=self.login()
        new_client=self.client; self.client=old_client
        self.assertEqual(self.request()[0],401)
        self.client=new_client
        self.assertEqual(self.request(body={'action':'disconnect'},csrf=newer['csrf'])[0],200)
        self.assertFalse(self.request()[2]['authenticated'])
        # Re-linking preserves the user's choices without retaining provider tokens.
        self.assertEqual(self.login()['user']['chosen'],['1766','1319'])

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
