"""Owner panel access contracts against a temporary site and a local disposable database only.

The synthetic login helper exists ONLY in that temporary site; it is never deployed.
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
class PanelHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import pymysql
        if not DATABASE.startswith('smash_schema_test') or os.environ.get('SMASH_SCHEMA_TEST_HOST', '127.0.0.1') not in ('127.0.0.1', 'localhost'):
            raise RuntimeError('Local disposable database required')
        port = int(os.environ.get('SMASH_SCHEMA_TEST_PORT', '3306'))
        cls.db = pymysql.connect(host='127.0.0.1', port=port, user='root', password=os.environ['SMASH_SCHEMA_TEST_PASSWORD'], database=DATABASE, autocommit=True)
        cls.temp = tempfile.TemporaryDirectory(prefix='smash-panel-http-')
        home = Path(cls.temp.name)
        cls.site, cls.private, sessions = home/'site', home/'private-smash', home/'sessions'
        for path in (cls.site/'data', cls.private, sessions):
            path.mkdir(parents=True)
        for filename in ('database.php', 'accounts.php', 'stats.php', 'account-api.php', 'panel-api.php', 'panel.php', 'panel.css', 'panel.js', 'panel-model.js'):
            shutil.copyfile(SITE/filename, cls.site/filename)
        shutil.copyfile(SITE/'data/public.json', cls.site/'data/public.json')
        config = dict(database=dict(host='127.0.0.1', port=port, name=DATABASE, user='root', password=os.environ['SMASH_SCHEMA_TEST_PASSWORD']))
        (cls.private/'config.local.php').write_text('<?php return json_decode('+json.dumps(json.dumps(config))+', true);')
        (cls.site/'fixture-login.php').write_text('''<?php
        require __DIR__.'/database.php'; require __DIR__.'/accounts.php';
        smash_account_session_start(); $pdo=smash_account_connect(__DIR__);
        $admin=isset($_GET['admin']);
        $id=smash_account_login($pdo,['startggId'=>$admin?'8999401':'8999402','playerId'=>null,'tag'=>$admin?'Dueña QA':'Jugador QA','url'=>null],time());
        $pdo->exec("INSERT IGNORE INTO user_roles (user_id, role) VALUES ($id, 'player'), ($id, 'organizer')");
        if ($admin) $pdo->exec("INSERT IGNORE INTO user_roles (user_id, role) VALUES ($id, 'admin')");
        $user=smash_account_user($pdo,$id);
        $_SESSION['smash_account']=['id'=>$id,'at'=>time(),'version'=>$user['connectionVersion'],'url'=>null,'avatarUrl'=>null];
        if (isset($_GET['remember'])) smash_account_remember_set(smash_account_remember_create($pdo,$_SESSION['smash_account'],time()),time());
        session_regenerate_id(true); echo 'ok';
        ''')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0)); cls.port = sock.getsockname()[1]
        cls.base = f'http://127.0.0.1:{cls.port}'
        cls.process = subprocess.Popen(['php', '-d', f'session.save_path={sessions}', '-d', 'display_errors=1', '-S', f'127.0.0.1:{cls.port}', '-t', str(cls.site)],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                urllib.request.urlopen(cls.base+'/panel.css', timeout=1).close(); break
            except OSError:
                time.sleep(.05)
        else:
            raise RuntimeError('Local PHP test server did not start')

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate(); cls.process.wait(timeout=10)
        with cls.db.cursor() as q:
            q.execute('DELETE FROM users WHERE startgg_user_id IN (8999401, 8999402)')
        cls.db.close(); cls.temp.cleanup()

    def setUp(self):
        self.cookies = http.cookiejar.CookieJar()
        self.client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))

    def get(self, path, method='GET'):
        req = urllib.request.Request(self.base+path, method=method, data=b'{}' if method == 'POST' else None)
        try: response = self.client.open(req, timeout=10)
        except urllib.error.HTTPError as error: response = error
        return response.status, response.headers, response.read().decode()

    def assert_private(self, headers):
        self.assertIn('no-store', headers['Cache-Control']); self.assertIn('noindex', headers['X-Robots-Tag'])

    def assert_reveals_nothing(self, body):
        for word in ('Visitas', 'registros', 'visitantes', 'Panel privado', 'panel.js', 'panel-api', 'report'):
            self.assertNotIn(word, body)

    def test_anonymous_is_asked_to_sign_in_and_sees_no_figures(self):
        status, headers, body = self.get('/panel.php')
        self.assertEqual(status, 401); self.assert_private(headers); self.assert_reveals_nothing(body)
        self.assertIn('Tu sesión', body); self.assertIn('action="./oauth.php"', body); self.assertIn('name="csrf"', body)
        self.assertIn('<title>Smash GT</title>', body); self.assertIn('name="robots" content="noindex', body)
        status, headers, body = self.get('/panel-api.php')
        self.assertEqual((status, json.loads(body)), (401, {'ok': False, 'reason': 'login_required'})); self.assert_private(headers)

    def test_other_accounts_get_no_access_and_no_hint(self):
        self.get('/fixture-login.php')
        status, headers, body = self.get('/panel.php')
        self.assertEqual(status, 403); self.assert_private(headers); self.assert_reveals_nothing(body)
        self.assertIn('Sin acceso.', body); self.assertNotIn('Cerrar sesión', body)
        status, _, body = self.get('/panel-api.php')
        self.assertEqual((status, json.loads(body)), (403, {'ok': False, 'reason': 'forbidden'}))

    def test_owner_gets_the_panel_and_aggregates_only(self):
        self.get('/fixture-login.php?admin=1')
        status, headers, body = self.get('/panel.php')
        self.assertEqual(status, 200); self.assert_private(headers)
        self.assertIn('Visitas y registros', body); self.assertIn('panel.js', body); self.assertIn('Cerrar sesión', body)
        status, headers, body = self.get('/panel-api.php')
        self.assertEqual(status, 200); self.assert_private(headers)
        data = json.loads(body)
        self.assertEqual(sorted(data['report']), ['accounts', 'counterStartedAt', 'daily', 'periods', 'seasonYear', 'today', 'updatedAt', 'weekly', 'yesterday'])
        self.assertEqual(sorted(data['report']['periods']), ['30', '7', '90', 'season']); self.assertRegex(data['csrf'], r'^[0-9a-f]{48}$')
        self.assertEqual(data['report']['seasonYear'], 2026)
        self.assertNotIn('Dueña', body); self.assertNotIn('8999401', body)
        self.assertEqual(self.get('/panel-api.php', method='POST')[0], 405)

    def test_remembered_owner_resumes_and_loses_access_when_the_role_is_removed(self):
        self.get('/fixture-login.php?admin=1&remember=1')
        session = next(c for c in self.cookies if c.name != 'smash_recordar')
        self.cookies.clear(session.domain, session.path, session.name)
        self.assertEqual(self.get('/panel.php')[0], 200); self.assertEqual(self.get('/panel-api.php')[0], 200)
        with self.db.cursor() as q:
            q.execute("DELETE r FROM user_roles r JOIN users u ON u.id=r.user_id WHERE u.startgg_user_id=8999401 AND r.role='admin'")
        self.assertEqual(self.get('/panel-api.php')[0], 403); self.assertEqual(self.get('/panel.php')[0], 403)
        with self.db.cursor() as q:
            q.execute("UPDATE oauth_connections o JOIN users u ON u.id=o.user_id SET o.revoked_at=UTC_TIMESTAMP(6) WHERE u.startgg_user_id=8999401")
        self.assertEqual(self.get('/panel-api.php')[0], 401); self.assertEqual(self.get('/panel.php')[0], 401)


if __name__ == '__main__': unittest.main(verbosity=2)
