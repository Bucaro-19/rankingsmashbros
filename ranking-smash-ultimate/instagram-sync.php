<?php
declare(strict_types=1);
if(PHP_SAPI!=='cli'){http_response_code(403);exit;}
ini_set('display_errors','0');ini_set('log_errors','0');ini_set('memory_limit','256M');set_time_limit(300);
require_once __DIR__ . '/instagram.php';
set_error_handler(static function($severity){if(!(error_reporting()&$severity))return true;throw new SmashInstagramError('instagram_runtime_error');});
try {$r=ig_run(__DIR__,time());echo json_encode($r,JSON_THROW_ON_ERROR)."\n";exit($r['ok']?0:1);}
catch(Throwable $error){echo '{"ok":false,"status":"failed","code":"instagram_capture_failed"}'."\n";exit(1);}
