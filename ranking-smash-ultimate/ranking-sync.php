<?php
declare(strict_types=1);
ini_set('display_errors', '0');
require_once __DIR__ . '/ranking-sync-lib.php';
header('Content-Type: application/json; charset=utf-8'); header('Cache-Control: no-store, private');
header('X-Content-Type-Options: nosniff'); header('Referrer-Policy: no-referrer');
function sr_response(int $status, array $data): void { http_response_code($status); echo json_encode($data, JSON_THROW_ON_ERROR); exit; }
if ($_SERVER['REQUEST_METHOD'] !== 'POST') { header('Allow: POST'); sr_response(405, ['ok' => false, 'reason' => 'method_not_allowed']); }
if ((int)($_SERVER['CONTENT_LENGTH'] ?? 0) > SR_COMPRESSED_MAX) sr_response(413, ['ok' => false, 'reason' => 'payload_too_large']);
try {
    $config = sr_sync_config(__DIR__);
    $body = file_get_contents('php://input', false, null, 0, SR_COMPRESSED_MAX + 1); sr_require(strlen($body) <= SR_COMPRESSED_MAX, 'payload_invalid');
    $auth = sr_auth($config, $_SERVER, $body, time()); sr_nonce($config, $auth, time());
    $type = strtolower(trim(explode(';', $_SERVER['CONTENT_TYPE'] ?? '')[0]));
    sr_require(in_array($type, ['application/gzip', 'application/json'], true), 'content_type_invalid');
    $db = smash_database_connect(smash_database_config(__DIR__));
    if ($type === 'application/gzip') sr_response(202, ['ok' => true] + sr_receive($db, $config, $body, $auth['hash']));
    sr_require(strlen($body) <= 1024, 'payload_invalid'); $request = json_decode($body, true, 16, JSON_THROW_ON_ERROR);
    if (($request['operation'] ?? null) === 'diagnostic') {
        $last = $db->query("SELECT status,error_code FROM sync_jobs WHERE kind='ranking_import' ORDER BY id DESC LIMIT 1")->fetch();
        sr_response(200, ['ok' => true, 'phpVersion' => PHP_MAJOR_VERSION . '.' . PHP_MINOR_VERSION, 'memoryLimit' => ini_get('memory_limit'),
            'postMaxSize' => ini_get('post_max_size'), 'maxExecutionTime' => ini_get('max_execution_time'), 'inboxWritable' => is_writable(sr_sync_directory($config)),
            'lastJob' => $last ?: null]);
    }
    sr_require(($request['operation'] ?? null) === 'status' && is_string($request['sha256'] ?? null) && preg_match('/\A[a-f0-9]{64}\z/D', $request['sha256']) === 1, 'payload_invalid');
    $job = sr_job($db, $request['sha256']); sr_response($job === null ? 404 : 200, $job === null ? ['ok' => false, 'reason' => 'job_not_found'] : ['ok' => true] + $job);
} catch (Throwable $e) {
    $reason = $e instanceof SmashRankingError ? $e->reason : 'receiver_unavailable';
    $status = ['unauthorized' => 401, 'replayed_request' => 409, 'content_type_invalid' => 415, 'payload_invalid' => 400][$reason] ?? 503;
    sr_response($status, ['ok' => false, 'reason' => $reason]);
}
