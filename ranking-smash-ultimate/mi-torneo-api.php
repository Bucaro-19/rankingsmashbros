<?php
declare(strict_types=1);
ini_set('display_errors','0');
require_once __DIR__.'/database.php';
require_once __DIR__.'/accounts.php';
require_once __DIR__.'/mi-torneo.php';
smash_account_session_start();
header('Content-Type: application/json; charset=utf-8');header('Cache-Control: no-store, private');header('X-Content-Type-Options: nosniff');header('Referrer-Policy: no-referrer');header('X-Robots-Tag: noindex, nofollow');
function mt_http(int $status,array $value): void {http_response_code($status);echo json_encode($value,JSON_THROW_ON_ERROR|JSON_UNESCAPED_UNICODE);exit;}
function mt_pdo(): PDO {static $db=null;return $db??($db=smash_account_connect(__DIR__));}
if(($_SERVER['REQUEST_METHOD']??'')!=='GET'){header('Allow: GET');mt_http(405,['ok'=>false,'reason'=>'method_not_allowed']);}
try{
    if(!smash_account_resume('mt_pdo',time()))mt_http(401,['ok'=>false,'reason'=>'login_required']);
    $user=smash_account_current(mt_pdo());
    if($_GET)mt_http(400,['ok'=>false,'reason'=>'parameters_not_allowed']);
    $snapshot=mt_read(__DIR__);$public=smash_account_public(__DIR__);$now=time();
    $response=mt_response($snapshot,$user['playerId'],$public,$now);
    $chosen=mt_profile_characters(mt_pdo(),$response);
    if($chosen)$response=mt_response($snapshot,$user['playerId'],$public,$now,$chosen);
    mt_http(200,$response);
}catch(SmashAccountError $e){if($e->reason==='login_required'){unset($_SESSION['smash_account']);mt_http(401,['ok'=>false,'reason'=>'login_required']);}mt_http(503,['ok'=>false,'reason'=>'tournament_unavailable']);}
catch(Throwable $e){mt_http(503,['ok'=>false,'reason'=>'tournament_unavailable']);}
