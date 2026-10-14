<?php
declare(strict_types=1);
require_once __DIR__.'/rival-import.php';
// Owner scope is fixed to Legends 7. Future events require a new explicit authorization.
const RC_EVENT_ID=1687524;
const RC_UNTIL='2026-10-26T06:00:00Z';
// Remains false until the owner clarifies the base-entity insert authorization.
const RC_ENTITY_INSERTS_AUTHORIZED=false;
function rc_policy(int $event,int $now): void {
    sr_require($event===RC_EVENT_ID,'analysis_event_not_authorized');
    sr_require($now<strtotime(RC_UNTIL),'analysis_authorization_expired');
    sr_require(RC_ENTITY_INSERTS_AUTHORIZED,'analysis_entity_authorization_required');
}
function rc_file(array $config,int $event): string {
    $dir=$config['private'].'/analysis-context';
    sr_require(!is_link($dir),'inbox_unavailable');
    if(!is_dir($dir))sr_require(mkdir($dir,0700),'inbox_unavailable');
    sr_require(realpath($dir)===$dir,'inbox_unavailable');return $dir.'/'.$event.'.json';
}
function rc_checkpoint(array $config,int $event): array {
    $path=rc_file($config,$event);
    if(!is_file($path))return ['revision'=>null,'checkpoint'=>null,'lastResult'=>null];
    sr_require(!is_link($path) && filesize($path)<=2*1024*1024,'analysis_checkpoint_invalid');
    $data=json_decode(file_get_contents($path),true,128,JSON_THROW_ON_ERROR);
    sr_require(is_array($data) && isset($data['revision'],$data['checkpoint'],$data['lastResult']),'analysis_checkpoint_invalid');return $data;
}
function rc_write_private(string $path,array $data): void {
    sr_require(!is_link($path),'inbox_unavailable');$temp=$path.'.'.bin2hex(random_bytes(8)).'.tmp';
    try {$raw=json_encode($data,JSON_THROW_ON_ERROR|JSON_UNESCAPED_UNICODE);sr_require(strlen($raw)<=2*1024*1024 && file_put_contents($temp,$raw,LOCK_EX)===strlen($raw) && chmod($temp,0600) && rename($temp,$path),'inbox_unavailable');}
    finally {if(is_file($temp))unlink($temp);}
}
function rc_roster(array $r): array {
    sr_require(($r['kind'] ?? null)==='analysis_roster' && ($r['schemaVersion'] ?? null)===1 && ($r['source'] ?? null)==='entrants');
    $event=sr_id($r['event']['id']);sr_require($r['event']['type']===1 && sr_id($r['event']['videogame']['id'])===1386);
    sr_require(count($r['players'])>0 && count($r['players'])<=1000 && $r['registrations']===count($r['players']));
    sr_at($r['capturedAt']);$ids=[];
    foreach($r['players'] as $pid=>$p) {sr_require(sr_id($pid)===sr_id($p['id']));sr_text($p['gamerTag'],100);$ids[]=sr_id($pid);}
    if($event===RC_EVENT_ID)sr_require(sr_id($r['tournament']['id'])===942547 && $r['tournament']['countryCode']==='SV' && $r['tournament']['slug']==='tournament/legends7','analysis_identity_conflict');
    return $ids;
}
function rc_pending(PDO $db,array $config,int $event): ?array {
    $rows=sr_query($db,"SELECT deduplication_key,status,error_code FROM sync_jobs WHERE kind='player_history' AND status<>'succeeded' ORDER BY id LIMIT 21");
    sr_require(count($rows)<=20,'analysis_queue_limit');
    foreach($rows as $row) {
        $file=sr_sync_directory($config).'/'.$row[0].'.json.gz';
        sr_require(is_file($file) && !is_link($file) && filesize($file)<=SR_COMPRESSED_MAX,'package_missing');
        $v=rc_envelope(file_get_contents($file));
        if($v['eventId']!==$event)continue;
        sr_require($row[1]!=='failed','analysis_failed_job_requires_review');
        return ['sha256'=>$row[0],'status'=>$row[1],'reason'=>$row[2]];
    }
    return null;
}
function rc_inventory(PDO $db,array $config,array $roster,int $now): array {
    $ids=rc_roster($roster);$event=sr_id($roster['event']['id']);rc_policy($event,$now);rc_ready($db);
    $known=array_map('intval',array_column(rc_existing($db,'players',$ids),0));
    $saved=rc_checkpoint($config,$event);
    return ['ok'=>true,'knownIds'=>$known,'pendingJob'=>rc_pending($db,$config,$event)]+$saved;
}
function rc_envelope(string $body): array {
    sr_require(strlen($body)<=SR_COMPRESSED_MAX && substr($body,0,2)==="\x1f\x8b",'payload_invalid');
    $raw=gzdecode($body,8*1024*1024+1);sr_require(is_string($raw) && strlen($raw)<=8*1024*1024,'payload_invalid');
    $obj=json_decode($raw,false,512,JSON_THROW_ON_ERROR);sr_require($obj instanceof stdClass && sr_json($obj)===$raw,'payload_invalid');
    $v=json_decode($raw,true,512,JSON_THROW_ON_ERROR);sr_require(!array_key_exists('_packageRaw',$v));
    if(isset($obj->package))$v['_packageRaw']=sr_json($obj->package);
    return $v;
}
function rc_validate_envelope(array $v): array {
    rc_keys($v,['operation','eventId','baseRevision','package','checkpoint','_packageRaw']);sr_require($v['operation']==='analysis_import');
    $event=sr_id($v['eventId']);$state=$v['checkpoint'];rc_keys($state,['stateVersion','roster','seasonYear','knownPlayerIds','coverage','pages']);
    sr_require($state['stateVersion']===1 && $state['seasonYear']===2026 && $state['pages']===[]);
    $ids=rc_roster($state['roster']);sr_require(sr_id($state['roster']['event']['id'])===$event);
    $p=rc_package($v['_packageRaw']);
    $c=$p['content'];sr_require(count($c['entities']['sets'])<=150 && count($c['entities']['games'])<=1500 && count($c['entities']['game_selections'])<=3000,'analysis_batch_limit');
    sr_require($c['sourceEventId']===$event && $c['seasonYear']===2026 && !array_diff($c['rootPlayerIds'],$ids));
    $root=array_fill_keys($c['rootPlayerIds'],true);$links=array_column($c['entities']['entrant_players'],'player_id','entrant_id');$sets=[];
    foreach($c['entities']['set_slots'] as $slot) if(isset($root[$links[$slot['entrant_id']] ?? 0]))$sets[$slot['set_id']]=true;
    foreach($c['entities']['sets'] as $set)sr_require(isset($sets[$set['id']]),'analysis_unrelated_set');
    sr_require(!array_diff(array_keys($state['coverage']),$ids) && !array_diff($c['rootPlayerIds'],array_keys($state['coverage'])));
    foreach($state['coverage'] as $pid=>$cov) {rc_keys($cov,['nextPage','totalPages','complete']);sr_int($cov['nextPage'],1,1000000);sr_require(is_bool($cov['complete']));if($cov['totalPages']!==null)sr_int($cov['totalPages'],0,1000000);}
    foreach($c['coverage'] as $pid=>$cov)sr_require(($state['coverage'][$pid] ?? null)===$cov && isset($root[$pid]));
    sr_require($v['baseRevision']===null || (is_string($v['baseRevision']) && preg_match('/^[a-f0-9]{64}$/D',$v['baseRevision'])));
    return $p;
}
function rc_job(PDO $db,string $hash): ?array {
    $r=sr_query($db,"SELECT id,status,error_code,requests_count FROM sync_jobs WHERE kind='player_history' AND deduplication_key=?",[$hash]);
    return !$r?null:['jobId'=>(int)$r[0][0],'status'=>$r[0][1],'reason'=>$r[0][2],'attempts'=>(int)$r[0][3]];
}
function rc_progress(array $saved,array $v): void {
    $old=$saved['checkpoint']['coverage'] ?? [];$next=$v['checkpoint']['coverage'];
    $roots=array_fill_keys($v['package']['content']['rootPlayerIds'],true);
    foreach($next as $pid=>$cov) {
        $before=$old[$pid] ?? ['nextPage'=>1,'totalPages'=>null,'complete'=>false];
        sr_require($cov['nextPage']>=$before['nextPage'] && (!$before['complete'] || $cov===$before),'analysis_checkpoint_regression');
        sr_require(isset($roots[$pid]) ? $cov['nextPage']>$before['nextPage'] : $cov===$before,'analysis_checkpoint_progress_invalid');
        if($cov['complete'])sr_require($cov['totalPages']!==null && $cov['nextPage']>$cov['totalPages'],'analysis_checkpoint_progress_invalid');
    }
}
function rc_receive(PDO $db,array $config,string $body,string $hash,int $now): array {
    $v=rc_envelope($body);
    if(($v['operation'] ?? null)==='analysis_inventory') {rc_keys($v,['operation','roster']);return rc_inventory($db,$config,$v['roster'],$now);}
    rc_policy(sr_id($v['eventId'] ?? null),$now);rc_ready($db);$p=rc_validate_envelope($v);
    sr_require((int)sr_query($db,'SELECT GET_LOCK(?,0)',['smash-ranking-receive-v1'])[0][0]===1,'receiver_busy');
    try {
        $job=rc_job($db,$hash);if($job!==null)return ['ok'=>true]+$job;
        $saved=rc_checkpoint($config,$v['eventId']);sr_require($saved['revision']===$v['baseRevision'],'analysis_checkpoint_conflict');
        rc_progress($saved,$v);
        sr_require(rc_pending($db,$config,$v['eventId'])===null,'analysis_job_pending');
        $path=sr_sync_directory($config).'/'.$hash.'.json.gz';sr_require(!is_link($path),'inbox_unavailable');$temp=$path.'.'.bin2hex(random_bytes(8)).'.tmp';
        try {sr_require(file_put_contents($temp,$body,LOCK_EX)===strlen($body) && chmod($temp,0600) && rename($temp,$path),'inbox_unavailable');sr_query($db,"INSERT INTO sync_jobs(kind,deduplication_key) VALUES ('player_history',?)",[$hash]);}
        finally {if(is_file($temp))unlink($temp);}
        return ['ok'=>true]+rc_job($db,$hash);
    } finally {sr_query($db,'SELECT RELEASE_LOCK(?)',['smash-ranking-receive-v1']);}
}
function rc_process(PDO $db,array $config,string $body,string $hash,int $now): array {
    $v=rc_envelope($body);rc_policy(sr_id($v['eventId']),$now);rc_ready($db);$p=rc_validate_envelope($v);
    $saved=rc_checkpoint($config,$v['eventId']);
    if($saved['revision']===$hash)return ['status'=>'already_imported']+$saved['lastResult'];
    sr_require($saved['revision']===$v['baseRevision'],'analysis_checkpoint_conflict');
    rc_progress($saved,$v);
    $dry=rc_import($db,$p);sr_require(in_array($dry['status'],['validated_no_writes','already_imported'],true),'analysis_validation_failed');
    // Write a private candidate BEFORE SQL. Atomic rename becomes visible only after the SQL receipt exists.
    // A killed worker after commit can finalize it without repeating capture or losing original counts.
    $active=rc_file($config,$v['eventId']);$candidate=$active.'.'.$hash.'.pending';
    if(!is_file($candidate)) {
        $candidateData=['revision'=>$hash,'checkpoint'=>$v['checkpoint'],'lastResult'=>['status'=>'imported']+$dry];
        rc_write_private($candidate,$candidateData);
    }
    sr_require(!is_link($candidate) && filesize($candidate)<=2*1024*1024,'inbox_unavailable');
    $candidateData=json_decode(file_get_contents($candidate),true,128,JSON_THROW_ON_ERROR);
    sr_require(($candidateData['revision'] ?? null)===$hash && ($candidateData['checkpoint'] ?? null)===$v['checkpoint'] && is_array($candidateData['lastResult'] ?? null),'analysis_checkpoint_invalid');
    rc_import($db,$p,true,strtotime(RC_UNTIL));$again=rc_import($db,$p,true,strtotime(RC_UNTIL));sr_require($again['status']==='already_imported','parity_failed');
    sr_require(rename($candidate,$active),'inbox_unavailable');return $candidateData['lastResult'];
}
