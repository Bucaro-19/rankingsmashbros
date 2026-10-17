<?php
declare(strict_types=1);
// Private file library: no database or external requests on inclusion/read.
const MT_EVENT='1687524';
const MT_END=1792987200;
const MT_MAX=8388608;
function mt_check(bool $ok): void {if(!$ok)throw new RuntimeException('bracket_invalid');}
function mt_keys(array $v,array $keys): void {$actual=array_keys($v);sort($actual);sort($keys);mt_check($actual===$keys);}
function mt_id($v,bool $opaque=false): string {mt_check(is_string($v)&&preg_match($opaque?'/^[A-Za-z0-9_-]{1,100}$/D':'/^[1-9][0-9]{0,19}$/D',$v)===1);return $v;}
function mt_text($v,int $max=255,bool $null=false): void {if($null&&$v===null)return;mt_check(is_string($v)&&mb_strlen($v)<=$max&&!preg_match('/[\x00-\x1f]/',$v));}
function mt_int($v,bool $null=false,int $min=0): void {if($null&&$v===null)return;mt_check(is_int($v)&&$v>=$min&&$v<=2147483647);}
function mt_validate(array $p): void {
    mt_keys($p,['schemaVersion','kind','capturedAt','event','registrationState','entrants','groups','audit']);
    mt_check($p['schemaVersion']===1&&$p['kind']==='my_tournament_bracket'&&in_array($p['registrationState'],['published','unavailable'],true));
    mt_text($p['capturedAt'],40);mt_check(preg_match('/^2026-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|\+00:00)$/D',$p['capturedAt'])===1&&strtotime($p['capturedAt'])!==false);
    $e=$p['event'];mt_keys($e,['id','tournamentId','name','tournamentName','slug','country','startAt','endAt','timezone']);
    mt_check($e['id']===MT_EVENT&&$e['tournamentId']==='942547'&&$e['country']==='SV'&&$e['slug']==='tournament/legends7/event/ultimate-singles');
    foreach(['name','tournamentName','slug'] as $k)mt_text($e[$k]);mt_int($e['startAt'],true,1);mt_int($e['endAt'],true,1);
    mt_text($e['timezone'],100,true);if($e['timezone']!==null)mt_check(in_array($e['timezone'],DateTimeZone::listIdentifiers(),true));
    mt_check(is_array($p['entrants'])&&count($p['entrants'])<=1000&&is_array($p['groups'])&&count($p['groups'])<=100);
    if($p['registrationState']==='unavailable')mt_check($p['entrants']===[]&&$p['groups']===[]);
    $entrants=[];$players=[];$groups=[];$seeds=[];$sets=[];$n=0;$m=0;
    foreach($p['entrants'] as $r){mt_keys($r,['id','playerId','tag','initialSeed']);$id=mt_id($r['id']);mt_check(!isset($entrants[$id]));$entrants[$id]=true;mt_text($r['tag'],100);mt_int($r['initialSeed'],true,1);if($r['playerId']!==null){$pid=mt_id($r['playerId']);mt_check(!isset($players[$pid]));$players[$pid]=true;}}
    foreach($p['groups'] as $g){
        mt_keys($g,['id','phaseId','phaseName','phaseOrder','identifier','state','bracketType','startAt','timeSource','seeds','sets','dataAvailable','setsAvailable']);
        $gid=mt_id($g['id']);mt_check(!isset($groups[$gid]));$groups[$gid]=true;mt_id($g['phaseId']);mt_text($g['phaseName']);mt_text($g['identifier'],100,true);mt_text($g['bracketType'],100,true);
        foreach(['phaseOrder','state'] as $k)mt_int($g[$k],true);mt_int($g['startAt'],true,1);
        mt_check(in_array($g['timeSource'],[null,'pool','wave','round'],true)&&(($g['startAt']===null)===($g['timeSource']===null))&&is_bool($g['dataAvailable'])&&is_bool($g['setsAvailable'])&&is_array($g['seeds'])&&is_array($g['sets']));
        if(!$g['dataAvailable'])mt_check($g['seeds']===[]&&$g['sets']===[]);if(!$g['setsAvailable'])mt_check($g['sets']===[]);
        $members=[];$localSeeds=[];
        foreach($g['seeds'] as $s){mt_keys($s,['id','entrantId','seed','groupSeed','isBye']);$sid=mt_id($s['id']);mt_check(!isset($seeds[$sid]));$seeds[$sid]=true;$localSeeds[$sid]=true;mt_check(is_bool($s['isBye'])||$s['isBye']===null);foreach(['seed','groupSeed'] as $k)mt_int($s[$k],true,1);if($s['entrantId']!==null){mt_id($s['entrantId']);mt_check(isset($entrants[$s['entrantId']]));$members[$s['entrantId']]=true;}$n++;}
        foreach($g['sets'] as $s){
            mt_keys($s,['id','round','roundText','startAt','state','winnerId','slots']);$sid=mt_id($s['id'],true);mt_check(!isset($sets[$sid]));$sets[$sid]=true;mt_int($s['round'],true,-2147483648);mt_text($s['roundText'],255,true);mt_int($s['startAt'],true,1);mt_int($s['state'],true);
            if($s['winnerId']!==null){mt_id($s['winnerId']);mt_check(isset($members[$s['winnerId']]));}
            mt_check(is_array($s['slots'])&&count($s['slots'])<=2);$indices=[];
            foreach($s['slots'] as $slot){mt_keys($slot,['index','entrantId','seedId','prereqId','prereqType','prereqPlacement']);mt_check(in_array($slot['index'],[0,1],true)&&!isset($indices[$slot['index']]));$indices[$slot['index']]=true;
                if($slot['entrantId']!==null){mt_id($slot['entrantId']);mt_check(isset($members[$slot['entrantId']]));}
                if($slot['seedId']!==null){mt_id($slot['seedId']);mt_check(isset($localSeeds[$slot['seedId']]));}
                if($slot['prereqId']!==null)mt_id($slot['prereqId'],true);mt_text($slot['prereqType'],32,true);mt_int($slot['prereqPlacement'],true);
            }$m++;
        }
    }
    mt_check($n<=5000&&$m<=5000);mt_keys($p['audit'],['requests','batches','elapsedMilliseconds']);foreach($p['audit'] as $v)mt_int($v);mt_check($p['audit']['requests']<=60&&$p['audit']['batches']>=1&&$p['audit']['batches']<=2&&$p['audit']['elapsedMilliseconds']<=240000);
}
function mt_path(string $site,bool $create=false): string {
    $root=realpath($site);mt_check($root!==false);$private=dirname($root).'/private-smash';mt_check(is_dir($private)&&!is_link($private));$dir=$private.'/brackets';mt_check(!is_link($dir));
    if($create&&!is_dir($dir))mt_check(mkdir($dir,0700));if(is_dir($dir))mt_check(realpath($dir)===$dir);
    return $dir.'/'.MT_EVENT.'.json';
}
function mt_read(string $site): ?array {
    $path=mt_path($site);if(!is_file($path))return null;mt_check(!is_link($path)&&filesize($path)<=MT_MAX);$raw=file_get_contents($path);mt_check(is_string($raw)&&strlen($raw)<=MT_MAX);$p=json_decode($raw,true,128,JSON_THROW_ON_ERROR);mt_check(is_array($p));mt_validate($p);return $p;
}
function mt_receive(string $site,string $body,int $now): array {
    mt_check($now<MT_END&&strlen($body)<=4194304&&substr($body,0,2)==="\x1f\x8b");$raw=gzdecode($body,MT_MAX+1);mt_check(is_string($raw)&&strlen($raw)<=MT_MAX);$p=json_decode($raw,true,128,JSON_THROW_ON_ERROR);mt_check(is_array($p));mt_validate($p);
    $at=strtotime($p['capturedAt']);mt_check($at<=$now+60&&$at>=$now-1800&&$at<MT_END);
    $path=mt_path($site,true);mt_check(!is_link($path)&&!is_link($path.'.lock'));$lock=fopen($path.'.lock','c');mt_check(is_resource($lock));chmod($path.'.lock',0600);$temp=null;
    try{mt_check(flock($lock,LOCK_EX));$old=mt_read($site);if($old!==null){if($old===$p)return ['ok'=>true,'status'=>'already_stored'];mt_check(strtotime($old['capturedAt'])<$at);}
        $temp=$path.'.'.bin2hex(random_bytes(8)).'.tmp';mt_check(file_put_contents($temp,$raw,LOCK_EX)===strlen($raw)&&chmod($temp,0600)&&rename($temp,$path));return ['ok'=>true,'status'=>'stored'];
    }finally{if($temp!==null&&is_file($temp))unlink($temp);flock($lock,LOCK_UN);fclose($lock);}
}
