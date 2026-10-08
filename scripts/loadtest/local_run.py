"""Create a NEW local MariaDB instance, run the bounded fixture, then remove only it.

Requires already installed MariaDB/PHP and the existing SQL test dependency PyMySQL.
Never reads ~/.my.cnf, server secrets, production SQL, or a remote dump.
"""
import argparse
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
import time

from local_site import free_port


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--scenarios',nargs='+',choices=('visitor','static','php-no-db','php-read','php-write','analysis-local'))
    args=parser.parse_args()
    if args.scenarios and len(args.scenarios)!=len(set(args.scenarios)):
        parser.error('Cada escenario una sola vez; no se amplía el tope del lote.')
    installer,daemon=shutil.which('mariadb-install-db'),shutil.which('mariadbd')
    if not installer or not daemon or not shutil.which('php'):
        parser.error('Usar MariaDB y PHP ya instalados. No se descarga ni instala nada automáticamente.')
    import pymysql
    with tempfile.TemporaryDirectory(prefix='smash-load-db-') as temp:
        home=Path(temp);port=free_port();process=None
        with (home/'setup.log').open('wb') as log:
            try:
                subprocess.run([installer,'--no-defaults',f'--datadir={home}/data','--auth-root-authentication-method=normal'],
                               stdout=log,stderr=log,check=True)
                process=subprocess.Popen([daemon,'--no-defaults',f'--datadir={home}/data',f'--socket={home}/db.sock',
                                          f'--port={port}','--bind-address=127.0.0.1',f'--pid-file={home}/db.pid',f'--log-error={home}/db.log'],
                                         stdout=log,stderr=log)
                for _ in range(100):
                    if process.poll() is not None: raise RuntimeError('MariaDB local no inició; no se usa otro servidor.')
                    try:
                        db=pymysql.connect(host='127.0.0.1',port=port,user='root',autocommit=True);break
                    except pymysql.MySQLError: time.sleep(.1)
                else: raise RuntimeError('MariaDB local no inició.')
                password=secrets.token_hex(24)
                with db.cursor() as q:q.execute('ALTER USER root@localhost IDENTIFIED BY %s',(password,))
                db.close()
                # This random password belongs only to the new disposable server. No command-line/log exposure.
                prior=os.environ.get('SMASH_LOAD_LOCAL_PASSWORD');os.environ['SMASH_LOAD_LOCAL_PASSWORD']=password
                old_args=sys.argv
                try:
                    sys.argv=['local_site.py','--db-port',str(port),'--output-dir',str(args.output_dir)]
                    if args.package:sys.argv+=['--package',str(args.package)]
                    if args.scenarios:sys.argv+=['--scenarios',*args.scenarios]
                    from local_site import main as measure
                    measure()
                finally:
                    sys.argv=old_args
                    if prior is None:os.environ.pop('SMASH_LOAD_LOCAL_PASSWORD',None)
                    else:os.environ['SMASH_LOAD_LOCAL_PASSWORD']=prior
            finally:
                if process:
                    process.terminate()
                    try:process.wait(timeout=15)
                    except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)


if __name__=='__main__': main()
