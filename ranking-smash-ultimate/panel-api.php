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
    if (isset($_GET['registrations'])) {
        $scope = $_GET['registrations']; $anchor = $_GET['day'] ?? gmdate('Y-m-d', time() - 21600); $offset = $_GET['offset'] ?? '0';
        $date = is_string($anchor) && preg_match('/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/D', $anchor) ? DateTimeImmutable::createFromFormat('!Y-m-d', $anchor, new DateTimeZone('UTC')) : false;
        if (!is_string($scope) || !$date || $date->format('Y-m-d') !== $anchor || $anchor > gmdate('Y-m-d', time() - 21600)
            || $anchor < '2000-01-01' || !is_string($offset) || !preg_match('/^(0|[1-9][0-9]{0,7})$/D', $offset) || (int)$offset > 10000000) {
            panel_response(400, ['ok' => false, 'reason' => 'invalid_registration_query']);
        }
        $snapshot = $_GET['snapshot'] ?? null;
        if ($snapshot !== null) {
            $saved = is_string($snapshot) ? ($_SESSION['smash_registration_snapshots'][$snapshot] ?? null) : null;
            if (!$saved || time() - $saved['at'] > 1800) panel_response(400, ['ok' => false, 'reason' => 'registration_snapshot_expired']);
            $anchor = $saved['day']; $season = $saved['season'];
        } else {
            $saved = ['maximumId' => (string)(panel_pdo()->query('SELECT COALESCE(MAX(id), 0) FROM users')->fetchColumn()),
                'scopes' => smash_stats_registration_scopes(panel_pdo(), $anchor, $season)];
        }
        panel_response(200, ['ok' => true, 'registrations' => smash_stats_registration_list(panel_pdo(), $scope, $anchor, $season, (int)$offset, $saved['maximumId'], $saved['scopes'])]);
    }
    // Freeze only bounds, never account rows, in this owner's private session. New accounts
    // won't shift pagination or disagree with the figures of an already opened report.
    $now = time(); $pdo = panel_pdo();
    $pdo->exec('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ'); $pdo->exec('START TRANSACTION READ ONLY');
    try {
        $report = smash_stats_report($pdo, $now, $season);
        $maximumId = (string)$pdo->query('SELECT COALESCE(MAX(id), 0) FROM users')->fetchColumn();
        $scopes = smash_stats_registration_scopes($pdo, $report['today']['date'], $season);
        $pdo->commit();
    } catch (Throwable $error) { if ($pdo->inTransaction()) $pdo->rollBack(); throw $error; }
    $snapshots = $_SESSION['smash_registration_snapshots'] ?? [];
    $snapshots = array_filter($snapshots, static function ($value) use ($now) { return $now - $value['at'] <= 1800; });
    $snapshots = array_slice($snapshots, -4, null, true);
    $snapshot = bin2hex(random_bytes(16));
    $snapshots[$snapshot] = ['at' => $now, 'day' => $report['today']['date'], 'season' => $season, 'maximumId' => $maximumId, 'scopes' => $scopes];
    $_SESSION['smash_registration_snapshots'] = $snapshots;
    panel_response(200, ['ok' => true, 'csrf' => $_SESSION['smash_account_csrf'], 'registrationSnapshot' => $snapshot, 'report' => $report]);
} catch (SmashStatsError $error) {
    panel_response($error->reason === 'invalid_registration_query' ? 400 : 503, ['ok' => false, 'reason' => $error->reason === 'invalid_registration_query' ? $error->reason : 'stats_unavailable']);
} catch (SmashAccountError $error) {
    if ($error->reason === 'login_required') { unset($_SESSION['smash_account']); panel_response(401, ['ok' => false, 'reason' => 'login_required']); }
    panel_response(503, ['ok' => false, 'reason' => 'stats_unavailable']);
} catch (Throwable $error) {
    panel_response(503, ['ok' => false, 'reason' => 'stats_unavailable']);
}
