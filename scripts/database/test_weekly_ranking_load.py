"""Tests for the operator-side weekly loader. Invented data; SQL cases need a disposable local database."""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock

from ranking_package import build_package, digest
from import_ranking import sql
from test_import_ranking import fixture
import weekly_ranking_load as loader
from weekly_ranking_load import LoadStopped

FIRST = '2026-10-04T11:43:18.348499+00:00'
SECOND = '2026-10-11T06:00:00+00:00'


def run(database_id, conclusion='success', event='schedule', branch='main', status='completed', created='2026-10-11T06:00:10Z'):
    return dict(databaseId=database_id, conclusion=conclusion, event=event, headBranch=branch, status=status, createdAt=created)


def linked(at, previous):
    raw, public = fixture(at)
    for view in (public, public['localRanking']):
        view['previousCutAt'] = previous
        for player in view['players']:
            player['previousRank'] = player['rank']
    return build_package(raw, public)


class StopsWith:
    """Context manager asserting the sanitized reason a step stops with."""
    def __init__(self, case, reason):
        self.case, self.reason = case, reason

    def __enter__(self):
        return self

    def __exit__(self, kind, error, _):
        self.case.assertIsInstance(error, LoadStopped, 'step did not stop')
        self.case.assertEqual(error.reason, self.reason)
        return True


class ContractTests(unittest.TestCase):
    def test_every_stop_reason_has_an_exit_code_and_ok_is_zero(self):
        source = Path(loader.__file__).read_text()
        reasons = set(re.findall(r"stop\('([a-z_]+)'\)", source))
        self.assertGreaterEqual(len(reasons), 12)
        self.assertEqual(reasons - set(loader.EXIT), set())
        self.assertEqual(loader.EXIT['ok'], 0)
        self.assertTrue(all(code > 0 for reason, code in loader.EXIT.items() if reason != 'ok'))

    def test_destination_and_source_are_fixed(self):
        self.assertEqual(loader.PUBLIC_URL, 'https://rankingsmashbros.com/data/public.json')
        self.assertEqual((loader.REPOSITORY, loader.WORKFLOW, loader.ARTIFACT), ('Bucaro-19/rankingsmashbros', 'smash-publish.yml', 'smash-gt-paquete-sql'))
        # The artifact the loader asks for is produced by the weekly workflow, after its deploy step.
        workflow = (Path(loader.__file__).resolve().parents[2] / '.github/workflows' / loader.WORKFLOW).read_text()
        self.assertIn('name: ' + loader.ARTIFACT, workflow)
        self.assertIn('path: scripts/smash/data/' + loader.PACKAGE, workflow)
        self.assertLess(workflow.index('run: python scripts/smash/deploy.py'), workflow.index('name: ' + loader.ARTIFACT))
        self.assertNotIn('if: always()', workflow[workflow.index('Guardar el paquete SQL del corte publicado'):workflow.index('name: ' + loader.ARTIFACT)])
        source = Path(loader.__file__).read_text()
        for option in ('--url', '--repo\'', '--host', '--password', '--user'):
            self.assertNotIn("add_argument('" + option, source)

    def test_selects_the_newest_successful_publication_on_main(self):
        runs = [run(5, created='2026-10-12T12:23:00Z', conclusion='skipped'),      # daily tick with the job skipped
                run(4, created='2026-10-11T07:00:00Z', conclusion='failure'),
                run(3, created='2026-10-11T06:00:10Z'),
                run(6, created='2026-10-13T00:00:00Z', status='in_progress', conclusion=None),
                run(7, created='2026-10-13T00:00:00Z', branch='feat/x'),
                run(8, created='2026-10-13T00:00:00Z', event='pull_request'),
                run(2, created='2026-10-04T06:00:10Z'),
                dict(conclusion='success', status='completed', event='schedule', headBranch='main', createdAt='2026-10-14T00:00:00Z', databaseId='9')]
        self.assertEqual(loader.select_run(runs), 3)
        self.assertEqual(loader.select_run(runs, 2), 2)
        for wanted in (4, 5, 6, 7, 99):
            with StopsWith(self, 'run_not_found'):
                loader.select_run(runs, wanted)
        with StopsWith(self, 'run_not_found'):
            loader.select_run([])

    def test_package_file_is_validated_before_anything_else(self):
        package = build_package(*fixture(FIRST))
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / loader.PACKAGE
            with StopsWith(self, 'package_missing'):
                loader.read_package(folder)
            target.write_text(json.dumps(package))
            self.assertEqual(loader.read_package(folder)['sha256'], package['sha256'])
            tampered = copy.deepcopy(package)
            tampered['content']['public']['players'][0]['rating'] += 1
            for content in ('{not json', json.dumps(tampered), json.dumps({'content': {}, 'sha256': 'x'}), '[]'):
                target.write_text(content)
                with StopsWith(self, 'package_invalid'):
                    loader.read_package(folder)
            target.unlink()
            (Path(folder) / 'elsewhere.json').write_text(json.dumps(package))
            target.symlink_to(Path(folder) / 'elsewhere.json')
            with StopsWith(self, 'package_missing'):
                loader.read_package(folder)
            with mock.patch.object(loader, 'MAX_BYTES', 10):
                target.unlink()
                target.write_text(json.dumps(package))
                with StopsWith(self, 'package_invalid'):
                    loader.read_package(folder)

    def test_only_the_cut_the_site_serves_is_accepted(self):
        raw, public = fixture(FIRST)
        package = build_package(raw, public)
        reordered = json.loads(json.dumps(public, sort_keys=True))
        loader.check_published(package, reordered)  # same content, any key order
        recaptured = copy.deepcopy(public)
        recaptured['characterCapturedAt'] = '2026-10-06T22:33:11+00:00'  # mains re-captured for a published cut
        other_cut = fixture(SECOND)[1]
        unpublished = copy.deepcopy(public)
        unpublished['players'][0]['rating'] += 1
        for live in (recaptured, other_cut, unpublished, {}):
            with StopsWith(self, 'not_the_published_cut'):
                loader.check_published(package, live)

    def test_chronology_rules(self):
        first, second = build_package(*fixture(FIRST)), linked(SECOND, FIRST)
        at_first, at_second = '2026-10-04 11:43:18.348499', '2026-10-11 06:00:00.000000'
        self.assertEqual(loader.check_chronology(first, []), 'new')
        self.assertEqual(loader.check_chronology(first, [(at_first, 'published')]), 'known')
        self.assertEqual(loader.check_chronology(second, [(at_first, 'published')]), 'new')
        self.assertEqual(loader.check_chronology(first, [(at_first, 'published'), (at_second, 'published')]), 'known')
        with StopsWith(self, 'older_than_stored_cut'):
            loader.check_chronology(first, [(at_second, 'published')])
        for state in ('importing', 'failed'):
            with StopsWith(self, 'unfinished_cut_present'):
                loader.check_chronology(second, [(at_first, state)])
        orphan = linked('2026-10-18T06:00:00+00:00', SECOND)
        with StopsWith(self, 'previous_cut_missing'):
            loader.check_chronology(orphan, [(at_first, 'published')])
        self.assertEqual(loader.check_chronology(orphan, [(at_first, 'published')], allow_gap=True), 'new')
        self.assertEqual(loader.check_chronology(orphan, [(at_first, 'published'), (at_second, 'published')]), 'new')

    def test_command_reports_one_sanitized_line_and_cleans_up(self):
        raw, public = fixture(FIRST)
        package = build_package(raw, public)
        seen = {}

        def download(run_id, directory):
            seen['directory'] = Path(directory)
            self.assertEqual(oct(Path(directory).stat().st_mode & 0o777), '0o700')
            (Path(directory) / loader.PACKAGE).write_text(json.dumps(package))

        def call(arguments, **patches):
            defaults = dict(fetch_public=lambda: public, connect=lambda *_: mock.MagicMock(), list_runs=lambda: [run(3)],
                            download_artifact=download, load=lambda *_, **__: {'status': 'validated_no_writes', 'sha256': package['sha256']},
                            status=lambda *_: {'sqlHasLiveCut': True})
            defaults.update(patches)
            output = io.StringIO()
            with contextlib.ExitStack() as stack:
                for name, value in defaults.items():
                    stack.enter_context(mock.patch.object(loader, name, value))
                stack.enter_context(contextlib.redirect_stdout(output))
                code = loader.main(arguments)
            lines = output.getvalue().splitlines()
            self.assertEqual(len(lines), 1)
            return code, json.loads(lines[0])

        code, report = call(['load', '--database', 'smash_schema_test'])
        self.assertEqual((code, report['ok'], report['run'], report['status']), (0, True, 3, 'validated_no_writes'))
        self.assertFalse(seen['directory'].exists())  # private download removed
        code, report = call(['status', '--database', 'smash_schema_test'])
        self.assertEqual((code, report), (0, {'sqlHasLiveCut': True, 'ok': True}))

        def refuse(reason):
            def step(*_, **__):
                raise LoadStopped(reason)
            return step

        def crash(*_, **__):
            raise RuntimeError('host=secret.example user=admin password=hunter2')

        for patches, expected_code, expected_reason in [
                (dict(fetch_public=refuse('public_unavailable')), 4, 'public_unavailable'),
                (dict(list_runs=refuse('github_unavailable')), 3, 'github_unavailable'),
                (dict(list_runs=lambda: [run(3, conclusion='skipped')]), 3, 'run_not_found'),
                (dict(download_artifact=refuse('artifact_unavailable')), 3, 'artifact_unavailable'),
                (dict(download_artifact=lambda *_: None), 3, 'package_missing'),
                (dict(load=refuse('not_the_published_cut')), 4, 'not_the_published_cut'),
                (dict(load=refuse('previous_cut_missing')), 5, 'previous_cut_missing'),
                (dict(connect=refuse('database_unavailable')), 6, 'database_unavailable'),
                (dict(load=crash), 6, 'unexpected_failure')]:
            with self.subTest(reason=expected_reason):
                code, report = call(['load', '--database', 'smash_schema_test', '--apply'], **patches)
                self.assertEqual((code, report), (expected_code, {'ok': False, 'reason': expected_reason}))
                self.assertFalse('directory' in seen and seen['directory'].exists())
        code, report = call(['load', '--database', 'bad name; drop'])
        self.assertEqual((code, report['reason']), (2, 'usage'))

    def test_connection_refuses_shared_credentials_file_and_hides_driver_errors(self):
        with tempfile.TemporaryDirectory() as folder:
            defaults = Path(folder) / 'client.cnf'
            with StopsWith(self, 'database_unavailable'):
                loader.connect(defaults, 'smash_schema_test')
            defaults.write_text('[client]\nhost=127.0.0.1\nport=1\nuser=nobody\npassword=test-only-secret\n')
            defaults.chmod(0o644)
            with StopsWith(self, 'database_unavailable'):
                loader.connect(defaults, 'smash_schema_test')
            defaults.chmod(0o600)
            try:
                loader.connect(defaults, 'smash_schema_test')
                self.fail('connection to a closed port must stop')
            except LoadStopped as stopped:
                self.assertEqual((stopped.reason, str(stopped)), ('database_unavailable', 'database_unavailable'))
            with StopsWith(self, 'usage'):
                loader.connect(defaults, 'smash;drop')


@unittest.skipUnless(os.environ.get('SMASH_SCHEMA_TEST_DB'), 'Requires disposable SQL service')
class LoadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import pymysql
        from pymysql.constants import CLIENT
        database = os.environ['SMASH_SCHEMA_TEST_DB']
        host = os.environ.get('SMASH_SCHEMA_TEST_HOST', '127.0.0.1')
        if not database.startswith('smash_schema_test') or host not in ('127.0.0.1', 'localhost'):
            raise RuntimeError('Only a local disposable database is allowed')
        cls.db = pymysql.connect(host=host, port=int(os.environ.get('SMASH_SCHEMA_TEST_PORT', 3306)), database=database, user='root',
                                 password=os.environ['SMASH_SCHEMA_TEST_PASSWORD'], charset='utf8mb4', autocommit=False,
                                 client_flag=CLIENT.MULTI_STATEMENTS)
        root = Path(__file__).resolve().parents[2]
        for name in ('schema.sql', 'seed-characters.sql'):
            with cls.db.cursor() as cursor:
                cursor.execute((root / 'docs/smash' / name).read_text())
                while cursor.nextset():
                    pass
        cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def clean(self):
        self.db.rollback()
        sql(self.db, 'UPDATE rankings SET previous_cut_id=NULL')
        for table in ('player_characters', 'rankings', 'cut_set_results', 'cut_events', 'cuts', 'set_slots', 'sets',
                      'entrant_players', 'entrants', 'events', 'tournaments', 'players'):
            sql(self.db, 'DELETE FROM `' + table + '`')
        self.db.commit()

    def setUp(self):
        self.clean()
        self.raw, self.public = fixture(FIRST)
        self.package = build_package(self.raw, self.public)

    def tearDown(self):
        self.clean()

    def cuts(self):
        found = sql(self.db, 'SELECT status, COUNT(*) FROM cuts GROUP BY status')
        self.db.rollback()
        return dict(found)

    def test_dry_run_apply_repeat_and_status(self):
        self.assertEqual(loader.status(self.db, self.public), {'liveCut': FIRST, 'storedCuts': 0, 'latestStoredCut': None,
                                                              'unfinishedCuts': 0, 'sqlHasLiveCut': False})
        report = loader.load(self.db, self.package, self.public)
        self.assertEqual((report['status'], report['position'], report['cutId']), ('validated_no_writes', 'new', None))
        self.assertEqual(self.cuts(), {})
        report = loader.load(self.db, self.package, self.public, apply=True)
        self.assertEqual((report['status'], report['repeat'], report['sha256']), ('imported', 'already_imported', self.package['sha256']))
        self.assertEqual(report['views']['combined']['players'], 2)
        self.assertEqual(self.cuts(), {'published': 1})
        again = loader.load(self.db, self.package, self.public, apply=True)
        self.assertEqual((again['status'], again['position'], again['cutId']), ('already_imported', 'known', report['cutId']))
        self.assertNotIn('repeat', again)
        self.assertEqual(self.cuts(), {'published': 1})
        state = loader.status(self.db, self.public)
        self.assertEqual((state['sqlHasLiveCut'], state['storedCuts'], state['latestStoredCut']), (True, 1, '2026-10-04 11:43:18.348499'))
        self.assertFalse(loader.status(self.db, fixture(SECOND)[1])['sqlHasLiveCut'])
        report_text = json.dumps([report, again, state])
        for private in ('Jugador', 'password', 'disposable-test-only', '127.0.0.1'):
            self.assertNotIn(private, report_text)

    def test_refuses_a_package_that_is_not_what_the_site_serves_before_touching_sql(self):
        recaptured = copy.deepcopy(self.public)
        recaptured['characterCapturedAt'] = '2026-10-06T22:33:11+00:00'
        for live in (recaptured, fixture(SECOND)[1]):
            with StopsWith(self, 'not_the_published_cut'):
                loader.load(self.db, self.package, live, apply=True)
        self.assertEqual(self.cuts(), {})
        self.assertEqual(sql(self.db, 'SELECT COUNT(*) FROM players')[0][0], 0)

    def test_weekly_sequence_links_the_previous_cut_and_refuses_disorder(self):
        first = loader.load(self.db, self.package, self.public, apply=True)
        second = linked(SECOND, FIRST)
        report = loader.load(self.db, second, second['content']['public'], apply=True)
        self.assertEqual((report['status'], report['position']), ('imported', 'new'))
        self.assertEqual(sql(self.db, 'SELECT COUNT(*) FROM rankings WHERE previous_cut_id=%s', (first['cutId'],))[0][0], 4)
        self.db.rollback()
        # A cut older than the newest stored one is never inserted behind it.
        older = build_package(*fixture('2026-10-07T06:00:00+00:00'))
        with StopsWith(self, 'older_than_stored_cut'):
            loader.load(self.db, older, older['content']['public'], apply=True)
        # A newer cut whose previous cut was skipped stops unless the gap is accepted explicitly.
        orphan = linked('2026-10-25T06:00:00+00:00', '2026-10-18T06:00:00+00:00')
        with StopsWith(self, 'previous_cut_missing'):
            loader.load(self.db, orphan, orphan['content']['public'], apply=True)
        self.assertEqual(self.cuts(), {'published': 2})
        accepted = loader.load(self.db, orphan, orphan['content']['public'], apply=True, allow_gap=True)
        self.assertEqual(accepted['status'], 'imported')
        self.assertEqual(sql(self.db, 'SELECT COUNT(*) FROM rankings WHERE cut_id=%s AND previous_cut_id IS NOT NULL', (accepted['cutId'],))[0][0], 0)
        self.db.rollback()
        self.assertEqual(self.cuts(), {'published': 3})

    def test_stops_on_an_unfinished_cut_and_on_importer_conflicts_without_partial_data(self):
        loader.load(self.db, self.package, self.public, apply=True)
        changed = copy.deepcopy(self.package)
        changed['content']['public']['players'][0]['rating'] += 1
        changed['sha256'] = digest(changed['content'])
        with StopsWith(self, 'import_rejected'):  # same cut identity, different content
            loader.load(self.db, changed, changed['content']['public'], apply=True)
        self.assertEqual(self.cuts(), {'published': 1})
        sql(self.db, "UPDATE cuts SET status='importing'")
        self.db.commit()
        second = linked(SECOND, FIRST)
        with StopsWith(self, 'unfinished_cut_present'):
            loader.load(self.db, second, second['content']['public'], apply=True)
        self.assertEqual(self.cuts(), {'importing': 1})

    def test_failure_inside_the_import_leaves_the_stored_history_untouched(self):
        first = loader.load(self.db, self.package, self.public, apply=True)
        sql(self.db, "CREATE TRIGGER reject_weekly_test BEFORE INSERT ON rankings FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='test-only-fault'")
        try:
            second = linked(SECOND, FIRST)
            with StopsWith(self, 'import_rejected'):
                loader.load(self.db, second, second['content']['public'], apply=True)
        finally:
            sql(self.db, 'DROP TRIGGER IF EXISTS reject_weekly_test')
            self.db.commit()
        self.assertEqual(self.cuts(), {'published': 1})
        self.assertEqual(sql(self.db, 'SELECT id FROM cuts')[0][0], first['cutId'])
        self.db.rollback()
        self.assertEqual(loader.load(self.db, self.package, self.public, apply=True)['status'], 'already_imported')


if __name__ == '__main__':
    unittest.main(verbosity=2)
