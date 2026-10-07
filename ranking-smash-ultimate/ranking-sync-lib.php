<?php
declare(strict_types=1);
require_once __DIR__ . '/database.php';
require_once __DIR__ . '/ranking-import.php';

const SR_SYNC_PATH = '/ranking-sync.php';
const SR_COMPRESSED_MAX = 4 * 1024 * 1024;
function sr_sync_config(string $root): array {
    $root = realpath($root); sr_require($root !== false, 'config_invalid');
    $private = dirname($root) . '/private-smash'; $file = $private . '/sync.local.php';
    sr_require(is_file($file) && realpath($file) === $file, 'sync_not_configured');
    $level = ob_get_level(); ob_start();
    try { $config = (static function ($path) { return require $path; })($file); }
    finally { while (ob_get_level() > $level) ob_end_clean(); }
    sr_require(is_array($config) && ($config['enabled'] ?? false) === true, 'sync_disabled');
    sr_require(is_string($config['key'] ?? null) && preg_match('/\A[a-f0-9]{64}\z/D', $config['key']) === 1, 'config_invalid');
    $config['private'] = $private; return $config;
}
function sr_sync_directory(array $config): string {
    $path = $config['private'] . '/ranking-inbox';
    if (!is_dir($path)) sr_require(mkdir($path, 0700), 'inbox_unavailable');
    sr_require(realpath($path) === $path && is_writable($path), 'inbox_unavailable');
    return $path;
}
function sr_signature(string $key, string $at, string $nonce, string $hash): string {
    return hash_hmac('sha256', "POST\n" . SR_SYNC_PATH . "\n$at\n$nonce\n$hash", $key);
}
function sr_auth(array $config, array $headers, string $body, int $now): array {
    $at = $headers['HTTP_X_SMASH_TIMESTAMP'] ?? ''; $nonce = $headers['HTTP_X_SMASH_NONCE'] ?? ''; $sig = $headers['HTTP_X_SMASH_SIGNATURE'] ?? '';
    sr_require(is_string($at) && preg_match('/\A[0-9]{10}\z/D', $at) === 1 && abs($now - (int)$at) <= 300
        && is_string($nonce) && preg_match('/\A[a-f0-9]{32}\z/D', $nonce) === 1
        && is_string($sig) && preg_match('/\A[a-f0-9]{64}\z/D', $sig) === 1, 'unauthorized');
    $hash = hash('sha256', $body); sr_require(hash_equals(sr_signature($config['key'], $at, $nonce, $hash), $sig), 'unauthorized');
    return ['nonce' => $nonce, 'timestamp' => (int)$at, 'hash' => $hash];
}
function sr_nonce(array $config, array $auth, int $now): void {
    $file = $config['private'] . '/ranking-nonces.json';
    sr_require(!is_link($file), 'inbox_unavailable');
    $handle = fopen($file, 'c+'); sr_require($handle !== false, 'inbox_unavailable'); chmod($file, 0600);
    try {
        sr_require(flock($handle, LOCK_EX), 'inbox_unavailable');
        $raw = stream_get_contents($handle, 128 * 1024); $seen = $raw === '' ? [] : json_decode($raw, true, 512, JSON_THROW_ON_ERROR);
        sr_require(is_array($seen), 'inbox_unavailable');
        $seen = array_filter($seen, static function ($time) use ($now) { return is_int($time) && $time >= $now - 600; });
        sr_require(!isset($seen[$auth['nonce']]), 'replayed_request'); sr_require(count($seen) < 1500, 'receiver_busy');
        $seen[$auth['nonce']] = $now; $raw = json_encode($seen, JSON_THROW_ON_ERROR);
        rewind($handle); sr_require(ftruncate($handle, 0) && fwrite($handle, $raw) === strlen($raw) && fflush($handle), 'inbox_unavailable');
    } finally { flock($handle, LOCK_UN); fclose($handle); }
}
function sr_job(PDO $db, string $hash): ?array {
    $s = $db->prepare("SELECT id,status,error_code,requests_count FROM sync_jobs WHERE deduplication_key=? AND kind='ranking_import'"); $s->execute([$hash]);
    $r = $s->fetch(); return $r === false ? null : ['jobId' => (int)$r['id'], 'status' => $r['status'], 'reason' => $r['error_code'], 'attempts' => (int)$r['requests_count']];
}
function sr_receive(PDO $db, array $config, string $body, string $hash): array {
    sr_require(strlen($body) <= SR_COMPRESSED_MAX && substr($body, 0, 2) === "\x1f\x8b", 'payload_invalid');
    $lock = 'smash-ranking-receive-v1'; sr_require((int)sr_query($db, 'SELECT GET_LOCK(?,0)', [$lock])[0][0] === 1, 'receiver_busy');
    try {
        $job = sr_job($db, $hash); if ($job !== null) return $job;
        $path = sr_sync_directory($config) . '/' . $hash . '.json.gz'; sr_require(!is_link($path), 'inbox_unavailable');
        $tmp = $path . '.' . bin2hex(random_bytes(8)) . '.tmp';
        try {
            sr_require(file_put_contents($tmp, $body, LOCK_EX) === strlen($body) && chmod($tmp, 0600) && rename($tmp, $path), 'inbox_unavailable');
            $s = $db->prepare("INSERT INTO sync_jobs(kind,deduplication_key) VALUES('ranking_import',?)"); $s->execute([$hash]);
        } finally { if (is_file($tmp)) unlink($tmp); }
        return sr_job($db, $hash);
    } finally { sr_query($db, 'SELECT RELEASE_LOCK(?)', [$lock]); }
}
function sr_process(PDO $db, string $root, array $config): array {
    $lock = 'smash-ranking-worker-v1'; sr_require((int)sr_query($db, 'SELECT GET_LOCK(?,0)', [$lock])[0][0] === 1, 'worker_busy');
    try {
        // Holding the worker lock proves that no other live worker owns a running job.
        $db->exec("UPDATE sync_jobs SET status='queued',error_code='worker_interrupted' WHERE kind='ranking_import' AND status='running'");
        $s = $db->query("SELECT id,deduplication_key,requests_count FROM sync_jobs WHERE kind='ranking_import' AND status='queued' AND (next_attempt_at IS NULL OR next_attempt_at <= UTC_TIMESTAMP(6)) ORDER BY id LIMIT 1");
        $job = $s->fetch(); if ($job === false) return ['ok' => true, 'status' => 'idle'];
        $id = (int)$job['id']; $hash = $job['deduplication_key']; sr_require(preg_match('/\A[a-f0-9]{64}\z/D', $hash) === 1, 'job_invalid');
        $q = $db->prepare("UPDATE sync_jobs SET status='running',started_at=UTC_TIMESTAMP(6),requests_count=requests_count+1,error_code=NULL WHERE id=?"); $q->execute([$id]);
        $path = sr_sync_directory($config) . '/' . $hash . '.json.gz';
        try {
            sr_require(is_file($path) && !is_link($path) && filesize($path) <= SR_COMPRESSED_MAX, 'package_missing');
            $body = file_get_contents($path); sr_require(hash_equals($hash, hash('sha256', $body)), 'transport_hash_invalid');
            $raw = gzdecode($body, 32 * 1024 * 1024 + 1); sr_require(is_string($raw) && strlen($raw) <= 32 * 1024 * 1024, 'package_invalid');
            $package = sr_package($raw); unset($raw, $body);
            $liveFile = $root . '/data/public.json'; sr_require(is_file($liveFile) && filesize($liveFile) <= 32 * 1024 * 1024, 'public_unavailable');
            $live = json_decode(file_get_contents($liveFile), false, 512, JSON_THROW_ON_ERROR);
            sr_require(sr_json($live) === $package['_public_json'], 'not_the_published_cut'); unset($live);
            $report = sr_import($db, $package, true);
            $again = sr_import($db, $package, true); sr_require($again['status'] === 'already_imported' && $again['cutId'] === $report['cutId'], 'parity_failed');
            $q = $db->prepare("UPDATE sync_jobs SET status='succeeded',finished_at=UTC_TIMESTAMP(6),next_attempt_at=NULL,error_code=NULL WHERE id=?"); $q->execute([$id]);
            unlink($path); return ['ok' => true, 'jobId' => $id] + $report;
        } catch (Throwable $e) {
            if ($db->inTransaction()) $db->rollBack();
            $reason = $e instanceof SmashRankingError ? $e->reason : 'import_failed';
            $retry = in_array($reason, ['import_busy', 'not_the_published_cut', 'public_unavailable'], true) && (int)$job['requests_count'] < 11;
            $q = $db->prepare('UPDATE sync_jobs SET status=?,finished_at=UTC_TIMESTAMP(6),next_attempt_at=DATE_ADD(UTC_TIMESTAMP(6), INTERVAL 5 MINUTE),error_code=? WHERE id=?');
            $q->execute([$retry ? 'queued' : 'failed', $reason, $id]);
            return ['ok' => false, 'jobId' => $id, 'reason' => $reason, 'retry' => $retry];
        }
    } finally { sr_query($db, 'SELECT RELEASE_LOCK(?)', [$lock]); }
}
