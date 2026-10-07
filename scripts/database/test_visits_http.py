"""Visit counter HTTP contracts against a temporary site and a local disposable database only."""
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
BROWSER = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15'


@unittest.skipUnless(DATABASE, 'Requires local disposable database')
class VisitHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import pymysql
        if not DATABASE.startswith('smash_schema_test') or os.environ.get('SMASH_SCHEMA_TEST_HOST', '127.0.0.1') not in ('127.0.0.1', 'localhost'):
            raise RuntimeError('Local disposable database required')
        port = int(os.environ.get('SMASH_SCHEMA_TEST_PORT', '3306'))
        cls.db = pymysql.connect(host='127.0.0.1', port=port, user='root', password=os.environ['SMASH_SCHEMA_TEST_PASSWORD'], database=DATABASE, autocommit=True)
        cls.temp = tempfile.TemporaryDirectory(prefix='smash-visits-http-')
        home = Path(cls.temp.name)
        cls.site, cls.private = home/'site', home/'private-smash'
        cls.site.mkdir(); cls.private.mkdir()
        for filename in ('database.php', 'visits.php', 'visita.php', 'visita.js'):
            shutil.copyfile(SITE/filename, cls.site/filename)
        config = dict(database=dict(host='127.0.0.1', port=port, name=DATABASE, user='root', password=os.environ['SMASH_SCHEMA_TEST_PASSWORD']))
        (cls.private/'config.local.php').write_text('<?php return json_decode('+json.dumps(json.dumps(config))+', true);')
        cls.log = home/'php-error.log'
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0)); cls.port = sock.getsockname()[1]
        cls.base = f'http://127.0.0.1:{cls.port}'
        # Fixed Guatemala day far in the past is impossible over HTTP; rows of today are removed instead.
        cls.process = subprocess.Popen(['php', '-d', 'display_errors=1', '-d', 'log_errors=1', '-d', f'error_log={cls.log}',
                                        '-S', f'127.0.0.1:{cls.port}', '-t', str(cls.site)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                urllib.request.urlopen(cls.base+'/visita.js', timeout=1).close(); break
            except OSError:
                time.sleep(.05)
        else:
            raise RuntimeError('Local PHP test server did not start')

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate(); cls.process.wait(timeout=10)
        cls.clean(); cls.db.close(); cls.temp.cleanup()

    @classmethod
    def clean(cls):
        with cls.db.cursor() as q:
            for table in ('site_visit_days', 'site_visitor_days', 'site_network_days'):
                q.execute(f'DELETE FROM {table} WHERE day >= DATE_SUB(UTC_DATE(), INTERVAL 1 DAY)')

    def setUp(self):
        self.clean()

    def count(self, table, column='COUNT(*)'):
        with self.db.cursor() as q:
            q.execute(f'SELECT {column} FROM {table}'); return int(q.fetchone()[0] or 0)

    def visit(self, page='inicio', cookie=None, method='POST', origin=True, agent=BROWSER, body=None, content_type='application/json', extra=None):
        headers = {'User-Agent': agent}
        if content_type: headers['Content-Type'] = content_type
        if origin is True: headers['Origin'] = self.base
        elif origin: headers['Origin'] = origin
        if cookie: headers['Cookie'] = 'smash_visita='+cookie
        headers.update(extra or {})
        data = (body if body is not None else json.dumps({'page': page, 'cookies': True})).encode() if method == 'POST' else None
        req = urllib.request.Request(self.base+'/visita.php', data=data, headers=headers, method=method)
        try: response = urllib.request.urlopen(req, timeout=10)
        except urllib.error.HTTPError as error: response = error
        cookies = ' '.join(response.headers.get_all('Set-Cookie') or [])
        token = cookies.split('smash_visita=')[1].split(';')[0] if 'smash_visita=' in cookies else None
        return response.status, response.read(), response.headers, token, cookies

    def test_first_visit_issues_cookie_and_later_visits_reuse_it(self):
        status, body, headers, token, cookies = self.visit()
        self.assertEqual((status, body), (204, b'')); self.assertIn('no-store', headers['Cache-Control'])
        self.assertRegex(token, r'^[0-9a-f]{64}$'); self.assertIn('HttpOnly', cookies); self.assertIn('SameSite=Lax', cookies); self.assertIn('path=/', cookies)
        self.assertEqual((self.count('site_visitor_days'), self.count('site_visit_days', 'SUM(views)'), self.count('site_network_days')), (1, 1, 1))
        self.assertEqual(self.visit('metodologia', cookie=token)[0], 204)
        self.assertEqual((self.count('site_visitor_days'), self.count('site_visit_days', 'SUM(views)')), (1, 2))
        key = (self.private/'visits.key')
        self.assertRegex(key.read_text(), r'^[0-9a-f]{64}$'); self.assertEqual(key.stat().st_mode & 0o777, 0o600)
        with self.db.cursor() as q:
            q.execute('SELECT visitor_hash FROM site_visitor_days UNION ALL SELECT network_hash FROM site_network_days')
            stored = ' '.join(row[0] for row in q.fetchall())
        self.assertNotIn(token, stored); self.assertNotIn('127.0.0.1', stored)
        self.assertFalse(self.log.exists() and self.log.read_text().strip(), 'Counting must not log')

    def test_forged_cookie_is_a_new_visitor_and_not_trusted(self):
        _, _, _, forged_reply, _ = self.visit(cookie='a'*64)
        self.assertRegex(forged_reply, r'^[0-9a-f]{64}$'); self.assertNotEqual(forged_reply, 'a'*64)
        self.visit(cookie='b'*64)
        # Each forged value was replaced by a server-signed identifier, bounded per network.
        self.assertEqual(self.count('site_network_days', 'SUM(new_visitors)'), 2)

    def test_rejections_do_not_count(self):
        cases = [dict(method='GET'), dict(origin=False), dict(origin='https://evil.test'), dict(page='encuesta'), dict(page='opiniones'),
                 dict(body='{"page":"inicio"' + ' '*300 + '}'), dict(body='not json'), dict(content_type='text/plain'),
                 dict(extra={'Sec-Fetch-Site': 'cross-site'}), dict(agent='Googlebot/2.1'), dict(agent='curl/8.4.0')]
        statuses = [self.visit(**case)[0] for case in cases]
        self.assertEqual(statuses, [405, 403, 403, 400, 400, 400, 400, 400, 403, 204, 204])
        self.assertEqual((self.count('site_visitor_days'), self.count('site_visit_days'), self.count('site_network_days')), (0, 0, 0))

    def test_storage_failure_is_silent(self):
        with self.db.cursor() as q:
            q.execute('RENAME TABLE site_network_days TO site_network_days_fixture_away')
        try:
            status, body, _, token, _ = self.visit()
        finally:
            with self.db.cursor() as q:
                q.execute('RENAME TABLE site_network_days_fixture_away TO site_network_days')
        self.assertEqual((status, body, token), (204, b'', None))
        self.assertEqual(self.count('site_visit_days'), 0)


if __name__ == '__main__': unittest.main(verbosity=2)
