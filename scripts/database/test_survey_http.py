"""Real submit and real read of the survey over HTTP against a disposable database.

An isolated PHP site, session folder, error log and private config are created per run. Every value
is invented; nothing here can reach production: the database must be smash_schema_test* on 127.0.0.1.
The server runs like production where it matters: a non-UTC PHP time zone, a non-strict global
sql_mode, errors that would be displayed unless the pages hide them, and the legacy answers file
still present on disk.
"""
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / 'ranking-smash-ultimate'
IMPORTER = ROOT / 'scripts/database/import_survey.php'
DATABASE = os.environ.get('SMASH_SCHEMA_TEST_DB', '')
VALID = dict(role='jugador', eligibility='nacionalidad-local', minimum='2-eventos-4-sets',
             international='todos-validos', clarity='4', confidence='5', comment='', source='', website='')
SAVED = '¡Respuesta recibida!'
STORAGE_ERROR = 'No pudimos guardar la respuesta. Intenta de nuevo más tarde.'
REVIEW = 'Revisa las respuestas e intenta de nuevo.'
RECENT = 'Ya recibimos una respuesta reciente de esta sesión. Gracias.'
COLUMNS = ['id', 'submitted_at', 'season_year', 'role', 'eligibility', 'minimum_activity', 'international',
           'clarity', 'confidence', 'source_url', 'comment', 'is_test', 'import_hash']
GUARD = '<?php http_response_code(404); exit; ?>\n'
DECOY = 'RESPUESTA-ANTIGUA-DEL-ARCHIVO-INVENTADA'
PRIVATE = 'COMENTARIO-PRIVADO-INVENTADO'


def file_line(at, comment, **changes):
    entry = dict(submittedAt=at, seasonYear=2026, role='jugador', eligibility='nacionalidad-local',
                 minimum='2-eventos-4-sets', international='todos-validos', clarity=4, confidence=5, source='', comment=comment)
    entry.update(changes)
    return json.dumps(entry, ensure_ascii=False, separators=(',', ':'))


@unittest.skipUnless(DATABASE, 'Requires disposable database service')
class SurveyHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import pymysql
        if not DATABASE.startswith('smash_schema_test'):
            raise RuntimeError('Survey HTTP tests only run against a disposable smash_schema_test* database')
        cls.port_db = int(os.environ.get('SMASH_SCHEMA_TEST_PORT', '3306'))
        cls.password = os.environ['SMASH_SCHEMA_TEST_PASSWORD']
        cls.db = pymysql.connect(host='127.0.0.1', port=cls.port_db, user='root', password=cls.password,
                                 database=DATABASE, charset='utf8mb4', autocommit=True)
        # Production's global sql_mode is not strict; both CI engines default to strict.
        cls.global_mode = cls.execute('SELECT @@GLOBAL.sql_mode')[0][0]
        cls.execute("SET GLOBAL sql_mode = 'NO_ENGINE_SUBSTITUTION'")
        cls.temp = tempfile.TemporaryDirectory(prefix='smash-survey-http-')
        home = Path(cls.temp.name)
        cls.site, cls.private, cls.sessions = home / 'site', home / 'private-smash', home / 'sessions'
        for folder in (cls.site / 'feedback-data', cls.private, cls.sessions):
            folder.mkdir(parents=True)
        for filename in ('database.php', 'survey.php', 'encuesta.php', 'opiniones.php'):
            (cls.site / filename).write_bytes((SITE / filename).read_bytes())
        (cls.site / 'feedback-data/admin-auth.php').write_text("<?php return '" + '$2y$12$' + 'A' * 53 + "';")
        # The frozen legacy file stays on the server after the migration: it must never be read or written.
        cls.legacy = cls.site / 'feedback-data/respuestas-2026.php'
        cls.legacy_bytes = (GUARD + file_line('2026-09-29T10:00:00+00:00', DECOY) + '\n').encode()
        cls.legacy.write_bytes(cls.legacy_bytes)
        cls.tree = sorted(str(path.relative_to(cls.site)) for path in cls.site.rglob('*'))
        cls.log = home / 'php-error.log'
        cls.config = cls.private / 'config.local.php'
        cls.write_config()
        cls.admin, cls.expired = 'smashsurveyhttptestonly', 'smashsurveyhttpexpired'
        # Synthetic administrator sessions, created exclusively for this temporary test site.
        for session, age in ((cls.admin, 0), (cls.expired, 9 * 3600)):
            subprocess.run(['php', '-d', f'session.save_path={cls.sessions}', '-r',
                            f'session_name("SMASHGT_ADMIN");session_id("{session}");session_start();'
                            f'$_SESSION["smash_admin"]=true;$_SESSION["smash_admin_at"]=time()-{age};session_write_close();'],
                           check=True, capture_output=True)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        cls.process = subprocess.Popen(
            ['php', '-d', f'session.save_path={cls.sessions}', '-d', 'date.timezone=America/Guatemala',
             '-d', 'display_errors=1', '-d', 'log_errors=1', '-d', f'error_log={cls.log}', '-d', 'opcache.enable=0',
             '-S', f'127.0.0.1:{port}', '-t', str(cls.site)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.base = f'http://127.0.0.1:{port}'
        for _ in range(100):
            try:
                urllib.request.urlopen(cls.base + '/encuesta.php', timeout=1).close()
                break
            except (OSError, urllib.error.URLError):
                time.sleep(0.05)
        else:
            raise RuntimeError('PHP test server did not start')

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate()
        cls.process.wait(timeout=5)
        cls.execute('DELETE FROM survey_responses')
        cls.execute('SET GLOBAL sql_mode = %s', (cls.global_mode,))
        cls.db.close()
        cls.temp.cleanup()

    @classmethod
    def write_config(cls, password=None):
        password = cls.password if password is None else password
        cls.config.write_text("<?php return ['database'=>['host'=>'127.0.0.1','port'=>%d,'name'=>'%s','user'=>'root','password'=>'%s']];"
                              % (cls.port_db, DATABASE, password))

    @classmethod
    def execute(cls, statement, args=None):
        with cls.db.cursor() as cursor:
            cursor.execute(statement, args)
            return cursor.fetchall()

    def setUp(self):
        self.write_config()
        self.execute('DELETE FROM survey_responses')

    def tearDown(self):
        # No double writing, no fallback: the legacy file is untouched and nothing new appears in the site.
        self.assertEqual(self.legacy.read_bytes(), self.legacy_bytes)
        self.assertEqual(sorted(str(path.relative_to(self.site)) for path in self.site.rglob('*')), self.tree)
        log = self.log.read_text() if self.log.exists() else ''
        # The server log may only carry reason codes: no answer text, no visitor or connection data.
        for line in log.splitlines():
            self.assertRegex(line, r'^\[[^\]]+\] Smash GT (encuesta|opiniones): [a-záéíóú ]+ \([A-Za-z_\\]+\)$')
        for private in (PRIVATE, DECOY, '127.0.0.1', 'disposable-test-only', 'wrong-test-only', 'PHPSESSID', 'SMASHGT_ADMIN'):
            self.assertNotIn(private, log)

    def count(self):
        return self.execute('SELECT COUNT(*) FROM survey_responses')[0][0]

    def connections(self):
        return int(self.execute("SHOW GLOBAL STATUS LIKE 'Connections'")[0][1])

    def visitor(self):
        return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def fetch(self, opener, path, fields=None, cookie=None, body=None):
        data = urllib.parse.urlencode(fields).encode() if fields is not None else body
        request = urllib.request.Request(self.base + path, data=data, headers={'Cookie': cookie} if cookie else {})
        try:
            response = opener.open(request, timeout=10)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            text = response.read().decode()
        self.assertNotIn(DECOY, text)  # the legacy file is never a source again
        return response.status, dict(response.headers), text

    def form(self, opener):
        status, _, body = self.fetch(opener, '/encuesta.php')
        self.assertEqual(status, 200)
        return re.search(r'name="nonce" value="([0-9a-f]{48})"', body).group(1)

    def submit(self, opener, nonce, **changes):
        return self.fetch(opener, '/encuesta.php', {**VALID, 'nonce': nonce, **changes})

    def panel(self, session='admin'):
        cookie = {'admin': self.admin, 'expired': self.expired, 'unknown': 'nobodyknowsthissession', None: None}[session]
        return self.fetch(urllib.request.build_opener(), '/opiniones.php', cookie=f'SMASHGT_ADMIN={cookie}' if cookie else None)

    def key(self, nonce, **answer):
        """Retry key computed by the library itself for a form token and an answer."""
        values = dict(role='jugador', eligibility='nacionalidad-local', minimum='2-eventos-4-sets',
                      international='todos-validos', clarity=4, confidence=5, source='', comment='')
        values.update(answer)
        script = ('require $argv[1]."/database.php"; require $argv[1]."/survey.php";'
                  'echo smash_survey_submission_key($argv[2], smash_survey_row_from_answer(json_decode($argv[3], true), 1790000000));')
        return subprocess.run(['php', '-r', script, str(SITE), nonce, json.dumps(values)], check=True,
                              capture_output=True, text=True).stdout

    def seed(self, at, **changes):
        row = dict(season_year=2026, role='jugador', eligibility='nacionalidad-local', minimum_activity='2-eventos-4-sets',
                   international='todos-validos', clarity=4, confidence=5, source_url=None, comment=None, is_test=0,
                   import_hash=hashlib.sha256(os.urandom(16)).hexdigest())
        row.update(changes, submitted_at=at)
        self.execute('INSERT INTO survey_responses (' + ','.join(row) + ') VALUES (' + ','.join(['%s'] * len(row)) + ')',
                     list(row.values()))

    def assert_no_leak(self, body):
        for text in ('SQLSTATE', 'PDOException', 'Fatal error', 'Warning', 'Deprecated', 'Notice', 'Stack trace',
                     str(self.temp.name), 'config.local', 'disposable-test-only', 'wrong-test-only'):
            self.assertNotIn(text, body)

    # --- survey form ---------------------------------------------------------------------

    def test_form_is_served_without_touching_the_database(self):
        before = self.connections()
        _, _, body = self.fetch(self.visitor(), '/encuesta.php')
        self.assertEqual(self.connections(), before)
        self.config.unlink()
        status, headers, body = self.fetch(self.visitor(), '/encuesta.php')
        self.assertEqual(status, 200)
        self.assertIn('no-store', headers['Cache-Control'])
        self.assertRegex(body, r'name="nonce" value="[0-9a-f]{48}"')
        self.assertIn('<meta name="smash-survey-storage" content="sql">', body)
        self.assertIn('class="survey-submit"', body)
        self.assert_no_leak(body)

    def test_valid_answer_is_stored_once_anonymously_and_session_limit_applies(self):
        person = self.visitor()
        nonce = self.form(person)
        before, connections = self.execute('SELECT UTC_TIMESTAMP()')[0][0], self.connections()
        answer = dict(role='organizador', eligibility='otra', minimum='otro', international='ninguno', clarity='2', confidence='3')
        status, _, body = self.submit(person, nonce, comment='  Texto inventado con ñ y 🎮\nsegunda línea  ',
                                      source=' https://www.start.gg/tournament/inventado/details ', **answer)
        self.assertEqual(status, 200)
        self.assertIn(SAVED, body)
        self.assertNotIn('class="survey-form"', body)
        self.assertEqual(self.connections(), connections + 1)  # exactly one connection for one stored answer
        description = [column[0] for column in self.execute('SHOW COLUMNS FROM survey_responses')]
        self.assertEqual(description, COLUMNS)  # nothing about the visitor can be stored
        rows = self.execute('SELECT submitted_at, season_year, role, eligibility, minimum_activity, international,'
                            ' clarity, confidence, source_url, comment, is_test, import_hash FROM survey_responses')
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertLessEqual(abs((row[0] - before).total_seconds()), 15)  # UTC, although PHP runs in Guatemala time
        self.assertEqual(row[0].microsecond, 0)
        expected_key = self.key(nonce, comment='Texto inventado con ñ y 🎮\nsegunda línea',
                                source='https://www.start.gg/tournament/inventado/details',
                                **{**answer, 'clarity': 2, 'confidence': 3})
        self.assertEqual(row[1:12], (2026, 'organizador', 'otra', 'otro', 'ninguno', 2, 3,
                                     'https://www.start.gg/tournament/inventado/details',
                                     'Texto inventado con ñ y 🎮\nsegunda línea', 0, expected_key))
        connections = self.connections()
        # A browser refresh re-posts the consumed form: rejected, nothing added.
        _, _, body = self.submit(person, nonce)
        self.assertIn(REVIEW, body)
        self.assertNotIn(SAVED, body)
        # A fresh form in the same session within five minutes: limited, nothing added.
        _, _, body = self.submit(person, self.form(person))
        self.assertIn(RECENT, body)
        self.assertEqual(self.count(), 1)
        self.assertEqual(self.connections(), connections)  # neither rejection opened a connection
        # Another person is not limited by somebody else's session, even with identical answers.
        other = self.visitor()
        _, _, body = self.submit(other, self.form(other))
        self.assertIn(SAVED, body)
        third = self.visitor()
        _, _, body = self.submit(third, self.form(third))
        self.assertIn(SAVED, body)
        self.assertEqual(self.count(), 3)

    def test_rejected_requests_store_nothing_open_no_connection_and_do_not_consume_the_form(self):
        person = self.visitor()
        nonce = self.form(person)
        outsider = self.visitor()
        self.form(outsider)
        cases = [
            (outsider, dict(nonce='0' * 48), REVIEW),                       # CSRF: token of no session
            (outsider, dict(nonce=nonce), REVIEW),                          # CSRF: token of another session
            (person, dict(website='http://spam.example'), REVIEW),          # honeypot
            (person, dict(role='admin'), REVIEW),
            (person, dict(clarity='6'), REVIEW),
            (person, dict(source='https://example.com/tournament/x'), 'el enlace no es de start.gg'),
            (person, dict(source='http://start.gg/tournament/x'), 'el enlace no es de start.gg'),
            (person, dict(comment='a' * 2001), 'demasiado largo'),
            (person, dict(comment='ñ' * 1001), 'demasiado largo'),         # limit is bytes, as before
        ]
        connections = self.connections()
        for opener, changes, expected in cases:
            with self.subTest(changes=str(changes)[:40]):
                status, _, body = self.submit(opener, changes.get('nonce', nonce), **{k: v for k, v in changes.items() if k != 'nonce'})
                self.assertEqual(status, 200)
                self.assertIn(expected, body)
                self.assertNotIn(SAVED, body)
                self.assert_no_leak(body)
        self.assertEqual(self.count(), 0)
        self.assertEqual(self.connections(), connections)  # spam and mistakes never reach the database
        # None of the rejections rotated the form token or started the five-minute limit.
        _, _, body = self.submit(person, nonce, comment='ñ' * 1000)
        self.assertIn(SAVED, body)
        self.assertEqual(self.count(), 1)

    def test_database_failure_is_reported_never_as_success_and_the_same_form_can_retry(self):
        person = self.visitor()
        nonce = self.form(person)
        for broken in ('wrong-password', 'missing-config', 'invalid-config'):
            with self.subTest(broken=broken):
                if broken == 'wrong-password':
                    self.write_config('wrong-test-only')
                elif broken == 'missing-config':
                    self.config.unlink()
                else:
                    self.config.write_text('<?php SECRET-MARKER syntax error')
                status, _, body = self.submit(person, nonce, comment=PRIVATE)
                self.assertEqual(status, 200)
                self.assertIn(STORAGE_ERROR, body)
                self.assertNotIn(SAVED, body)
                self.assertNotIn('SECRET-MARKER', body)
                self.assert_no_leak(body)
                self.assertIn(f'value="{nonce}"', body)  # form token kept: the visitor can retry at once
        self.write_config()
        self.assertEqual(self.count(), 0)
        log = self.log.read_text()
        for reason in ('connection_denied', 'config_missing', 'config_invalid'):
            self.assertIn(f'Smash GT encuesta: respuesta no guardada ({reason})', log)  # the owner can see why
        _, _, body = self.submit(person, nonce, comment=PRIVATE)
        self.assertIn(SAVED, body)
        self.assertEqual(self.count(), 1)

    def test_lost_confirmation_retry_does_not_duplicate_and_a_changed_answer_is_not_discarded(self):
        person = self.visitor()
        nonce = self.form(person)
        # The first attempt reached the database but the visitor never saw the confirmation and the
        # session was not updated (connection cut, or PHP stopped right after the commit).
        self.seed('2026-10-06 12:00:00', import_hash=self.key(nonce, comment='Primera versión inventada'), comment='Primera versión inventada')
        status, _, body = self.submit(person, nonce, comment='Primera versión inventada')
        self.assertEqual(status, 200)
        self.assertIn(SAVED, body)
        self.assertEqual(self.count(), 1)
        # The form is now consumed like any confirmed answer.
        _, _, body = self.submit(person, nonce, comment='Primera versión inventada')
        self.assertIn(REVIEW, body)
        self.assertEqual(self.count(), 1)
        # Same lost confirmation, but the visitor (or the next person on a shared device) then sends
        # a different answer with that form: it is stored, never answered with a false "received".
        other = self.visitor()
        nonce = self.form(other)
        self.seed('2026-10-06 12:05:00', import_hash=self.key(nonce, comment='Texto original inventado'), comment='Texto original inventado')
        _, _, body = self.submit(other, nonce, comment='Texto corregido inventado')
        self.assertIn(SAVED, body)
        self.assertEqual(sorted(row[0] for row in self.execute('SELECT comment FROM survey_responses')),
                         ['Primera versión inventada', 'Texto corregido inventado', 'Texto original inventado'])

    def test_internal_test_prefix_is_flagged_and_invalid_bytes_are_substituted(self):
        tester, person = self.visitor(), self.visitor()
        _, _, body = self.submit(tester, self.form(tester), comment='PRUEBA TÉCNICA INTERNA — inventada')
        self.assertIn(SAVED, body)
        fields = {key: value for key, value in VALID.items() if key != 'comment'}
        raw = urllib.parse.urlencode({**fields, 'nonce': self.form(person)}).encode() + b'&comment=bytes%FFinventados'
        _, _, body = self.fetch(person, '/encuesta.php', body=raw)
        self.assertIn(SAVED, body)
        rows = dict(self.execute('SELECT comment, is_test FROM survey_responses'))
        self.assertEqual(rows, {'PRUEBA TÉCNICA INTERNA — inventada': 1, 'bytes�inventados': 0})
        _, _, body = self.panel()
        self.assertIn('<strong>1</strong><span>respuestas reales recibidas</span>', body)
        self.assertNotIn('PRUEBA TÉCNICA INTERNA', body)

    # --- private panel -------------------------------------------------------------------

    def seed_panel(self):
        self.seed('2026-10-01 05:30:00', clarity=4, confidence=2,
                  comment='<b>negrita</b> & "comillas"\nsegunda línea', source_url='https://www.start.gg/tournament/inventado')
        self.seed('2026-10-02 03:10:00', role='organizador', eligibility='otra', minimum_activity='3-eventos-6-sets',
                  international='solo-grandes', clarity=5, confidence=3)
        self.seed('2026-10-03 00:00:00', is_test=1, comment='PRUEBA TÉCNICA INTERNA sembrada', clarity=1, confidence=1)
        self.seed('2027-01-05 00:00:00', season_year=2027, comment='Temporada siguiente inventada', clarity=1, confidence=1)
        self.seed('2026-10-01 05:30:00', role='espectador', clarity=3, confidence=4, import_hash=None,
                  comment='Mismo segundo, guardada después')

    def test_panel_shows_community_answers_with_the_existing_rules(self):
        self.seed_panel()
        connections = self.connections()
        status, headers, body = self.panel()
        self.assertEqual(status, 200)
        self.assertEqual(self.connections(), connections + 1)
        self.assertIn('no-store', headers['Cache-Control'])
        self.assertIn('<meta name="smash-survey-storage" content="sql">', body)
        self.assertIn('<strong>3</strong><span>respuestas reales recibidas</span>', body)
        self.assertNotIn('Aún no hay respuestas', body)
        self.assertIn('<strong>4,0 / 5</strong><span>Claridad de la explicación</span>', body)
        self.assertIn('<strong>3,0 / 5</strong><span>Confianza en el piloto</span>', body)
        for label, expected in [('Jugadores', 1), ('Organizadores', 1), ('Espectadores', 1), ('Otros', 0),
                                ('Nacionalidad y juego local', 2), ('Otra propuesta', 1), ('2 torneos y 4 sets', 2),
                                ('3 torneos y 6 sets', 1), ('Solo los más grandes', 1), ('Todos los válidos', 2)]:
            self.assertIn(f'<span>{label}</span><strong>{expected}</strong></div><progress value="{expected}" max="3">', body)
        # Stored in UTC, shown in Guatemala time (UTC-6), newest first; equal instants keep storage order.
        cards = re.findall(r'<article class="comment-card"><div class="comment-meta"><time>([^<]+)</time><span>([^<]+)</span>', body)
        self.assertEqual(cards, [('01/10/2026 21:10', 'Organizadores'), ('30/09/2026 23:30', 'Jugadores'),
                                 ('30/09/2026 23:30', 'Espectadores')])
        self.assertIn('<p>&lt;b&gt;negrita&lt;/b&gt; &amp; &quot;comillas&quot;<br />\nsegunda línea</p>', body)
        self.assertNotIn('<b>negrita</b>', body)
        self.assertEqual(body.count('Ver referencia en start.gg ↗'), 1)
        self.assertIn('href="https://www.start.gg/tournament/inventado"', body)
        self.assertIn('<dd>4 / 5 · 2 / 5</dd>', body)
        for hidden in ('PRUEBA TÉCNICA INTERNA', 'Temporada siguiente inventada'):
            self.assertNotIn(hidden, body)
        self.assert_no_leak(body)
        # The existing administrator diagnostic also tells which PHP serves the site.
        _, _, diagnostic = self.fetch(urllib.request.build_opener(), '/opiniones.php?diagnostico=base', cookie=f'SMASHGT_ADMIN={self.admin}')
        status = json.loads(diagnostic)
        self.assertEqual((status['connection'], status['counts']['survey_responses']), ('connected', 5))
        self.assertRegex(status['phpVersion'], r'^\d+\.\d+$')

    def test_panel_without_answers_and_panel_with_unreadable_database_are_different(self):
        _, _, empty = self.panel()
        self.assertIn('<strong>0</strong><span>respuestas reales recibidas</span>', empty)
        self.assertIn('Aún no hay respuestas de la comunidad.', empty)
        self.assertNotIn('No se pudieron leer las respuestas', empty)
        self.seed_panel()
        for broken, reason in (('wrong-password', 'connection_denied'), ('missing-config', 'config_missing')):
            with self.subTest(broken=broken):
                if broken == 'wrong-password':
                    self.write_config('wrong-test-only')
                else:
                    self.config.unlink()
                status, _, body = self.panel()
                self.assertEqual(status, 200)
                self.assertIn('No se pudieron leer las respuestas.', body)
                for absent in ('respuestas reales recibidas', 'Aún no hay respuestas', 'LO QUE PROPONEN', 'comment-card', 'rating-grid'):
                    self.assertNotIn(absent, body)
                self.assertIn('Cerrar sesión', body)
                self.assertIn('href="./opiniones.php?diagnostico=base"', body)
                self.assert_no_leak(body)
                self.assertIn(f'Smash GT opiniones: lectura fallida ({reason})', self.log.read_text())

    def test_answers_are_never_exposed_without_a_valid_administrator_session(self):
        self.seed_panel()
        private = ('negrita', 'respuestas reales recibidas', 'comment-card', 'Mismo segundo', 'rating-grid', 'LO QUE PROPONEN')
        connections = self.connections()
        # With the database reachable: a leak would show here.
        for session in (None, 'expired', 'unknown'):
            with self.subTest(session=session):
                status, _, body = self.panel(session)
                self.assertEqual(status, 200)
                self.assertIn('name="password"', body)
                for text in private:
                    self.assertNotIn(text, body)
        for path in ('/opiniones.php?diagnostico=base', '/encuesta.php'):
            _, _, body = self.fetch(self.visitor(), path)
            for text in private:
                self.assertNotIn(text, body)
        login = self.visitor()
        _, _, page = self.fetch(login, '/opiniones.php')
        nonce = re.search(r'name="nonce" value="([0-9a-f]{48})"', page).group(1)
        _, _, body = self.fetch(login, '/opiniones.php', dict(action='login', nonce=nonce, password='clave-inventada-incorrecta'))
        self.assertIn('Clave incorrecta.', body)
        for text in private:
            self.assertNotIn(text, body)
        self.assertEqual(self.connections(), connections)  # none of these requests even connected
        # And the login page does not need the database at all.
        self.config.unlink()
        status, _, body = self.panel(None)
        self.assertEqual(status, 200)
        self.assertIn('name="password"', body)

    # --- importer command line: the gate used before reopening submissions -----------------

    def importer(self, *arguments):
        done = subprocess.run(['php', str(IMPORTER), *arguments], capture_output=True, text=True, timeout=30)
        output = done.stdout + done.stderr
        for private in (PRIVATE, 'Línea inventada', 'disposable-test-only', str(self.temp.name)):
            self.assertNotIn(private, output)
        try:
            return done.returncode, json.loads(done.stdout or done.stderr)
        except ValueError:
            return done.returncode, output

    def test_importer_command_line_compare_gate(self):
        folder = Path(self.temp.name)
        shared = file_line('2026-09-30T10:00:00+00:00', 'Línea inventada compartida ' + PRIVATE)
        first, second, empty = folder / 'archivo-a.php', folder / 'archivo-b.php', folder / 'solo-guarda.php'
        first.write_text(GUARD + '\n'.join([shared, file_line('2026-09-30T11:00:00+00:00', 'Línea inventada A2'),
                                            file_line('2026-09-30T12:00:00+00:00', 'PRUEBA TÉCNICA INTERNA inventada')]) + '\n')
        second.write_text(GUARD + '\n'.join([shared, file_line('2026-10-01T09:00:00+00:00', 'Línea inventada B2', role='otro')]) + '\n')
        empty.write_text(GUARD)
        site = ['--site-root', str(self.site)]
        try:
            code, report = self.importer('--file', str(first), *site, '--compare', '--no-extra')
            self.assertEqual((code, report['ok'], report['missingInDatabase']), (1, False, 3))  # nothing imported yet
            self.assertEqual(self.importer('--file', str(first), *site, '--apply')[0], 0)
            code, report = self.importer('--file', str(first), *site, '--compare', '--no-extra')
            self.assertEqual((code, report['ok'], report['matched'], report['databaseRowsNotInFile'], report['files']), (0, True, 3, 0, 1))
            self.assertEqual(self.importer('--file', str(second), *site, '--apply')[1]['inserted'], 1)
            # One file alone no longer explains the table...
            code, report = self.importer('--file', str(first), *site, '--compare', '--no-extra')
            self.assertEqual((code, report['ok'], report['fileFullyStored'], report['databaseRowsNotInFile']), (1, False, True, 1))
            self.assertEqual(self.importer('--file', str(first), *site, '--compare')[0], 0)  # ...but its lines are all stored
            # ...every imported source together does: the shared line counts once.
            code, report = self.importer('--file', str(first), '--file', str(second), *site, '--compare', '--no-extra')
            self.assertEqual((code, report['ok'], report['files'], report['rowsPerFile'], report['fileRows'], report['matched'],
                              report['databaseRows'], report['databaseRowsNotInFile'], report['fileTestRows'], report['databaseTestRows']),
                             (0, True, 2, [3, 2], 4, 4, 4, 0, 1, 1))
            # A stray row (an answer received by the SQL form, or anything else) fails the strict gate only.
            self.seed('2026-10-06 12:00:00', comment='Fila ajena a los archivos')
            both = ['--file', str(first), '--file', str(second), *site, '--compare']
            self.assertEqual(self.importer(*both, '--no-extra')[0], 1)
            self.assertEqual(self.importer(*both)[0], 0)
            # A stored value that differs from its line always fails.
            self.execute("UPDATE survey_responses SET clarity = 1 WHERE comment = 'Línea inventada A2'")
            code, report = self.importer(*both)
            self.assertEqual((code, report['ok'], report['valueMismatches'], report['matched']), (1, False, 1, 3))
            # Comparing against a file without answers proves nothing.
            code, report = self.importer('--file', str(empty), *site, '--compare')
            self.assertEqual((code, report['ok'], report['fileRows']), (1, False, 0))
            for invalid in (['--file', str(first), *site, '--apply', '--compare'],
                            ['--file', str(first), *site, '--no-extra'],
                            ['--file', str(first), '--file', str(second), *site, '--apply'],
                            ['--file', str(first), '--file', str(second)],
                            ['--file', str(first), '--compare'],
                            [*site, '--compare'],
                            ['--file', str(first), *site, *site, '--compare']):
                with self.subTest(invalid=invalid[-2:]):
                    code, report = self.importer(*invalid)
                    self.assertEqual(code, 2)
                    self.assertIn('Uso:', report)
        finally:
            for path in (first, second, empty):
                path.unlink()


class SurveyStaticContractTests(unittest.TestCase):
    """Checks that need no database: they also run in the plain CI job."""

    def test_libraries_and_logs_are_denied_by_the_web_server_and_the_library_does_not_log(self):
        htaccess = (SITE / '.htaccess').read_text()
        for name in ('database.php', 'survey.php', 'error_log'):
            self.assertRegex(htaccess, r'<Files "%s">\s*Require all denied\s*</Files>' % re.escape(name))
        source = (SITE / 'survey.php').read_text()
        for forbidden in ('REMOTE_ADDR', 'HTTP_USER_AGENT', 'HTTP_X_FORWARDED', 'session_id(', 'error_log(', 'file_put_contents', 'fopen(', 'setcookie('):
            self.assertNotIn(forbidden, source)

    def test_pages_no_longer_use_the_file_never_print_errors_and_log_reason_codes_only(self):
        for page in ('encuesta.php', 'opiniones.php'):
            source = (SITE / page).read_text()
            for forbidden in ('respuestas-2026', 'respuestas-', 'flock(', 'fwrite(', 'file_put_contents', 'REMOTE_ADDR', 'HTTP_USER_AGENT'):
                self.assertNotIn(forbidden, source)
            self.assertIn("ini_set('display_errors', '0');", source)
            self.assertIn("require_once __DIR__ . '/survey.php';", source)
            logged = re.findall(r'error_log\((.*)\);', source)
            self.assertEqual(len(logged), 1, page)
            self.assertRegex(logged[0], r"^'Smash GT [a-z]+: [a-záéíóú ]+ \(' \. smash_survey_failure_code\(\$failure\) \. '\)'$")


if __name__ == '__main__':
    unittest.main(verbosity=2)
