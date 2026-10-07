"""Operator-side weekly load of the published cut into SQL. Dry run by default.

Runs on the owner's Mac, the only machine allowed to reach the production database. It finds the
weekly publication run, downloads its capture artifact with gh, proves that the package is exactly
the cut the site is serving, checks chronology against the cuts already stored and then calls the
reviewed importer. It adds no server surface and never prints credentials, connection details,
package contents or driver errors: only reason codes, hashes, timestamps and counts.
"""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request

from ranking_package import canonical, instant, validate_package
from import_ranking import import_package

REPOSITORY = 'Bucaro-19/rankingsmashbros'
WORKFLOW = 'smash-publish.yml'
# Uploaded only after a successful publication, so it exists only for cuts the site received.
ARTIFACT = 'smash-gt-paquete-sql'
PACKAGE = 'database-package.json'
# Fixed destination: the loader never accepts another site or another repository.
PUBLIC_URL = 'https://rankingsmashbros.com/data/public.json'
MAX_BYTES = 32 * 1024 * 1024

# Exit codes are stable so a scheduler or a person can tell the cases apart without reading logs.
EXIT = {'ok': 0, 'usage': 2, 'github_unavailable': 3, 'run_not_found': 3, 'artifact_unavailable': 3, 'package_missing': 3,
        'package_invalid': 4, 'not_the_published_cut': 4, 'public_unavailable': 4,
        'older_than_stored_cut': 5, 'previous_cut_missing': 5, 'unfinished_cut_present': 5,
        'database_unavailable': 6, 'import_rejected': 6, 'parity_not_confirmed': 6}


class LoadStopped(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def stop(reason):
    raise LoadStopped(reason)


def gh(*args):
    try:
        done = subprocess.run(['gh', *args], capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout if done.returncode == 0 else None


def list_runs():
    out = gh('run', 'list', '--repo', REPOSITORY, '--workflow', WORKFLOW, '--branch', 'main', '--limit', '30',
             '--json', 'databaseId,conclusion,status,event,headBranch,createdAt')
    if out is None:
        # gh missing, not signed in, or GitHub unreachable.
        stop('github_unavailable')
    return json.loads(out)


def select_run(runs, run_id=None):
    """Newest completed, successful publication on main; skipped schedule ticks are not publications."""
    usable = [r for r in runs if r.get('status') == 'completed' and r.get('conclusion') == 'success'
              and r.get('headBranch') == 'main' and r.get('event') in ('schedule', 'workflow_dispatch')
              and type(r.get('databaseId')) is int]
    if run_id is not None:
        usable = [r for r in usable if r['databaseId'] == run_id]
    if not usable:
        stop('run_not_found')
    return max(usable, key=lambda r: (r['createdAt'], r['databaseId']))['databaseId']


def download_artifact(run_id, directory):
    if gh('run', 'download', str(run_id), '--repo', REPOSITORY, '--name', ARTIFACT, '--dir', str(directory)) is None:
        stop('artifact_unavailable')


def fetch_public():
    try:
        request = urllib.request.Request(PUBLIC_URL, headers={'Cache-Control': 'no-cache'})
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status != 200 or response.geturl() != PUBLIC_URL:
                stop('public_unavailable')
            body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            stop('public_unavailable')
        return json.loads(body)
    except LoadStopped:
        raise
    except Exception:
        stop('public_unavailable')


def read_package(directory):
    path = Path(directory) / PACKAGE
    if not path.is_file() or path.is_symlink():
        # The package step may fail without blocking the public publication.
        stop('package_missing')
    if path.stat().st_size > MAX_BYTES:
        stop('package_invalid')
    try:
        package = json.loads(path.read_text())
        validate_package(package)
    except Exception:
        stop('package_invalid')
    return package


def check_published(package, live_public):
    """Only a cut the site really serves may enter history: stale, unpublished or re-captured variants stop here."""
    if canonical(package['content']['public']) != canonical(live_public):
        stop('not_the_published_cut')


def stored_cuts(db):
    with db.cursor() as cursor:
        cursor.execute('SELECT generated_at, status FROM cuts ORDER BY generated_at')
        return [(at.isoformat(sep=' ', timespec='microseconds') if isinstance(at, datetime) else str(at), status)
                for at, status in cursor.fetchall()]


def check_chronology(package, cuts, *, allow_gap=False):
    public = package['content']['public']
    this = instant(public['generatedAt'])
    if any(status != 'published' for _, status in cuts):
        stop('unfinished_cut_present')
    moments = [at for at, _ in cuts]
    if this in moments:
        return 'known'
    if moments and this < max(moments):
        # Links to the previous cut are never back-filled: history is loaded in order or not at all.
        stop('older_than_stored_cut')
    if moments and not allow_gap:
        for view in (public, public['localRanking']):
            previous = view.get('previousCutAt')
            if previous is not None and instant(previous) not in moments:
                stop('previous_cut_missing')
    return 'new'


def connect(defaults_file, database):
    if not re.fullmatch('[A-Za-z0-9_]+', database):
        stop('usage')
    defaults = Path(defaults_file)
    if not defaults.is_file() or defaults.stat().st_mode & 0o077:
        stop('database_unavailable')
    try:
        import pymysql
        return pymysql.connect(read_default_file=str(defaults), database=database, charset='utf8mb4',
                               autocommit=False, connect_timeout=10, read_timeout=180, write_timeout=180)
    except Exception:
        # Driver errors can carry host, user or password fragments.
        stop('database_unavailable')


def load(db, package, live_public, *, apply=False, allow_gap=False):
    """Checks and import against an open connection. Returns a sanitized report."""
    check_published(package, live_public)
    try:
        position = check_chronology(package, stored_cuts(db), allow_gap=allow_gap)
        db.rollback()
    except LoadStopped:
        raise
    except Exception:
        stop('database_unavailable')
    public = package['content']['public']
    report = {'sha256': package['sha256'], 'generatedAt': public['generatedAt'], 'position': position}
    try:
        outcome = import_package(db, package, apply=apply)
        report.update(status=outcome['status'], cutId=outcome.get('cutId'), views=outcome['views'])
        if apply and outcome['status'] == 'imported':
            # A second pass must recognise the cut and re-prove parity without writing.
            again = import_package(db, package, apply=True)
            if again['status'] != 'already_imported' or again.get('cutId') != outcome.get('cutId'):
                stop('parity_not_confirmed')
            report['repeat'] = 'already_imported'
    except LoadStopped:
        raise
    except Exception:
        stop('import_rejected')
    return report


def status(db, live_public):
    cuts = stored_cuts(db)
    db.rollback()
    live = instant(live_public['generatedAt'])
    return {'liveCut': live_public['generatedAt'], 'storedCuts': len(cuts),
            'latestStoredCut': cuts[-1][0] if cuts else None,
            'unfinishedCuts': sum(1 for _, state in cuts if state != 'published'),
            'sqlHasLiveCut': any(at == live and state == 'published' for at, state in cuts)}


def notify(title, message):
    if sys.platform != 'darwin':
        return
    script = 'display notification %s with title %s' % (json.dumps(message), json.dumps(title))
    try:
        subprocess.run(['osascript', '-e', script], capture_output=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        pass


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=('status', 'load'))
    parser.add_argument('--database', required=True)
    parser.add_argument('--defaults-file', type=Path, default=Path.home() / '.my.cnf')
    parser.add_argument('--run-id', type=int, help='Publication run to load instead of the latest successful one')
    parser.add_argument('--apply', action='store_true', help='Write the validated cut in one transaction')
    parser.add_argument('--allow-gap', action='store_true',
                        help='Accept that the previous cut is not stored (its link stays empty forever)')
    parser.add_argument('--notify', action='store_true', help='Show the outcome as a macOS notification')
    args = parser.parse_args(argv)
    workdir, db, result = None, None, None
    try:
        if not re.fullmatch('[A-Za-z0-9_]+', args.database):
            stop('usage')
        live_public = fetch_public()
        db = connect(args.defaults_file, args.database)
        if args.command == 'status':
            result = dict(status(db, live_public), ok=True)
        else:
            run_id = select_run(list_runs(), args.run_id)
            workdir = Path(tempfile.mkdtemp(prefix='smash-weekly-'))
            os.chmod(workdir, 0o700)
            download_artifact(run_id, workdir)
            package = read_package(workdir)
            result = dict(load(db, package, live_public, apply=args.apply, allow_gap=args.allow_gap), ok=True, run=run_id)
        code = EXIT['ok']
    except LoadStopped as stopped:
        result, code = {'ok': False, 'reason': stopped.reason}, EXIT.get(stopped.reason, 6)
    except Exception:
        result, code = {'ok': False, 'reason': 'unexpected_failure'}, 6
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:
                pass
        if workdir is not None:
            shutil.rmtree(workdir, ignore_errors=True)
    print(json.dumps(result, ensure_ascii=False))
    if args.notify:
        notify('Smash GT · carga SQL', result.get('status') or result.get('reason') or ('al día' if result.get('sqlHasLiveCut') else 'pendiente'))
    return code


if __name__ == '__main__':
    sys.exit(main())
