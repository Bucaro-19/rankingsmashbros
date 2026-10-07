<?php
declare(strict_types=1);
// Disposable-test bridge. Never deployed; refuses external/production databases.
require_once __DIR__ . '/../../ranking-smash-ultimate/ranking-sync-lib.php';
set_error_handler(static function () { throw new SmashRankingError('runtime_failure'); });
try {
    $mode = $argv[1];
    if ($mode === 'auth') {
        $input = json_decode(file_get_contents($argv[2]), true, 512, JSON_THROW_ON_ERROR);
        $report = sr_auth(['key' => $input['key']], $input['headers'], $input['body'], $input['now']);
        if (isset($input['private'])) { sr_nonce(['private' => $input['private']], $report, $input['now']); sr_nonce(['private' => $input['private']], $report, $input['now']); }
    } else {
        $package = $mode === 'worker' ? null : sr_package(file_get_contents($argv[2]));
        if ($mode === 'validate') $report = ['sha256' => $package['sha256'], 'peakMemoryBytes' => memory_get_peak_usage(true)];
        else {
            $name = getenv('SMASH_SCHEMA_TEST_DB'); $host = getenv('SMASH_SCHEMA_TEST_HOST') ?: '127.0.0.1';
            sr_require(is_string($name) && strpos($name, 'smash_schema_test') === 0 && in_array($host, ['localhost', '127.0.0.1'], true), 'test_database_required');
            $db = smash_database_connect(['host' => $host, 'name' => $name, 'port' => (int)(getenv('SMASH_SCHEMA_TEST_PORT') ?: 3306), 'user' => 'root', 'password' => getenv('SMASH_SCHEMA_TEST_PASSWORD')]);
            if ($mode === 'worker') $report = sr_process($db, $argv[2], ['private' => $argv[3]]);
            else $report = sr_import($db, $package, $mode === 'apply');
        }
    }
    echo json_encode(['ok' => true, 'result' => $report], JSON_THROW_ON_ERROR) . "\n";
} catch (Throwable $e) { echo json_encode(['ok' => false, 'reason' => $e instanceof SmashRankingError ? $e->reason : 'test_failed']) . "\n"; exit(1); }
