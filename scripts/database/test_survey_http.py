"""Real submit and real read of the survey over HTTP against a disposable database.

An isolated PHP site, session folder and private config are created per run. Every value is
invented; nothing here can reach production: the database must be smash_schema_test* on 127.0.0.1.
"""
import hashlib
import http.cookiejar
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
DATABASE = os.environ.get('SMASH_SCHEMA_TEST_DB', '')
VALID = dict(role='jugador', eligibility='nacionalidad-local', minimum='2-eventos-4-sets',
             international='todos-validos', clarity='4', confidence='5', comment='', source='', website='')
SAVED = '¡Respuesta recibida!'
STORAGE_ERROR = 'No pudimos guardar la respuesta. Intenta de nuevo más tarde.'
REVIEW = 'Revisa las respuestas e intenta de nuevo.'
RECENT = 'Ya recibimos una respuesta reciente de esta sesión. Gracias.'
COLUMNS = ['id', 'submitted_at', 'season_year', 'role', 'eligibility', 'minimum_activity', 'international',
           'clarity', 'confidence', 'source_url', 'comment', 'is_test', 'import_hash']


def submission_key(nonce):
    return hashlib.sha256(('smashgt-encuesta-web-v1\n' + nonce).encode()).hexdigest()


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
        cls.temp = tempfile.TemporaryDirectory(prefix='smash-survey-http-')
        home = Path(cls.temp.name)
        cls.site, cls.private, cls.sessions = home / 'site', home / 'private-smash', home / 'sessions'
        for folder in (cls.site / 'feedback-data', cls.private, cls.sessions):
            folder.mkdir(parents=True)
        for filename in ('database.php', 'survey.php', 'encuesta.php', 'opiniones.php'):
            (cls.site / filename).write_bytes((SITE / filename).read_bytes())
        (cls.site / 'feedback-data/admin-auth.php').write_text("<?php return '" + '$2y$12$' + 'A' * 53 + "';")
        cls.config = cls.private / 'config.local.php'
        cls.write_config()
        cls.admin = 'smashsurveyhttptestonly'
        # Synthetic administrator session, created exclusively for this temporary test site.
        subprocess.run(['php', '-d', f'session.save_path={cls.sessions}', '-r',
                        f'session_name("SMASHGT_ADMIN");session_id("{cls.admin}");session_start();'
                        '$_SESSION["smash_admin"]=true;$_SESSION["smash_admin_at"]=time();session_write_close();'],
                       check=True, capture_output=True)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        cls.process = subprocess.Popen(['php', '-d', f'session.save_path={cls.sessions}', '-S', f'127.0.0.1:{port}',
                                        '-t', str(cls.site)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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

    def count(self):
        return self.execute('SELECT COUNT(*) FROM survey_responses')[0][0]

    def visitor(self):
        return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def fetch(self, opener, path, fields=None, cookie=None):
        data = urllib.parse.urlencode(fields).encode() if fields is not None else None
        request = urllib.request.Request(self.base + path, data=data, headers={'Cookie': cookie} if cookie else {})
        try:
            response = opener.open(request, timeout=10)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, dict(response.headers), response.read().decode()

    def form(self, opener):
        status, _, body = self.fetch(opener, '/encuesta.php')
        self.assertEqual(status, 200)
        return re.search(r'name="nonce" value="([0-9a-f]{48})"', body).group(1)

    def submit(self, opener, nonce, **changes):
        return self.fetch(opener, '/encuesta.php', {**VALID, 'nonce': nonce, **changes})

    def panel(self, authenticated=True):
        return self.fetch(urllib.request.build_opener(), '/opiniones.php',
                          cookie=f'SMASHGT_ADMIN={self.admin}' if authenticated else None)

    def seed(self, at, **changes):
        row = dict(season_year=2026, role='jugador', eligibility='nacionalidad-local', minimum_activity='2-eventos-4-sets',
                   international='todos-validos', clarity=4, confidence=5, source_url=None, comment=None, is_test=0,
                   import_hash=hashlib.sha256(os.urandom(16)).hexdigest())
        row.update(changes, submitted_at=at)
        self.execute('INSERT INTO survey_responses (' + ','.join(row) + ') VALUES (' + ','.join(['%s'] * len(row)) + ')',
                     list(row.values()))

    def assert_no_leak(self, body):
        for text in ('SQLSTATE', 'PDOException', 'Fatal error', 'Warning:', 'Deprecated:', 'Stack trace',
                     str(self.temp.name), 'config.local', 'disposable-test-only', 'wrong-test-only'):
            self.assertNotIn(text, body)

    # --- survey form ---------------------------------------------------------------------

    def test_form_is_served_without_touching_the_database(self):
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
        before = self.execute('SELECT UTC_TIMESTAMP()')[0][0]
        status, _, body = self.submit(person, nonce, role='organizador', eligibility='otra', minimum='otro',
                                      international='ninguno', clarity='2', confidence='3',
                                      comment='  Texto inventado con ñ y 🎮\nsegunda línea  ',
                                      source=' https://www.start.gg/tournament/inventado/details ')
        self.assertEqual(status, 200)
        self.assertIn(SAVED, body)
        self.assertNotIn('class="survey-form"', body)
        description = [column[0] for column in self.execute('SHOW COLUMNS FROM survey_responses')]
        self.assertEqual(description, COLUMNS)  # nothing about the visitor can be stored
        rows = self.execute('SELECT submitted_at, season_year, role, eligibility, minimum_activity, international,'
                            ' clarity, confidence, source_url, comment, is_test, import_hash FROM survey_responses')
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertLessEqual(abs((row[0] - before).total_seconds()), 15)  # stored in UTC from the PHP clock
        self.assertEqual(row[0].microsecond, 0)
        self.assertEqual(row[1:12], (2026, 'organizador', 'otra', 'otro', 'ninguno', 2, 3,
                                     'https://www.start.gg/tournament/inventado/details',
                                     'Texto inventado con ñ y 🎮\nsegunda línea', 0, submission_key(nonce)))
        # A browser refresh re-posts the consumed form: rejected, nothing added.
        _, _, body = self.submit(person, nonce)
        self.assertIn(REVIEW, body)
        self.assertNotIn(SAVED, body)
        # A fresh form in the same session within five minutes: limited, nothing added.
        _, _, body = self.submit(person, self.form(person))
        self.assertIn(RECENT, body)
        self.assertEqual(self.count(), 1)
        # Another person is not limited by somebody else's session, even with identical answers.
        other = self.visitor()
        _, _, body = self.submit(other, self.form(other))
        self.assertIn(SAVED, body)
        third = self.visitor()
        _, _, body = self.submit(third, self.form(third))
        self.assertIn(SAVED, body)
        self.assertEqual(self.count(), 3)

    def test_rejected_requests_store_nothing_and_do_not_consume_the_form(self):
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
        for opener, changes, expected in cases:
            with self.subTest(changes=str(changes)[:40]):
                status, _, body = self.submit(opener, changes.get('nonce', nonce), **{k: v for k, v in changes.items() if k != 'nonce'})
                self.assertEqual(status, 200)
                self.assertIn(expected, body)
                self.assertNotIn(SAVED, body)
                self.assert_no_leak(body)
        self.assertEqual(self.count(), 0)
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
                status, _, body = self.submit(person, nonce, comment='Comentario inventado que no debe perderse en silencio')
                self.assertEqual(status, 200)
                self.assertIn(STORAGE_ERROR, body)
                self.assertNotIn(SAVED, body)
                self.assertNotIn('SECRET-MARKER', body)
                self.assert_no_leak(body)
                self.assertIn(f'value="{nonce}"', body)  # form token kept: the visitor can retry at once
        self.write_config()
        self.assertEqual(self.count(), 0)
        self.assertFalse((self.site / 'feedback-data/respuestas-2026.php').exists())  # no second source, no fallback
        _, _, body = self.submit(person, nonce, comment='Comentario inventado que no debe perderse en silencio')
        self.assertIn(SAVED, body)
        self.assertEqual(self.count(), 1)

    def test_lost_acknowledgement_retry_does_not_duplicate(self):
        person = self.visitor()
        nonce = self.form(person)
        # The first attempt reached the database but the visitor never saw the confirmation and the
        # session was not updated (connection cut, or PHP stopped right after the INSERT).
        self.seed('2026-10-06 12:00:00', import_hash=submission_key(nonce), comment='Primera versión inventada')
        status, _, body = self.submit(person, nonce, comment='Primera versión inventada')
        self.assertEqual(status, 200)
        self.assertIn(SAVED, body)
        self.assertEqual(self.count(), 1)
        self.assertEqual(self.execute('SELECT comment FROM survey_responses')[0][0], 'Primera versión inventada')
        # The form is now consumed like any confirmed answer.
        _, _, body = self.submit(person, nonce, comment='Primera versión inventada')
        self.assertIn(REVIEW, body)
        self.assertEqual(self.count(), 1)

    def test_internal_test_prefix_is_flagged_and_invalid_bytes_are_substituted(self):
        tester, person = self.visitor(), self.visitor()
        _, _, body = self.submit(tester, self.form(tester), comment='PRUEBA TÉCNICA INTERNA — inventada')
        self.assertIn(SAVED, body)
        data = urllib.parse.urlencode({**VALID, 'nonce': self.form(person)}).encode() + b'&comment=bytes%FFinventados'
        request = urllib.request.Request(self.base + '/encuesta.php', data=data.replace(b'comment=&', b''))
        with person.open(request, timeout=10) as response:
            self.assertIn(SAVED, response.read().decode())
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
        status, headers, body = self.panel()
        self.assertEqual(status, 200)
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

    def test_panel_without_answers_and_panel_with_unreadable_database_are_different(self):
        _, _, empty = self.panel()
        self.assertIn('<strong>0</strong><span>respuestas reales recibidas</span>', empty)
        self.assertIn('Aún no hay respuestas de la comunidad.', empty)
        self.assertNotIn('No se pudieron leer las respuestas', empty)
        self.seed_panel()
        for broken in ('wrong-password', 'missing-config'):
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

    def test_answers_are_never_exposed_without_the_administrator_session(self):
        self.seed_panel()
        self.config.unlink()  # the login page must not need the database at all
        status, _, body = self.panel(authenticated=False)
        self.assertEqual(status, 200)
        self.assertIn('name="password"', body)
        for private in ('negrita', 'respuestas reales recibidas', 'comment-card', 'Mismo segundo'):
            self.assertNotIn(private, body)
        self.write_config()
        for path in ('/opiniones.php?diagnostico=base', '/encuesta.php'):
            _, _, body = self.fetch(self.visitor(), path)
            self.assertNotIn('negrita', body)
            self.assertNotIn('Mismo segundo', body)


class SurveyStaticContractTests(unittest.TestCase):
    """Checks that need no database: they also run in the plain CI job."""

    def test_library_is_denied_by_the_web_server_and_holds_no_secret(self):
        htaccess = (SITE / '.htaccess').read_text()
        for library in ('database.php', 'survey.php'):
            self.assertRegex(htaccess, r'<Files "%s">\s*Require all denied\s*</Files>' % re.escape(library))
        source = (SITE / 'survey.php').read_text()
        for forbidden in ('REMOTE_ADDR', 'HTTP_USER_AGENT', 'session_id(', 'error_log(', 'file_put_contents', 'fopen('):
            self.assertNotIn(forbidden, source)

    def test_pages_no_longer_use_the_file_and_never_print_errors(self):
        for page in ('encuesta.php', 'opiniones.php'):
            source = (SITE / page).read_text()
            self.assertNotIn('respuestas-2026', source)
            self.assertNotIn('flock(', source)
            self.assertIn("ini_set('display_errors', '0');", source)
            self.assertIn("require_once __DIR__ . '/survey.php';", source)


if __name__ == '__main__':
    unittest.main(verbosity=2)
