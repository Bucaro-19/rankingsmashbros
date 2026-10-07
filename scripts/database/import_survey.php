<?php
declare(strict_types=1);

// Importador de la encuesta anónima hacia survey_responses.
// Biblioteca + CLI. No cambia quién lee o escribe la encuesta: solo copia líneas ya guardadas.
// Nunca imprime comentarios, enlaces ni credenciales; los errores indican línea y motivo.

const SMASH_SURVEY_GUARD = "<?php http_response_code(404); exit; ?>\n";
const SMASH_SURVEY_TEST_PREFIX = 'PRUEBA TÉCNICA INTERNA';
const SMASH_SURVEY_MAX_FILE_BYTES = 5 * 1024 * 1024;
const SMASH_SURVEY_MAX_LINE_BYTES = 32768;
const SMASH_SURVEY_KEYS = ['submittedAt', 'seasonYear', 'role', 'eligibility', 'minimum',
    'international', 'clarity', 'confidence', 'source', 'comment'];
const SMASH_SURVEY_CHOICES = [
    'role' => ['jugador', 'organizador', 'espectador', 'otro'],
    'eligibility' => ['nacionalidad-local', 'nacionalidad', 'otra'],
    'minimum' => ['2-eventos-4-sets', '3-eventos-6-sets', 'otro'],
    'international' => ['todos-validos', 'solo-grandes', 'ninguno'],
];
const SMASH_SURVEY_COLUMNS = ['submitted_at', 'season_year', 'role', 'eligibility', 'minimum_activity',
    'international', 'clarity', 'confidence', 'source_url', 'comment', 'is_test', 'import_hash'];

final class SmashSurveyImportError extends RuntimeException
{
    public $reason;
    public $lineNumber;
    public function __construct(string $reason, ?int $lineNumber = null)
    {
        $this->reason = $reason;
        $this->lineNumber = $lineNumber;
        // The message never carries file contents, only where and why.
        parent::__construct(($lineNumber === null ? '' : 'Línea ' . $lineNumber . ': ') . $reason);
    }
}

// Regla fija del hash: SHA-256 de los bytes exactos de la línea, sin su salto de línea final.
function smash_survey_line_hash(string $lineWithoutNewline): string
{
    return hash('sha256', $lineWithoutNewline);
}

function smash_survey_row(string $line, int $number): array
{
    if ($line === '') throw new SmashSurveyImportError('empty_line', $number);
    if (strlen($line) > SMASH_SURVEY_MAX_LINE_BYTES) throw new SmashSurveyImportError('line_too_long', $number);
    if (!mb_check_encoding($line, 'UTF-8')) throw new SmashSurveyImportError('invalid_utf8', $number);
    // encuesta.php writes one compact object per line; padding or CRLF means the file was edited.
    if ($line[0] !== '{' || substr($line, -1) !== '}') throw new SmashSurveyImportError('invalid_json', $number);
    try {
        $entry = json_decode($line, true, 4, JSON_THROW_ON_ERROR);
    } catch (JsonException $error) {
        throw new SmashSurveyImportError('invalid_json', $number);
    }
    if (!is_array($entry) || array_keys($entry) !== SMASH_SURVEY_KEYS) {
        throw new SmashSurveyImportError('unexpected_fields', $number);
    }
    // encuesta.php writes gmdate('c'): always UTC with an explicit +00:00 offset.
    $at = $entry['submittedAt'];
    if (!is_string($at) || !preg_match('/\A(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})\+00:00\z/D', $at, $m)
        || !checkdate((int)$m[2], (int)$m[3], (int)$m[1]) || (int)$m[4] > 23 || (int)$m[5] > 59 || (int)$m[6] > 59) {
        throw new SmashSurveyImportError('invalid_submitted_at', $number);
    }
    $year = $entry['seasonYear'];
    if (!is_int($year) || $year < 2026 || $year > 2100) throw new SmashSurveyImportError('invalid_season_year', $number);
    foreach (SMASH_SURVEY_CHOICES as $field => $allowed) {
        if (!is_string($entry[$field]) || !in_array($entry[$field], $allowed, true)) {
            throw new SmashSurveyImportError('invalid_' . $field, $number);
        }
    }
    foreach (['clarity', 'confidence'] as $field) {
        if (!is_int($entry[$field]) || $entry[$field] < 1 || $entry[$field] > 5) {
            throw new SmashSurveyImportError('invalid_' . $field, $number);
        }
    }
    $source = $entry['source'];
    if (!is_string($source) || strlen($source) > 250) throw new SmashSurveyImportError('invalid_source', $number);
    if ($source !== '') {
        $parts = filter_var($source, FILTER_VALIDATE_URL) ? parse_url($source) : false;
        if (!is_array($parts) || ($parts['scheme'] ?? '') !== 'https'
            || !in_array(strtolower((string)($parts['host'] ?? '')), ['start.gg', 'www.start.gg'], true)) {
            throw new SmashSurveyImportError('invalid_source', $number);
        }
    }
    $comment = $entry['comment'];
    if (!is_string($comment) || strlen($comment) > 2000) throw new SmashSurveyImportError('invalid_comment', $number);
    return [
        'submitted_at' => "$m[1]-$m[2]-$m[3] $m[4]:$m[5]:$m[6].000000",
        'season_year' => $year,
        'role' => $entry['role'],
        'eligibility' => $entry['eligibility'],
        'minimum_activity' => $entry['minimum'],
        'international' => $entry['international'],
        'clarity' => $entry['clarity'],
        'confidence' => $entry['confidence'],
        'source_url' => $source === '' ? null : $source,
        'comment' => $comment === '' ? null : $comment,
        // Same rule opiniones.php uses to hide the internal technical submission.
        'is_test' => strpos($comment, SMASH_SURVEY_TEST_PREFIX) === 0 ? 1 : 0,
        'import_hash' => smash_survey_line_hash($line),
    ];
}

// Reads the whole protected file under a shared lock. Any invalid line rejects the file:
// a partial result must never be mistaken for a complete migration.
function smash_survey_parse_file(string $path): array
{
    if (!is_file($path) || is_link($path)) throw new SmashSurveyImportError('file_missing');
    $handle = @fopen($path, 'rb');
    if (!$handle) throw new SmashSurveyImportError('file_unreadable');
    try {
        if (!flock($handle, LOCK_SH)) throw new SmashSurveyImportError('file_locked');
        $size = fstat($handle)['size'] ?? 0;
        if ($size > SMASH_SURVEY_MAX_FILE_BYTES) throw new SmashSurveyImportError('file_too_large');
        $content = $size > 0 ? fread($handle, $size) : '';
        flock($handle, LOCK_UN);
    } finally {
        fclose($handle);
    }
    if (!is_string($content) || strlen($content) !== $size) throw new SmashSurveyImportError('file_unreadable');
    if (strncmp($content, SMASH_SURVEY_GUARD, strlen(SMASH_SURVEY_GUARD)) !== 0) {
        throw new SmashSurveyImportError('guard_missing', 1);
    }
    $body = substr($content, strlen(SMASH_SURVEY_GUARD));
    if ($body === '') return [];
    // Every response is written with its newline; a missing one means a truncated write.
    if (substr($body, -1) !== "\n") {
        throw new SmashSurveyImportError('truncated_last_line', substr_count($content, "\n") + 1);
    }
    $rows = [];
    $seen = [];
    foreach (explode("\n", substr($body, 0, -1)) as $index => $line) {
        $number = $index + 2;
        $row = smash_survey_row($line, $number);
        if (isset($seen[$row['import_hash']])) throw new SmashSurveyImportError('duplicate_line', $number);
        $seen[$row['import_hash']] = true;
        $rows[] = $row;
    }
    return $rows;
}

function smash_survey_same(array $row, array $stored): bool
{
    foreach (SMASH_SURVEY_COLUMNS as $column) {
        $a = $row[$column];
        $b = $stored[$column] ?? null;
        if ($a === null || $b === null) {
            if ($a !== $b) return false;
        } elseif ((string)$a !== (string)$b) {
            return false;
        }
    }
    return true;
}

// One transaction for the whole file. Re-running inserts nothing; a stored row that no longer
// matches its hash is a conflict to audit, never overwritten.
function smash_survey_import(PDO $pdo, array $rows, bool $apply): array
{
    $find = 'SELECT ' . implode(', ', SMASH_SURVEY_COLUMNS) . ' FROM survey_responses WHERE import_hash = ?';
    $insert = 'INSERT INTO survey_responses (' . implode(', ', SMASH_SURVEY_COLUMNS) . ') VALUES ('
        . implode(', ', array_fill(0, count(SMASH_SURVEY_COLUMNS), '?')) . ')';
    $result = ['fileRows' => count($rows), 'inserted' => 0, 'alreadyPresent' => 0,
        'testRows' => count(array_filter($rows, static fn($row) => $row['is_test'] === 1)), 'applied' => false];
    try {
        $pdo->beginTransaction();
        $before = (int)$pdo->query('SELECT COUNT(*) FROM survey_responses')->fetchColumn();
        $findStatement = $pdo->prepare($find);
        $insertStatement = $pdo->prepare($insert);
        foreach ($rows as $index => $row) {
            $findStatement->execute([$row['import_hash']]);
            $stored = $findStatement->fetch(PDO::FETCH_ASSOC);
            $findStatement->closeCursor();
            if ($stored !== false) {
                if (!smash_survey_same($row, $stored)) throw new SmashSurveyImportError('hash_conflict', $index + 2);
                $result['alreadyPresent']++;
                continue;
            }
            $insertStatement->execute(array_map(static fn($column) => $row[$column], SMASH_SURVEY_COLUMNS));
            $result['inserted']++;
        }
        $after = (int)$pdo->query('SELECT COUNT(*) FROM survey_responses')->fetchColumn();
        if ($after !== $before + $result['inserted']) throw new SmashSurveyImportError('count_mismatch');
        $result['tableRowsBefore'] = $before;
        $result['tableRowsAfter'] = $apply ? $after : $before;
        if ($apply) {
            $pdo->commit();
            $result['applied'] = true;
        } else {
            $pdo->rollBack();
        }
        return $result;
    } catch (Throwable $error) {
        if ($pdo->inTransaction()) $pdo->rollBack();
        if ($error instanceof SmashSurveyImportError) throw $error;
        // PDO messages may quote row values; keep them out of the output.
        throw new SmashSurveyImportError('database_write_failed');
    }
}

function smash_survey_cli(array $argv): int
{
    $options = ['file' => null, 'site-root' => null, 'apply' => false];
    for ($i = 1; $i < count($argv); $i++) {
        if ($argv[$i] === '--apply') $options['apply'] = true;
        elseif (in_array($argv[$i], ['--file', '--site-root'], true) && isset($argv[$i + 1])) $options[substr($argv[$i], 2)] = $argv[++$i];
        else {
            fwrite(STDERR, "Uso: php import_survey.php --file RUTA [--site-root CARPETA_DEL_SITIO] [--apply]\n");
            return 2;
        }
    }
    if ($options['file'] === null || ($options['apply'] && $options['site-root'] === null)) {
        fwrite(STDERR, "Uso: php import_survey.php --file RUTA [--site-root CARPETA_DEL_SITIO] [--apply]\n");
        return 2;
    }
    try {
        $rows = smash_survey_parse_file($options['file']);
        $summary = ['fileRows' => count($rows),
            'testRows' => count(array_filter($rows, static fn($row) => $row['is_test'] === 1)), 'applied' => false];
        if ($options['site-root'] !== null) {
            require_once $options['site-root'] . '/database.php';
            $pdo = smash_database_connect(smash_database_config($options['site-root']));
            $summary = smash_survey_import($pdo, $rows, $options['apply']);
        }
        echo json_encode(['ok' => true] + $summary, JSON_PRETTY_PRINT) . "\n";
        return 0;
    } catch (SmashSurveyImportError $error) {
        fwrite(STDERR, json_encode(['ok' => false, 'reason' => $error->reason, 'line' => $error->lineNumber]) . "\n");
        return 1;
    } catch (Throwable $error) {
        $reason = property_exists($error, 'reason') && is_string($error->reason) ? $error->reason : 'unexpected_failure';
        fwrite(STDERR, json_encode(['ok' => false, 'reason' => $reason, 'line' => null]) . "\n");
        return 1;
    }
}

if (PHP_SAPI === 'cli' && isset($argv[0]) && realpath($argv[0]) === __FILE__) {
    ini_set('display_errors', '0');
    exit(smash_survey_cli($argv));
}
