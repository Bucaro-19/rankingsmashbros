"""Manual cPanel installer with an invented token and disposable paths; no network."""
import json
import os
from pathlib import Path
import pty
import select
import shutil
import signal
import subprocess
import tempfile
import time
import unittest

SOURCE = Path(__file__).resolve().parents[2] / 'docs/smash/configurar-instagram-cpanel.sh'
TOKEN = 'IGAA_FAKE_SETUP_ONLY_12345678901234567890'


@unittest.skipUnless(shutil.which('php'), 'PHP CLI required')
class InstagramSetupTests(unittest.TestCase):
    def setUp(self):
        result=subprocess.run(['php','-r','exit(PHP_VERSION_ID>=80100 && extension_loaded("curl") && extension_loaded("gd") && extension_loaded("mbstring") ? 0 : 1);'],capture_output=True)
        if result.returncode:self.skipTest('PHP 8.1+, curl, GD and mbstring required; installed in database matrix')

    def run_setup(self, base, *, fresh='SI', token=TOKEN, existing=False, trace=False):
        base=Path(base).resolve(); target=base/'private-smash/instagram.local.php'
        if existing:
            target.parent.mkdir();target.write_text('PRESERVE_EXISTING_CONFIG')
        script=base/'setup.sh'
        script.write_text(SOURCE.read_text().replace('/usr/local/bin/php',shutil.which('php'))
                          .replace('/home/ivcjgjlk/private-smash/instagram.local.php',str(target)))
        pid,fd=pty.fork()
        if pid==0:
            os.execlp('bash','bash',*(['-x'] if trace else []),str(script))
        output=b''; answered=False; pasted=False; status=None; deadline=time.monotonic()+15
        try:
            while time.monotonic()<deadline:
                if select.select([fd],[],[],.1)[0]:
                    try:part=os.read(fd,8192)
                    except OSError:break
                    if not part:break
                    output+=part
                    if not answered and b'Escrib' in output:
                        os.write(fd,(fresh+'\n').encode());answered=True
                    if not pasted and b'no se mostrar' in output:
                        os.write(fd,(token+'\n').encode());pasted=True
                result,exit_status=os.waitpid(pid,os.WNOHANG)
                if result:
                    status=exit_status
                    break
            while status is None and time.monotonic()<deadline:
                result,exit_status=os.waitpid(pid,os.WNOHANG)
                if result:status=exit_status
                else:time.sleep(.01)
            if status is None:
                os.kill(pid,signal.SIGTERM);os.waitpid(pid,0)
                self.fail('Setup timed out')
        finally:os.close(fd)
        return os.waitstatus_to_exitcode(status),output.decode(errors='replace'),target

    def test_fresh_token_hidden_even_with_trace_and_private_disabled_config(self):
        with tempfile.TemporaryDirectory() as base:
            code,out,target=self.run_setup(base,trace=True)
            self.assertEqual(code,0,out);self.assertNotIn(TOKEN,out)
            self.assertIn('DESACTIVADA',out);self.assertEqual(target.stat().st_mode&0o777,0o600)
            info=json.loads(subprocess.check_output(['php','-r',
                '$c=require $argv[1];echo json_encode(["enabled"=>$c["enabled"],"id"=>$c["account_id"],"tokenMatches"=>$c["access_token"]===$argv[2],"age"=>time()-strtotime($c["issued_at"])]);',
                '--',str(target),TOKEN],text=True))
            self.assertEqual(info['enabled'],False);self.assertEqual(info['id'],'17841423954542472')
            self.assertTrue(info['tokenMatches']);self.assertTrue(86400<=info['age']<86410)
            self.assertEqual(set(Path(base).resolve().iterdir()),{Path(base).resolve()/'setup.sh',target.parent})

    def test_declining_does_not_ask_for_token_or_write_file(self):
        with tempfile.TemporaryDirectory() as base:
            code,out,target=self.run_setup(base,fresh='NO')
            self.assertEqual(code,0);self.assertNotIn('Pegá el token',out)
            self.assertFalse(target.exists());self.assertFalse(target.parent.exists())

    def test_existing_configuration_is_not_overwritten_or_read(self):
        with tempfile.TemporaryDirectory() as base:
            code,out,target=self.run_setup(base,existing=True)
            self.assertEqual(code,1);self.assertIn('ya existe',out)
            self.assertNotIn('Escribí SI',out);self.assertNotIn('PRESERVE_EXISTING_CONFIG',out)
            self.assertEqual(target.read_text(),'PRESERVE_EXISTING_CONFIG')

    def test_invalid_token_is_not_echoed_or_saved(self):
        with tempfile.TemporaryDirectory() as base:
            code,out,target=self.run_setup(base,token='FAKE INVALID KEY')
            self.assertEqual(code,1,out);self.assertNotIn('FAKE INVALID KEY',out)
            self.assertFalse(target.exists())


if __name__=='__main__':unittest.main()
