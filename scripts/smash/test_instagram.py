"""Invented public health, deployment preservation and CLI HTTP boundary; no Instagram/SQL."""
import contextlib
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
import urllib.request
import urllib.error

import check_instagram as health
from deploy import FILES, deploy
from test_seo import fixture, SITE

NOW = datetime(2026, 10, 27, 19, tzinfo=timezone.utc)


def status():
    return dict(schemaVersion=1, checkedAt=NOW.isoformat(), ok=True, status='ready', code=None)


class InstagramTests(unittest.TestCase):
    def test_health_is_fresh_success_only_and_prints_no_remote_details(self):
        self.assertTrue(health.check(status(), NOW))
        for change in ({'ok': False}, {'ok': 1}, {'status': 'not_configured'}, {'code': 'instagram_refresh_failed'},
                       {'checkedAt': (NOW-timedelta(hours=4)).isoformat()}, {'checkedAt': (NOW+timedelta(hours=1)).isoformat()},
                       {'checkedAt': 'bad'}, {'checkedAt': None}, {'checkedAt': 123}, {'schemaVersion': True}, {'schemaVersion': 2}, {'access_token': 'FAKE_PRIVATE_CREDENTIAL'}):
            self.assertFalse(health.check(dict(status(), **change), NOW), change)
        with patch.object(health.urllib.request, 'urlopen', side_effect=RuntimeError('FAKE_PRIVATE_CREDENTIAL')):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(health.main(), 1)
        self.assertNotIn('FAKE_PRIVATE_CREDENTIAL', out.getvalue())
        self.assertEqual(json.loads(out.getvalue()), {'ok': False, 'status': 'instagram_capture_needs_attention'})

    def test_assets_and_full_deploy_never_overwrite_feed_status_or_pictures(self):
        self.assertTrue({'instagram.html','instagram.css','instagram.js','instagram.php','instagram-sync.php','assets/instagram/.htaccess'} <= set(FILES))
        self.assertNotIn('data/instagram.json', FILES); self.assertNotIn('data/instagram-status.json', FILES)
        for assets_only in (False, True):
            with self.subTest(assets_only=assets_only), tempfile.TemporaryDirectory() as directory:
                source=Path(directory);fixture(source)
                untouched={'data/instagram.json':b'LAST_GOOD_FEED', 'data/instagram-status.json':b'SAFE_HEALTH',
                           'assets/instagram/'+'a'*64+'-full.webp':b'GOOD_IMAGE'}
                remote=dict(untouched)
                remote['data/public.json']=(SITE/'data/public.json').read_bytes()
                remote['data/agenda.json']=(SITE/'data/agenda.json').read_bytes()
                old_public=remote['data/public.json'];ftp=Mock()
                ftp.retrbinary.side_effect=lambda command, cb: cb(remote[command.removeprefix('RETR ')])
                ftp.storbinary.side_effect=lambda command, f: remote.update({command.removeprefix('STOR '):f.read()})
                ftp.rename.side_effect=lambda src,dst: remote.update({dst:remote.pop(src)})
                with patch.dict('os.environ', {'SMASH_FTP_DIR':'.'}):deploy(ftp,source,assets_only=assets_only)
                for key,value in untouched.items():self.assertEqual(remote[key],value)
                if assets_only:self.assertEqual(remote['data/public.json'],old_public)
                self.assertFalse(ftp.delete.called)

    def test_monitor_is_read_only_and_libraries_are_denied(self):
        workflow=(SITE.parent/'.github/workflows/smash-instagram-health.yml').read_text()
        self.assertIn("cron: '29 */2 * * *'",workflow);self.assertIn("SMASH_INSTAGRAM_ENABLED == 'true'",workflow)
        for unwanted in ('FTP_PASSWORD','INSTAGRAM_ACCESS_TOKEN','MYSQL','STARTGG_TOKEN','contents: write'):self.assertNotIn(unwanted,workflow)
        ht=(SITE/'.htaccess').read_text()
        for name in ('instagram.php','instagram-sync.php'):self.assertIn(f'<Files "{name}">\n  Require all denied\n</Files>',ht)
        self.assertIn('max-age=31536000, immutable',(SITE/'assets/instagram/.htaccess').read_text())
        script=(SITE/'instagram.php').read_text()
        self.assertNotIn('database.php',script);self.assertNotIn('error_log(',script);self.assertNotIn('getMessage()',script)
        self.assertNotIn('curl_error(',script)

    @unittest.skipUnless(shutil.which('php'), 'PHP CLI required')
    def test_http_cannot_execute_worker_or_library_and_unconfigured_cli_is_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);root=base/'site';root.mkdir();(root/'data').mkdir();(root/'assets/instagram').mkdir(parents=True);(base/'private-smash').mkdir(mode=0o700)
            for name in ('instagram.php','instagram-sync.php'):shutil.copyfile(SITE/name,root/name)
            run=subprocess.run(['php',str(root/'instagram-sync.php')],capture_output=True,text=True,timeout=10)
            self.assertEqual(run.returncode,0);self.assertEqual(run.stderr,'');self.assertEqual(json.loads(run.stdout)['status'],'not_configured')
            self.assertFalse((root/'data/instagram.json').exists())
            with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            server=subprocess.Popen(['php','-S',f'127.0.0.1:{port}','-t',str(root)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            try:
                for _ in range(100):
                    try:
                        with socket.create_connection(('127.0.0.1',port),timeout=.1):break
                    except OSError:time.sleep(.02)
                for name in ('instagram-sync.php','instagram.php'):
                    with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(f'http://127.0.0.1:{port}/{name}',timeout=5)
                    self.assertEqual(error.exception.code,403)
            finally:server.terminate();server.wait(timeout=5)


if __name__ == '__main__':unittest.main()
