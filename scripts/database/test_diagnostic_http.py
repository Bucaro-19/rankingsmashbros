"""HTTP contract checks with an isolated PHP site/session, never user credentials."""
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]


class DiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='smash-db-http-')
        home = Path(cls.temp.name)
        cls.site = home / 'site'
        cls.site.mkdir()
        (cls.site / 'feedback-data').mkdir()
        cls.sessions = home / 'sessions'
        cls.sessions.mkdir()
        cls.private = home / 'private-smash'
        cls.private.mkdir()
        for filename in ('database.php', 'opiniones.php'):
            (cls.site / filename).write_bytes((ROOT / 'ranking-smash-ultimate' / filename).read_bytes())
        (cls.site / 'feedback-data/admin-auth.php').write_text("<?php return '" + '$2y$12$' + 'A'*53 + "';")
        cls.session_id = 'smashdiagnostictestonly'
        # Synthetic session, created exclusively for this temporary test site.
        subprocess.run(['php', '-d', f'session.save_path={cls.sessions}', '-r',
            'session_name("SMASHGT_ADMIN");session_id("smashdiagnostictestonly");session_start();'
            '$_SESSION["smash_admin"]=true;$_SESSION["smash_admin_at"]=time();session_write_close();'],
            check=True, capture_output=True)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            cls.port = sock.getsockname()[1]
        cls.process = subprocess.Popen(['php', '-d', f'session.save_path={cls.sessions}',
            '-S', f'127.0.0.1:{cls.port}', '-t', str(cls.site)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.url = f'http://127.0.0.1:{cls.port}/opiniones.php?diagnostico=base'
        for _ in range(100):
            try:
                urllib.request.urlopen(f'http://127.0.0.1:{cls.port}/opiniones.php', timeout=1).close()
                break
            except (OSError, urllib.error.URLError):
                time.sleep(0.05)
        else:
            raise RuntimeError('PHP test server did not start')

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate()
        cls.process.wait(timeout=5)
        cls.temp.cleanup()

    def request(self, *, authenticated=False, method='GET'):
        headers = {'Cookie': f'SMASHGT_ADMIN={self.session_id}'} if authenticated else {}
        request = urllib.request.Request(self.url, headers=headers, method=method)
        try:
            response = urllib.request.urlopen(request, timeout=5)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, dict(response.headers), response.read().decode()

    def test_unauthorized_does_not_inspect_config_or_database(self):
        status, headers, body = self.request()
        self.assertEqual(status, 401)
        self.assertEqual(json.loads(body)['error']['code'], 'login_required')
        self.assertNotIn('config_missing', body)
        self.assertIn('no-store', headers['Cache-Control'])

    def test_authenticated_missing_file_is_sanitized(self):
        status, headers, body = self.request(authenticated=True)
        self.assertEqual(status, 503)
        self.assertEqual(json.loads(body)['error']['code'], 'config_missing')
        self.assertNotIn(str(self.temp.name), body)

    def test_parse_and_unexpected_output_never_leak(self):
        config = self.private / 'config.local.php'
        try:
            for content in ['SECRET-MARKER-DO-NOT-RETURN', '<?php password SECRET-MARKER-DO-NOT-RETURN syntaxerror;']:
                config.write_text(content)
                status, headers, body = self.request(authenticated=True)
                self.assertEqual(status, 503)
                self.assertEqual(json.loads(body)['error']['code'], 'config_invalid')
                self.assertNotIn('SECRET-MARKER', body)
                self.assertNotIn(str(self.temp.name), body)
        finally:
            if config.exists():
                config.unlink()

    def test_read_only_endpoint_rejects_post(self):
        status, headers, body = self.request(authenticated=True, method='POST')
        self.assertEqual(status, 405)
        self.assertEqual(headers['Allow'], 'GET')


if __name__ == '__main__':
    unittest.main(verbosity=2)
