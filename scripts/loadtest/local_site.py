"""Isolated fixture server. Never published; only loopback + an EMPTY dedicated test DB.

Uses existing PyMySQL/importer for setup. HTTP static/gzip/304 is served by Python;
PHP endpoints are forwarded to four local PHP CLI workers. This is NOT LiteSpeed.
"""
import argparse
from contextlib import contextmanager
import gzip
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT/'ranking-smash-ultimate'
sys.path.insert(0, str(ROOT/'scripts/database'))
sys.path.insert(0, str(ROOT/'scripts/smash'))
from import_ranking import import_package
from ranking_package import canonical
from smash_load import MAX_USERS, PATHS, UA, run


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0)); return sock.getsockname()[1]


@contextmanager
def local_site(port, package=None):
    import pymysql
    from pymysql.constants import CLIENT
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError('Puerto local explícito requerido.')
    password = os.environ['SMASH_LOAD_LOCAL_PASSWORD']
    database = 'smash_load_test_' + os.urandom(6).hex()
    db = pymysql.connect(host='127.0.0.1',port=port,user='root',password=password,
                         charset='utf8mb4',autocommit=True,client_flag=CLIENT.MULTI_STATEMENTS)
    # No remote host option, no defaults file, and never reuse/drop somebody else's DB.
    temp = tempfile.TemporaryDirectory(prefix='smash-load-local-')
    home = Path(temp.name); site=home/'site'; private=home/'private-smash'; sessions=home/'sessions'
    for path in (site/'data',private,sessions): path.mkdir(parents=True)
    process = server = monitor = None; stopped=threading.Event()
    counts = {}; peaks = dict(phpRssKiB=0, dbThreadsRunning=0, phpProcesses=0)
    try:
        with db.cursor() as q:
            q.execute('CREATE DATABASE '+database+' CHARACTER SET utf8mb4'); q.execute('USE '+database)
            for file in [ROOT/'docs/smash/schema.sql', ROOT/'docs/smash/seed-characters.sql',
                         *sorted((ROOT/'docs/smash/migrations').glob('*.sql'))]:
                q.execute(file.read_text())
                while q.nextset(): pass
        if package:
            data = json.loads(Path(package).read_text())
        else:
            from test_import_ranking import fixture
            from ranking_package import build_package
            data = build_package(*fixture())
        import_package(db,data,apply=True)
        public = data['content']['public']
        for name in ('index.html','arena.css','database.php','accounts.php','stats.php','premium.php',
                     'analisis.php','analisis-api.php','account-api.php','visits.php','visita.php'):
            shutil.copyfile(SITE/name,site/name)
        raw_public=(SITE/'data/public.json').read_bytes()
        (site/'data/public.json').write_bytes(raw_public if json.loads(raw_public)==public else canonical(public).encode('utf-8'))
        config = dict(database=dict(host='127.0.0.1',port=port,name=database,user='root',password=password))
        (private/'config.local.php').write_text('<?php return json_decode('+json.dumps(json.dumps(config))+',true);')
        (private/'config.local.php').chmod(0o600)
        # Seed a local admin via CLI; no HTTP login endpoint, provider credentials, or payment.
        login = home/'seed-session.php'
        login.write_text('''<?php
        require $argv[1].'/database.php'; require $argv[1].'/accounts.php';
        $db=smash_account_connect($argv[1]);
        $id=smash_account_login($db,['startggId'=>'999999999999','playerId'=>$argv[2],'tag'=>'Load test local','url'=>null],time());
        $db->exec("INSERT IGNORE INTO user_roles(user_id,role) VALUES ($id,'admin')");
        $user=smash_account_user($db,$id); $cookies=[];
        for ($i=0;$i<40;$i++) { smash_account_session_start();
            $_SESSION['smash_account']=['id'=>$id,'at'=>time(),'version'=>$user['connectionVersion'],'url'=>null,'avatarUrl'=>null];
            $cookies[]=session_name().'='.session_id(); session_write_close(); session_id(''); }
        file_put_contents($argv[3],json_encode($cookies)); chmod($argv[3],0600);
        ''')
        cookies_file=private/'local-sessions.json'
        cookies=[]
        def refresh_sessions():
            # Earlier profiles take >24 min: PHP's normal file-session GC may remove
            # unused seed sessions. Renew only this disposable fixture immediately
            # before analysis, preserving normal server session settings.
            subprocess.run(['php','-d',f'session.save_path={sessions}',str(login),str(site),public['players'][0]['id'],str(cookies_file)],
                           check=True,stdout=subprocess.DEVNULL)
            cookies[:]=json.loads(cookies_file.read_text())
            if len(set(cookies))!=MAX_USERS: raise ValueError('Sesiones locales deben ser independientes.')
        refresh_sessions()
        php_port=free_port()
        env={**os.environ, 'PHP_CLI_SERVER_WORKERS':'4'}
        process=subprocess.Popen(['php','-d','memory_limit=512M','-d','display_errors=0','-d',f'session.save_path={sessions}',
                                  '-S',f'127.0.0.1:{php_port}','-t',str(site)],env=env,
                                 stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        for _ in range(100):
            try:
                with socket.create_connection(('127.0.0.1',php_port),timeout=.5): break
            except OSError: time.sleep(.05)
        else: raise RuntimeError('PHP local no inició.')
        static={}
        for path,name in (('/','index.html'),('/arena.css','arena.css'),('/data/public.json','data/public.json')):
            body=(site/name).read_bytes(); static[path]=(body,gzip.compress(body,mtime=0),'"'+hashlib.sha256(body).hexdigest()+'"')
        front_port=free_port()
        class Handler(BaseHTTPRequestHandler):
            protocol_version='HTTP/1.1'
            def log_message(self,*args): pass
            def do_GET(self): self.serve()
            def do_POST(self): self.serve()
            def serve(self):
                path=self.path.split('?',1)[0]
                if path not in PATHS: self.send_error(404); return
                if path in static:
                    body,compressed,tag=static[path]
                    not_modified=self.headers.get('If-None-Match')==tag
                    use_gzip='gzip' in self.headers.get('Accept-Encoding','')
                    payload=b'' if not_modified else compressed if use_gzip else body
                    self.send_response(304 if not_modified else 200)
                    self.send_header('ETag',tag); self.send_header('Cache-Control','no-cache')
                    self.send_header('Content-Type','application/json' if path.endswith('.json') else 'text/css' if path.endswith('.css') else 'text/html')
                    if use_gzip and not not_modified: self.send_header('Content-Encoding','gzip')
                    self.send_header('Content-Length',str(len(payload))); self.end_headers(); self.wfile.write(payload); return
                connection=http.client.HTTPConnection('127.0.0.1',php_port,timeout=5)
                body=self.rfile.read(int(self.headers.get('Content-Length',0))) if self.command=='POST' else None
                headers={k:v for k,v in self.headers.items() if k.lower() not in ('connection','transfer-encoding')}
                try:
                    connection.request(self.command,self.path,body=body,headers=headers)
                    reply=connection.getresponse(); payload=reply.read()
                    self.send_response(reply.status)
                    for key,value in reply.getheaders():
                        if key.lower() not in ('content-length','connection','transfer-encoding','server','date'):
                            self.send_header(key,value)
                    self.send_header('Content-Length',str(len(payload))); self.end_headers(); self.wfile.write(payload)
                except (OSError,http.client.HTTPException):
                    self.send_error(503)
                finally: connection.close()
        server=ThreadingHTTPServer(('127.0.0.1',front_port),Handler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        def watch():
            connection=pymysql.connect(host='127.0.0.1',port=port,user='root',password=password,database=database,autocommit=True)
            try:
                while not stopped.wait(1):
                    # Aggregate PHP parent/workers RSS is an upper estimate (shared pages counted repeatedly).
                    rows=subprocess.check_output(['ps','-axo','pid,ppid,rss'],text=True).splitlines()[1:]
                    entries=[tuple(map(int,row.split())) for row in rows if len(row.split())==3]
                    pids={process.pid}|{pid for pid,ppid,_ in entries if ppid==process.pid}
                    peaks['phpProcesses']=max(peaks['phpProcesses'],len(pids))
                    peaks['phpRssKiB']=max(peaks['phpRssKiB'],sum(rss for pid,_,rss in entries if pid in pids))
                    with connection.cursor() as q:
                        q.execute("SHOW GLOBAL STATUS LIKE 'Threads_running'"); peaks['dbThreadsRunning']=max(peaks['dbThreadsRunning'],int(q.fetchone()[1]))
            finally: connection.close()
        monitor=threading.Thread(target=watch,daemon=True); monitor.start()
        with db.cursor() as q:
            for table in ('players','events','sets','games','game_selections','rankings'):
                q.execute('SELECT COUNT(*) FROM '+table); counts[table]=q.fetchone()[0]
            q.execute('SELECT VERSION()'); version=q.fetchone()[0]
        def visit_count():
            with db.cursor() as q:
                q.execute('SELECT COALESCE(SUM(views),0) FROM site_visit_days'); return int(q.fetchone()[0])
        yield dict(origin=f'http://127.0.0.1:{front_port}',cookies=cookies,rival=public['players'][1]['id'],
                   rows=counts,dbVersion=version,phpWorkers=4,peaks=peaks,visit_count=visit_count,refresh_sessions=refresh_sessions,
                   compressedPublicBytes=len(static['/data/public.json'][1]),publicBytes=len(static['/data/public.json'][0]))
    finally:
        stopped.set()
        if monitor: monitor.join(timeout=3)
        if server: server.shutdown(); server.server_close()
        if process:
            os.killpg(process.pid,signal.SIGTERM); process.wait(timeout=10)
        with db.cursor() as q: q.execute('DROP DATABASE '+database)
        db.close(); temp.cleanup()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db-port',type=int,required=True)
    parser.add_argument('--package',type=Path)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--scenarios',nargs='+',choices=('visitor','static','php-no-db','php-read','php-write','analysis-local'),
                        default=['visitor','static','php-no-db','php-read','php-write','analysis-local'])
    args=parser.parse_args()
    def interrupt(*_): raise KeyboardInterrupt
    signal.signal(signal.SIGTERM,interrupt)
    if len(args.scenarios)!=len(set(args.scenarios)) or len(args.scenarios)>6:
        parser.error('Una ejecución admite cada escenario una sola vez (tope lote 12,000 peticiones).')
    summary=[]
    with local_site(args.db_port,args.package) as fixture:
        for scenario in args.scenarios:
            if scenario=='analysis-local': fixture['refresh_sessions']()
            print('START '+scenario,flush=True); before=fixture['visit_count']()
            fixture['peaks'].update(phpRssKiB=0,dbThreadsRunning=0,phpProcesses=0)
            report=run(fixture['origin'],scenario,args.output_dir/(scenario+'.json'),
                       cookies=fixture['cookies'] if scenario=='analysis-local' else None,
                       rival=fixture['rival'] if scenario=='analysis-local' else None,
                       progress=lambda step: print('STAGE '+json.dumps(dict(users=step['users'],p95=step['metrics']['p95'],errors=step['metrics']['errors'],complete=step['complete'],reason=step['stopReason'])),flush=True))
            delta=fixture['visit_count']()-before
            report['fixture']={key:fixture[key] for key in ('rows','dbVersion','phpWorkers','compressedPublicBytes','publicBytes')}
            report['fixture']['resourcePeaksCumulative']=dict(fixture['peaks'])
            report['falsePageViewsRecorded']=delta
            report['falsePageViewsInProduction']=0
            report['writeVerified']=scenario!='php-write' or delta==report.get('writeRequestsAttempted',0)
            if not report['writeVerified']: report['stopReason']='counter_not_written'
            from smash_load import save
            save(args.output_dir/(scenario+'.json'),report)
            summary.append(report); print('DONE '+json.dumps(dict(scenario=scenario,stopReason=report['stopReason'],falseViews=delta,
                                    stages=[dict(users=s['users'],p95=s['metrics']['p95'],errors=s['metrics']['errors'],complete=s['complete']) for s in report['steps']])),flush=True)
            if report['stopReason']!='completed_capped_ladder': break
    from smash_load import save
    save(args.output_dir/'local-summary.json',summary)
    if summary and summary[-1]['stopReason']!='completed_capped_ladder':
        parser.exit(3,'Laboratorio detenido; revisar el informe antes de repetir.\n')


if __name__=='__main__': main()
