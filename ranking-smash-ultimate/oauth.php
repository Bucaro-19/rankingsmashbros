<?php
declare(strict_types=1);
ini_set('display_errors', '0');
require_once __DIR__ . '/database.php';
require_once __DIR__ . '/accounts.php';
smash_account_session_start();
header('Cache-Control: no-store, private');
header('Referrer-Policy: no-referrer');
header('X-Content-Type-Options: nosniff');
function account_redirect(string $state): void { header('Location: ./cuenta.html#' . $state, true, 303); exit; }
try {
    $config = smash_account_oauth_config(__DIR__);
    if ($_SERVER['REQUEST_METHOD'] === 'POST') {
        if (!smash_account_csrf_valid($_SESSION, $_POST['csrf'] ?? null)) throw new SmashAccountError('csrf_invalid');
        if ($config === null) account_redirect('no-disponible');
        // Fixed callback and provider URLs; no return URL is accepted from the request.
        header('Location: ' . smash_account_authorize($_SESSION, $config, time()), true, 303); exit;
    }
    if ($_SERVER['REQUEST_METHOD'] !== 'GET') { header('Allow: GET, POST'); http_response_code(405); exit; }
    smash_account_consume_state($_SESSION, $_GET['state'] ?? null, time());
    if (isset($_GET['error'])) {
        if ($_GET['error'] === 'access_denied') account_redirect('cancelado');
        throw new SmashAccountError('provider_unavailable');
    }
    if ($config === null) account_redirect('no-disponible');
    if (!is_string($_GET['code'] ?? null)) throw new SmashAccountError('oauth_code_invalid');
    $identity = smash_account_exchange($config, $_GET['code']);
    $pdo = smash_account_connect(__DIR__);
    $id = smash_account_login($pdo, $identity, time());
    $user = smash_account_user($pdo, $id);
    session_regenerate_id(true);
    $_SESSION['smash_account_csrf'] = bin2hex(random_bytes(24));
    $_SESSION['smash_account'] = ['id' => $id, 'at' => time(), 'url' => $identity['url'], 'avatarUrl' => $identity['avatarUrl'], 'version' => $user['connectionVersion']];
    smash_account_remember_revoke($pdo, $_COOKIE[SMASH_ACCOUNT_REMEMBER_COOKIE] ?? null);
    $remember = smash_account_remember_create($pdo, $_SESSION['smash_account'], time());
    if ($remember !== null) smash_account_remember_set($remember, time());
    account_redirect('vinculada');
} catch (Throwable $error) {
    // No application logging of codes, state, tokens, provider bodies or driver errors.
    account_redirect('error');
}
