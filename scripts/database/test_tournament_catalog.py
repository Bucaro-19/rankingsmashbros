"""Optional private tournament catalog: contracts, importer parity and real hosting queue."""
import copy
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import urllib.request
import shutil
import unittest

from ranking_package import build_package, canonical, digest, validate_package, CATALOG_COLUMNS
from import_ranking import import_package, sql
import test_import_ranking as fixtures
import test_hosting_sync as hosting
import publish_sql as sender

FIRST = '2026-10-04T11:43:18.348499+00:00'
SECOND = '2026-10-11T06:00:00+00:00'
MIGRATION = fixtures.ROOT / 'docs/smash/migrations/005_organizer_tops.sql'


def catalog():
    return [dict(id='10', name='Torneo Á', slug='tournament/test10', startAt=1767276000,
        city='Ciudad de Guatemala', ownerId='77', events=[
            dict(id='100', name='Singles', type=1, numEntrants=20, startAt=1767362400, reason=None),
            dict(id='199', name='Dobles', type=2, numEntrants=8, startAt=None, reason='not_singles')]),
        dict(id='99', name='Fuera del corte', slug='event/not-a-tournament', startAt=None,
            city=None, ownerId=None, events=[dict(id='999', name=None, numEntrants=None, reason='under_20_entrants')])]


def package(at=FIRST, source=None):
    raw, public = fixtures.fixture(at)
    raw['tournamentCatalog'] = catalog() if source is None else source
    return build_package(raw, public)


class CatalogContractTests(unittest.TestCase):
    def check_php(self, p):
        if not hosting.PHP:
            self.skipTest('PHP CLI required')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'package.json'; path.write_text(canonical(p))
            return hosting.bridge('validate', path)

    def test_normalization_determinism_and_unchanged_public_entities_mains(self):
        p = package(); self.assertEqual(p, package()); validate_package(p)
        old = build_package(*fixtures.fixture()); c = p['content']; rows = c['tournamentCatalog']
        self.assertEqual(c['packageVersion'], 3)
        self.assertEqual(c['public'], old['content']['public'])
        self.assertEqual(c['entities'], old['content']['entities'])
        self.assertEqual(c['gameContextSetIds'], old['content']['gameContextSetIds'])
        self.assertEqual(rows[0]['starts_at'], '2026-01-01 14:00:00.000000')  # Tournament, not event time.
        self.assertEqual(rows[0]['owner_startgg_user_id'], 77)
        self.assertEqual(rows[2]['slug'], None); self.assertEqual(rows[2]['starts_at'], None)
        self.assertTrue(self.check_php(p)['ok'])
        reversed_source = catalog()[::-1]; reversed_source[1]['events'].reverse()
        self.assertEqual(p, package(source=reversed_source))
        self.assertTrue(self.check_php(package(source=[]))['ok'])

    def test_null_absent_and_legacy_pinned_hashes(self):
        raw, public = fixtures.fixture(); base = build_package(raw, public)
        raw['tournamentCatalog'] = None
        self.assertEqual(base, build_package(raw, public))
        for p, expected in ((base, '83d408314770e33bb7906bad9a71b1094fd9b69a970209025cbb4f10f2b922a7'),
                            (fixtures.legacy_package(base), 'fe6396196b208f0e2bd01e0af72336b9a6566ead6761749f0637ec8bd6f029d2')):
            before = canonical(p); validate_package(p)
            self.assertEqual(p['sha256'], expected); self.assertEqual(before, canonical(p))
            self.assertEqual(self.check_php(p)['result']['sha256'], expected)

    def test_rehashed_invalid_catalog_rejected_by_both_validators(self):
        for kind in ('duplicate', 'owner', 'big_id', 'id_type', 'name', 'city', 'event_name', 'slug',
                     'ascii', 'reason', 'entrants', 'timestamp', 'date', 'inconsistent', 'columns', 'missing', 'object', 'legacy'):
            p = package(); c = p['content']; rows = c['tournamentCatalog']; r = rows[0]
            if kind == 'duplicate': rows.append(copy.deepcopy(r))
            if kind == 'owner': r['owner_startgg_user_id'] = 0
            if kind == 'big_id': r['event_id'] = 9223372036854775808
            if kind == 'id_type': r['event_id'] = '100'
            if kind == 'name': r['tournament_name'] = 'a' * 256
            if kind == 'city': r['city'] = 'Á' * 121
            if kind == 'event_name': r['event_name'] = 'a' * 256
            if kind == 'slug': r['slug'] = 'event/wrong'
            if kind == 'ascii': r['slug'] = 'tournament/ñ'
            if kind == 'reason': r['reason'] = 'made_up'
            if kind == 'entrants': r['entrants'] = -1
            if kind == 'timestamp': r['captured_at'] = '2026-10-03 00:00:00.000000'
            if kind == 'date': r['starts_at'] = '2026-02-30 00:00:00.000000'
            if kind == 'inconsistent': rows[1]['owner_startgg_user_id'] = 78
            if kind == 'columns': r['extra'] = 'ignored?'
            if kind == 'missing': del c['tournamentCatalog']
            if kind == 'object': c['tournamentCatalog'] = {}
            if kind == 'legacy': c['packageVersion'] = 2
            p['sha256'] = digest(c)
            with self.subTest(kind=kind):
                with self.assertRaises((ValueError, KeyError)): validate_package(p)
                self.assertFalse(self.check_php(p)['ok'])

    def test_exporter_rejects_malformed_capture_without_silent_empty_replacement(self):
        for kind in ('object', 'duplicate_tournament', 'duplicate_event', 'reason', 'long_slug', 'id'):
            source = catalog()
            if kind == 'object': source = {}
            if kind == 'duplicate_tournament': source.append(copy.deepcopy(source[0]))
            if kind == 'duplicate_event': source[1]['events'][0]['id'] = '100'
            if kind == 'reason': source[0]['events'][0]['reason'] = 'wrong'
            if kind == 'long_slug': source[0]['slug'] = 'tournament/' + 'x' * 255
            if kind == 'id': source[0]['ownerId'] = True
            with self.subTest(kind=kind), self.assertRaises(ValueError): package(source=source)


@unittest.skipUnless(hosting.PHP and os.environ.get('SMASH_SCHEMA_TEST_DB'), 'Disposable SQL service required')
class CatalogSQLTests(unittest.TestCase):
    @classmethod
    def install(cls):
        with cls.db.cursor() as cursor:
            cursor.execute(MIGRATION.read_text())
            while cursor.nextset(): pass

    @classmethod
    def setUpClass(cls):
        fixtures.ImportTests.setUpClass.__func__(cls)
        cls.install()

    @classmethod
    def tearDownClass(cls): cls.db.close()

    clear_core = hosting.HostingSQLTests.clear
    run_package = hosting.HostingSQLTests.run_package
    core_snapshot = hosting.HostingSQLTests.snapshot

    def clear(self):
        self.db.rollback()
        sql(self.db, 'DROP TRIGGER IF EXISTS corrupt_catalog_test')
        self.install(); self.clear_core(); sql(self.db, 'DELETE FROM tournament_catalog'); self.db.commit()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name).resolve(); self.path = self.folder / 'package.json'
        self.clear()

    def tearDown(self): self.clear()

    def apply(self, importer, p, apply=True):
        if importer == 'python': return import_package(self.db, p, apply=apply)
        out = self.run_package(p, 'apply' if apply else 'dry'); self.assertTrue(out['ok'], out)
        return out['result']

    def catalog_rows(self):
        return sql(self.db, 'SELECT ' + CATALOG_COLUMNS.replace(' ', ',') + ' FROM tournament_catalog ORDER BY tournament_id,event_id')

    def test_replacement_parity_replay_and_empty_catalog(self):
        comparisons = []
        source = catalog(); source[0]['events'].pop(); source[0]['ownerId'] = None
        source[0]['city'] = 'Quetzaltenango'; source.pop()
        first, second = package(), package(SECOND, source)
        for importer in ('python', 'php'):
            with self.subTest(importer=importer):
                self.clear()
                self.assertEqual(self.apply(importer, first, False)['catalog'], dict(status='ready', rows=3))
                self.assertEqual(self.catalog_rows(), ())
                self.assertEqual(self.apply(importer, first)['catalog'], dict(status='replaced', rows=3))
                self.assertEqual(len(self.catalog_rows()), 3)
                initial = sql(self.db, 'SELECT source_hash,public_snapshot FROM cuts ORDER BY id')
                self.assertEqual(self.apply(importer, second)['catalog'], dict(status='replaced', rows=1))
                self.assertEqual(len(self.catalog_rows()), 1)
                self.assertEqual(initial[0], sql(self.db, 'SELECT source_hash,public_snapshot FROM cuts ORDER BY id')[0])
                before = self.catalog_rows()
                for p in (first, second):
                    report = self.apply(importer, p)
                    self.assertEqual(report['status'], 'already_imported')
                    self.assertEqual(report['catalog']['status'], 'not_reapplied')
                    self.assertEqual(before, self.catalog_rows())
                comparisons.append((self.core_snapshot(compare_importers=True), before))
                self.assertEqual(self.apply(importer, package('2026-10-18T06:00:00Z', []))['catalog'], dict(status='replaced', rows=0))
                self.assertEqual(self.catalog_rows(), ())
        self.assertEqual(*comparisons)

    def test_null_absent_v1_v2_preserve_catalog_and_hashes(self):
        for importer in ('python', 'php'):
            with self.subTest(importer=importer):
                self.clear(); self.apply(importer, package()); before = self.catalog_rows()
                for i, kind in enumerate(('null', 'absent', 'v1', 'v2')):
                    raw, public = fixtures.fixture(f'2026-10-{11+i:02}T06:00:00Z')
                    if kind == 'null': raw['tournamentCatalog'] = None
                    p = build_package(raw, public)
                    if kind == 'v1': p = fixtures.legacy_package(p)
                    self.assertEqual(self.apply(importer, p)['catalog']['status'], 'not_in_package')
                    self.assertEqual(self.apply(importer, p)['status'], 'already_imported')
                    self.assertEqual(before, self.catalog_rows())
                    self.assertEqual(sql(self.db, 'SELECT source_hash FROM cuts ORDER BY id DESC LIMIT 1')[0][0], p['sha256'])

    def test_missing_migration_imports_cut_and_replay_after_install_does_not_backfill(self):
        for importer in ('python', 'php'):
            with self.subTest(importer=importer):
                self.clear(); sql(self.db, 'DROP TABLE tournament_catalog')
                sql(self.db, "DELETE FROM schema_migrations WHERE version='005_organizer_tops'")
                first = package()
                self.assertEqual(self.apply(importer, first, False)['catalog']['status'], 'migration_missing')
                report = self.apply(importer, first)
                self.assertEqual(report['status'], 'imported'); self.assertEqual(report['catalog']['status'], 'migration_missing')
                self.assertEqual(self.apply(importer, first)['status'], 'already_imported')
                self.assertEqual(sql(self.db, 'SELECT source_hash FROM cuts')[0][0], first['sha256'])
                self.install()
                self.assertEqual(self.apply(importer, first)['status'], 'already_imported')
                self.assertEqual(self.catalog_rows(), ())
                self.assertEqual(self.apply(importer, package(SECOND))['catalog']['status'], 'replaced')

    def test_unmarked_table_is_untouched_and_broken_installed_schema_fails_safely(self):
        for importer in ('python', 'php'):
            with self.subTest(importer=importer):
                self.clear(); self.apply(importer, package()); before = self.catalog_rows()
                sql(self.db, "DELETE FROM schema_migrations WHERE version='005_organizer_tops'")
                self.assertEqual(self.apply(importer, package(SECOND))['catalog']['status'], 'migration_missing')
                self.assertEqual(before, self.catalog_rows())
                self.install(); sql(self.db, 'DROP TABLE tournament_catalog')
                third = package('2026-10-18T06:00:00Z')
                if importer == 'python':
                    with self.assertRaises(ValueError): import_package(self.db, third, apply=True)
                else: self.assertEqual(self.run_package(third)['reason'], 'schema_invalid')
                self.assertEqual(sql(self.db, 'SELECT COUNT(*) FROM cuts')[0][0], 2)

    def test_catalog_and_cut_rollback_together_including_catalog_parity_failure(self):
        for importer in ('python', 'php'):
            for fault in ('ranking', 'catalog'):
                with self.subTest(importer=importer, fault=fault):
                    self.clear(); self.apply(importer, package())
                    before = (self.core_snapshot(), self.catalog_rows())
                    if fault == 'ranking':
                        sql(self.db, "CREATE TRIGGER reject_hosting_test BEFORE INSERT ON rankings FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='test-only'")
                    else:
                        sql(self.db, "CREATE TRIGGER corrupt_catalog_test BEFORE INSERT ON tournament_catalog FOR EACH ROW SET NEW.city='test-only-corruption'")
                    p = package(SECOND, catalog()[:1])
                    if importer == 'python':
                        with self.assertRaises(Exception): import_package(self.db, p, apply=True)
                    else: self.assertFalse(self.run_package(p)['ok'])
                    self.assertEqual(before, (self.core_snapshot(), self.catalog_rows()))

    def test_real_receiver_queue_worker_with_and_without_migration(self):
        for installed in (True, False):
            with self.subTest(installed=installed):
                self.clear()
                if not installed:
                    sql(self.db, 'DROP TABLE tournament_catalog')
                    sql(self.db, "DELETE FROM schema_migrations WHERE version='005_organizer_tops'")
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory).resolve(); site = root / 'site'; private = root / 'private-smash'
                    site.mkdir(); private.mkdir(); (site / 'data').mkdir()
                    for name in ('database.php', 'ranking-import.php', 'ranking-sync-lib.php', 'ranking-sync.php', 'characters.js'):
                        shutil.copy(fixtures.ROOT / 'ranking-smash-ultimate' / name, site)
                    key = '1' * 64
                    (private / 'sync.local.php').write_text("<?php return ['enabled'=>true,'key'=>'" + key + "'];")
                    config = dict(database=dict(host='127.0.0.1', port=int(os.environ.get('SMASH_SCHEMA_TEST_PORT', 3306)),
                        name=os.environ['SMASH_SCHEMA_TEST_DB'], user='root', password=os.environ['SMASH_SCHEMA_TEST_PASSWORD']))
                    (private / 'config.local.php').write_text("<?php return json_decode('" + json.dumps(config) + "',true);")
                    p = package(); (site / 'data/public.json').write_text(canonical(p['content']['public']))
                    with socket.socket() as sock: sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
                    process = subprocess.Popen([hosting.PHP, '-S', f'127.0.0.1:{port}', '-t', str(site)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    try:
                        for _ in range(100):
                            try:
                                with socket.create_connection(('127.0.0.1', port), timeout=.1): break
                            except OSError: time.sleep(.02)
                        body = sender.transport(p)
                        self.assertLess(len(body), 4*1024*1024); self.assertLess(len(canonical(p).encode()), 32*1024*1024)
                        def fetch(payload, content_type='application/gzip'):
                            at = str(int(time.time())); nonce = __import__('secrets').token_hex(16)
                            headers = {'Content-Type': content_type, 'X-Smash-Timestamp': at, 'X-Smash-Nonce': nonce,
                                'X-Smash-Signature': sender.signature(key, at, nonce, payload)}
                            req = urllib.request.Request(f'http://127.0.0.1:{port}/ranking-sync.php', data=payload, headers=headers)
                            with urllib.request.urlopen(req, timeout=5) as response: return response.status, json.loads(response.read())
                        code, queued = fetch(body); self.assertEqual(code, 202); self.assertEqual(queued['status'], 'queued')
                        self.assertEqual(fetch(body)[1]['jobId'], queued['jobId'])
                        report = hosting.bridge('worker', site, private)
                        self.assertTrue(report['ok'], report); self.assertEqual(report['result']['status'], 'imported')
                        self.assertEqual(report['result']['catalog'], dict(status='replaced' if installed else 'migration_missing', rows=3))
                        self.assertLess(report['result']['peakMemoryBytes'], 512*1024*1024)
                        self.assertEqual(sql(self.db, 'SELECT status FROM sync_jobs'), (('succeeded',),))
                        self.assertEqual(sql(self.db, 'SELECT source_hash FROM cuts')[0][0], p['sha256'])
                        self.assertEqual(fetch(body)[1]['status'], 'succeeded')
                        if installed: self.assertEqual(len(self.catalog_rows()), 3)
                        else:
                            self.assertEqual(sql(self.db, "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name='tournament_catalog'")[0][0], 0)
                        self.assertEqual(list((private / 'ranking-inbox').glob('*.json.gz')), [])
                    finally:
                        process.terminate(); process.wait(timeout=5)

    def test_large_v3_worker_within_transport_and_memory_limits(self):
        def large(raw):
            match = raw['sets']['500']; template = match['games'][0]
            match['games'] = [dict(template, id=10000+i) for i in range(5000)]
            raw['tournamentCatalog'] = [dict(id=str(20000+i), name=f'Torneo de prueba {i}',
                slug=f'tournament/test-{i}', startAt=1767276000, city=None, ownerId=None,
                events=[dict(id=str(30000+i), name='Singles', numEntrants=20, reason=None)]) for i in range(1000)]
        p = build_package(*fixtures.fixture(mutate=large))
        data = self.folder / 'data'; data.mkdir(); (data / 'public.json').write_text(canonical(p['content']['public']))
        raw_size = len(canonical(p).encode()); gzip_size = len(sender.transport(p))
        self.assertLess(raw_size, sender.MAX_BYTES); self.assertLess(gzip_size, sender.COMPRESSED_MAX)
        hosting.HostingSQLTests.queue(self, p)
        start = time.monotonic(); report = hosting.bridge('worker', self.folder, self.folder)
        self.assertTrue(report['ok'], report); self.assertEqual(report['result']['status'], 'imported')
        self.assertEqual(report['result']['catalog'], dict(status='replaced', rows=1000))
        self.assertEqual(sql(self.db, 'SELECT COUNT(*) FROM games')[0][0], 5000)
        self.assertEqual(sql(self.db, 'SELECT COUNT(*) FROM game_selections')[0][0], 10000)
        self.assertEqual(len(self.catalog_rows()), 1000)
        self.assertLess(report['result']['peakMemoryBytes'], 512*1024*1024)
        print(json.dumps(dict(test='synthetic_v3_worker', canonicalBytes=raw_size, gzipBytes=gzip_size,
            peakMemoryBytes=report['result']['peakMemoryBytes'], seconds=round(time.monotonic()-start, 3))))


if __name__ == '__main__': unittest.main(verbosity=2)
