<?php
declare(strict_types=1);

// Library only. Apache blocks direct access; nothing is read or written on inclusion.
// Storage of the anonymous community survey in survey_responses. No IP, e-mail, account,
// user agent or session identifier is ever stored or logged here.

const SMASH_SURVEY_SEASON = 2026;
// Same rule the file era used to hide the internal technical submission from the panel.
const SMASH_SURVEY_INTERNAL_TEST_PREFIX = 'PRUEBA TÉCNICA INTERNA';
const SMASH_SURVEY_OPTIONS = [
    'role' => ['jugador', 'organizador', 'espectador', 'otro'],
    'eligibility' => ['nacionalidad-local', 'nacionalidad', 'otra'],
    'minimum' => ['2-eventos-4-sets', '3-eventos-6-sets', 'otro'],
    'international' => ['todos-validos', 'solo-grandes', 'ninguno'],
];

final class SmashSurveyStorageError extends RuntimeException
{
    public $reason;
    public function __construct(string $reason)
    {
        $this->reason = $reason;
        // Driver messages can quote row values; only a reason code leaves this library.
        parent::__construct('No se pudo completar la operación de la encuesta.');
    }
}

// Opens the private connection only when a caller is about to read or write answers.
function smash_survey_connect(string $siteRoot): PDO
{
    $pdo = smash_database_connect(smash_database_config($siteRoot));
    try {
        // The hosting default is not strict: without this an over-long or invalid value
        // would be truncated with a warning instead of rejecting the statement.
        $pdo->exec("SET SESSION sql_mode = CONCAT(@@sql_mode, ',STRICT_TRANS_TABLES')");
        // A stalled table must fail this request quickly instead of parking a PHP worker.
        $pdo->exec('SET SESSION innodb_lock_wait_timeout = 5, lock_wait_timeout = 5');
    } catch (PDOException $error) {
        throw new SmashSurveyStorageError('session_setup_failed');
    }
    return $pdo;
}

// The file era stored comments through json_encode with JSON_INVALID_UTF8_SUBSTITUTE,
// so invalid bytes became U+FFFD. Keep that exact transformation before binding to utf8mb4.
function smash_survey_clean_text(string $value): string
{
    $encoded = json_encode($value, JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE);
    $clean = is_string($encoded) ? json_decode($encoded) : null;
    return is_string($clean) ? $clean : '';
}

// Retry key of a web answer: the random per-session form token plus the exact answer. Sending
// the same answer again with the same form (lost confirmation, browser resend) hits the unique
// key and adds nothing; a different answer is a different key and is stored like any other.
// The key identifies a submission attempt, never a person.
function smash_survey_submission_key(string $formToken, array $row): string
{
    if (!preg_match('/\A[0-9a-f]{48}\z/D', $formToken)) throw new SmashSurveyStorageError('invalid_form_token');
    $answer = json_encode([$row['season_year'], $row['role'], $row['eligibility'], $row['minimum_activity'],
        $row['international'], $row['clarity'], $row['confidence'], $row['source_url'], $row['comment']],
        JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    if (!is_string($answer)) throw new SmashSurveyStorageError('invalid_answer');
    return hash('sha256', "smashgt-encuesta-web-v1\n" . $formToken . "\n" . hash('sha256', $answer));
}

// Reason code or class name of a failure, safe to log: never a message, a value or a visitor datum.
function smash_survey_failure_code(Throwable $failure): string
{
    $reason = ($failure instanceof SmashSurveyStorageError || $failure instanceof SmashDatabaseError) ? $failure->reason : null;
    return is_string($reason) && preg_match('/\A[a-z_]{1,60}\z/D', $reason) ? $reason : get_class($failure);
}

// Builds the stored row from an answer already validated by the form handler. The checks are
// repeated here so no other caller can put out-of-contract values into the table.
function smash_survey_row_from_answer(array $answer, int $now): array
{
    foreach (SMASH_SURVEY_OPTIONS as $field => $allowed) {
        if (!is_string($answer[$field] ?? null) || !in_array($answer[$field], $allowed, true)) {
            throw new SmashSurveyStorageError('invalid_answer');
        }
    }
    foreach (['clarity', 'confidence'] as $field) {
        if (!is_int($answer[$field] ?? null) || $answer[$field] < 1 || $answer[$field] > 5) {
            throw new SmashSurveyStorageError('invalid_answer');
        }
    }
    $source = $answer['source'] ?? null;
    $comment = $answer['comment'] ?? null;
    // Byte limits, exactly as the form handler has always enforced them.
    if (!is_string($source) || !is_string($comment) || strlen($source) > 250 || strlen($comment) > 2000 || $now < 1) {
        throw new SmashSurveyStorageError('invalid_answer');
    }
    $comment = smash_survey_clean_text($comment);
    $source = smash_survey_clean_text($source);
    return [
        // PHP clock in UTC with second precision, the same clock and shape as the imported rows.
        'submitted_at' => gmdate('Y-m-d H:i:s', $now) . '.000000',
        'season_year' => SMASH_SURVEY_SEASON,
        'role' => $answer['role'],
        'eligibility' => $answer['eligibility'],
        'minimum_activity' => $answer['minimum'],
        'international' => $answer['international'],
        'clarity' => $answer['clarity'],
        'confidence' => $answer['confidence'],
        'source_url' => $source === '' ? null : $source,
        'comment' => $comment === '' ? null : $comment,
        'is_test' => strpos($comment, SMASH_SURVEY_INTERNAL_TEST_PREFIX) === 0 ? 1 : 0,
    ];
}

// Returns 'inserted' or 'already_saved'. Anything else throws: the caller must not report
// success, must not mark the session and must not write anywhere else.
function smash_survey_store(PDO $pdo, array $answer, string $formToken, int $now): string
{
    $row = smash_survey_row_from_answer($answer, $now);
    $row['import_hash'] = smash_survey_submission_key($formToken, $row);
    // Own the transaction: a caller's pending work must never be committed or rolled back here.
    if ($pdo->inTransaction()) throw new SmashSurveyStorageError('transaction_already_active');
    $columns = array_keys($row);
    $confirmed = false;
    try {
        // Explicit transaction: the answer is durable because it was committed, not because the
        // server happens to run with autocommit.
        $pdo->beginTransaction();
        $insert = $pdo->prepare('INSERT INTO survey_responses (' . implode(', ', $columns) . ') VALUES ('
            . implode(', ', array_fill(0, count($columns), '?')) . ')');
        $insert->execute(array_values($row));
        $confirmed = $insert->rowCount() === 1;
        if ($confirmed) $pdo->commit();
        else $pdo->rollBack();
    } catch (PDOException $error) {
        try {
            if ($pdo->inTransaction()) $pdo->rollBack();
        } catch (PDOException $ignored) {
        }
        // Integrity errors include CHECK violations as well as the unique retry key. Only a row
        // that really exists under this key means this same answer of this form is already stored.
        if (substr((string)$error->getCode(), 0, 2) === '23' && smash_survey_key_exists($pdo, $row['import_hash'])) {
            return 'already_saved';
        }
        throw new SmashSurveyStorageError('write_failed');
    }
    if (!$confirmed) throw new SmashSurveyStorageError('write_unconfirmed');
    return 'inserted';
}

function smash_survey_key_exists(PDO $pdo, string $submissionKey): bool
{
    try {
        $find = $pdo->prepare('SELECT COUNT(*) FROM survey_responses WHERE import_hash = ?');
        $find->execute([$submissionKey]);
        return (int)$find->fetchColumn() === 1;
    } catch (PDOException $error) {
        return false;
    }
}

// Community answers of the season in the shape the private panel has always rendered:
// newest first, internal test entries excluded, NULL shown as empty text.
function smash_survey_rows(PDO $pdo): array
{
    try {
        $select = $pdo->prepare('SELECT submitted_at, role, eligibility, minimum_activity, international,'
            . ' clarity, confidence, source_url, comment FROM survey_responses'
            . ' WHERE season_year = ? AND is_test = 0 ORDER BY submitted_at DESC, id ASC');
        $select->execute([SMASH_SURVEY_SEASON]);
        $stored = $select->fetchAll(PDO::FETCH_ASSOC);
    } catch (PDOException $error) {
        throw new SmashSurveyStorageError('read_failed');
    }
    $rows = [];
    foreach ($stored as $row) {
        $at = (string)$row['submitted_at'];
        if (!preg_match('/\A\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}/', $at)) throw new SmashSurveyStorageError('read_failed');
        $rows[] = [
            // DATETIME carries no offset; the stored instant is UTC and must say so explicitly.
            'submittedAt' => substr($at, 0, 10) . 'T' . substr($at, 11, 8) . '+00:00',
            'role' => (string)$row['role'],
            'eligibility' => (string)$row['eligibility'],
            'minimum' => (string)$row['minimum_activity'],
            'international' => (string)$row['international'],
            // Drivers may return numeric columns as strings; the panel averages integers only.
            'clarity' => (int)$row['clarity'],
            'confidence' => (int)$row['confidence'],
            'source' => (string)($row['source_url'] ?? ''),
            'comment' => (string)($row['comment'] ?? ''),
        ];
    }
    return $rows;
}
