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
function account_response(int $status, array $data): void {
    http_response_code($status); echo json_encode($data, JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE); exit;
}
function account_pdo(): PDO {
    static $pdo = null;
    return $pdo ?? ($pdo = smash_account_connect(__DIR__));
}
function account_signed_in(): bool { return smash_account_resume('account_pdo', time()); }
function account_sign_out(?string $userId = null): void {
    $token = $_COOKIE[SMASH_ACCOUNT_REMEMBER_COOKIE] ?? null;
    if ($token !== null || $userId !== null) {
        try { smash_account_remember_revoke(account_pdo(), $token, $userId); } catch (Throwable $error) {}
        smash_account_remember_set(null, time());
    }
    unset($_SESSION['smash_account'], $_SESSION['smash_oauth_pending']); session_regenerate_id(true);
    $_SESSION['smash_account_csrf'] = bin2hex(random_bytes(24));
}
function account_verified_user(PDO $pdo): array { return smash_account_current($pdo); }
// The organizer tab is offered only once the weekly catalog (migration 005) has reached this database.
function account_organizer_ready(): bool {
    try { return account_pdo()->query('SELECT 1 FROM tournament_catalog LIMIT 1')->fetchColumn() !== false; }
    catch (Throwable $error) { return false; }
}
if (!in_array($_SERVER['REQUEST_METHOD'], ['GET', 'POST'], true)) {
    header('Allow: GET, POST'); account_response(405, ['ok' => false, 'reason' => 'method_not_allowed']);
}
try {
    $ready = smash_account_oauth_config(__DIR__) !== null;
    if ($_SERVER['REQUEST_METHOD'] === 'POST') {
        if (!smash_account_csrf_valid($_SESSION, $_SERVER['HTTP_X_CSRF_TOKEN'] ?? null)) account_response(403, ['ok' => false, 'reason' => 'csrf_invalid']);
        if (!account_signed_in()) account_response(401, ['ok' => false, 'reason' => 'login_required']);
        if ((int)($_SERVER['CONTENT_LENGTH'] ?? 0) > 4096) account_response(413, ['ok' => false, 'reason' => 'body_too_large']);
        if (strtolower(trim(explode(';', $_SERVER['CONTENT_TYPE'] ?? '')[0])) !== 'application/json') account_response(415, ['ok' => false, 'reason' => 'json_required']);
        $body = json_decode(file_get_contents('php://input', false, null, 0, 4097), true);
        if (!is_array($body) || !is_string($body['action'] ?? null)) account_response(400, ['ok' => false, 'reason' => 'invalid_action']);
        if ($body['action'] === 'logout') { account_sign_out(); account_response(200, ['ok' => true]); }
        $pdo = account_pdo(); account_verified_user($pdo);
        $userId = $_SESSION['smash_account']['id'];
        smash_account_preferences($pdo, $userId, $body['action'], $body, $_SESSION['smash_account']['version']);
        if ($body['action'] === 'disconnect') account_sign_out($userId);
        account_response(200, ['ok' => true]);
    }
    if (!account_signed_in()) {
        unset($_SESSION['smash_account']);
        account_response(200, ['ok' => true, 'authenticated' => false, 'oauthReady' => $ready, 'csrf' => $_SESSION['smash_account_csrf']] + (account_organizer_ready() ? ['organizerReady' => true] : []));
    }
    $pdo = account_pdo(); $user = account_verified_user($pdo);
    $user['avatarUrl'] = smash_account_safe_image($_SESSION['smash_account']['avatarUrl'] ?? null);
    $user['url'] = $_SESSION['smash_account']['url'] ?? $user['url'];
    // Only the owner's account learns that a private panel exists; nobody else receives the key.
    $owner = smash_stats_is_owner($pdo, $user['id']) ? ['panel' => true] : [];
    if (account_organizer_ready()) $owner['organizerReady'] = true;
    account_response(200, $owner + ['ok' => true, 'authenticated' => true, 'oauthReady' => $ready,
        'csrf' => $_SESSION['smash_account_csrf'], 'user' => $user, 'profile' => smash_account_profile(smash_account_public(__DIR__), $user['playerId'])]);
} catch (SmashAccountError $error) {
    if ($error->reason === 'login_required') {
        unset($_SESSION['smash_account']);
        if (isset($_COOKIE[SMASH_ACCOUNT_REMEMBER_COOKIE])) smash_account_remember_set(null, time());
        account_response(401, ['ok' => false, 'reason' => 'login_required']);
    }
    $status = strpos($error->reason, 'invalid_') === 0 ? 400 : 503;
    account_response($status, ['ok' => false, 'reason' => $error->reason]);
} catch (Throwable $error) {
    account_response(503, ['ok' => false, 'reason' => 'account_unavailable']);
}
