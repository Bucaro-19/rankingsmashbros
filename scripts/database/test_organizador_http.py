"""Organizer top access contracts against a temporary site and a local disposable database only.

The synthetic login and seed helpers exist ONLY in that temporary site; they are never deployed.
"""
import http.cookiejar
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
FIXTURE_LOGIN = '''<?php
require __DIR__.'/database.php'; require __DIR__.'/accounts.php'; require __DIR__.'/organizer_fixture.php';
smash_account_session_start(); $pdo=smash_account_connect(__DIR__);
if (isset($_GET['seed'])) { organizer_fixture_clean($pdo); organizer_fixture_seed($pdo); echo 'seeded'; exit; }
if (isset($_GET['clean'])) { organizer_fixture_clean($pdo); echo 'clean'; exit; }
$n=['org'=>1,'co'=>2,'other'=>3][$_GET['as']];
$id=(string)$pdo->query('SELECT id FROM users WHERE startgg_user_id='.(ORGANIZER_FIXTURE_BASE+$n))->fetchColumn();
$pdo->exec("INSERT IGNORE INTO oauth_connections (user_id, scopes) VALUES ($id, 'user.identity')");
$pdo->exec("INSERT IGNORE INTO user_roles (user_id, role) VALUES ($id, 'player')");
if (!isset($_GET['nointerest'])) $pdo->exec("INSERT IGNORE INTO user_roles (user_id, role) VALUES ($id, 'organizer')");
if (isset($_GET['admin'])) $pdo->exec("INSERT IGNORE INTO user_roles (user_id, role) VALUES ($id, 'admin')");
if (isset($_GET['wide'])) organizer_fixture_more_players($pdo);
$user=smash_account_user($pdo,$id);
$_SESSION['smash_account']=['id'=>$id,'at'=>time(),'version'=>$user['connectionVersion'],'url'=>null,'avatarUrl'=>null];
session_regenerate_id(true); echo $id;
'''


def build_site(home, port):
    site, private, sessions = home/'site', home/'private-smash', home/'sessions'
    for path in (site/'data', private, sessions):
        path.mkdir(parents=True)
    for filename in ('database.php', 'accounts.php', 'stats.php', 'premium.php', 'organizador.php', 'organizador-api.php', 'top.php', 'top.css', 'characters.js', 'account-api.php', 'premium-api.php', 'cuenta.html', 'cuenta.css', 'cuenta.js', 'account-model.js', 'premium.js', 'organizador.js', 'organizador.css', 'tops.php', 'tops-api.php'):
        shutil.copyfile(SITE/filename, site/filename)
    shutil.copyfile(ROOT/'scripts/database/organizer_fixture.php', site/'organizer_fixture.php')
    shutil.copyfile(SITE/'data/public.json', site/'data/public.json')
    config = dict(database=dict(host='127.0.0.1', port=port, name=DATABASE, user='root', password=os.environ['SMASH_SCHEMA_TEST_PASSWORD']))
    (private/'config.local.php').write_text('<?php return json_decode('+json.dumps(json.dumps(config))+', true);')
    (private/'recurrente.local.php').write_text("<?php return ['enabled'=>true,'secret_key'=>'sk_test_%s','webhook_secret'=>'whsec_%s'];" % ('a'*40, 'b'*32))
    (site/'fixture-login.php').write_text(FIXTURE_LOGIN)
    return site, sessions


@unittest.skipUnless(DATABASE, 'Requires local disposable database')
class OrganizerHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import pymysql
        if not DATABASE.startswith('smash_schema_test') or os.environ.get('SMASH_SCHEMA_TEST_HOST', '127.0.0.1') not in ('127.0.0.1', 'localhost'):
            raise RuntimeError('Local disposable database required')
        port = int(os.environ.get('SMASH_SCHEMA_TEST_PORT', '3306'))
        cls.db = pymysql.connect(host='127.0.0.1', port=port, user='root', password=os.environ['SMASH_SCHEMA_TEST_PASSWORD'], database=DATABASE, autocommit=True)
        cls.temp = tempfile.TemporaryDirectory(prefix='smash-organizer-http-')
        site, sessions = build_site(Path(cls.temp.name), port)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0)); cls.port = sock.getsockname()[1]
        cls.base = f'http://127.0.0.1:{cls.port}'
        cls.process = subprocess.Popen(['php', '-d', f'session.save_path={sessions}', '-d', 'display_errors=1', '-S', f'127.0.0.1:{cls.port}', '-t', str(site)],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                urllib.request.urlopen(cls.base+'/top.css', timeout=1).close(); break
            except OSError:
                time.sleep(.05)
        else:
            raise RuntimeError('Local PHP test server did not start')

    @classmethod
    def tearDownClass(cls):
        try: urllib.request.urlopen(cls.base+'/fixture-login.php?clean=1', timeout=10).close()
        finally:
            cls.process.terminate(); cls.process.wait(timeout=10); cls.db.close(); cls.temp.cleanup()

    def setUp(self):
        urllib.request.urlopen(self.base+'/fixture-login.php?seed=1', timeout=10).close()
        self.client = self.browser()

    def browser(self):
        return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(self, path, body=None, csrf=None, client=None, raw=False):
        headers = {'Content-Type': 'application/json'} if body is not None else {}
        if csrf: headers['X-CSRF-Token'] = csrf
        req = urllib.request.Request(self.base+path, data=None if body is None else json.dumps(body).encode(), headers=headers)
        try: response = (client or self.client).open(req, timeout=10)
        except urllib.error.HTTPError as error: response = error
        text = response.read().decode()
        response.close()
        return (response.status, response.headers, text) if raw else (response.status, json.loads(text))

    def login(self, who, extra='', client=None):
        return self.call(f'/fixture-login.php?as={who}{extra}', client=client, raw=True)[2]

    def premium(self, user_id, end='2099-01-01 00:00:00'):
        with self.db.cursor() as q:
            q.execute("INSERT INTO premium_subscriptions (user_id, plan, live_mode, provider_checkout_id, status, current_period_end, created_at, updated_at) VALUES (%s,'annual',0,%s,'active',%s,'2026-10-01','2026-10-01')",
                      (user_id, f'ch_org_{user_id}_{end[:4]}', end))

    def test_visitor_sees_nothing_and_cannot_act(self):
        status, data = self.call('/organizador-api.php')
        self.assertEqual((status, data['authenticated'], data['state'], data['invite']), (200, False, 'login', None)); self.assertNotIn('data', data)
        self.assertEqual(self.call('/organizador-api.php', {'action': 'settings', 'publicEnabled': True}, data['csrf']), (401, {'ok': False, 'reason': 'login_required'}))
        self.assertEqual(self.call('/organizador-api.php', {'action': 'settings'})[0], 403)
        self.assertEqual(self.call('/organizador-api.php?invita='+'a'*48)[1]['invite'], {'valid': False})
        # The account page offers the tab only when the catalog has reached the database.
        self.assertIs(self.call('/account-api.php')[1]['organizerReady'], True)
        with self.db.cursor() as q:
            q.execute('SELECT COUNT(*) FROM tournament_catalog WHERE tournament_id NOT BETWEEN 8999500000 AND 8999599999')
            others = q.fetchone()[0]
        self.call('/fixture-login.php?clean=1', raw=True)
        if not others: self.assertNotIn('organizerReady', self.call('/account-api.php')[1])

    def test_access_order_interest_then_premium_then_data(self):
        org = self.login('org', '&nointerest=1')
        self.assertEqual(self.call('/organizador-api.php')[1]['state'], 'interest')
        self.login('org')
        data = self.call('/organizador-api.php')[1]
        self.assertEqual((data['state'], data['expiredAt'], data['premiumAvailable'], data['role']), ('premium', None, True, 'owner')); self.assertNotIn('data', data)
        for action in ({'action': 'settings', 'publicEnabled': True}, {'action': 'invite'}, {'action': 'review', 'url': 'https://www.start.gg/tournament/torneo-5'}):
            self.assertEqual(self.call('/organizador-api.php', action, data['csrf']), (403, {'ok': False, 'reason': 'premium_required'}))
        self.premium(org, '2026-01-01 00:00:00')
        expired = self.call('/organizador-api.php')[1]
        self.assertEqual((expired['state'], expired['expiredAt']), ('expired', '2026-01-01T00:00:00+00:00')); self.assertNotIn('data', expired)
        self.premium(org)
        data = self.call('/organizador-api.php')[1]
        self.assertEqual(data['state'], 'data'); self.assertEqual(data['publicUrl'], 'https://rankingsmashbros.com/top/arena-xela')
        self.assertEqual([row['alias'] for row in data['data']['top']], ['Kenji', 'Vlad', 'Momo']); self.assertEqual(data['members'], [])
        self.assertNotIn('pendingReviews', data); self.assertNotIn('startgg', json.dumps(data).lower().replace('start.gg', ''))

    def test_owner_settings_public_page_and_closed_states(self):
        org = self.login('org'); self.premium(org)
        csrf = self.call('/organizador-api.php')[1]['csrf']
        status, headers, page = self.call('/top.php?o=arena-xela', raw=True)
        self.assertEqual(status, 200); self.assertIn('Este enlace está desactivado', page); self.assertNotIn('Kenji', page)
        self.assertIn('noindex', headers['X-Robots-Tag']); self.assertIn('name="robots" content="noindex', page); self.assertIsNone(headers['Set-Cookie'])
        self.assertEqual(self.call('/organizador-api.php', {'action': 'settings', 'topSize': 7}, csrf), (400, {'ok': False, 'reason': 'invalid_setting'}))
        status, data = self.call('/organizador-api.php', {'action': 'settings', 'publicEnabled': True, 'topSize': 5}, csrf)
        self.assertEqual((status, data['organizer']), (200, {'name': 'Árena Xelá', 'slug': 'arena-xela', 'publicEnabled': True, 'topSize': 5}))
        anonymous = self.browser()
        status, headers, page = self.call('/top.php?o=arena-xela', client=anonymous, raw=True)
        self.assertEqual(status, 200)
        for text in ('Top 5 · Temporada 2026', 'Árena Xelá', 'Kenji', 'Muestra pequeña: 2 torneos.', 'Torneos usados', 'Torneo 1', 'Quetzaltenango', 'Pagar no da puntos ni cambia puestos.', '30/08/2026 – 27/09/2026'):
            self.assertIn(text, page)
        for text in ('<b>Solo</b>', 'Ajeno', 'Torneo 3', 'Coorganizan', '<script', 'Set-Cookie'):
            self.assertNotIn(text, page)
        with self.db.cursor() as q:
            q.execute('UPDATE premium_subscriptions SET current_period_end=%s WHERE user_id=%s', ('2026-01-01 00:00:00', org))
        page = self.call('/top.php?o=arena-xela', client=anonymous, raw=True)[2]
        self.assertIn('Este top está en pausa', page); self.assertNotIn('Kenji', page); self.assertNotIn('premium', page.lower())
        status, _, page = self.call('/top.php?o=no-existe', client=anonymous, raw=True)
        self.assertEqual(status, 404); self.assertIn('No encontramos este top', page)
        self.assertEqual(self.call('/top.php?o=%27%20OR%201', client=anonymous, raw=True)[0], 404)

    def test_co_organizer_joins_by_invitation_and_only_looks(self):
        org = self.login('org'); self.premium(org)
        csrf = self.call('/organizador-api.php')[1]['csrf']
        status, invite = self.call('/organizador-api.php', {'action': 'invite'}, csrf)
        self.assertEqual(status, 200); self.assertRegex(invite['inviteUrl'], r'^https://rankingsmashbros\.com/cuenta\.html\?invita=[a-f0-9]{48}#torneos$')
        token = invite['inviteUrl'].split('invita=')[1].split('#')[0]
        guest = self.browser()
        self.assertEqual(self.call('/organizador-api.php?invita='+token, client=guest)[1]['invite'], {'valid': True, 'organizer': 'Árena Xelá'})
        co = self.login('co', '&nointerest=1', client=guest)
        seen = self.call('/organizador-api.php?invita='+token, client=guest)[1]
        self.assertEqual(seen['invite'], {'valid': True, 'organizer': 'Árena Xelá', 'own': False, 'member': False}); self.assertEqual(seen['state'], 'interest')
        # Another account's organizer id is never taken on trust.
        self.assertEqual(self.call('/organizador-api.php?organizador='+org, client=guest), (403, {'ok': False, 'reason': 'forbidden'}))
        self.assertEqual(self.call('/organizador-api.php', {'action': 'join', 'token': token}, seen['csrf'], client=guest), (200, {'ok': True, 'organizer': org}))
        self.assertEqual(self.call('/organizador-api.php', {'action': 'join', 'token': token}, seen['csrf'], client=guest), (400, {'ok': False, 'reason': 'invalid_invite'}))
        # Each account pays for itself: joined and credited, but the top needs the co-organizer's own premium.
        gate = self.call('/organizador-api.php?organizador='+org, client=guest)[1]
        self.assertEqual((gate['state'], gate['role']), ('premium', 'member')); self.assertNotIn('data', gate)
        self.assertEqual(self.call('/organizador-api.php')[1]['data']['coorganizers'], ['Coorganizador'])
        self.call('/organizador-api.php', {'action': 'settings', 'publicEnabled': True}, csrf)
        self.assertIn('Coorganizan: Coorganizador', self.call('/top.php?o=arena-xela', client=self.browser(), raw=True)[2])
        self.premium(co)
        team = self.call('/organizador-api.php?organizador='+org, client=guest)[1]
        self.assertEqual((team['state'], team['role'], team['members']), ('data', 'member', None)); self.assertEqual(team['data']['top'][0]['alias'], 'Kenji')
        self.assertEqual([c['role'] for c in team['contexts']], ['owner', 'member'])
        for action in ({'action': 'settings', 'publicEnabled': True}, {'action': 'invite'}, {'action': 'removeMember', 'member': co}, {'action': 'resolve', 'claim': '1', 'approve': True}):
            self.assertEqual(self.call('/organizador-api.php', {**action, 'organizer': org}, seen['csrf'], client=guest), (403, {'ok': False, 'reason': 'forbidden'}))
        self.assertEqual(self.call('/organizador-api.php')[1]['members'][0]['name'], 'Coorganizador')
        self.assertEqual(self.call('/organizador-api.php', {'action': 'leave', 'organizer': org}, seen['csrf'], client=guest), (200, {'ok': True}))
        self.assertEqual(self.call('/organizador-api.php?organizador='+org, client=guest), (403, {'ok': False, 'reason': 'forbidden'}))

    def test_reviews_are_requested_by_the_organizer_and_resolved_by_the_site_owner(self):
        org = self.login('org'); self.premium(org)
        csrf = self.call('/organizador-api.php')[1]['csrf']
        self.assertEqual(self.call('/organizador-api.php', {'action': 'review', 'url': 'https://example.com/tournament/x'}, csrf), (400, {'ok': False, 'reason': 'invalid_tournament_url'}))
        self.assertEqual(self.call('/organizador-api.php', {'action': 'review', 'url': 'https://www.start.gg/tournament/torneo-5/details'}, csrf), (200, {'ok': True}))
        events = {e['name']: e for e in self.call('/organizador-api.php')[1]['data']['events']}
        self.assertEqual((events['Torneo 5']['status'], events['Torneo 5']['review']['status']), ('unconfirmed', 'sent'))
        claim = events['Torneo 5']['review']['id']
        self.assertEqual(self.call('/organizador-api.php', {'action': 'resolve', 'claim': claim, 'approve': True}, csrf), (403, {'ok': False, 'reason': 'forbidden'}))
        owner = self.browser(); self.login('other', '&admin=1', client=owner)
        panel = self.call('/organizador-api.php', client=owner)[1]
        self.assertEqual([(r['organizer'], r['tournament'], r['inCatalog']) for r in panel['pendingReviews'] if r['id'] == claim], [('Árena Xelá', 'Torneo 5', True)])
        self.assertEqual(panel['state'], 'data')
        status, done = self.call('/organizador-api.php', {'action': 'resolve', 'claim': claim, 'approve': True}, panel['csrf'], client=owner)
        self.assertEqual((status, [r for r in done['pendingReviews'] if r['id'] == claim]), (200, []))
        data = self.call('/organizador-api.php')[1]['data']
        self.assertEqual(data['summary']['eventsCounted'], 3); self.assertEqual(data['top'][0]['alias'], 'Ajeno')

    def assert_free_projection(self, data, expected_players=3):
        self.assertNotIn('data', data)
        for key in ('members', 'publicUrl', 'top', 'rest', 'summary', 'pendingReviews'):
            self.assertNotIn(key, data)
        teaser = data['teaser']
        self.assertEqual(set(teaser), {'headline', 'locked'})
        self.assertEqual(teaser['headline'], {'kind': 'latest_counted_tournament', 'name': 'Torneo 2', 'date': '2026-09-27',
                                             'url': 'https://www.start.gg/tournament/torneo-2/event/singles'})
        self.assertEqual(teaser['locked'], {'tournaments': 5, 'countedTournaments': 2, 'rankedPlayers': expected_players, 'validSets': 7})
        for forbidden in ('Kenji', 'Vlad', 'Momo', 'Ajeno', 'setsWon', 'setsLost', 'points', 'rank', 'detail', 'opponents', 'message'):
            self.assertNotIn('\"'+forbidden+'\"', json.dumps(teaser))

    def test_free_expired_and_member_teasers_do_not_send_paid_data_or_create_profiles(self):
        org = self.login('org')
        free = self.call('/organizador-api.php')[1]
        self.assert_free_projection(free)
        with self.db.cursor() as q:
            q.execute('SELECT COUNT(*) FROM organizer_profiles WHERE user_id=%s', (org,))
            self.assertEqual(q.fetchone()[0], 0)
        self.premium(org, '2026-01-01 00:00:00')
        expired = self.call('/organizador-api.php')[1]
        self.assertEqual(expired['state'], 'expired'); self.assert_free_projection(expired)
        self.premium(org)
        full = self.call('/organizador-api.php')[1]
        self.assertNotIn('teaser', full)
        token = self.call('/organizador-api.php', {'action': 'invite'}, full['csrf'])[1]['inviteUrl'].split('invita=')[1].split('#')[0]
        co_client = self.browser(); self.login('co', '&nointerest=1', client=co_client)
        csrf = self.call('/organizador-api.php', client=co_client)[1]['csrf']
        self.call('/organizador-api.php', {'action': 'join', 'token': token}, csrf, client=co_client)
        member = self.call('/organizador-api.php?organizador='+org, client=co_client)[1]
        self.assertEqual((member['state'], member['role']), ('premium', 'member')); self.assert_free_projection(member)
        # Leaving is free, even without the organizer interest or a subscription.
        self.assertEqual(self.call('/organizador-api.php', {'action': 'leave', 'organizer': org}, csrf, client=co_client), (200, {'ok': True}))
        self.assertEqual(self.call('/organizador-api.php?organizador='+org, client=co_client)[0], 403)

    def test_unrelated_contexts_are_rejected_and_invalid_settings_are_atomic(self):
        org = self.login('org'); self.premium(org)
        data = self.call('/organizador-api.php')[1]; csrf = data['csrf']; before = data['data']['organizer']
        for invalid in ('0', '99999999', org+'x'):
            self.assertEqual(self.call('/organizador-api.php?organizador='+invalid)[0], 403)
            self.assertEqual(self.call('/organizador-api.php', {'action': 'settings', 'organizer': invalid, 'publicEnabled': True}, csrf)[0], 403)
        self.assertEqual(self.call('/organizador-api.php?organizador[]=1')[0], 403)
        self.assertEqual(self.call('/organizador-api.php', {'action': 'settings', 'publicEnabled': True, 'topSize': 7}, csrf)[0], 400)
        self.assertEqual(self.call('/organizador-api.php')[1]['data']['organizer'], before)

    def test_all_top_sizes_with_large_field_and_switch_off(self):
        org = self.login('org', '&wide=1'); self.premium(org)
        csrf = self.call('/organizador-api.php')[1]['csrf']
        baseline = None
        for size in (5, 10, 15):
            self.assertEqual(self.call('/organizador-api.php', {'action': 'settings', 'topSize': size, 'publicEnabled': True}, csrf)[0], 200)
            data = self.call('/organizador-api.php')[1]['data']
            self.assertEqual((len(data['top']), len(data['rest'])), (size, 21-size))
            order = [(r['alias'], r['rank'], r['points']) for r in data['top']+data['rest']]
            if baseline is None: baseline = order
            self.assertEqual(order, baseline)
            status, headers, page = self.call('/top.php?o=arena-xela', client=self.browser(), raw=True)
            self.assertEqual(status, 200); self.assertIn(f'Top {size} · Temporada 2026', page)
            self.assertEqual(page.count('role="row"'), size+1)
            self.assertIn('no-store', headers['Cache-Control'])
        self.call('/organizador-api.php', {'action': 'settings', 'publicEnabled': False}, csrf)
        closed = self.call('/top.php?o=arena-xela', client=self.browser(), raw=True)[2]
        self.assertIn('Este enlace está desactivado', closed); self.assertNotIn('Kenji', closed)

    def test_review_of_small_context_never_admits_it_to_the_top(self):
        co = self.login('co'); self.premium(co)
        csrf = self.call('/organizador-api.php')[1]['csrf']
        self.call('/organizador-api.php', {'action': 'review', 'url': 'https://www.start.gg/tournament/torneo-4'}, csrf)
        admin = self.browser(); self.login('other', '&admin=1', client=admin)
        panel = self.call('/organizador-api.php', client=admin)[1]
        claim = next(r for r in panel['pendingReviews'] if r['organizer'] == 'Coorganizador')
        self.assertEqual(self.call('/organizador-api.php', {'action': 'resolve', 'claim': claim['id'], 'approve': True}, panel['csrf'], client=admin)[0], 200)
        data = self.call('/organizador-api.php')[1]['data']
        self.assertEqual(data['summary']['validSets'], 0); self.assertEqual(data['top'], [])
        self.assertEqual((data['events'][0]['status'], data['events'][0]['reason']), ('excluded', 'small'))

    def test_empty_organizer_free_and_premium_states(self):
        co = self.login('co')
        free = self.call('/organizador-api.php')[1]
        self.assertEqual(free['teaser'], {'headline': None, 'locked': {'tournaments': 0, 'countedTournaments': 0, 'rankedPlayers': 0, 'validSets': 0}})
        self.premium(co)
        full = self.call('/organizador-api.php')[1]
        self.assertEqual((full['data']['events'], full['data']['top'], full['publicUrl']), ([], [], None))

    def test_review_catalog_arrival_rejection_retry_and_owner_permissions(self):
        org = self.login('org'); self.premium(org)
        csrf = self.call('/organizador-api.php')[1]['csrf']
        # Requested before a weekly catalog refresh: keep the claim's tournament_id NULL.
        with self.db.cursor() as q:
            q.execute("INSERT INTO organizer_claims (organizer_user_id, requested_by, tournament_slug, created_at) VALUES (%s,%s,'tournament/torneo-5','2026-10-01')", (org, org))
            claim = str(q.lastrowid)
        owner = self.browser(); self.login('other', '&admin=1', client=owner)
        panel = self.call('/organizador-api.php', client=owner)[1]
        row = next(r for r in panel['pendingReviews'] if r['id'] == claim)
        self.assertEqual((row['inCatalog'], row['tournament'], row['requestedBy']), (True, 'Torneo 5', 'Árena Xelá'))
        # An admin needs no paid subscription. Everyone else must be denied, including forged actions.
        self.assertEqual(self.call('/organizador-api.php', {'action': 'resolve', 'claim': claim, 'approve': True}, csrf)[0], 403)
        for message in (' ', 'x'*256):
            self.assertEqual(self.call('/organizador-api.php', {'action': 'resolve', 'claim': claim, 'approve': False, 'message': message}, panel['csrf'], client=owner)[0], 400)
        self.assertEqual(self.call('/organizador-api.php', {'action': 'resolve', 'claim': claim, 'approve': False, 'message': 'No se acreditó la organización.'}, panel['csrf'], client=owner)[0], 200)
        rejected = next(e for e in self.call('/organizador-api.php')[1]['data']['events'] if e['review'] and e['review']['id'] == claim)
        self.assertEqual(rejected['review']['message'], 'No se acreditó la organización.')
        self.assertEqual(self.call('/organizador-api.php', {'action': 'review', 'url': 'https://www.start.gg/tournament/torneo-5'}, csrf)[0], 200)
        self.assertEqual(self.call('/organizador-api.php', {'action': 'resolve', 'claim': claim, 'approve': True}, panel['csrf'], client=owner)[0], 200)
        self.assertEqual(self.call('/organizador-api.php', {'action': 'resolve', 'claim': claim, 'approve': False, 'message': 'Otro criterio.'}, panel['csrf'], client=owner)[0], 400)
        self.assertEqual(self.call('/organizador-api.php')[1]['data']['summary']['eventsCounted'], 3)
        # An unknown tournament cannot be approved until it reaches the catalog.
        self.call('/organizador-api.php', {'action': 'review', 'url': 'https://www.start.gg/tournament/no-catalogo'}, csrf)
        unknown = next(r for r in self.call('/organizador-api.php', client=owner)[1]['pendingReviews'] if not r['inCatalog'])
        self.assertEqual(self.call('/organizador-api.php', {'action': 'resolve', 'claim': unknown['id'], 'approve': True}, panel['csrf'], client=owner)[0], 400)

    def test_concurrent_invitation_replacement_and_consumption(self):
        org = self.login('org'); self.premium(org)
        guest = self.browser(); co = self.login('co', client=guest)
        other_client = self.browser(); other = self.login('other', client=other_client)
        worker = r"""
require $argv[1].'/ranking-smash-ultimate/database.php';
require $argv[1].'/ranking-smash-ultimate/organizador.php';
$name=getenv('SMASH_SCHEMA_TEST_DB');
if (strpos($name,'smash_schema_test')!==0) exit(2);
$pdo=smash_database_connect(['host'=>'127.0.0.1','port'=>(int)getenv('SMASH_SCHEMA_TEST_PORT'),'name'=>$name,'user'=>'root','password'=>getenv('SMASH_SCHEMA_TEST_PASSWORD')]);
try {
 if ($argv[2]==='invite') echo json_encode(['token'=>smash_org_invite($pdo,$argv[3],time())]);
 else echo json_encode(['joined'=>smash_org_join($pdo,$argv[3],$argv[4],time())]);
} catch (SmashOrganizerError $e) {echo json_encode(['reason'=>$e->reason]);}
"""
        def concurrent(args):
            processes = []
            self.db.begin()
            try:
                with self.db.cursor() as q: q.execute('SELECT id FROM users WHERE id=%s FOR UPDATE', (org,))
                for argv in args:
                    processes.append(subprocess.Popen(['php', '-r', worker, str(ROOT), *argv], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
                time.sleep(.25)
                self.assertTrue(all(p.poll() is None for p in processes), 'Both clients wait for the organizer lock')
            finally: self.db.rollback()
            try:
                outputs = [p.communicate(timeout=10) for p in processes]
                self.assertTrue(all(p.returncode == 0 for p in processes))
                return [json.loads(out) for out, _ in outputs]
            finally:
                for p in processes:
                    if p.poll() is None: p.kill(); p.wait(timeout=5)
        tokens = [r['token'] for r in concurrent([['invite', org], ['invite', org]])]
        self.assertEqual(sum(self.call('/organizador-api.php?invita='+t, client=self.browser())[1]['invite']['valid'] for t in tokens), 1)
        token = next(t for t in tokens if self.call('/organizador-api.php?invita='+t, client=self.browser())[1]['invite']['valid'])
        results = concurrent([['join', co, token], ['join', other, token]])
        self.assertEqual(sum(r.get('joined') == org for r in results), 1)
        self.assertEqual(sum(r.get('reason') == 'invalid_invite' for r in results), 1)
        with self.db.cursor() as q:
            q.execute('SELECT COUNT(*) FROM organizer_members WHERE organizer_user_id=%s', (org,))
            self.assertEqual(q.fetchone()[0], 1)

    def test_method_and_body_contracts(self):
        self.login('org')
        csrf = self.call('/organizador-api.php')[1]['csrf']
        self.assertEqual(self.call('/organizador-api.php', {'action': 'x' * 2000}, csrf)[0], 413)
        req = urllib.request.Request(self.base+'/organizador-api.php', data=b'action=invite', headers={'X-CSRF-Token': csrf})
        with self.assertRaises(urllib.error.HTTPError) as error: self.client.open(req, timeout=10)
        self.assertEqual(error.exception.code, 415)
        req = urllib.request.Request(self.base+'/organizador-api.php', method='DELETE')
        with self.assertRaises(urllib.error.HTTPError) as error: self.client.open(req, timeout=10)
        self.assertEqual(error.exception.code, 405)


if __name__ == '__main__': unittest.main(verbosity=2)
