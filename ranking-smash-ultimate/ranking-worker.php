<?php
declare(strict_types=1);
if (PHP_SAPI !== 'cli') { http_response_code(403); exit; }
ini_set('display_errors', '0');
require_once __DIR__ . '/ranking-sync-lib.php';
set_error_handler(static function () { throw new SmashRankingError('runtime_failure'); });
try {
    $config = sr_sync_config(__DIR__); $db = smash_database_connect(smash_database_config(__DIR__));
    $report = sr_process($db, __DIR__, $config);
    $report['peakMemoryBytes'] = memory_get_peak_usage(true);
    echo json_encode($report, JSON_THROW_ON_ERROR) . "\n"; exit($report['ok'] ? 0 : 1);
} catch (Throwable $e) {
    echo json_encode(['ok' => false, 'reason' => $e instanceof SmashRankingError ? $e->reason : 'worker_unavailable']) . "\n"; exit(1);
}
