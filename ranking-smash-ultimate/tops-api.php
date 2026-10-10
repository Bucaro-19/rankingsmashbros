<?php
declare(strict_types=1);
// Anonymous public GET/HEAD only. No session, cookies, provider or start.gg calls.
ini_set('display_errors', '0');
require_once __DIR__ . '/database.php';
require_once __DIR__ . '/stats.php';
require_once __DIR__ . '/premium.php';
require_once __DIR__ . '/organizador.php';
require_once __DIR__ . '/tops.php';
header('Content-Type: application/json; charset=utf-8');
header('X-Content-Type-Options: nosniff');
header('X-Robots-Tag: noindex, nofollow');
header('Cache-Control: no-store');
$method = $_SERVER['REQUEST_METHOD'] ?? 'GET';
$pdo = null;
try {
    if (!in_array($method, ['GET', 'HEAD'], true)) {
        header('Allow: GET, HEAD'); http_response_code(405); $data = ['ok' => false, 'reason' => 'method_not_allowed'];
    } else {
        $raw = $_GET['limit'] ?? (string)SMASH_TOPS_LIMIT; $after = $_GET['after'] ?? '';
        if (!is_string($raw) || !preg_match('/\A(?:[1-9]|1[0-2])\z/', $raw) || !is_string($after)
            || ($after !== '' && !preg_match('/\A[a-z0-9-]{1,60}\z/', $after))) throw new InvalidArgumentException('invalid_query');
        $pdo = smash_database_connect(smash_database_config(__DIR__));
        $config = smash_premium_config(__DIR__);
        // A consistent read-only snapshot prevents toggling sharing/status between
        // the candidate list and public-view checks; no writer is blocked.
        $pdo->exec('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ');
        $pdo->exec('SET TRANSACTION READ ONLY');
        $pdo->beginTransaction();
        $data = smash_tops_directory($pdo, $config, time(), (int)$raw, $after);
        $pdo->commit();
        $body = json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR);
        $etag = '"' . hash('sha256', $body) . '"';
        header('Cache-Control: public, max-age=' . SMASH_TOPS_CACHE_SECONDS . ', must-revalidate');
        header('ETag: ' . $etag);
        $matches = array_map('trim', explode(',', $_SERVER['HTTP_IF_NONE_MATCH'] ?? ''));
        if (in_array($etag, $matches, true) || in_array('W/' . $etag, $matches, true) || in_array('*', $matches, true)) {
            http_response_code(304); exit;
        }
        if ($method !== 'HEAD') echo $body;
        exit;
    }
} catch (InvalidArgumentException $error) {
    http_response_code(400); $data = ['ok' => false, 'reason' => 'invalid_query'];
} catch (Throwable $error) {
    if ($pdo instanceof PDO && $pdo->inTransaction()) $pdo->rollBack();
    http_response_code(503); $data = ['ok' => false, 'reason' => 'tops_unavailable'];
}
if ($method !== 'HEAD') echo json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
