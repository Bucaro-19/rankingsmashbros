<?php
declare(strict_types=1);
ini_set('display_errors', '0');
require_once __DIR__ . '/database.php';
require_once __DIR__ . '/accounts.php';
require_once __DIR__ . '/premium.php';
smash_account_session_start();
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, private');
header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: no-referrer');
function premium_response(int $status, array $data): void {
    http_response_code($status); echo json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES); exit;
}
function premium_pdo(): PDO {
    static $pdo = null;
    return $pdo ?? ($pdo = smash_account_connect(__DIR__));
}
if (!in_array($_SERVER['REQUEST_METHOD'], ['GET', 'POST'], true)) { header('Allow: GET, POST'); premium_response(405, ['ok' => false, 'reason' => 'method_not_allowed']); }
try {
    $config = smash_premium_config(__DIR__);
    $plans = [];
    foreach (SMASH_PREMIUM_PLANS as $key => $plan) $plans[$key] = ['amountInCents' => $plan['cents'], 'currency' => 'USD', 'interval' => $plan['interval']];
    $post = $_SERVER['REQUEST_METHOD'] === 'POST';
    if ($post && !smash_account_csrf_valid($_SESSION, $_SERVER['HTTP_X_CSRF_TOKEN'] ?? null)) premium_response(403, ['ok' => false, 'reason' => 'csrf_invalid']);
    if (!smash_account_resume('premium_pdo', time())) {
        if ($post) premium_response(401, ['ok' => false, 'reason' => 'login_required']);
        premium_response(200, ['ok' => true, 'authenticated' => false, 'available' => $config !== null, 'plans' => $plans, 'csrf' => $_SESSION['smash_account_csrf']]);
    }
    $user = smash_account_current(premium_pdo());
    if ($config === null) {
        if ($post) premium_response(503, ['ok' => false, 'reason' => 'premium_unavailable']);
        premium_response(200, ['ok' => true, 'authenticated' => true, 'available' => false, 'plans' => $plans, 'csrf' => $_SESSION['smash_account_csrf'],
            'premium' => ['premium' => false, 'plan' => null, 'status' => 'none', 'currentPeriodEnd' => null, 'cancelRequested' => false, 'pending' => false]]);
    }
    if ($post) {
        if ((int)($_SERVER['CONTENT_LENGTH'] ?? 0) > 512) premium_response(413, ['ok' => false, 'reason' => 'body_too_large']);
        if (strtolower(trim(explode(';', $_SERVER['CONTENT_TYPE'] ?? '')[0])) !== 'application/json') premium_response(415, ['ok' => false, 'reason' => 'json_required']);
        $body = json_decode((string)file_get_contents('php://input', false, null, 0, 513), true);
        $action = is_array($body) ? ($body['action'] ?? null) : null;
        if ($action === 'checkout') {
            // The address is Recurrente's hosted page for this account's own checkout; the browser goes there to pay.
            premium_response(200, ['ok' => true, 'checkoutUrl' => smash_premium_start(premium_pdo(), $config, $user['id'], $body['plan'] ?? null, time())]);
        }
        if ($action === 'cancel') {
            smash_premium_cancel(premium_pdo(), $config, $user['id'], time());
            premium_response(200, ['ok' => true, 'premium' => smash_premium_status(premium_pdo(), $user['id'], $config['live'], time())]);
        }
        premium_response(400, ['ok' => false, 'reason' => 'invalid_action']);
    }
    smash_premium_refresh(premium_pdo(), $config, $user['id'], time());
    premium_response(200, ['ok' => true, 'authenticated' => true, 'available' => true, 'test' => !$config['live'], 'plans' => $plans, 'csrf' => $_SESSION['smash_account_csrf'],
        'premium' => smash_premium_status(premium_pdo(), $user['id'], $config['live'], time())]);
} catch (SmashAccountError $error) {
    if ($error->reason === 'login_required') { unset($_SESSION['smash_account']); premium_response(401, ['ok' => false, 'reason' => 'login_required']); }
    premium_response(503, ['ok' => false, 'reason' => 'premium_unavailable']);
} catch (SmashPremiumError $error) {
    premium_response(strpos($error->reason, 'invalid_') === 0 ? 400 : 503, ['ok' => false, 'reason' => strpos($error->reason, 'invalid_') === 0 ? $error->reason : 'premium_unavailable']);
} catch (Throwable $error) {
    premium_response(503, ['ok' => false, 'reason' => 'premium_unavailable']);
}
