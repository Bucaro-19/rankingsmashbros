"""PHP/Python parity and authenticated hosting transport. Invented/disposable data only."""
import copy
import gzip
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import socket
import time
import urllib.request
import urllib.error
import unittest
from unittest import mock

from ranking_package import build_package, canonical, digest
from test_import_ranking import fixture, ROOT, legacy_package, corrected_games
from import_ranking import sql, import_package
from test_weekly_ranking_load import linked, FIRST, SECOND
import publish_sql as sender

PHP = shutil.which('php')
BRIDGE = ROOT / 'scripts/database/php_ranking_bridge.php'
TABLES = ('player_characters', 'rankings', 'cut_set_results', 'cut_events', 'cuts', 'game_selections', 'games', 'set_slots', 'sets', 'entrant_players', 'entrants', 'events', 'tournaments', 'players')


def bridge(mode, path, *args):
    out = subprocess.run([PHP, '-d', 'memory_limit=512M', str(BRIDGE), mode, str(path), *map(str, args)], capture_output=True, text=True, timeout=90)
    if out.stderr: raise AssertionError('PHP emitted an unexpected diagnostic')
    return json.loads(out.stdout)


@unittest.skipUnless(PHP, 'PHP CLI required')
class ContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'package.json'; self.package = build_package(*fixture())

    def check(self, package=None, raw=None):
        self.path.write_text(raw if raw is not None else canonical(package or self.package))
        return bridge('validate', self.path)

    def test_php_accepts_exact_canonical_python_hash_and_unicode(self):
        self.assertEqual(self.check()['result']['sha256'], self.package['sha256'])
        changed = copy.deepcopy(self.package)
        changed['content']['limitations'].append({'emptyObject': {}, 'emptyArray': [], 'unicode': '\u2028😀 / ñ'})
        changed['sha256'] = digest(changed['content'])
        self.assertEqual(self.check(changed)['result']['sha256'], changed['sha256'])
        self.assertEqual(gzip.decompress(sender.transport(changed)).decode(), canonical(changed))

    def test_event_set_totals_can_exceed_ranked_players_results(self):
        # Public ledger omits matches between players outside the ranking.
        p = copy.deepcopy(self.package)
        for v in (p['content']['public'], p['content']['public']['localRanking']):
            v['events'][0]['validSets'] += 1; v['counts']['sets'] += 1
        p['sha256'] = digest(p['content'])
        self.assertTrue(self.check(p)['ok'])

    def test_invalid_relations_and_activity_with_recomputed_hash_are_rejected(self):
        for kind in ('entrant', 'winner', 'activity', 'mains', 'rank', 'local', 'previous', 'hash'):
            p = copy.deepcopy(self.package); c = p['content']; v = c['public']
            if kind == 'entrant': c['entities']['entrants'][0]['event_id'] = 102
            if kind == 'winner': c['entities']['sets'][0]['winner_entrant_id'] = 999
            if kind == 'activity': v['players'][0]['activity']['events'][0]['wins'] += 1
            if kind == 'mains': v['players'][0]['mains'][0]['games'] += 1
            if kind == 'rank': v['players'][0]['rank'] = 2
            if kind == 'local': v['localRanking']['events'][0]['country'] = 'MX'
            if kind == 'previous': v['players'][0]['previousRank'] = 1
            if kind != 'hash': p['sha256'] = digest(c)
            else: p['sha256'] = '0' * 64
            with self.subTest(kind=kind): self.assertFalse(self.check(p)['ok'])


    def test_game_relations_catalog_and_published_mains_reject_in_both_languages(self):
        from ranking_package import validate_package
        for kind in ('set','winner','entrant','character','number','duplicate','ambiguous','coverage','time','missing_selection'):
            p = copy.deepcopy(self.package); c = p['content']; t = c['entities']; g = t['games'][0]; r = t['game_selections'][0]
            if kind == 'set': g['set_id'] = 999
            if kind == 'winner': g['winner_entrant_id'] = 1011
            if kind == 'entrant': r['entrant_id'] = 1011
            if kind == 'character': r['character_id'] = 999999
            if kind == 'number': g['game_number'] = 0
            if kind == 'duplicate': t['games'].append(copy.deepcopy(g))
            if kind == 'ambiguous': t['game_selections'].append(dict(r, character_id=1302))
            if kind == 'coverage': c['gameContextSetIds'].append(999)
            if kind == 'time': g['synced_at'] = '2026-10-01 00:00:00.000000'
            if kind == 'missing_selection': t['game_selections'].pop()
            p['sha256'] = digest(c)
            with self.subTest(kind=kind):
                with self.assertRaises((ValueError,KeyError)): validate_package(p)
                self.assertFalse(self.check(p)['ok'])
        self.assertTrue(self.check(legacy_package(self.package))['ok'])
        random = build_package(*fixture(mutate=lambda raw: raw['sets']['500']['games'][0]['selections'][0]['character'].update(id=1746,name='Random Character')))
        self.assertTrue(self.check(random)['ok'])
    def test_noncanonical_duplicate_keys_and_float_hashes_stop(self):
        self.assertFalse(self.check(raw=json.dumps(self.package))['ok'])
        self.assertFalse(self.check(raw=canonical(self.package).replace('"packageVersion":2', '"packageVersion":2,"packageVersion":2'))['ok'])
        p = copy.deepcopy(self.package); p['content']['extra'] = 1.0; p['sha256'] = digest(p['content'])
        self.assertFalse(self.check(p)['ok'])
        with self.assertRaises(sender.SyncStopped): sender.transport(p)

    def test_hmac_matches_php_and_rejects_tampering_expiry_and_replay(self):
        key, at, nonce, body = '1' * 64, '1791350000', '2' * 32, 'payload'
        headers = {'HTTP_X_SMASH_TIMESTAMP': at, 'HTTP_X_SMASH_NONCE': nonce, 'HTTP_X_SMASH_SIGNATURE': sender.signature(key, at, nonce, body.encode())}
        value = {'key': key, 'headers': headers, 'body': body, 'now': int(at)}
        self.path.write_text(json.dumps(value)); self.assertTrue(bridge('auth', self.path)['ok'])
        for change in ('body', 'timestamp', 'nonce'):
            altered = copy.deepcopy(value)
            if change == 'body': altered['body'] += '!'
            if change == 'timestamp': altered['now'] += 301
            if change == 'nonce': altered['headers']['HTTP_X_SMASH_NONCE'] = '3' * 32
            self.path.write_text(json.dumps(altered)); self.assertEqual(bridge('auth', self.path)['reason'], 'unauthorized')
        value['private'] = self.temp.name; self.path.write_text(json.dumps(value))
        self.assertEqual(bridge('auth', self.path)['reason'], 'replayed_request')

    def test_sender_requires_import_success_and_sanitizes_failures(self):
        with mock.patch.object(sender, 'request', side_effect=[{'ok': True, 'status': 'queued', 'jobId': 2}, {'ok': True, 'status': 'succeeded', 'jobId': 2}]):
            self.assertEqual(sender.deliver('1' * 64, b'body', pause=lambda _: None)['status'], 'sql_synchronized')
        for status in ('failed', 'unknown'):
            with mock.patch.object(sender, 'request', return_value={'status': status}), self.assertRaises(sender.SyncStopped): sender.deliver('1' * 64, b'body')
        with mock.patch.object(sender, 'request', return_value={'status': 'queued'}), self.assertRaises(sender.SyncStopped): sender.deliver('1' * 64, b'body', wait_seconds=0)


@unittest.skipUnless(PHP and os.environ.get('SMASH_SCHEMA_TEST_DB'), 'Disposable SQL service required')
class HostingSQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from test_import_ranking import ImportTests
        ImportTests.setUpClass.__func__(cls)
    @classmethod
    def tearDownClass(cls): cls.db.close()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name).resolve(); self.path = self.folder / 'package.json'
        self.clear()

    def clear(self):
        self.db.rollback(); sql(self.db, 'DROP TRIGGER IF EXISTS reject_hosting_test'); sql(self.db, 'UPDATE rankings SET previous_cut_id=NULL')
        sql(self.db, "DELETE FROM sync_jobs WHERE kind='ranking_import'")
        for t in TABLES: sql(self.db, 'DELETE FROM `' + t + '`')
        sql(self.db, 'ALTER TABLE cuts AUTO_INCREMENT=1'); self.db.commit()

    def tearDown(self): self.clear()

    def run_package(self, p, mode='apply'):
        self.path.write_text(canonical(p)); return bridge(mode, self.path)

    def snapshot(self, *, compare_importers=False):
        found = {}
        for t in TABLES:
            ignored = {'imported_at'}
            if compare_importers and t == 'players':
                # SQL generates this wall-clock timestamp independently for
                # each import. All package/source dates remain in the comparison;
                # rollback/conflict snapshots still include these columns.
                ignored.add('updated_at')
            columns = [r[0] for r in sql(self.db, 'SHOW COLUMNS FROM `' + t + '`') if r[0] not in ignored]
            found[t] = sorted(sql(self.db, 'SELECT `' + '`,`'.join(columns) + '` FROM `' + t + '`'), key=repr)
        return found

    def test_python_php_identical_tables_first_repeat_and_linked_second_cut(self):
        first, second = build_package(*fixture()), linked(SECOND, FIRST)
        import_package(self.db, first, apply=True); import_package(self.db, second, apply=True); expected = self.snapshot(compare_importers=True)
        self.clear()
        self.assertEqual(self.run_package(first, 'dry')['result']['status'], 'validated_no_writes')
        self.assertEqual(sql(self.db, 'SELECT COUNT(*) FROM cuts')[0][0], 0)
        for p in (first, second):
            self.assertEqual(self.run_package(p)['result']['status'], 'imported')
            self.assertEqual(self.run_package(p)['result']['status'], 'already_imported')
        self.assertEqual(expected, self.snapshot(compare_importers=True))

    def test_failure_mid_write_rolls_back_and_conflict_preserves_history(self):
        first = build_package(*fixture())
        sql(self.db, "CREATE TRIGGER reject_hosting_test BEFORE INSERT ON rankings FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='test-only'")
        self.assertFalse(self.run_package(first)['ok']); self.assertEqual(sql(self.db, 'SELECT COUNT(*) FROM cuts')[0][0], 0)
        self.assertEqual(sql(self.db, 'SELECT COUNT(*) FROM players')[0][0], 0)
        sql(self.db, 'DROP TRIGGER reject_hosting_test'); self.assertTrue(self.run_package(first)['ok']); before = self.snapshot()
        changed = copy.deepcopy(first); changed['content']['public']['players'][0]['rating'] += 1; changed['sha256'] = digest(changed['content'])
        self.assertEqual(self.run_package(changed)['reason'], 'cut_conflict'); self.assertEqual(before, self.snapshot())


    def test_corrections_replace_context_keep_snapshots_and_replay_cannot_revert(self):
        first = build_package(*fixture()); second = build_package(*fixture(SECOND, mutate=corrected_games))
        comparisons = []
        for importer in ('python','php'):
            with self.subTest(importer=importer):
                self.clear()
                def apply(p):
                    if importer == 'python': return import_package(self.db,p,apply=True)
                    result = self.run_package(p); self.assertTrue(result['ok'],result); return result['result']
                initial = apply(first)
                old_snapshot = sql(self.db,'SELECT public_snapshot,source_hash FROM cuts WHERE id=%s',(initial['cutId'],))
                self.assertEqual(apply(second)['status'],'imported')
                self.assertEqual(sql(self.db,'SELECT id,winner_entrant_id FROM games ORDER BY id'),((9000,1002),(9001,1001)))
                self.assertEqual(sql(self.db,'SELECT game_id,entrant_id,character_id FROM game_selections ORDER BY game_id,entrant_id'),
                    ((9000,1001,1302),(9000,1002,1319),(9001,1002,1319)))
                self.assertEqual(old_snapshot,sql(self.db,'SELECT public_snapshot,source_hash FROM cuts WHERE id=%s',(initial['cutId'],)))
                before = self.snapshot()
                for p in (first,second): self.assertEqual(apply(p)['status'],'already_imported')
                self.assertEqual(before,self.snapshot())
                comparisons.append(self.snapshot(compare_importers=True))
        self.assertEqual(*comparisons)

    def test_empty_and_invalidated_sets_clear_old_games_in_both_importers(self):
        for change in ('empty','dq'):
            def mutate(raw):
                if change == 'empty': raw['sets']['500']['games'] = []
                else: raw['sets']['500']['displayScore'] = 'DQ'; raw['sets']['500']['winnerId'] = None
            second = build_package(*fixture(SECOND, mutate=mutate))
            for importer in ('python','php'):
                with self.subTest(change=change, importer=importer):
                    self.clear(); first=build_package(*fixture()); import_package(self.db,first,apply=True)
                    if importer == 'python': import_package(self.db,second,apply=True)
                    else: self.assertTrue(self.run_package(second)['ok'])
                    for t in ('games','game_selections'): self.assertEqual(sql(self.db,'SELECT COUNT(*) FROM '+t)[0][0],0)
                    self.assertEqual(sql(self.db,'SELECT COUNT(*) FROM player_characters WHERE cut_id=1')[0][0],4)
                    self.assertEqual(sql(self.db,'SELECT source_hash FROM cuts WHERE id=1')[0][0],first['sha256'])

    def test_uncaptured_competitive_set_keeps_prior_context(self):
        def abroad(raw):
            raw['sets']['504']['games'] = [dict(id=9500,winnerId=1022,selections=[
                dict(entrant=dict(id=1021),character=dict(id=1302,name='Mario')),
                dict(entrant=dict(id=1022),character=dict(id=1319,name='Pikachu'))])]
        first = build_package(*fixture(mutate=abroad))
        raw, public = fixture(SECOND)
        local = copy.deepcopy(public['localRanking'])
        public = dict(local, status='international_pilot',rankingScope='combined',localRanking=local)
        second = build_package(raw,public)
        self.assertNotIn(504,second['content']['gameContextSetIds'])
        for importer in ('python','php'):
            self.clear(); import_package(self.db,first,apply=True)
            if importer == 'python': import_package(self.db,second,apply=True)
            else: self.assertTrue(self.run_package(second)['ok'])
            self.assertEqual(sql(self.db,'SELECT id FROM games WHERE set_id=504'),((9500,),))

    def test_game_collision_changed_slots_and_failed_cut_rollback_existing_context(self):
        for kind in ('collision','slots','failure','older'):
            for importer in ('python','php'):
                with self.subTest(kind=kind, importer=importer):
                    self.clear(); first = build_package(*fixture()); import_package(self.db,first,apply=True)
                    def mutate(raw):
                        if kind == 'collision': raw['sets']['501']['games'] = raw['sets']['500']['games']; raw['sets']['500']['games'] = []
                        else: corrected_games(raw)
                        if kind == 'slots':
                            for m in raw['sets'].values():
                                if m['event']['id'] != 100: continue
                                m['slots'][0]['entrant']['id'] = 1003
                                if m['winnerId'] == 1001: m['winnerId'] = 1003
                                for g in m['games']:
                                    if g['winnerId'] == 1001: g['winnerId'] = 1003
                                    for r in g['selections']:
                                        if r['entrant']['id'] == 1001: r['entrant']['id'] = 1003
                    second = build_package(*fixture(SECOND if kind != 'older' else '2026-10-01T06:00:00Z', mutate=mutate))
                    before = self.snapshot()
                    if kind == 'failure': sql(self.db, "CREATE TRIGGER reject_hosting_test BEFORE INSERT ON rankings FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='test-only'")
                    if importer == 'python':
                        with self.assertRaises(Exception): import_package(self.db,second,apply=True)
                    else: self.assertFalse(self.run_package(second)['ok'])
                    self.assertEqual(before,self.snapshot())

    def test_legacy_v1_new_v2_repeat_preserves_context_and_catalog_checked_in_sql(self):
        first = legacy_package(build_package(*fixture())); second = build_package(*fixture(SECOND))
        for importer in ('python','php'):
            self.clear()
            def apply(p):
                if importer == 'python': return import_package(self.db,p,apply=True)
                result = self.run_package(p); self.assertTrue(result['ok'],result); return result['result']
            apply(first); self.assertEqual(sql(self.db,'SELECT COUNT(*) FROM games')[0][0],0)
            apply(second); before = self.snapshot()
            self.assertEqual(apply(first)['status'],'already_imported'); self.assertEqual(before,self.snapshot())
        self.clear(); sql(self.db,'DELETE FROM characters WHERE id=1746')
        try:
            random = build_package(*fixture(mutate=lambda raw: raw['sets']['500']['games'][0]['selections'][0]['character'].update(id=1746,name='Random Character')))
            with self.assertRaises(ValueError): import_package(self.db,random,apply=True)
            self.assertEqual(self.run_package(random)['reason'],'character_missing')
            self.assertEqual(sql(self.db,'SELECT COUNT(*) FROM cuts')[0][0],0)
        finally:
            with self.db.cursor() as cursor:
                cursor.execute((ROOT/'docs/smash/seed-characters.sql').read_text())
                while cursor.nextset(): pass
            self.db.commit()

    def queue(self, p):
        body = sender.transport(p); hash_ = __import__('hashlib').sha256(body).hexdigest()
        inbox = self.folder / 'ranking-inbox'; inbox.mkdir(exist_ok=True); (inbox / (hash_ + '.json.gz')).write_bytes(body)
        sql(self.db, "INSERT INTO sync_jobs(kind,deduplication_key) VALUES('ranking_import',%s)", (hash_,)); self.db.commit()
        return hash_

    def worker(self): return bridge('worker', self.folder, self.folder)

    def test_worker_with_5000_games_stays_within_transport_and_memory_limits(self):
        def large(raw):
            m = raw['sets']['500']; template = m['games'][0]
            m['games'] = [dict(template, id=10000+i) for i in range(5000)]
        package = build_package(*fixture(mutate=large))
        body = sender.transport(package)
        self.assertLess(len(body), sender.COMPRESSED_MAX)
        self.assertLess(len(canonical(package).encode()), sender.MAX_BYTES)
        self.queue(package); data = self.folder/'data'; data.mkdir()
        (data/'public.json').write_text(canonical(package['content']['public']))
        report = self.worker()
        self.assertTrue(report['ok'], report); self.assertEqual(report['result']['status'], 'imported')
        self.assertLess(report['result']['peakMemoryBytes'], 512*1024*1024)
        self.assertEqual(sql(self.db,'SELECT COUNT(*) FROM games')[0][0],5000)
        self.assertEqual(sql(self.db,'SELECT COUNT(*) FROM game_selections')[0][0],10000)

    def test_worker_requires_live_cut_recovers_interruption_and_cleans_success(self):
        first = build_package(*fixture()); hash_ = self.queue(first)
        data = self.folder / 'data'; data.mkdir(); (data / 'public.json').write_text(canonical(fixture(SECOND)[1]))
        self.assertEqual(self.worker()['result']['reason'], 'not_the_published_cut')
        self.assertEqual(sql(self.db, 'SELECT COUNT(*) FROM cuts')[0][0], 0)
        sql(self.db, "UPDATE sync_jobs SET status='running',next_attempt_at=NULL WHERE deduplication_key=%s", (hash_,))
        (data / 'public.json').write_text(canonical(first['content']['public']))
        self.assertEqual(self.worker()['result']['status'], 'imported')
        self.assertFalse((self.folder / 'ranking-inbox' / (hash_ + '.json.gz')).exists())
        self.assertEqual(sql(self.db, 'SELECT status FROM sync_jobs')[0][0], 'succeeded')
        self.assertEqual(self.worker()['result']['status'], 'idle')

    def test_missing_previous_and_unfinished_cut_stop_without_partial_rows(self):
        first = build_package(*fixture()); self.assertTrue(self.run_package(first)['ok'])
        second = linked(SECOND, '2026-10-05T00:00:00Z')
        self.assertEqual(self.run_package(second)['reason'], 'previous_cut_missing')
        self.assertEqual(sql(self.db, 'SELECT COUNT(*) FROM cuts')[0][0], 1)
        sql(self.db, "UPDATE cuts SET status='importing'")
        self.assertEqual(self.run_package(linked(SECOND, FIRST))['reason'], 'unfinished_cut_present')

    def test_real_http_authentication_queue_deduplication_and_worker(self):
        site, private = self.folder / 'site', self.folder / 'private-smash'
        site.mkdir(); private.mkdir(); (site / 'data').mkdir()
        for filename in ('database.php', 'ranking-import.php', 'ranking-sync-lib.php', 'ranking-sync.php', 'characters.js'):
            shutil.copy(ROOT / 'ranking-smash-ultimate' / filename, site)
        key = '1' * 64
        (private / 'sync.local.php').write_text("<?php return ['enabled'=>true,'key'=>'" + key + "'];")
        config = dict(database=dict(host='127.0.0.1', port=int(os.environ.get('SMASH_SCHEMA_TEST_PORT', 3306)), name=os.environ['SMASH_SCHEMA_TEST_DB'], user='root', password=os.environ['SMASH_SCHEMA_TEST_PASSWORD']))
        (private / 'config.local.php').write_text("<?php return json_decode('" + json.dumps(config) + "',true);")
        package = build_package(*fixture()); (site / 'data/public.json').write_text(canonical(package['content']['public']))
        with socket.socket() as sock: sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
        process = subprocess.Popen([PHP, '-S', f'127.0.0.1:{port}', '-t', str(site)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(lambda: (process.terminate(), process.wait(timeout=5)))
        for _ in range(100):
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=.1): break
            except OSError: time.sleep(.02)
        def fetch(body=None, headers=None, path='ranking-sync.php'):
            req = urllib.request.Request(f'http://127.0.0.1:{port}/' + path, data=body, headers=headers or {})
            try: response = urllib.request.urlopen(req, timeout=5)
            except urllib.error.HTTPError as e: response = e
            with response: return response.status, json.loads(response.read()) if path == 'ranking-sync.php' else None
        def signed(body, nonce=None, type_='application/gzip'):
            at = str(int(time.time())); nonce = nonce or __import__('secrets').token_hex(16)
            return {'Content-Type': type_, 'X-Smash-Timestamp': at, 'X-Smash-Nonce': nonce, 'X-Smash-Signature': sender.signature(key, at, nonce, body)}
        self.assertEqual(fetch()[0], 405)
        self.assertEqual(fetch(b'unsigned')[0], 401)
        self.assertEqual(sql(self.db, 'SELECT COUNT(*) FROM sync_jobs')[0][0], 0)
        body = sender.transport(package); headers = signed(body)
        code, response = fetch(body, headers); self.assertEqual(code, 202); self.assertEqual(response['status'], 'queued')
        self.assertEqual(fetch(body, headers)[0], 409)
        self.assertEqual(fetch(body + b'!', signed(body))[0], 401)
        self.assertEqual(fetch(body, signed(body))[1]['jobId'], response['jobId'])
        self.assertEqual(sql(self.db, 'SELECT COUNT(*) FROM sync_jobs')[0][0], 1)
        self.assertEqual(bridge('worker', site, private)['result']['status'], 'imported')
        hash_ = __import__('hashlib').sha256(body).hexdigest()
        status_body = canonical({'operation': 'status', 'sha256': hash_}).encode()
        self.assertEqual(fetch(status_body, signed(status_body, type_='application/json'))[1]['status'], 'succeeded')
        self.assertEqual(fetch(body, signed(body))[1]['status'], 'succeeded')
        self.assertEqual(fetch(path='ranking-inbox/' + hash_ + '.json.gz')[0], 404)
        self.assertEqual(sql(self.db, 'SELECT COUNT(*) FROM cuts')[0][0], 1)


if __name__ == '__main__': unittest.main(verbosity=2)
