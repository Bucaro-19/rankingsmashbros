"""No production traffic. Limits/brakes/window/HTTP contracts on loopback only."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import gzip
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import smash_load as load


def row(status=200, seconds=.01, error=None, endpoint='/'):
    return dict(status=status,seconds=seconds,error=error,endpoint=endpoint,bytes=10)


class SafetyTests(unittest.TestCase):
    def test_origins_have_no_arbitrary_domains_ports_paths_credentials_or_query(self):
        for text in ('https://start.gg','https://recurrente.com','https://www.rankingsmashbros.com',
                     'http://rankingsmashbros.com','https://rankingsmashbros.com:444',
                     'https://a:b@rankingsmashbros.com','https://rankingsmashbros.com/path',
                     'https://rankingsmashbros.com/?token=secret','https://rankingsmashbros.com/#x'):
            with self.subTest(text=text),self.assertRaises(ValueError): load.origin(text,True)
        self.assertEqual(load.origin('https://rankingsmashbros.com/',True),'https://rankingsmashbros.com')
        for text in ('http://localhost:1234','http://192.168.1.1:1234','https://127.0.0.1:1234','http://127.0.0.1'):
            with self.assertRaises(ValueError): load.origin(text)
        self.assertEqual(load.origin('http://127.0.0.1:1234'),'http://127.0.0.1:1234')

    def test_cli_plans_only_without_execute_and_cannot_override_hard_limits(self):
        with tempfile.TemporaryDirectory() as temp:
            command=[sys.executable,str(Path(load.__file__)),'--origin','https://rankingsmashbros.com',
                     '--production','--output',str(Path(temp)/'out.json')]
            reply=subprocess.run(command,capture_output=True,text=True,check=True)
            data=json.loads(reply.stdout); self.assertFalse(data['execute'])
            self.assertEqual(data['steps'],[1,2,5,10,20,40]);self.assertEqual(data['stepSeconds'],60)
            self.assertEqual(data['maxRequests'],2000);self.assertTrue(data['visitsExcluded'])
            self.assertFalse((Path(temp)/'out.json').exists())
            for flag in ('--users','--max-users','--requests','--duration','--timeout','--error-rate','--p95'):
                reply=subprocess.run(command+[flag,'100000'],capture_output=True,text=True)
                self.assertNotEqual(reply.returncode,0)
            reply=subprocess.run(command+['--execute'],capture_output=True,text=True)
            self.assertNotEqual(reply.returncode,0); self.assertIn('orden expresa',reply.stderr)
            self.assertFalse((Path(temp)/'out.json').exists())

    def test_caps_are_global_and_atomic_even_with_many_threads(self):
        budget=load.Budget()
        with ThreadPoolExecutor(max_workers=40) as pool:
            success=list(pool.map(lambda _:budget.reserve(),range(2400)))
        self.assertEqual(sum(success),2000);self.assertEqual(budget.requests,2000)
        self.assertFalse(budget.reserve())
        budget=load.Budget()
        with ThreadPoolExecutor(max_workers=40) as pool:
            success=list(pool.map(lambda _:budget.reserve(write=True),range(100)))
        self.assertEqual(sum(success),10);self.assertEqual((budget.requests,budget.writes),(10,10))

    def test_latency_and_error_brakes_are_strict_and_include_php_and_429_508(self):
        self.assertIsNone(load.brake([]));self.assertIsNone(load.brake([row(seconds=3)]))
        self.assertEqual(load.brake([row(seconds=3.001)]),'p95_over_3_seconds')
        self.assertIsNone(load.brake([row(error='unexpected_status')]+[row() for _ in range(99)]))
        self.assertEqual(load.brake([row(error='timeout')]+[row() for _ in range(98)]),'errors_over_1_percent')
        for status in (429,500,503,508,'transport_error'):
            self.assertEqual(load.brake([row(status=status,error='unexpected_status')]),'errors_over_1_percent')
        rows=[row() for _ in range(100)]+[row(seconds=3.1,endpoint='/account-api.php')]
        self.assertEqual(load.percentile([s['seconds'] for s in rows],95),.01)
        self.assertEqual(load.brake(rows),'endpoint_p95_over_3_seconds')
        stats=load.metrics([row(status=508,error='unexpected_status'),row()],2)
        self.assertEqual(stats['errors'],1);self.assertEqual(stats['errorRate'],.5)
        self.assertEqual(stats['statusCounts'],{'508':1,'200':1});self.assertEqual(stats['bodyBytes'],20)
        self.assertEqual(load.percentile(list(range(1,101)),95),95)

    def test_cron_and_owner_windows_never_include_weekends_or_daytime(self):
        for minute,second in ((0,0),(1,29),(2,17),(3,30),(4,59),(5,0)):
            self.assertFalse(load.safe_cron_slot(datetime(2026,10,9,1,minute,second,tzinfo=load.GT)))
        self.assertTrue(load.safe_cron_slot(datetime(2026,10,9,1,1,30,tzinfo=load.GT)))
        self.assertTrue(load.safe_cron_slot(datetime(2026,10,9,1,2,0,tzinfo=load.GT)))
        for a,b in (('2026-10-10T01:00:00-06:00','2026-10-10T01:20:00-06:00'),
                    ('2026-10-11T00:00:00-06:00','2026-10-11T00:20:00-06:00'),
                    ('2026-10-09T13:00:00-06:00','2026-10-09T13:20:00-06:00'),
                    ('2026-10-09T01:00:00-06:00','2026-10-09T02:00:00-06:00'),
                    ('2026-10-09T01:00:00','2026-10-09T01:20:00')):
            with self.assertRaises(ValueError): load.production_window(a,b)
        a,b=load.production_window('2026-10-09T01:00:00-06:00','2026-10-09T01:29:00-06:00')
        self.assertEqual((b-a).total_seconds(),1740)

    def test_runner_stops_at_first_failed_step_and_never_raises_level_after(self):
        with tempfile.TemporaryDirectory() as temp:
            def result(*args,**kwargs):
                return dict(users=args[2],complete=args[2]==1,stopReason=None if args[2]==1 else 'errors_over_1_percent')
            with patch.object(load,'stage',side_effect=result) as stage,patch.object(load,'COOLDOWN_SECONDS',0),patch.object(load.tempfile,'gettempdir',return_value=temp):
                report=load.run('http://127.0.0.1:1234','visitor',Path(temp)/'out.json')
            self.assertEqual([c.args[2] for c in stage.call_args_list],[1,2])
            self.assertEqual(report['stopReason'],'errors_over_1_percent')
            self.assertEqual(len(json.loads((Path(temp)/'out.json').read_text())['steps']),2)
            with patch.object(load,'stage') as stage:
                for scenario in ('analysis-local','php-write'):
                    with self.assertRaises(ValueError): load.run('https://rankingsmashbros.com',scenario,Path(temp)/'out.json',production=True)
                with self.assertRaises(ValueError): load.run('https://rankingsmashbros.com','visitor',Path(temp)/'out.json',production=True)
                stage.assert_not_called()

    def test_two_runs_cannot_multiply_caps_on_this_machine(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(load.tempfile,'gettempdir',return_value=temp):
            with (Path(temp)/'smashgt-loadtest.lock').open('a') as mutex:
                load.fcntl.flock(mutex,load.fcntl.LOCK_EX|load.fcntl.LOCK_NB)
                with patch.object(load,'stage') as stage,self.assertRaises(ValueError):
                    load.run('http://127.0.0.1:1234','static',Path(temp)/'out.json')
                stage.assert_not_called()

    def test_interrupt_saves_partial_report_without_another_step(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(load.tempfile,'gettempdir',return_value=temp):
            with patch.object(load,'stage',side_effect=KeyboardInterrupt) as stage:
                report=load.run('http://127.0.0.1:1234','visitor',Path(temp)/'out.json')
            self.assertEqual(report['stopReason'],'operator_interrupt');self.assertEqual(stage.call_count,1)
            self.assertTrue((Path(temp)/'out.json').is_file())

    def test_local_batch_rejects_duplicates_before_any_database_connection(self):
        command=[sys.executable,str(Path(load.__file__).with_name('local_site.py')),'--db-port','33318','--output-dir','/tmp/not-used','--scenarios','visitor','visitor']
        reply=subprocess.run(command,capture_output=True,text=True)
        self.assertNotEqual(reply.returncode,0);self.assertIn('una sola vez',reply.stderr)

    def test_stage_never_exceeds_users_or_budget_and_rejects_a_higher_step(self):
        for value in (0,3,41,80):
            with self.assertRaises(ValueError): load.stage('http://127.0.0.1:1234','static',value,load.Budget())
        with self.assertRaises(ValueError): load.stage('http://127.0.0.1:1234','php-write',5,load.Budget())
        active=[0,0]; mutex=threading.Lock()
        class Client:
            validator=None
            def __init__(self,*args): pass
            def close(self): pass
            def request(self,path,conditional=False):
                with mutex: active[0]+=1;active[1]=max(active)
                time.sleep(.005)
                with mutex: active[0]-=1
                return row(endpoint=path)
        with patch.object(load,'Transport',Client),patch.object(load,'STEP_SECONDS',.035),patch.object(load,'PACE_SECONDS',.01):
            result=load.stage('http://127.0.0.1:1234','php-read',5,load.Budget())
        self.assertLessEqual(active[1],5);self.assertGreater(active[1],1);self.assertTrue(result['complete'])


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.calls=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_GET(self):
                cls.calls.append(dict(path=self.path,agent=self.headers.get('User-Agent'),conditional=self.headers.get('If-None-Match'),cookie=self.headers.get('Cookie')))
                if self.path=='/':
                    self.send_response(302);self.send_header('Location','https://start.gg/');self.end_headers();return
                if self.path=='/account-api.php':
                    self.send_response(503);self.end_headers();self.wfile.write(b'{"ok":false}');return
                if self.path=='/data/public.json':
                    if self.headers.get('If-None-Match')=='"test-cut"':
                        self.send_response(304);self.end_headers();return
                    self.send_response(200);self.send_header('ETag','"test-cut"');self.send_header('Set-Cookie','PHPSESSID=synthetic-do-not-log; HttpOnly');self.send_header('Content-Encoding','gzip');self.end_headers()
                    self.wfile.write(gzip.compress(json.dumps(dict(rankingComputed=True,players=[dict(id='1')])).encode()));return
                self.send_response(401);self.end_headers();self.wfile.write(b'{"reason":"login_required"}')
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.base='http://127.0.0.1:'+str(cls.server.server_port)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join()

    def setUp(self): self.calls.clear()

    def test_live_503_brakes_the_real_ladder_and_does_not_retry(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(load.tempfile,'gettempdir',return_value=temp):
            report=load.run(self.base,'php-read',Path(temp)/'out.json')
        self.assertEqual(report['stopReason'],'errors_over_1_percent')
        self.assertEqual([s['users'] for s in report['steps']],[1])
        self.assertLess(report['steps'][0]['elapsedSeconds'],1)
        self.assertEqual(report['steps'][0]['metrics']['statusCounts'],{'503':1})
        self.assertEqual(len(self.calls),1)

    def test_only_first_party_no_redirect_following_and_304_has_zero_bytes(self):
        client=load.Transport(self.base)
        try:
            first=client.request('/data/public.json');second=client.request('/data/public.json',True)
            self.assertEqual((first['status'],first['error']),(200,None))
            self.assertEqual((second['status'],second['bytes'],second['error']),(304,0,None))
            redirect=client.request('/');self.assertEqual(redirect['error'],'unexpected_status')
            self.assertEqual(len(self.calls),3)
            self.assertEqual({c['agent'] for c in self.calls},{'SmashGT-LoadTest'})
            self.assertEqual(self.calls[1]['conditional'],'"test-cut"')
            self.assertIn('PHPSESSID=synthetic-do-not-log',self.calls[1]['cookie'])
            self.assertNotIn('synthetic-do-not-log',json.dumps(second))
            self.assertEqual(client.request('/analisis-api.php')['error'],None) # Expected anonymous pre-auth, no SQL.
            for path in ('/encuesta.php','/oauth.php','/ranking-sync.php','/recurrente-webhook.php',
                         'https://start.gg/','/account-api.php?action=logout','/premium-api.php','/analisis-api.php?rival=2&me=1'):
                with self.assertRaises(ValueError): client.request(path)
        finally: client.close()


if __name__=='__main__': unittest.main(verbosity=2)
