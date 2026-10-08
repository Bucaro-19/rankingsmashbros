<?php
declare(strict_types=1);
ini_set('display_errors','0');
require_once __DIR__.'/database.php';
require_once __DIR__.'/accounts.php';
require_once __DIR__.'/stats.php';
require_once __DIR__.'/premium.php';
require_once __DIR__.'/analisis.php';
smash_account_session_start();
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, private');
header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: no-referrer');
header('X-Robots-Tag: noindex, nofollow');
function analisis_response(int $status, array $data): void {
    http_response_code($status); echo json_encode($data,JSON_THROW_ON_ERROR|JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES); exit;
}
function analisis_pdo(): PDO {
    static $db=null; return $db ?? ($db=smash_account_connect(__DIR__));
}
if (($_SERVER['REQUEST_METHOD'] ?? '')!=='GET') { header('Allow: GET'); analisis_response(405,['ok'=>false,'reason'=>'method_not_allowed']); }
try {
    if (!smash_account_resume('analisis_pdo',time())) analisis_response(401,['ok'=>false,'reason'=>'login_required']);
    $db=analisis_pdo(); $user=smash_account_current($db);
    smash_analisis_rate($_SESSION,time());
    // Auth resume retains the existing session housekeeping. The analysis itself is SQL READ ONLY.
    $db->exec('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ'); $db->exec('SET TRANSACTION READ ONLY'); $db->beginTransaction();
    $data=smash_analisis_response($db,smash_account_public(__DIR__),$user,$_GET,smash_premium_config(__DIR__),time(),$_SESSION['smash_account']['avatarUrl'] ?? null);
    $db->rollBack(); analisis_response(200,$data);
} catch (SmashAnalisisError $e) {
    if (isset($db) && $db->inTransaction()) $db->rollBack();
    if ($e->reason==='rate_limited') header('Retry-After: 60');
    $status=$e->reason==='rate_limited' ? 429 : ($e->reason==='rival_not_found' ? 404 : ($e->reason==='game_limit_exceeded' ? 503 : 400));
    analisis_response($status,['ok'=>false,'reason'=>$e->reason]);
} catch (SmashAccountError $e) {
    if (isset($db) && $db->inTransaction()) $db->rollBack();
    if ($e->reason==='login_required') { unset($_SESSION['smash_account']); analisis_response(401,['ok'=>false,'reason'=>'login_required']); }
    analisis_response(503,['ok'=>false,'reason'=>'analysis_unavailable']);
} catch (Throwable $e) {
    if (isset($db) && $db->inTransaction()) $db->rollBack();
    analisis_response(503,['ok'=>false,'reason'=>'analysis_unavailable']);
}
