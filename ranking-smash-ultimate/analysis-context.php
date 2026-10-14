<?php
declare(strict_types=1);
// Optional analysis-only history. No I/O on inclusion, no writes/provider requests.
function smash_analysis_context(PDO $db, int $year, string $me, ?string $rival, bool $full, array $publishedIds = []): array {
    $empty=['players'=>[], 'results'=>[], 'events'=>[], 'games'=>[], 'completed'=>[], 'rowCount'=>0];
    $ready=smash_analisis_query($db,"SELECT version FROM schema_migrations WHERE version='007_analysis_context'");
    if (!$ready) return $empty;
    $people=smash_analisis_query($db,'SELECT p.id,p.tag,p.country_code,p.profile_url FROM analysis_context_players c JOIN players p ON p.id=c.player_id WHERE c.season_year=? LIMIT 1001',[$year]);
    if (count($people)>1000) throw new SmashAnalisisError('game_limit_exceeded');
    $out=$empty;
    foreach ($people as $p) $out['players'][(string)$p['id']]=['playerId'=>(string)$p['id'],'tag'=>$p['tag'],'country'=>$p['country_code'],'url'=>$p['profile_url'],'avatarUrl'=>null,'rank'=>['gt'=>null,'intl'=>null],'points'=>['gt'=>null,'intl'=>null]];
    if (!$people) return $out;
    $from=$year.'-01-01 06:00:00'; $to=($year+1).'-01-01 06:00:00';
    $rows=smash_analisis_query($db,"SELECT s.id,s.event_id,s.winner_entrant_id,s.display_score,s.completed_at,
        a.entrant_id AS ea,b.entrant_id AS eb,pa.player_id AS a,pb.player_id AS b,
        xa.tag AS tag_a,xb.tag AS tag_b,e.name,e.starts_at,e.url,t.name AS tournament,t.country_code
        FROM sets s JOIN events e ON e.id=s.event_id JOIN tournaments t ON t.id=e.tournament_id
        JOIN set_slots a ON a.set_id=s.id AND a.slot_index=0 JOIN set_slots b ON b.set_id=s.id AND b.slot_index=1
        JOIN entrant_players pa ON pa.entrant_id=a.entrant_id JOIN entrant_players pb ON pb.entrant_id=b.entrant_id
        JOIN players xa ON xa.id=pa.player_id JOIN players xb ON xb.id=pb.player_id
        WHERE s.status='completed' AND s.outcome_type='competitive' AND e.videogame_id=1386 AND e.entrant_size=1
        AND e.starts_at>=? AND e.starts_at<? AND (pa.player_id IN (?,?) OR pb.player_id IN (?,?))
        AND s.winner_entrant_id IN (a.entrant_id,b.entrant_id) AND pa.player_id<>pb.player_id
        AND NOT EXISTS(SELECT 1 FROM entrant_players x WHERE x.entrant_id=a.entrant_id AND x.player_id<>pa.player_id)
        AND NOT EXISTS(SELECT 1 FROM entrant_players x WHERE x.entrant_id=b.entrant_id AND x.player_id<>pb.player_id)
        AND EXISTS(SELECT 1 FROM analysis_context_players c WHERE c.season_year=? AND c.player_id IN (pa.player_id,pb.player_id))
        ORDER BY s.id LIMIT 5001",[$from,$to,$me,$rival ?? $me,$me,$rival ?? $me,$year]);
    if (count($rows)>5000) throw new SmashAnalisisError('game_limit_exceeded');
    foreach ($rows as $r) {
        $win=(string)$r['winner_entrant_id']===(string)$r['ea']; $eid=(string)$r['event_id']; $sid=(string)$r['id'];
        $out['results'][$sid]=['id'=>$sid,'eventId'=>$eid,'playerIds'=>[(string)$r[$win?'a':'b'],(string)$r[$win?'b':'a']],
            'playerTags'=>[$r[$win?'tag_a':'tag_b'],$r[$win?'tag_b':'tag_a']],'score'=>$r['display_score'],'country'=>$r['country_code']];
        $out['events'][$eid]=['id'=>$eid,'name'=>$r['tournament'],'eventName'=>$r['name'],'date'=>gmdate('Y-m-d',strtotime($r['starts_at'].' UTC')-21600),'country'=>$r['country_code'],'url'=>$r['url']];
        $out['completed'][$sid]=$r['completed_at'];
    }
    if (!$full || !$out['results']) return $out;
    $n=0;
    foreach (array_chunk(array_values(array_diff(array_keys($out['results']),$publishedIds)),500) as $ids) {
        $q=$db->prepare('SELECT g.id,g.set_id,g.game_number,g.winner_entrant_id,s.event_id,ss.entrant_id,ep.player_id,gs.character_id
            FROM games g JOIN sets s ON s.id=g.set_id JOIN set_slots ss ON ss.set_id=s.id
            JOIN entrant_players ep ON ep.entrant_id=ss.entrant_id
            LEFT JOIN game_selections gs ON gs.game_id=g.id AND gs.set_id=s.id AND gs.entrant_id=ss.entrant_id
            WHERE g.winner_entrant_id IS NOT NULL AND g.set_id IN ('.implode(',',array_fill(0,count($ids),'?')).') LIMIT '.(SMASH_ANALISIS_GAME_ROWS+1));
        $q->execute($ids);
        while ($r=$q->fetch(PDO::FETCH_ASSOC)) {
            if (++$n>SMASH_ANALISIS_GAME_ROWS) throw new SmashAnalisisError('game_limit_exceeded');
            $gid=(string)$r['id'];$en=(string)$r['entrant_id'];
            if (!isset($out['games'][$gid])) $out['games'][$gid]=['id'=>$gid,'number'=>(int)$r['game_number'],'setId'=>(string)$r['set_id'],'eventId'=>(string)$r['event_id'],'winner'=>(string)$r['winner_entrant_id'],'picks'=>[]];
            $out['games'][$gid]['picks'][$en]['players'][(string)$r['player_id']]=true;
            if ($r['character_id']!==null) $out['games'][$gid]['picks'][$en]['characters'][(string)$r['character_id']]=true;
        }
    }
    $out['rowCount']=$n;
    return $out;
}
function smash_analysis_overlay(array $public, array $context): array {
    $have=[];foreach ($public['results'] ?? [] as $r) $have[(string)$r['id']]=true;
    $events=[];foreach ($public['events'] as $e) $events[(string)$e['id']]=true;
    $local=[];foreach ($public['localRanking']['events'] as $e) $local[(string)$e['id']]=true;
    foreach ($context['results'] as $id=>$r) {
        if (isset($have[(string)$id])) continue; // Published immutable outcome always wins.
        $e=$context['events'][$r['eventId']];$public['results'][]=$r;
        if (!isset($events[$r['eventId']])) { $public['events'][]=$e;$events[$r['eventId']]=true; }
        if ($e['country']==='GT') {
            $public['localRanking']['results'][]=$r;
            if (!isset($local[$r['eventId']])) { $public['localRanking']['events'][]=$e;$local[$r['eventId']]=true; }
        }
    }
    return $public;
}
function smash_analysis_merge_games(array $data, array $context, array $original): array {
    if (($data['rowCount'] ?? 0)+$context['rowCount']>SMASH_ANALISIS_GAME_ROWS) throw new SmashAnalisisError('game_limit_exceeded');
    $published=[];foreach ($original['results'] ?? [] as $r) $published[(string)$r['id']]=true;
    foreach ($context['games'] as $id=>$g) if (!isset($published[$g['setId']])) $data['games'][$id]=$g;
    foreach ($context['completed'] as $id=>$at) if (!isset($published[(string)$id])) $data['completed'][$id]=$at;
    if ($data['games']) $data['status']='available';
    return $data;
}
function smash_analysis_context_detection(array $games, array $catalog, string $id, int $total): array {
    $usage=[];$sets=[];
    foreach (smash_analisis_game_rows($games,$catalog) as $g) foreach ($g['sides'] as $side) {
        if ($side['player']!==$id || $side['slug']===null) continue;
        $slug=$side['slug'];$usage[$slug]=($usage[$slug] ?? 0)+1;$sets[$g['setId']]=true;
    }
    $bySlug=[];foreach ($catalog as $cid=>$c) $bySlug[$c['slug']]=['id'=>(string)$cid,'name'=>$c['name']];
    $sum=array_sum($usage);$rows=[];
    foreach ($usage as $slug=>$n) $rows[]=['characterId'=>$bySlug[$slug]['id'],'slug'=>$slug,'name'=>$bySlug[$slug]['name'],'games'=>$n,'totalGames'=>$sum,'usableForMatchups'=>true];
    usort($rows,static fn($a,$b)=>($b['games']<=>$a['games']) ?: strcmp($a['characterId'],$b['characterId']));
    return ['detected'=>$rows,'coverage'=>['registered'=>count($sets),'total'=>$total,'source'=>'analysis_context']];
}
