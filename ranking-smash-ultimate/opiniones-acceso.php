<?php
declare(strict_types=1);
// Lets the site owner's signed-in account (admin role) into the opinions panel without its password.
// opiniones.php is untouched: this only opens the same private session that page already checks.
// It reads no survey answer and reveals nothing to anyone else.
ini_set('display_errors', '0');
require_once __DIR__ . '/database.php';
require_once __DIR__ . '/accounts.php';
require_once __DIR__ . '/stats.php';
smash_account_session_start();
header('Cache-Control: no-store, private');
header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: no-referrer');
header('X-Robots-Tag: noindex, nofollow');
header('Content-Type: text/plain; charset=utf-8');
function access_end(int $status, string $text): void { http_response_code($status); echo $text; exit; }
function access_pdo(): PDO {
    static $pdo = null;
    return $pdo ?? ($pdo = smash_account_connect(__DIR__));
}
if ($_SERVER['REQUEST_METHOD'] !== 'POST') { header('Allow: POST'); access_end(405, 'Método no permitido.'); }
if (!smash_account_csrf_valid($_SESSION, $_POST['csrf'] ?? null)) access_end(403, 'Sin acceso.');
try {
    if (!smash_account_resume('access_pdo', time())) access_end(401, 'Inicia sesión.');
    $user = smash_account_current(access_pdo());
    if (!smash_stats_is_owner(access_pdo(), $user['id'])) access_end(403, 'Sin acceso.');
} catch (SmashAccountError $error) {
    if ($error->reason === 'login_required') { unset($_SESSION['smash_account']); access_end(401, 'Inicia sesión.'); }
    access_end(503, 'No disponible.');
} catch (Throwable $error) {
    access_end(503, 'No disponible.');
}
// Close the account session and open the opinions panel's own one, with that page's exact cookie rules.
session_write_close();
session_name('SMASHGT_ADMIN');
session_set_cookie_params([
    'lifetime' => 0, 'path' => rtrim(str_replace('\\', '/', dirname($_SERVER['SCRIPT_NAME'] ?? '/')), '/') . '/',
    'secure' => PHP_SAPI !== 'cli-server',
    'httponly' => true, 'samesite' => 'Strict',
]);
$known = $_COOKIE['SMASHGT_ADMIN'] ?? null;
session_id(is_string($known) && preg_match('/\A[A-Za-z0-9,-]{22,128}\z/D', $known) === 1 ? $known : session_create_id());
session_start();
session_regenerate_id(true);
$_SESSION = ['smash_admin' => true, 'smash_admin_at' => time(), 'smash_admin_attempts' => [], 'smash_admin_nonce' => bin2hex(random_bytes(24))];
header('Location: ./opiniones.php', true, 303);
exit;
