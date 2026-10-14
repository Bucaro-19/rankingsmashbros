<?php
declare(strict_types=1);
// Analysis-only importer, parity oracle: scripts/database/rival_context.py. No I/O on inclusion.
function rc_columns(): array { return [
    'players'=>'id tag known_as country_code country_basis profile_url synced_at',
    'tournaments'=>'id name slug country_code url synced_at',
    'events'=>'id tournament_id name videogame_id entrant_size starts_at registered_entrants active_players url synced_at',
    'entrants'=>'id event_id name competitive_sets final_placement synced_at',
    'entrant_players'=>'entrant_id player_id registered_tag',
    'sets'=>'id event_id source_state status outcome_type winner_entrant_id display_score completed_at source_updated_at synced_at source_hash',
    'set_slots'=>'set_id slot_index event_id entrant_id score is_dq',
    'games'=>'id set_id game_number winner_entrant_id stage_id synced_at',
    'game_selections'=>'game_id set_id entrant_id character_id',
]; }
function rc_keys(array $value, array $keys): void { $a=array_keys($value);sort($a);sort($keys);sr_require($a===$keys); }
function rc_package(string $raw): array {
    sr_require(strlen($raw)<=32*1024*1024);
    $obj=json_decode($raw,false,512,JSON_THROW_ON_ERROR);sr_require($obj instanceof stdClass && sr_json($obj)===$raw);
    $p=json_decode($raw,true,512,JSON_THROW_ON_ERROR);rc_keys($p,['content','sha256']);
    sr_require(is_string($p['sha256']) && hash_equals(hash('sha256',sr_json($obj->content)),$p['sha256']));
    $c=$p['content'];rc_keys($c,['contextVersion','kind','seasonYear','capturedAt','sourceEventId','rootPlayerIds','entities','gameScores','audit','coverage']);
    sr_require($c['contextVersion']===1 && $c['kind']==='rival_analysis_only');sr_int($c['seasonYear'],2000,2100);sr_id($c['sourceEventId']);$at=sr_at($c['capturedAt']);
    $t=$c['entities'];$columns=rc_columns();rc_keys($t,array_keys($columns));$ids=[];$links=[];$slots=[];
    foreach ($columns as $table=>$cols) {
        sr_require(is_array($t[$table]));
        foreach ($t[$table] as $r) sr_require(is_array($r) && !array_diff(array_keys($r),explode(' ',$cols)));
    }
    foreach (['players','tournaments','events','entrants','sets','games'] as $table) $ids[$table]=sr_index($t[$table]);
    sr_require(count($t['sets'])<=5000 && count($c['rootPlayerIds'])>0 && count($c['rootPlayerIds'])<=1000 && count(array_unique($c['rootPlayerIds']))===count($c['rootPlayerIds']));
    foreach ($c['rootPlayerIds'] as $id) sr_require(isset($ids['players'][sr_id($id)]));
    foreach ($t['players'] as $r) { sr_text($r['tag'],100);sr_text($r['known_as'] ?? null,100,true);sr_text($r['country_basis'] ?? null,255,true); }
    foreach ($t['entrant_players'] as $r) { $en=sr_id($r['entrant_id']);$pid=sr_id($r['player_id']);$key="$en:$pid";sr_require(!isset($links[$key]) && isset($ids['entrants'][$en],$ids['players'][$pid]));$links[$key]=true; }
    foreach ($t['set_slots'] as $r) { $sid=sr_id($r['set_id']);$i=sr_int($r['slot_index'],0,1);$key="$sid:$i";sr_require(!isset($slots[$key]) && isset($ids['sets'][$sid]));$slots[$key]=$r; }
    $lo=$c['seasonYear'].'-01-01 06:00:00.000000';$hi=($c['seasonYear']+1).'-01-01 06:00:00.000000';
    foreach ($t['events'] as $e) sr_require(isset($ids['tournaments'][sr_id($e['tournament_id'])]) && $e['videogame_id']===1386 && $e['entrant_size']===1 && $e['starts_at']>=$lo && $e['starts_at']<$hi);
    foreach ($t['entrants'] as $e) sr_require(isset($ids['events'][sr_id($e['event_id'])]));
    foreach ($t['sets'] as $s) {
        $sid=sr_id($s['id']);$eid=sr_id($s['event_id']);sr_require(isset($ids['events'][$eid]));$pair=[];
        for($i=0;$i<2;$i++) { $r=$slots["$sid:$i"] ?? null;sr_require($r!==null && $r['event_id']===$eid && ($r['entrant_id']===null || ($ids['entrants'][$r['entrant_id']]['event_id'] ?? null)===$eid));$pair[]=$r['entrant_id']; }
        sr_require($s['winner_entrant_id']===null || in_array($s['winner_entrant_id'],$pair,true));
    }
    $numbers=[];$selections=[];$known=sr_character_ids();
    foreach ($t['games'] as $g) {
        $sid=sr_id($g['set_id']);$n=sr_int($g['game_number'],1,65535);$key="$sid:$n";
        sr_require(($ids['sets'][$sid]['outcome_type'] ?? null)==='competitive' && !isset($numbers[$key]) && in_array($g['winner_entrant_id'],[$slots["$sid:0"]['entrant_id'],$slots["$sid:1"]['entrant_id']],true) && $g['synced_at']===$at);$numbers[$key]=true;
    }
    foreach ($t['game_selections'] as $r) {
        $gid=sr_id($r['game_id']);$sid=sr_id($r['set_id']);$en=sr_id($r['entrant_id']);$key="$gid:$en";
        sr_require(($ids['games'][$gid]['set_id'] ?? null)===$sid && isset($known[sr_id($r['character_id'])]) && !isset($selections[$key]) && in_array($en,[$slots["$sid:0"]['entrant_id'],$slots["$sid:1"]['entrant_id']],true));$selections[$key]=true;
    }
    $scores=[];foreach ($c['gameScores'] as $r) {rc_keys($r,['game_id','entrant1_score','entrant2_score']);$gid=sr_id($r['game_id']);sr_require(isset($ids['games'][$gid]) && !isset($scores[$gid]));$scores[$gid]=true;foreach(['entrant1_score','entrant2_score'] as $key) if($r[$key]!==null) sr_int($r[$key],-2147483648,2147483647);}
    sr_require(count($scores)===count($ids['games']));return $p;
}
function rc_ready(PDO $db): void {
    sr_require((bool)sr_query($db,"SELECT version FROM schema_migrations WHERE version='007_analysis_context'"),'analysis_migration_required');
    $engines=array_column(sr_query($db,'SELECT table_name,engine FROM information_schema.tables WHERE table_schema=DATABASE()'),1,0);
    foreach(array_merge(array_keys(rc_columns()),['analysis_context_batches','analysis_context_players','analysis_game_scores']) as $table) sr_require(($engines[$table] ?? null)==='InnoDB','analysis_schema_invalid');
}
function rc_existing(PDO $db,string $table,array $ids,string $cols='id',string $key='id'): array {return sr_context_rows($db,$table,$cols,$ids,$key);}
function rc_plan(PDO $db,array $c): array {
    $t=$c['entities'];$found=[];
    foreach(['events'=>'tournament_id','entrants'=>'event_id','sets'=>'event_id','games'=>'set_id'] as $table=>$field) {
        $found[$table]=array_column(rc_existing($db,$table,array_column($t[$table],'id'),'id '.$field),1,0);
        foreach($t[$table] as $r) sr_require(!isset($found[$table][$r['id']]) || (int)$found[$table][$r['id']]===$r[$field],'analysis_identity_conflict');
    }
    $wanted=array_column($t['entrant_players'],'player_id','entrant_id');
    foreach(rc_existing($db,'entrant_players',array_keys($wanted),'entrant_id player_id','entrant_id') as $r) sr_require(($wanted[$r[0]] ?? null)===(int)$r[1],'analysis_identity_conflict');
    $slots=[];foreach($t['set_slots'] as $r) $slots[$r['set_id'].':'.$r['slot_index']]=[$r['event_id'],$r['entrant_id']];
    foreach(rc_existing($db,'set_slots',array_keys($found['sets']),'set_id slot_index event_id entrant_id','set_id') as $r) sr_require(($slots[$r[0].':'.$r[1]] ?? null)===[(int)$r[2],$r[3]===null?null:(int)$r[3]],'analysis_identity_conflict');
    $rows=$t;$selected=[];$games=[];
    $rows['sets']=array_values(array_filter($t['sets'],static fn($r)=>!isset($found['sets'][$r['id']])));
    foreach($rows['sets'] as $r) $selected[$r['id']]=true;
    $rows['set_slots']=array_values(array_filter($t['set_slots'],static fn($r)=>isset($selected[$r['set_id']])));
    $rows['games']=array_values(array_filter($t['games'],static fn($r)=>isset($selected[$r['set_id']])));
    foreach($rows['games'] as $r) {sr_require(!isset($found['games'][$r['id']]),'analysis_identity_conflict');$games[$r['id']]=true;}
    $rows['game_selections']=array_values(array_filter($t['game_selections'],static fn($r)=>isset($games[$r['game_id']])));
    $scores=array_values(array_filter($c['gameScores'],static fn($r)=>isset($games[$r['game_id']])));
    $counts=['roots'=>count($c['rootPlayerIds']),'newRosterPlayers'=>count($c['rootPlayerIds'])-count(rc_existing($db,'players',$c['rootPlayerIds'])),
        'newPlayers'=>count($t['players'])-count(rc_existing($db,'players',array_column($t['players'],'id'))),'newSets'=>count($selected),'existingSetsKept'=>count($t['sets'])-count($selected),'newGames'=>count($games),'newSelections'=>count($rows['game_selections'])];
    return [$rows,$scores,$counts];
}
function rc_import(PDO $db,array $p,bool $apply=false,?int $authorizedUntil=null): array {
    $locked=false;
    try {
        if($apply) {sr_require((int)sr_query($db,'SELECT GET_LOCK(?,0)',['smash-ranking-import-v1'])[0][0]===1,'import_busy');$locked=true;}
        $db->exec("SET time_zone='+00:00'");$db->exec("SET SESSION sql_mode=CONCAT(@@sql_mode,',STRICT_TRANS_TABLES')");
        $db->exec('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE');if(!$apply)$db->exec('SET TRANSACTION READ ONLY');$db->beginTransaction();
        $ready=(bool)sr_query($db,"SELECT version FROM schema_migrations WHERE version='007_analysis_context'");
        if($ready)rc_ready($db);
        [$rows,$scores,$counts]=rc_plan($db,$p['content']);$c=$p['content'];
        if(!$ready) {sr_require(!$apply,'analysis_migration_required');return ['status'=>'migration_required_no_writes']+$counts;}
        if(sr_query($db,'SELECT source_hash FROM analysis_context_batches WHERE source_hash=?',[$p['sha256']]))return ['status'=>'already_imported']+$counts;
        if(!$apply)return ['status'=>'validated_no_writes']+$counts;
        foreach(rc_columns() as $table=>$columns)sr_insert($db,$table,$columns,$rows[$table],true);
        sr_insert($db,'analysis_game_scores','game_id entrant1_score entrant2_score',$scores,true);
        sr_query($db,'INSERT INTO analysis_context_batches(source_hash,source_event_id,season_year,captured_at) VALUES (?,?,?,?)',[$p['sha256'],$c['sourceEventId'],$c['seasonYear'],sr_at($c['capturedAt'])]);
        foreach($c['rootPlayerIds'] as $pid)sr_query($db,'INSERT INTO analysis_context_players(player_id,season_year,source_hash) VALUES (?,?,?) ON DUPLICATE KEY UPDATE source_hash=VALUES(source_hash)',[$pid,$c['seasonYear'],$p['sha256']]);
        // Compare every newly inserted relation/result, never update existing graph rows.
        foreach(rc_columns()+['analysis_game_scores'=>'game_id entrant1_score entrant2_score'] as $table=>$columns) {
            $wanted=$table==='analysis_game_scores'?$scores:$rows[$table];$cols=explode(' ',$columns);
            foreach($wanted as $r) {
                $keys=$table==='game_selections'?['game_id','entrant_id']:($table==='entrant_players'?['entrant_id','player_id']:($table==='set_slots'?['set_id','slot_index']:($table==='analysis_game_scores'?['game_id']:['id'])));
                $where=implode(' AND ',array_map(static fn($k)=>$k.'=?',$keys));
                $actual=sr_query($db,'SELECT '.implode(',',$cols).' FROM '.$table.' WHERE '.$where,array_map(static fn($k)=>$r[$k],$keys));
                // Globals may preexist and are intentionally preserved. Their identities were checked in the plan.
                if(in_array($table,['players','tournaments','events','entrants','entrant_players'],true)) {sr_require(count($actual)===1,'parity_failed');continue;}
                sr_equal_rows($actual,[array_map(static fn($k)=>$r[$k] ?? null,$cols)]);
            }
        }
        foreach($c['rootPlayerIds'] as $pid)sr_require((bool)sr_query($db,'SELECT player_id FROM analysis_context_players WHERE season_year=? AND player_id=?',[$c['seasonYear'],$pid]),'parity_failed');
        if($authorizedUntil!==null)sr_require(time()<$authorizedUntil,'analysis_authorization_expired');
        $db->commit();return ['status'=>'imported']+$counts;
    } finally {if($db->inTransaction())$db->rollBack();if($locked)sr_query($db,'SELECT RELEASE_LOCK(?)',['smash-ranking-import-v1']);}
}
