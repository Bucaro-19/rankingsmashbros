<?php
declare(strict_types=1);
ini_set('display_errors', '0');
require_once __DIR__ . '/database.php';
require_once __DIR__ . '/visits.php';
header('Cache-Control: no-store, private');
header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: no-referrer');
// Counting must never disturb a page: every outcome is an empty answer, and failures are silent.
function visit_end(int $status): void { http_response_code($status); exit; }
if ($_SERVER['REQUEST_METHOD'] !== 'POST') { header('Allow: POST'); visit_end(405); }
if (!smash_visit_same_origin($_SERVER)) visit_end(403);
if ((int)($_SERVER['CONTENT_LENGTH'] ?? 0) > 256
    || strtolower(trim(explode(';', $_SERVER['CONTENT_TYPE'] ?? '')[0])) !== 'application/json') visit_end(400);
$body = json_decode((string)file_get_contents('php://input', false, null, 0, 257), true);
$page = is_array($body) ? smash_visit_page($body['page'] ?? null) : null;
if ($page === null) visit_end(400);
if (smash_visit_automated($_SERVER['HTTP_USER_AGENT'] ?? null)) visit_end(204);
try {
    $now = time();
    $key = smash_visit_key(__DIR__);
    $address = $_SERVER['REMOTE_ADDR'] ?? '';
    if (!is_string($address) || filter_var($address, FILTER_VALIDATE_IP) === false) visit_end(204);
    $token = $_COOKIE[SMASH_VISIT_COOKIE] ?? null;
    if (!smash_visit_token_valid($key, $token)) $token = null;
    $pdo = smash_database_connect(smash_database_config(__DIR__));
    $pdo->exec('SET SESSION innodb_lock_wait_timeout = 5, lock_wait_timeout = 5');
    $result = smash_visit_record($pdo, $key, smash_visit_day($now), $page, $token, smash_visit_network_hash($key, $address),
        ($body['cookies'] ?? true) !== false, smash_visit_signed_in($pdo, $_COOKIE['smash_recordar'] ?? null, $now));
    if ($result['token'] !== null) smash_visit_cookie_set($result['token'], $now);
} catch (Throwable $error) {
    // No logging: an error here could only repeat request details.
}
visit_end(204);
