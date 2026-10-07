<?php
declare(strict_types=1);
ini_set('display_errors', '0');
require __DIR__ . '/import_survey.php';

// Todos los datos de este archivo son inventados. No copiar respuestas reales a Git.
function verify(bool $condition, string $label): void {
    if (!$condition) throw new RuntimeException('Test failed: ' . $label);
}
function rejects(callable $fn, string $reason, ?int $line = null): void {
    try { $fn(); } catch (SmashSurveyImportError $error) {
        verify($error->reason === $reason, "$reason, got {$error->reason}");
        verify($error->lineNumber === $line, "$reason line " . var_export($error->lineNumber, true));
        return;
    }
    throw new RuntimeException('Expected rejection: ' . $reason);
}
function entry(array $changes = []): array {
    return $changes + ['submittedAt' => '2026-09-30T18:05:09+00:00', 'seasonYear' => 2026, 'role' => 'jugador',
        'eligibility' => 'nacionalidad-local', 'minimum' => '2-eventos-4-sets', 'international' => 'todos-validos',
        'clarity' => 4, 'confidence' => 5, 'source' => '', 'comment' => ''];
}
function line(array $changes = [], ?array $keys = null): string {
    $value = entry($changes);
    // array + keeps the caller's order first; restore the order encuesta.php writes.
    $ordered = [];
    foreach ($keys ?? SMASH_SURVEY_KEYS as $key) if (array_key_exists($key, $value)) $ordered[$key] = $value[$key];
    return json_encode($ordered, JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE);
}
function fixture(string $path, array $lines, string $guard = SMASH_SURVEY_GUARD, string $ending = "\n"): void {
    file_put_contents($path, $guard . ($lines ? implode("\n", $lines) . $ending : ''));
}

const SECRET = 'COMENTARIO-PRIVADO-INVENTADO';
$dir = sys_get_temp_dir() . '/smash-survey-test-' . bin2hex(random_bytes(8));
mkdir($dir, 0700);
$file = $dir . '/respuestas-2026.php';
try {
    $valid = [
        line(['comment' => "Me gusta el piloto.\nSegunda línea con acentos: áéíóú ñ 🎮"]),
        line(['submittedAt' => '2026-10-01T00:00:00+00:00', 'role' => 'organizador', 'eligibility' => 'otra',
            'minimum' => 'otro', 'international' => 'ninguno', 'clarity' => 1, 'confidence' => 1,
            'source' => 'https://www.start.gg/tournament/ejemplo-inventado/details', 'comment' => SECRET]),
        line(['submittedAt' => '2026-10-02T23:59:59+00:00', 'comment' => SMASH_SURVEY_TEST_PREFIX . ' — envío inventado']),
    ];
    fixture($file, $valid);
    $rows = smash_survey_parse_file($file);
    verify(count($rows) === 3, 'three rows parsed');
    verify($rows[0]['submitted_at'] === '2026-09-30 18:05:09.000000', 'UTC datetime with microseconds');
    verify($rows[0]['source_url'] === null && $rows[1]['source_url'] !== null, 'empty source becomes NULL');
    verify($rows[0]['comment'] !== null && strpos($rows[0]['comment'], "\n") !== false, 'multiline comment preserved');
    verify(line(['comment' => '']) !== '' && smash_survey_row(line(), 2)['comment'] === null, 'empty comment becomes NULL');
    verify($rows[1]['minimum_activity'] === 'otro', 'minimum maps to minimum_activity');
    verify([$rows[0]['is_test'], $rows[1]['is_test'], $rows[2]['is_test']] === [0, 0, 1], 'is_test follows panel rule');
    verify($rows[1]['import_hash'] === hash('sha256', $valid[1]), 'hash of original line bytes without newline');
    verify(strlen($rows[0]['import_hash']) === 64 && count(array_unique(array_column($rows, 'import_hash'))) === 3, 'distinct hashes');
    // The same response serialised differently is a different line: the hash follows bytes, not meaning.
    verify(smash_survey_line_hash($valid[0]) !== smash_survey_line_hash(json_encode(json_decode($valid[0], true))), 'byte-level hash');

    fixture($file, []);
    verify(smash_survey_parse_file($file) === [], 'guard only file is empty, not an error');

    rejects(fn() => smash_survey_parse_file($dir . '/missing.php'), 'file_missing');
    symlink($file, $dir . '/link.php');
    rejects(fn() => smash_survey_parse_file($dir . '/link.php'), 'file_missing');
    unlink($dir . '/link.php');
    fixture($file, $valid, "<?php exit; ?>\n");
    rejects(fn() => smash_survey_parse_file($file), 'guard_missing', 1);
    file_put_contents($file, '');
    rejects(fn() => smash_survey_parse_file($file), 'guard_missing', 1);
    fixture($file, $valid, SMASH_SURVEY_GUARD, '');
    rejects(fn() => smash_survey_parse_file($file), 'truncated_last_line', 4);
    fixture($file, [$valid[0], '', $valid[1]]);
    rejects(fn() => smash_survey_parse_file($file), 'empty_line', 3);
    fixture($file, [$valid[0], $valid[1], $valid[0]]);
    rejects(fn() => smash_survey_parse_file($file), 'duplicate_line', 4);
    fixture($file, [$valid[0], $valid[1] . "\r"]);
    rejects(fn() => smash_survey_parse_file($file), 'invalid_json', 3) ;

    $invalid = [
        'invalid_json' => '{"submittedAt":',
        'invalid_utf8' => substr(line(['comment' => 'ñ']), 0, -3) . "\xC3\"}",
        'line_too_long' => line(['comment' => str_repeat('a', 2000)]) . str_repeat(' ', SMASH_SURVEY_MAX_LINE_BYTES),
        'unexpected_fields' => line([], array_slice(SMASH_SURVEY_KEYS, 0, 9)),
        'invalid_submitted_at' => line(['submittedAt' => '2026-09-30T18:05:09-06:00']),
        'invalid_season_year' => line(['seasonYear' => '2026']),
        'invalid_role' => line(['role' => 'admin']),
        'invalid_eligibility' => line(['eligibility' => 'x']),
        'invalid_minimum' => line(['minimum' => '']),
        'invalid_international' => line(['international' => null]),
        'invalid_clarity' => line(['clarity' => 6]),
        'invalid_confidence' => line(['confidence' => '5']),
        'invalid_source' => line(['source' => 'https://example.com/tournament/x']),
        'invalid_comment' => line(['comment' => str_repeat('a', 2001)]),
    ];
    foreach ($invalid as $reason => $bad) {
        fixture($file, [$valid[0], $bad]);
        rejects(fn() => smash_survey_parse_file($file), $reason, 3);
    }
    foreach ([['unexpected_fields', json_encode(entry() + ['ip' => '203.0.113.9'])],
        ['unexpected_fields', line([], array_reverse(SMASH_SURVEY_KEYS))], ['invalid_json', '[]'], ['invalid_json', '"texto"'], ['invalid_json', ' ' . line()], ['unexpected_fields', '{}'],
        ['invalid_submitted_at', line(['submittedAt' => '2026-02-30T10:00:00+00:00'])],
        ['invalid_submitted_at', line(['submittedAt' => '2026-09-30T24:00:00+00:00'])],
        ['invalid_submitted_at', line(['submittedAt' => '2026-09-30 18:05:09'])],
        ['invalid_season_year', line(['seasonYear' => 2025])], ['invalid_clarity', line(['clarity' => 0])],
        ['invalid_clarity', line(['clarity' => 4.5])], ['invalid_source', line(['source' => 'http://start.gg/x'])],
        ['invalid_source', line(['source' => 'https://start.gg.example.com/x'])],
        ['invalid_source', line(['source' => 'https://start.gg/' . str_repeat('a', 250)])],
        ['invalid_comment', line(['comment' => ['x']])]] as [$reason, $bad]) {
        rejects(fn() => smash_survey_row($bad, 9), $reason, 9);
    }
    // Errors identify the line and reason only; private text never reaches the message.
    fixture($file, [$valid[1], line(['comment' => SECRET, 'clarity' => 9])]);
    try { smash_survey_parse_file($file); verify(false, 'must reject'); } catch (SmashSurveyImportError $error) {
        verify(strpos($error->getMessage(), SECRET) === false && strpos($error->getMessage(), 'start.gg') === false, 'no private text in errors');
        verify($error->getMessage() === 'Línea 3: invalid_clarity', 'message format');
    }
    echo "Survey parsing, validation and privacy checks passed.\n";

    $suite = static function (PDO $pdo, string $engine) use ($file, $valid, $dir): void {
        $count = static fn() => (int)$pdo->query('SELECT COUNT(*) FROM survey_responses')->fetchColumn();
        $dump = static fn() => $pdo->query('SELECT ' . implode(', ', SMASH_SURVEY_COLUMNS) . ' FROM survey_responses ORDER BY import_hash')->fetchAll(PDO::FETCH_ASSOC);
        verify($count() === 0, "$engine starts empty");
        fixture($file, $valid);
        $rows = smash_survey_parse_file($file);

        // A library caller's transaction belongs to the caller, including its pending writes.
        $pdo->beginTransaction();
        $pending = $pdo->prepare('INSERT INTO survey_responses (' . implode(', ', SMASH_SURVEY_COLUMNS) . ') VALUES ('
            . implode(', ', array_fill(0, count(SMASH_SURVEY_COLUMNS), '?')) . ')');
        $pending->execute(array_values($rows[0]));
        rejects(fn() => smash_survey_import($pdo, $rows, true), 'transaction_already_active');
        verify($pdo->inTransaction() && $count() === 1, "$engine caller transaction and row preserved");
        $pdo->rollBack();
        verify($count() === 0, "$engine caller controls rollback");

        $empty = smash_survey_compare($pdo, $rows);
        verify($empty['matched'] === 0 && $empty['missingInDatabase'] === 3 && $empty['fileFullyStored'] === false
            && $empty['databaseRows'] === 0, "$engine compare reports a file that was never imported");

        $dry = smash_survey_import($pdo, $rows, false);
        verify($dry['inserted'] === 3 && $dry['applied'] === false && $count() === 0, "$engine dry run writes nothing");
        $first = smash_survey_import($pdo, $rows, true);
        verify($first === ['fileRows' => 3, 'inserted' => 3, 'alreadyPresent' => 0, 'testRows' => 1, 'applied' => true,
            'tableRowsBefore' => 0, 'tableRowsAfter' => 3], "$engine first import");
        $stored = $dump();
        verify(count($stored) === 3, "$engine three rows stored");
        foreach ($rows as $row) {
            $match = array_values(array_filter($stored, static fn($s) => $s['import_hash'] === $row['import_hash']));
            verify(count($match) === 1 && smash_survey_same($row, $match[0]), "$engine stored values equal the file");
        }
        verify((int)$pdo->query('SELECT COUNT(*) FROM survey_responses WHERE is_test = 1')->fetchColumn() === 1, "$engine is_test kept");
        verify((int)$pdo->query('SELECT COUNT(*) FROM survey_responses WHERE comment IS NULL OR source_url IS NULL')->fetchColumn() === 2, "$engine NULLs");

        // Row-by-row evidence, counts only and without writing.
        verify(smash_survey_compare($pdo, $rows) === ['fileRows' => 3, 'matched' => 3, 'missingInDatabase' => 0,
            'valueMismatches' => 0, 'fileTestRows' => 1, 'databaseRows' => 3, 'databaseTestRows' => 1,
            'databaseRowsNotInFile' => 0, 'fileFullyStored' => true], "$engine compare proves the copy");
        verify($dump() === $stored && !$pdo->inTransaction(), "$engine compare is read-only");

        $second = smash_survey_import($pdo, smash_survey_parse_file($file), true);
        verify($second['inserted'] === 0 && $second['alreadyPresent'] === 3 && $count() === 3, "$engine repeat is a no-op");
        verify($dump() === $stored, "$engine repeat changes no value");

        // The live file only grows: a later run adds just the new lines.
        $extra = line(['submittedAt' => '2026-10-05T12:00:00+00:00', 'role' => 'espectador']);
        fixture($file, array_merge($valid, [$extra]));
        $third = smash_survey_import($pdo, smash_survey_parse_file($file), true);
        verify($third['inserted'] === 1 && $third['alreadyPresent'] === 3 && $count() === 4, "$engine appended line");

        // Rows that are not lines of this file (another file, or answers received by the SQL form,
        // which carry their own key or none) are counted apart and never fail the copy check.
        $pending->execute(array_merge(array_slice(array_values($rows[1]), 0, 11), [null]));
        $apart = smash_survey_compare($pdo, $rows);
        verify($apart['fileFullyStored'] === true && $apart['matched'] === 3 && $apart['databaseRows'] === 5
            && $apart['databaseRowsNotInFile'] === 2, "$engine compare separates rows that are not in the file");
        $pdo->exec('DELETE FROM survey_responses WHERE import_hash IS NULL');

        // An invalid line anywhere rejects the file before any write.
        fixture($file, array_merge($valid, [line(['submittedAt' => '2026-10-06T12:00:00+00:00']), line(['clarity' => 7])]));
        rejects(fn() => smash_survey_import($pdo, smash_survey_parse_file($file), true), 'invalid_clarity', 6);
        verify($count() === 4, "$engine invalid file inserts nothing");

        // A failure in the middle of the transaction rolls back the rows already inserted in it.
        $late = [smash_survey_row(line(['submittedAt' => '2026-10-07T01:00:00+00:00']), 2),
            smash_survey_row(line(['submittedAt' => '2026-10-07T02:00:00+00:00']), 3)];
        $late[1]['clarity'] = null;
        rejects(fn() => smash_survey_import($pdo, $late, true), 'database_write_failed');
        verify($count() === 4 && !$pdo->inTransaction(), "$engine mid-transaction failure rolls back");

        // A stored row that no longer matches its hash is reported, not overwritten.
        $pdo->exec("UPDATE survey_responses SET clarity = 2 WHERE import_hash = '" . $rows[0]['import_hash'] . "'");
        fixture($file, $valid);
        rejects(fn() => smash_survey_import($pdo, smash_survey_parse_file($file), true), 'hash_conflict', 2);
        verify((int)$pdo->query("SELECT clarity FROM survey_responses WHERE import_hash = '" . $rows[0]['import_hash'] . "'")->fetchColumn() === 2, "$engine conflict not overwritten");
        $changed = smash_survey_compare($pdo, $rows);
        verify($changed['valueMismatches'] === 1 && $changed['matched'] === 2 && $changed['fileFullyStored'] === false,
            "$engine compare detects a stored value that differs from its line");
        echo "Survey import, repetition and rollback passed on $engine.\n";
    };

    $sqlite = new PDO('sqlite::memory:', null, null, [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
    $sqlite->exec('CREATE TABLE survey_responses (id INTEGER PRIMARY KEY AUTOINCREMENT, submitted_at TEXT NOT NULL,
        season_year INTEGER NOT NULL, role TEXT NOT NULL, eligibility TEXT NOT NULL, minimum_activity TEXT NOT NULL,
        international TEXT NOT NULL, clarity INTEGER NOT NULL, confidence INTEGER NOT NULL, source_url TEXT NULL,
        comment TEXT NULL, is_test INTEGER NOT NULL DEFAULT 0, import_hash TEXT NULL UNIQUE)');
    $suite($sqlite, 'SQLite stand-in');

    if (getenv('SMASH_SCHEMA_TEST_DB')) {
        verify(strpos(getenv('SMASH_SCHEMA_TEST_DB'), 'smash_schema_test') === 0, 'disposable database only');
        require dirname(__DIR__, 2) . '/ranking-smash-ultimate/database.php';
        $pdo = smash_database_connect(['host' => '127.0.0.1', 'port' => (int)getenv('SMASH_SCHEMA_TEST_PORT'),
            'name' => getenv('SMASH_SCHEMA_TEST_DB'), 'user' => 'root', 'password' => (string)getenv('SMASH_SCHEMA_TEST_PASSWORD')]);
        $pdo->exec('DELETE FROM survey_responses');
        try {
            $suite($pdo, (string)$pdo->query('SELECT VERSION()')->fetchColumn());
        } finally {
            $pdo->exec('DELETE FROM survey_responses');
        }
    }
} finally {
    foreach (glob($dir . '/*') ?: [] as $leftover) unlink($leftover);
    rmdir($dir);
}
