<?php
declare(strict_types=1);
ini_set('display_errors', '0');
require_once __DIR__ . '/database.php';
require_once __DIR__ . '/accounts.php';
require_once __DIR__ . '/stats.php';
smash_account_session_start();
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, private');
header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: no-referrer');
header('X-Robots-Tag: noindex, nofollow');
function panel_response(int $status, array $data): void {
    http_response_code($status); echo json_encode($data, JSON_UNESCAPED_UNICODE); exit;
}
function panel_pdo(): PDO {
    static $pdo = null;
    return $pdo ?? ($pdo = smash_account_connect(__DIR__));
}
if ($_SERVER['REQUEST_METHOD'] !== 'GET') { header('Allow: GET'); panel_response(405, ['ok' => false, 'reason' => 'method_not_allowed']); }
try {
    if (!smash_account_resume('panel_pdo', time())) panel_response(401, ['ok' => false, 'reason' => 'login_required']);
    $user = smash_account_current(panel_pdo());
    // Any other account learns nothing: no figures and no hint of what the page holds.
    if (!smash_stats_is_owner(panel_pdo(), $user['id'])) panel_response(403, ['ok' => false, 'reason' => 'forbidden']);
    $season = (int)(smash_account_public(__DIR__)['seasonYear'] ?? gmdate('Y', time() - 21600));
    panel_response(200, ['ok' => true, 'csrf' => $_SESSION['smash_account_csrf'], 'report' => smash_stats_report(panel_pdo(), time(), $season)]);
} catch (SmashAccountError $error) {
    if ($error->reason === 'login_required') { unset($_SESSION['smash_account']); panel_response(401, ['ok' => false, 'reason' => 'login_required']); }
    panel_response(503, ['ok' => false, 'reason' => 'stats_unavailable']);
} catch (Throwable $error) {
    panel_response(503, ['ok' => false, 'reason' => 'stats_unavailable']);
}
