"""Premium HTTP contracts against a temporary site and a local disposable database only.

Never contacts Recurrente: the invented key is used only for requests that stop before any
provider call (anonymous reads, rejected writes, and webhooks that need no lookup).
"""
import base64
import hashlib
import hmac
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
SECRET = 'whsec_' + base64.b64encode(b'k' * 24).decode()


@unittest.skipUnless(DATABASE, 'Requires local disposable database')
class PremiumHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import pymysql
        if not DATABASE.startswith('smash_schema_test') or os.environ.get('SMASH_SCHEMA_TEST_HOST', '127.0.0.1') not in ('127.0.0.1', 'localhost'):
            raise RuntimeError('Local disposable database required')
        port = int(os.environ.get('SMASH_SCHEMA_TEST_PORT', '3306'))
        cls.db = pymysql.connect(host='127.0.0.1', port=port, user='root', password=os.environ['SMASH_SCHEMA_TEST_PASSWORD'], database=DATABASE, autocommit=True)
        cls.temp = tempfile.TemporaryDirectory(prefix='smash-premium-http-')
        home = Path(cls.temp.name)
        cls.site, cls.private, sessions = home/'site', home/'private-smash', home/'sessions'
        for path in (cls.site, cls.private, sessions):
            path.mkdir(parents=True)
        for filename in ('database.php', 'accounts.php', 'premium.php', 'premium-api.php', 'recurrente-webhook.php'):
            shutil.copyfile(SITE/filename, cls.site/filename)
        config = dict(database=dict(host='127.0.0.1', port=port, name=DATABASE, user='root', password=os.environ['SMASH_SCHEMA_TEST_PASSWORD']))
        (cls.private/'config.local.php').write_text('<?php return json_decode('+json.dumps(json.dumps(config))+', true);')
        cls.log = home/'php-error.log'
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0)); cls.port = sock.getsockname()[1]
        cls.base = f'http://127.0.0.1:{cls.port}'
        cls.process = subprocess.Popen(['php', '-d', f'session.save_path={sessions}', '-d', 'display_errors=1', '-d', 'log_errors=1', '-d', f'error_log={cls.log}',
                                        '-S', f'127.0.0.1:{cls.port}', '-t', str(cls.site)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                urllib.request.urlopen(cls.base+'/premium-api.php', timeout=1).close(); break
            except urllib.error.HTTPError:
                break
            except OSError:
                time.sleep(.05)
        else:
            raise RuntimeError('Local PHP test server did not start')

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate(); cls.process.wait(timeout=10)
        with cls.db.cursor() as q:
            q.execute("DELETE FROM premium_events WHERE event_id LIKE 'msg_http_%'")
        cls.db.close(); cls.temp.cleanup()

    def configure(self, enabled=True):
        (self.private/'recurrente.local.php').write_text('<?php return '+("['enabled'=>%s,'secret_key'=>'sk_test_%s','webhook_secret'=>'%s'];" % ('true' if enabled else 'false', 'a'*40, SECRET)))

    def call(self, path, body=None, headers=None, method=None):
        req = urllib.request.Request(self.base+path, data=body, headers=headers or {}, method=method)
        try: response = urllib.request.urlopen(req, timeout=10)
        except urllib.error.HTTPError as error: response = error
        return response.status, response.headers, response.read().decode()

    def webhook(self, body, event='msg_http_1', at=None, secret=SECRET, signature=None):
        at = str(int(time.time()) if at is None else at)
        raw = body.encode()
        mac = base64.b64encode(hmac.new(base64.b64decode(secret[6:]), f'{event}.{at}.'.encode()+raw, hashlib.sha256).digest()).decode()
        return self.call('/recurrente-webhook.php', raw, {'Content-Type': 'application/json', 'svix-id': event, 'svix-timestamp': at, 'svix-signature': signature or 'v1,'+mac})

    def events(self):
        with self.db.cursor() as q:
            q.execute("SELECT event_id, event_type, outcome FROM premium_events WHERE event_id LIKE 'msg_http_%' ORDER BY event_id"); return q.fetchall()

    def test_plans_are_public_and_writes_need_an_account(self):
        self.configure()
        status, headers, body = self.call('/premium-api.php')
        data = json.loads(body)
        self.assertEqual(status, 200); self.assertIn('no-store', headers['Cache-Control'])
        self.assertEqual((data['authenticated'], data['available']), (False, True)); self.assertNotIn('premium', data)
        self.assertEqual(data['plans'], {'monthly': {'amountInCents': 300, 'currency': 'USD', 'interval': 'month'}, 'annual': {'amountInCents': 2400, 'currency': 'USD', 'interval': 'year'}})
        self.assertNotIn('sk_test', body); self.assertNotIn('whsec', body)
        post = lambda payload, extra=None: self.call('/premium-api.php', json.dumps(payload).encode(), {'Content-Type': 'application/json', **(extra or {})})[0]
        self.assertEqual(post({'action': 'checkout', 'plan': 'annual'}), 403)
        self.assertEqual(post({'action': 'checkout', 'plan': 'annual'}, {'X-CSRF-Token': 'forged'}), 403)
        self.assertEqual(self.call('/premium-api.php', method='PUT')[0], 405)
        self.assertFalse(data['paused'])
        # The pause file stops new payments and says so; without it, or with "0", payments are open.
        flag=self.site/'pagos-en-pausa.txt'; self.addCleanup(lambda: flag.unlink(missing_ok=True))
        flag.write_text('1\n'); self.assertTrue(json.loads(self.call('/premium-api.php')[2])['paused'])
        flag.write_text('0\n'); self.assertFalse(json.loads(self.call('/premium-api.php')[2])['paused'])
        self.configure(enabled=False)
        self.assertFalse(json.loads(self.call('/premium-api.php')[2])['available'])

    def test_webhook_requires_a_valid_signature_and_runs_once(self):
        self.configure()
        body = json.dumps({'event_type': 'payment_intent.succeeded', 'id': 'pa_http1', 'customer': {'email': 'privada@example.com'}})
        self.assertEqual(self.webhook(body, signature='v1,' + base64.b64encode(b'x'*32).decode())[0], 401)
        self.assertEqual(self.webhook(body, secret='whsec_' + base64.b64encode(b'z'*24).decode())[0], 401)
        self.assertEqual(self.webhook(body, at=int(time.time()) - 600)[0], 401)
        self.assertEqual(self.call('/recurrente-webhook.php', body.encode(), {'Content-Type': 'application/json'})[0], 401)
        self.assertEqual(self.call('/recurrente-webhook.php')[0], 405)
        self.assertEqual(self.events(), ())
        status, _, answer = self.webhook(body)
        self.assertEqual((status, answer), (204, ''))
        self.assertEqual(self.webhook(body)[0], 204)
        self.assertEqual(self.events(), (('msg_http_1', 'payment_intent.succeeded', 'ignored'),))
        self.assertEqual(self.webhook('not json', event='msg_http_2')[0], 400)
        self.assertEqual(self.webhook('x' * 70000, event='msg_http_3')[0], 413)
        self.assertFalse(self.log.exists() and 'privada' in self.log.read_text(), 'The payer e-mail must never reach a log')
        self.configure(enabled=False)
        self.assertEqual(self.webhook(body, event='msg_http_4')[0], 503)


if __name__ == '__main__': unittest.main(verbosity=2)
