<?php
declare(strict_types=1);
ini_set('display_errors', '0');
// Not UTC on purpose: a local-time clock in the code under test must not pass as UTC.
date_default_timezone_set('America/Guatemala');
require dirname(__DIR__, 2) . '/ranking-smash-ultimate/database.php';
require dirname(__DIR__, 2) . '/ranking-smash-ultimate/survey.php';
require __DIR__ . '/import_survey.php';

// Todos los datos de este archivo son inventados. No copiar respuestas reales a Git.
function verify(bool $condition, string $label): void {
    if (!$condition) throw new RuntimeException('Test failed: ' . $label);
}
function rejects(callable $fn, string $reason): void {
    try { $fn(); } catch (SmashSurveyStorageError $error) {
        verify($error->reason === $reason, "$reason, got {$error->reason}");
        return;
    }
    throw new RuntimeException('Expected rejection: ' . $reason);
}
function answer(array $changes = []): array {
    return $changes + ['role' => 'jugador', 'eligibility' => 'nacionalidad-local', 'minimum' => '2-eventos-4-sets',
        'international' => 'todos-validos', 'clarity' => 4, 'confidence' => 5, 'source' => '', 'comment' => ''];
}
function token(int $n): string { return str_pad(dechex($n), 48, 'a', STR_PAD_LEFT); }

const SECRET = 'COMENTARIO-PRIVADO-INVENTADO';
const AT = 1790000000; // 2026-09-21 14:13:20 UTC

// Contract shared with the form handler and the importer.
verify(SMASH_SURVEY_OPTIONS === SMASH_SURVEY_CHOICES, 'web form and importer accept the same options');
verify(SMASH_SURVEY_INTERNAL_TEST_PREFIX === SMASH_SURVEY_TEST_PREFIX, 'one rule marks internal test entries');
$form = file_get_contents(dirname(__DIR__, 2) . '/ranking-smash-ultimate/encuesta.php');
foreach (SMASH_SURVEY_OPTIONS as $field => $allowed) {
    foreach ($allowed as $value) verify(strpos($form, "name=\"$field\" value=\"$value\"") !== false, "form offers $field=$value");
    verify(strpos($form, "choice('$field', ['" . implode("', '", $allowed) . "'])") !== false, "form validates $field with the library list");
}

$base = smash_survey_row_from_answer(answer(['comment' => 'Texto inventado ñ', 'source' => 'https://start.gg/x/y']), AT);
$key = smash_survey_submission_key(token(1), $base);
// The formula is pinned: form token, then the hash of the exact stored answer.
verify($key === hash('sha256', "smashgt-encuesta-web-v1\n" . token(1) . "\n" . hash('sha256',
    '[2026,"jugador","nacionalidad-local","2-eventos-4-sets","todos-validos",4,5,"https://start.gg/x/y","Texto inventado ñ"]')), 'pinned key formula');
verify($key === smash_survey_submission_key(token(1), smash_survey_row_from_answer(answer(['comment' => 'Texto inventado ñ', 'source' => 'https://start.gg/x/y']), AT + 999)), 'same form and answer, same key at any time');
verify($key !== smash_survey_submission_key(token(2), $base), 'another form, another key');
foreach ([['comment' => 'Texto inventado n'], ['clarity' => 3], ['role' => 'otro'], ['source' => '']] as $change) {
    verify($key !== smash_survey_submission_key(token(1), smash_survey_row_from_answer(answer($change + ['comment' => 'Texto inventado ñ', 'source' => 'https://start.gg/x/y']), AT)), 'another answer, another key');
}
foreach (['', 'abc', str_repeat('g', 48), str_repeat('A', 48), token(1) . "\n"] as $bad) {
    rejects(fn() => smash_survey_submission_key($bad, $base), 'invalid_form_token');
}
verify(smash_survey_failure_code(new SmashSurveyStorageError('write_failed')) === 'write_failed', 'storage reason code');
verify(smash_survey_failure_code(new SmashDatabaseError('connection_denied')) === 'connection_denied', 'connector reason code');
verify(smash_survey_failure_code(new RuntimeException('host=secreto password=x')) === 'RuntimeException', 'unexpected failures log only their class');
verify(smash_survey_failure_code(new SmashSurveyStorageError("Robert'); DROP")) === 'SmashSurveyStorageError', 'odd reasons are never logged verbatim');

verify(smash_survey_clean_text("ok ñ 🎮") === "ok ñ 🎮", 'valid text is untouched');
verify(smash_survey_clean_text("a\xC3(b\xFF") === "a\u{FFFD}(b\u{FFFD}", 'invalid bytes become U+FFFD as in the file era');
verify(smash_survey_clean_text('') === '', 'empty stays empty');

$row = smash_survey_row_from_answer(answer(['comment' => "Línea 1\nLínea 2", 'source' => 'https://www.start.gg/tournament/inventado']), AT);
verify(array_merge(array_keys($row), ['import_hash']) === SMASH_SURVEY_COLUMNS, 'row uses exactly the importer columns, nothing about the visitor');
verify($row['submitted_at'] === '2026-09-21 14:13:20.000000' && $row['season_year'] === 2026, 'UTC second precision and season');
verify($row['minimum_activity'] === '2-eventos-4-sets' && $row['is_test'] === 0, 'mapping');
$blank = smash_survey_row_from_answer(answer(), AT);
verify($blank['comment'] === null && $blank['source_url'] === null, 'empty text is stored as NULL like imported rows');
verify(smash_survey_row_from_answer(answer(['comment' => SMASH_SURVEY_INTERNAL_TEST_PREFIX . ' x']), AT)['is_test'] === 1, 'internal test prefix sets is_test');
verify(smash_survey_row_from_answer(answer(['comment' => 'prueba técnica interna']), AT)['is_test'] === 0, 'prefix rule is case sensitive, as before');
foreach ([['role' => 'admin'], ['eligibility' => null], ['minimum' => 1], ['international' => ''], ['clarity' => '4'],
    ['clarity' => 0], ['confidence' => 6], ['comment' => str_repeat('a', 2001)], ['source' => str_repeat('a', 251)],
    ['comment' => null], ['source' => ['x']]] as $bad) {
    rejects(fn() => smash_survey_row_from_answer(answer($bad), AT), 'invalid_answer');
}
rejects(fn() => smash_survey_row_from_answer(answer(), 0), 'invalid_answer');
echo "Survey row contract checks passed.\n";

$suite = static function (PDO $pdo, string $engine, bool $realEngine): void {
    $count = static fn() => (int)$pdo->query('SELECT COUNT(*) FROM survey_responses')->fetchColumn();
    verify($count() === 0, "$engine starts empty");
    verify(smash_survey_rows($pdo) === [], "$engine empty table reads as no answers");

    $first = answer(['comment' => SECRET, 'clarity' => 2, 'confidence' => 3]);
    verify(smash_survey_store($pdo, $first, token(1), AT) === 'inserted' && !$pdo->inTransaction(), "$engine first write, committed");
    // Same answer of the same form again (confirmation lost, or the session write failed): nothing is added.
    verify(smash_survey_store($pdo, $first, token(1), AT + 30) === 'already_saved', "$engine retry of the same answer");
    verify(smash_survey_store($pdo, $first, token(1), AT + 3000) === 'already_saved' && $count() === 1, "$engine retry is recognised at any later time");
    // Two different people may send identical answers: different forms, two rows.
    verify(smash_survey_store($pdo, answer(), token(2), AT + 100) === 'inserted', "$engine identical answers, other form");
    verify(smash_survey_store($pdo, answer(), token(3), AT + 100) === 'inserted', "$engine identical answers, third form, same second");
    verify(smash_survey_store($pdo, answer(['comment' => SMASH_SURVEY_INTERNAL_TEST_PREFIX . ' — inventada', 'role' => 'otro']), token(4), AT + 200) === 'inserted', "$engine internal test stored");
    verify(smash_survey_store($pdo, answer(['role' => 'organizador', 'eligibility' => 'otra', 'minimum' => 'otro', 'international' => 'ninguno',
        'clarity' => 1, 'confidence' => 1, 'source' => 'https://start.gg/tournament/inventado/details',
        'comment' => "<script>alert(1)</script>\nñ 🎮 \xFF"]), token(5), AT + 300) === 'inserted', "$engine hostile text stored as data");
    verify($count() === 5, "$engine five rows");
    // A different answer sent with a form whose earlier answer was stored without the session
    // learning it (shared device, corrected text) is a new answer, never a silent discard.
    $pdo->beginTransaction();
    try {
        smash_survey_store($pdo, answer(['comment' => 'otro texto inventado']), token(1), AT + 400);
        verify(false, "$engine a caller transaction must be refused");
    } catch (SmashSurveyStorageError $error) {
        verify($error->reason === 'transaction_already_active' && $pdo->inTransaction(), "$engine caller transaction left alone");
    }
    $pdo->rollBack();
    verify(smash_survey_store($pdo, answer(['comment' => 'otro texto inventado']), token(1), AT + 400) === 'inserted', "$engine same form, different answer is stored");
    verify($count() === 6, "$engine six rows");
    $pdo->exec("DELETE FROM survey_responses WHERE comment = 'otro texto inventado'");

    $stored = $pdo->query('SELECT * FROM survey_responses ORDER BY id')->fetchAll(PDO::FETCH_ASSOC);
    verify(array_keys($stored[0]) === array_merge(['id'], SMASH_SURVEY_COLUMNS), "$engine table has no visitor columns");
    verify((string)$stored[0]['comment'] === SECRET && (int)$stored[0]['clarity'] === 2, "$engine first answer kept, not overwritten");
    verify($stored[1]['comment'] === null && $stored[1]['source_url'] === null, "$engine NULL for empty text");
    verify(substr((string)$stored[0]['submitted_at'], 0, 19) === '2026-09-21 14:13:20', "$engine stored instant is UTC");
    verify((string)$stored[4]['comment'] === "<script>alert(1)</script>\nñ 🎮 \u{FFFD}", "$engine utf8mb4 text and substitution preserved");

    $rows = smash_survey_rows($pdo);
    verify(count($rows) === 4, "$engine internal test entry is not a community answer");
    verify(array_keys($rows[0]) === ['submittedAt', 'role', 'eligibility', 'minimum', 'international', 'clarity', 'confidence', 'source', 'comment'], "$engine panel shape");
    verify(array_column($rows, 'submittedAt') === ['2026-09-21T14:18:20+00:00', '2026-09-21T14:15:00+00:00', '2026-09-21T14:15:00+00:00', '2026-09-21T14:13:20+00:00'], "$engine newest first with explicit UTC offset");
    verify(date('d/m/Y H:i', strtotime($rows[3]['submittedAt'])) === '21/09/2026 08:13', "$engine panel shows Guatemala time from the UTC instant");
    verify($rows[0]['role'] === 'organizador' && $rows[0]['minimum'] === 'otro' && $rows[0]['source'] === 'https://start.gg/tournament/inventado/details', "$engine values mapped back");
    verify($rows[0]['clarity'] === 1 && $rows[3]['clarity'] === 2 && is_int($rows[1]['confidence']), "$engine scores are integers for the averages");
    verify($rows[1]['comment'] === '' && $rows[1]['source'] === '', "$engine NULL is shown as empty text");
    verify(strtotime($rows[3]['submittedAt']) === AT, "$engine instant survives the round trip");

    // Imported lines and web answers live together; the importer's comparison still holds.
    $line = '{"submittedAt":"2026-09-01T10:00:00+00:00","seasonYear":2026,"role":"espectador","eligibility":"nacionalidad","minimum":"otro","international":"solo-grandes","clarity":3,"confidence":3,"source":"","comment":"Línea inventada del archivo"}';
    $imported = smash_survey_import($pdo, [smash_survey_row($line, 2)], true);
    verify($imported['inserted'] === 1, "$engine importer still works next to web rows");
    $compare = smash_survey_compare($pdo, [smash_survey_row($line, 2)]);
    verify($compare['fileFullyStored'] && $compare['matched'] === 1 && $compare['databaseRowsNotInFile'] === 5, "$engine comparison counts web rows apart");
    $rows = smash_survey_rows($pdo);
    verify(count($rows) === 5 && end($rows)['submittedAt'] === '2026-09-01T10:00:00+00:00', "$engine imported line listed in date order");

    // Other seasons never mix into this panel.
    $pdo->exec("UPDATE survey_responses SET season_year = 2027 WHERE import_hash = '" . smash_survey_submission_key(token(2), smash_survey_row_from_answer(answer(), AT)) . "'");
    verify(count(smash_survey_rows($pdo)) === 4, "$engine season filter");

    // Failures surface as sanitized reasons and never as success.
    $before = $count();
    // An integrity error that is NOT the retry key (a CHECK or a constraint added later) must
    // never be reported as an answer already saved.
    $pdo->exec($realEngine
        ? "CREATE TRIGGER survey_test_integrity BEFORE INSERT ON survey_responses FOR EACH ROW BEGIN IF NEW.role = 'otro' AND NEW.clarity = 1 THEN SIGNAL SQLSTATE '23000' SET MESSAGE_TEXT = 'test-only integrity fault'; END IF; END"
        : "CREATE TRIGGER survey_test_integrity BEFORE INSERT ON survey_responses WHEN NEW.role = 'otro' AND NEW.clarity = 1 BEGIN SELECT RAISE(ABORT, 'constraint failed: test-only'); END");
    try {
        rejects(fn() => smash_survey_store($pdo, answer(['role' => 'otro', 'clarity' => 1]), token(8), AT), 'write_failed');
        verify($count() === $before && !$pdo->inTransaction(), "$engine integrity error without a stored row is a failure");
    } finally {
        $pdo->exec('DROP TRIGGER survey_test_integrity');
    }
    if ($realEngine) {
        verify(strpos((string)$pdo->query('SELECT @@SESSION.sql_mode')->fetchColumn(), 'STRICT_TRANS_TABLES') !== false, "$engine strict mode for survey statements");
        verify((int)$pdo->query('SELECT @@SESSION.innodb_lock_wait_timeout')->fetchColumn() === 5
            && (int)$pdo->query('SELECT @@SESSION.lock_wait_timeout')->fetchColumn() === 5, "$engine bounded lock waits");
        $bad = smash_survey_row_from_answer(answer(), AT);
        $bad['import_hash'] = smash_survey_submission_key(token(9), $bad);
        $bad['role'] = str_repeat('x', 31);
        try {
            $pdo->prepare('INSERT INTO survey_responses (' . implode(', ', array_keys($bad)) . ') VALUES (?,?,?,?,?,?,?,?,?,?,?,?)')->execute(array_values($bad));
            verify(false, "$engine over-long value must be rejected, not truncated");
        } catch (PDOException $error) {
            verify($count() === $before, "$engine strict mode rejected the row");
        }
    }
    $pdo->exec('ALTER TABLE survey_responses RENAME TO survey_responses_hidden');
    try {
        try {
            smash_survey_store($pdo, answer(['comment' => SECRET]), token(6), AT);
            verify(false, "$engine write must fail");
        } catch (SmashSurveyStorageError $error) {
            verify($error->reason === 'write_failed' && strpos($error->getMessage(), SECRET) === false
                && stripos($error->getMessage(), 'survey_responses') === false, "$engine write failure is sanitized");
        }
        rejects(fn() => smash_survey_rows($pdo), 'read_failed');
    } finally {
        $pdo->exec('ALTER TABLE survey_responses_hidden RENAME TO survey_responses');
    }
    verify($count() === $before, "$engine failed write stored nothing");
    verify(smash_survey_store($pdo, answer(['comment' => SECRET]), token(6), AT) === 'inserted', "$engine same form succeeds once storage is back");
    echo "Survey storage, retry contract and panel read passed on $engine.\n";
};

$sqlite = new PDO('sqlite::memory:', null, null, [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
$sqlite->exec('CREATE TABLE survey_responses (id INTEGER PRIMARY KEY AUTOINCREMENT, submitted_at TEXT NOT NULL,
    season_year INTEGER NOT NULL, role TEXT NOT NULL, eligibility TEXT NOT NULL, minimum_activity TEXT NOT NULL,
    international TEXT NOT NULL, clarity INTEGER NOT NULL, confidence INTEGER NOT NULL, source_url TEXT NULL,
    comment TEXT NULL, is_test INTEGER NOT NULL DEFAULT 0, import_hash TEXT NULL UNIQUE)');
$suite($sqlite, 'SQLite stand-in', false);

if (getenv('SMASH_SCHEMA_TEST_DB')) {
    verify(strpos(getenv('SMASH_SCHEMA_TEST_DB'), 'smash_schema_test') === 0, 'disposable database only');
    // Same connection path as production: a private config beside a site folder.
    $home = sys_get_temp_dir() . '/smash-survey-storage-' . bin2hex(random_bytes(8));
    mkdir($home . '/site', 0700, true);
    mkdir($home . '/private-smash', 0700);
    $config = ['database' => ['host' => '127.0.0.1', 'port' => (int)getenv('SMASH_SCHEMA_TEST_PORT'),
        'name' => getenv('SMASH_SCHEMA_TEST_DB'), 'user' => 'root', 'password' => (string)getenv('SMASH_SCHEMA_TEST_PASSWORD')]];
    file_put_contents($home . '/private-smash/config.local.php', '<?php return ' . var_export($config, true) . ';');
    $admin = smash_database_connect($config['database']);
    $globalMode = (string)$admin->query('SELECT @@GLOBAL.sql_mode')->fetchColumn();
    try {
        // Production's global mode is not strict; the CI engines' default is. Reproduce production
        // so the strictness asserted below can only come from the library.
        $admin->exec("SET GLOBAL sql_mode = 'NO_ENGINE_SUBSTITUTION'");
        $plain = smash_database_connect($config['database']);
        verify(strpos((string)$plain->query('SELECT @@SESSION.sql_mode')->fetchColumn(), 'STRICT') === false, 'precondition: connector sessions are not strict by themselves');
        $plain = null;
        $pdo = smash_survey_connect($home . '/site');
        $pdo->exec('DELETE FROM survey_responses');
        try {
            $suite($pdo, (string)$pdo->query('SELECT VERSION()')->fetchColumn(), true);
        } finally {
            $pdo->exec('DELETE FROM survey_responses');
        }
    } finally {
        $admin->prepare('SET GLOBAL sql_mode = ?')->execute([$globalMode]);
        unlink($home . '/private-smash/config.local.php');
        rmdir($home . '/private-smash');
        rmdir($home . '/site');
        rmdir($home);
    }
}
