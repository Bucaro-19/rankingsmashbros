<?php
declare(strict_types=1);
require_once __DIR__.'/../../ranking-smash-ultimate/ranking-sync-lib.php';
set_error_handler(static function(){throw new SmashRankingError('runtime_failure');});
try {
    $input=json_decode(stream_get_contents(STDIN),true,512,JSON_THROW_ON_ERROR);$mode=$input['mode'];
    if($mode==='validate')$report=rc_package($input['raw']);
    else {
        $name=getenv('SMASH_SCHEMA_TEST_DB');$host=getenv('SMASH_SCHEMA_TEST_HOST') ?: '127.0.0.1';
        sr_require(is_string($name) && strpos($name,'smash_schema_test')===0 && in_array($host,['127.0.0.1','localhost'],true),'test_database_required');
        $db=smash_database_connect(['host'=>$host,'name'=>$name,'port'=>(int)(getenv('SMASH_SCHEMA_TEST_PORT') ?: 3306),'user'=>'root','password'=>getenv('SMASH_SCHEMA_TEST_PASSWORD')]);
        $p=rc_package($input['raw']);$report=rc_import($db,$p,$mode==='apply');
    }
    echo json_encode(['ok'=>true,'result'=>$report,'peakMemoryBytes'=>memory_get_peak_usage(true)],JSON_THROW_ON_ERROR);
} catch(Throwable $e){echo json_encode(['ok'=>false,'reason'=>$e instanceof SmashRankingError?$e->reason:'test_failed']);exit(1);}
