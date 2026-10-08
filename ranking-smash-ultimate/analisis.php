<?php
declare(strict_types=1);
// Library only. No I/O on inclusion. All analysis queries are SELECTs; no provider calls.
const SMASH_ANALISIS_GAME_ROWS = 50000;
final class SmashAnalisisError extends RuntimeException {
    public $reason;
    public function __construct(string $reason) { $this->reason = $reason; parent::__construct('No se pudo consultar el análisis.'); }
}
function smash_analisis_query(PDO $db, string $sql, array $params = []): array {
    $q = $db->prepare($sql); $q->execute($params); return $q->fetchAll(PDO::FETCH_ASSOC);
}
function smash_analisis_scope($value): string {
    $scopes = ['gt'=>'gt', 'guatemala'=>'gt', 'intl'=>'intl', 'combined'=>'intl'];
    if (!is_string($value) || !isset($scopes[$value])) throw new SmashAnalisisError('invalid_scope');
    return $scopes[$value];
}
function smash_analisis_normalize(string $text): string {
    $text = mb_strtolower($text, 'UTF-8');
    $text = strtr($text, ['á'=>'a','à'=>'a','â'=>'a','ä'=>'a','ã'=>'a','å'=>'a','é'=>'e','è'=>'e','ê'=>'e','ë'=>'e',
        'í'=>'i','ì'=>'i','î'=>'i','ï'=>'i','ó'=>'o','ò'=>'o','ô'=>'o','ö'=>'o','õ'=>'o','ú'=>'u','ù'=>'u','û'=>'u','ü'=>'u','ñ'=>'n','ç'=>'c','ý'=>'y','ÿ'=>'y']);
    return (string)preg_replace('/\p{M}/u', '', $text);
}
function smash_analisis_rate(array &$session, int $now): void {
    $recent = array_values(array_filter($session['smash_analisis_requests'] ?? [], static fn($at) => is_int($at) && $at > $now-60 && $at <= $now));
    if (count($recent) >= 30) throw new SmashAnalisisError('rate_limited');
    $recent[] = $now; $session['smash_analisis_requests'] = $recent;
}
function smash_analisis_confidence(int $own, int $scene): ?string {
    if ($own >= 8 || ($own >= 4 && $scene >= 200)) return 'alta';
    if ($own >= 4 || ($own >= 2 && $scene >= 80)) return 'media';
    if ($own >= 2 || $scene >= 150) return 'baja';
    return null;
}
function smash_analisis_probability(?int $mine, ?int $theirs, string $method): ?float {
    // rank.py: points=1500+400/ln(10)*strength; BT p=logistic(strengthMe-strengthRival).
    if ($mine === null || $theirs === null || $method !== 'BT-PILOTO-3') return null;
    $x = ($theirs-$mine)/400; // Stable tails, without changing the model or display clipping.
    return $x >= 0 ? pow(10, -$x)/(1+pow(10, -$x)) : 1/(1+pow(10, $x));
}
function smash_analisis_score(array $set, string $me): array {
    $won = (string)$set['playerIds'][0] === $me;
    if (!preg_match('/(?:^|\s)([0-9]{1,2}) - .*\s([0-9]{1,2})$/u', (string)($set['score'] ?? ''), $m) || (int)$m[1] === (int)$m[2]) return [null,null];
    $high=max((int)$m[1],(int)$m[2]); $low=min((int)$m[1],(int)$m[2]);
    return $won ? [$high,$low] : [$low,$high];
}
function smash_analisis_access(PDO $db, array $user, ?array $config, int $now): array {
    $admin = smash_stats_is_owner($db,$user['id']);
    $status = $config === null ? null : smash_premium_status($db,$user['id'],$config['live'],$now);
    $active = $status !== null && $status['premium']; $end = $status['currentPeriodEnd'] ?? null;
    $expired = !$active && $end !== null && strtotime($end) <= $now ? $end : null;
    return ['premium'=>['active'=>$active,'expiredAt'=>$expired], 'access'=>['full'=>$admin || $active,'reason'=>$admin ? 'admin' : ($active ? 'premium' : 'free')]];
}
function smash_analisis_index(array $public): array {
    $out = [];
    foreach (['intl'=>$public,'gt'=>$public['localRanking']] as $scope=>$v) {
        foreach ($v['players'] as $p) {
            $id=(string)$p['id'];
            if (!isset($out[$id])) $out[$id]=['playerId'=>$id,'tag'=>$p['tag'],'avatarUrl'=>null,'country'=>null,'url'=>$p['url'] ?? null,'rank'=>['gt'=>null,'intl'=>null],'points'=>['gt'=>null,'intl'=>null]];
            $out[$id]['rank'][$scope]=$p['rank']; $out[$id]['points'][$scope]=$p['rating'];
        }
        foreach ($v['results'] ?? [] as $r) foreach ($r['playerIds'] as $i=>$id) {
            $id=(string)$id;
            if (!isset($out[$id])) $out[$id]=['playerId'=>$id,'tag'=>$r['playerTags'][$i] ?? 'Rival sin alias','avatarUrl'=>null,'country'=>null,'url'=>null,'rank'=>['gt'=>null,'intl'=>null],'points'=>['gt'=>null,'intl'=>null]];
        }
    }
    return $out;
}
function smash_analisis_enrich_players(PDO $db, array &$players): void {
    foreach (array_chunk(array_keys($players),500) as $ids) {
        foreach (smash_analisis_query($db,'SELECT id,country_code,profile_url FROM players WHERE id IN ('.implode(',',array_fill(0,count($ids),'?')).')',$ids) as $r) {
            $id=(string)$r['id']; $players[$id]['country']=$r['country_code'];
            $players[$id]['url']=$players[$id]['url'] ?? $r['profile_url'];
        }
    }
}
function smash_analisis_record(array $results, string $me, string $rival): array {
    $wins=0; $losses=0;
    foreach ($results as $r) if (in_array($me,$r['playerIds'],true) && in_array($rival,$r['playerIds'],true)) {
        if ($r['playerIds'][0] === $me) $wins++; else $losses++;
    }
    return ['wins'=>$wins,'losses'=>$losses,'sets'=>$wins+$losses];
}
function smash_analisis_catalog(PDO $db): array {
    $out=[]; foreach (smash_analisis_query($db,'SELECT id,name,slug,icon_url,portrait_url FROM characters') as $r) $out[(string)$r['id']]=$r;
    return $out;
}
function smash_analisis_detection(array $public, string $id, array $catalog): array {
    $detected=[]; $coverage=null; $total=0;
    foreach ($public['results'] ?? [] as $r) if (in_array($id,$r['playerIds'],true)) $total++;
    foreach ($public['players'] as $p) if ((string)$p['id'] === $id) {
        $total=$p['sets']; $coverage=['registered'=>$p['mainCoverage']['setsWithSelections'],'total'=>$p['mainCoverage']['setsQueried'],'source'=>'published'];
        $sum=array_sum(array_column($p['mains'],'games'));
        foreach ($p['mains'] as $m) {
            $cid=(string)$m['characterId']; $detected[]=['characterId'=>$cid,'slug'=>$catalog[$cid]['slug'] ?? null,'name'=>$m['name'],
                'games'=>$m['games'],'totalGames'=>$sum,'usableForMatchups'=>$cid !== '1746' && isset($catalog[$cid])];
        }
        break;
    }
    return ['detected'=>$detected,'coverage'=>$coverage ?? ['registered'=>null,'total'=>$total,'source'=>'unavailable']];
}
function smash_analisis_games(PDO $db, array $public): array {
    $at=(new DateTimeImmutable($public['generatedAt']))->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d H:i:s.u');
    $cuts=smash_analisis_query($db,"SELECT id,public_snapshot FROM cuts WHERE generated_at=? AND season_year=? AND method_version=? AND status='published'",[$at,$public['seasonYear'],$public['methodVersion']]);
    if (count($cuts)!==1 || json_decode($cuts[0]['public_snapshot'],true) != $public) return ['status'=>'cut_not_synced','games'=>[],'completed'=>[]];
    $cut=$cuts[0]['id'];
    $completed=[]; foreach (smash_analisis_query($db,"SELECT r.set_id,s.completed_at FROM cut_set_results r JOIN sets s ON s.id=r.set_id WHERE r.cut_id=? AND r.scope='combined'",[$cut]) as $r) $completed[(string)$r['set_id']]=$r['completed_at'];
    $captured=(new DateTimeImmutable($public['characterCapturedAt']))->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d H:i:s.u');
    $q=$db->prepare("SELECT g.id,g.set_id,g.game_number,g.winner_entrant_id,s.event_id,ss.entrant_id,ep.player_id,gs.character_id
        FROM cut_events ce JOIN sets s ON s.event_id=ce.event_id AND s.outcome_type='competitive'
        JOIN games g ON g.set_id=s.id AND g.synced_at<=? AND g.winner_entrant_id IS NOT NULL
        JOIN set_slots ss ON ss.set_id=g.set_id AND ss.entrant_id IS NOT NULL
        JOIN entrant_players ep ON ep.entrant_id=ss.entrant_id
        LEFT JOIN game_selections gs ON gs.game_id=g.id AND gs.set_id=g.set_id AND gs.entrant_id=ss.entrant_id
        WHERE ce.cut_id=? AND ce.scope='combined' LIMIT ".(SMASH_ANALISIS_GAME_ROWS+1));
    $q->execute([$captured,$cut]); $games=[]; $rows=0;
    while ($r=$q->fetch(PDO::FETCH_ASSOC)) {
        if (++$rows>SMASH_ANALISIS_GAME_ROWS) throw new SmashAnalisisError('game_limit_exceeded');
        $gid=(string)$r['id']; $en=(string)$r['entrant_id'];
        if (!isset($games[$gid])) $games[$gid]=['id'=>$gid,'number'=>(int)$r['game_number'],'setId'=>(string)$r['set_id'],'eventId'=>(string)$r['event_id'],'winner'=>(string)$r['winner_entrant_id'],'picks'=>[]];
        $games[$gid]['picks'][$en]['players'][(string)$r['player_id']]=true;
        if ($r['character_id']!==null) $games[$gid]['picks'][$en]['characters'][(string)$r['character_id']]=true;
    }
    return ['status'=>$games ? 'available' : 'empty','games'=>$games,'completed'=>$completed];
}
function smash_analisis_set_characters(array $games, array $results, array $catalog): array {
    $sets=[]; $invalid=[]; $ledger=[]; $numbers=[];
    foreach ($results as $r) $ledger[(string)$r['id']]=$r['playerIds'];
    foreach ($games as $g) {
        $sid=$g['setId']; $ids=[];
        foreach ($g['picks'] as $pick) if (count($pick['players'])===1) $ids[]=(string)array_key_first($pick['players']);
        $expected=$ledger[$sid] ?? []; sort($ids); sort($expected);
        if (count($g['picks'])!==2 || count($ids)!==2 || $ids!==$expected || !isset($g['picks'][$g['winner']])) { $invalid[$sid]=true; continue; }
        $numbers[$sid][]=$g['number'];
        foreach ($g['picks'] as $pick) {
        if (count($pick['players'])!==1) continue; $pid=(string)array_key_first($pick['players']);
        $sets[$g['setId']][$pid]['total']=($sets[$g['setId']][$pid]['total'] ?? 0)+1;
        $chars=$pick['characters'] ?? [];
        if (count($chars)===1) {
            $cid=(string)array_key_first($chars);
            if ($cid!=='1746' && isset($catalog[$cid])) { $sets[$g['setId']][$pid]['valid']=($sets[$g['setId']][$pid]['valid'] ?? 0)+1; $sets[$g['setId']][$pid]['chars'][$cid]=true; }
        }
        }
    }
    $out=[];
    foreach ($results as $r) foreach ($r['playerIds'] as $pid) {
        $pid=(string)$pid; $data=$sets[(string)$r['id']][$pid] ?? null;
        if (isset($invalid[(string)$r['id']]) || !$data || ($data['valid'] ?? 0)!==$data['total'] || count($data['chars'] ?? [])!==1) continue;
        [$a,$b]=smash_analisis_score($r,$pid);
        if ($a===null || $data['total']!==$a+$b) continue; // Only attribute a whole set when all its games can be verified.
        $sequence=$numbers[(string)$r['id']] ?? []; sort($sequence);
        if ($sequence!==range(1,$a+$b)) continue;
        $out[(string)$r['id']][$pid]=$catalog[(string)array_key_first($data['chars'])]['slug'];
    }
    return $out;
}
function smash_analisis_pool(array $detected): array {
    return array_slice(array_column(array_values(array_filter($detected,static fn($d)=>$d['usableForMatchups'])),'slug'),0,3);
}
function smash_analisis_matrix(array $games, array $catalog, array $mine, array $his, string $me, string $rival): array {
    $out=[];
    foreach ($mine as $a) foreach ($his as $b) $out[$a.'|'.$b]=['me'=>[0,0],'him'=>[0,0],'scene'=>[0,0],'sceneGames'=>0,'mirror'=>$a===$b];
    foreach ($games as $g) {
        if (count($g['picks'])!==2 || !isset($g['picks'][$g['winner']])) continue;
        $picks=[];
        foreach ($g['picks'] as $en=>$pick) {
            $chars=$pick['characters'] ?? [];
            if (count($chars)!==1 || count($pick['players'])!==1) continue;
            $cid=(string)array_key_first($chars);
            if ($cid==='1746' || !isset($catalog[$cid])) continue;
            $picks[]=['slug'=>$catalog[$cid]['slug'],'pid'=>(string)array_key_first($pick['players']),'won'=>(string)$en===$g['winner']];
        }
        if (count($picks)!==2 || $picks[0]['pid']===$picks[1]['pid']) continue;
        foreach ($out as $key=>&$record) {
            [$a,$b]=explode('|',$key); $matched=false;
            foreach ($picks as $i=>$pick) {
                $other=$picks[1-$i]; $result=$pick['won'] ? 0 : 1;
                if ($pick['slug']===$a && $other['slug']===$b) {
                    $record['scene'][$result]++; $matched=true;
                    if ($pick['pid']===$me) $record['me'][$result]++;
                }
                if ($pick['pid']===$rival && $pick['slug']===$b && $other['slug']===$a) $record['him'][$result]++;
            }
            if ($matched) $record['sceneGames']++; // A mirror has two player observations but is still ONE game.
        }
        unset($record);
    }
    return $out;
}
function smash_analisis_recommendations(array $chosen, array $his, array $h2h, array $chars, array $matrix, string $me): array {
    if (!$chosen || !$his) return [];
    $out=[]; $strength=['alta'=>3,'media'=>2,'baja'=>1]; $opponent=$his[0];
    foreach ($chosen as $slug) {
        $own=[0,0]; foreach ($h2h as $r) if (($chars[(string)$r['id']][$me] ?? null)===$slug) $own[$r['playerIds'][0]===$me ? 0 : 1]++;
        $scene=$matrix[$slug.'|'.$opponent] ?? ['scene'=>[0,0],'sceneGames'=>0];
        $n=array_sum($own); $confidence=smash_analisis_confidence($n,$scene['sceneGames']);
        if ($confidence===null) continue;
        $basis=$own[0]!==$own[1] ? 'own_sets' : 'scene_games'; $record=$basis==='own_sets' ? $own : $scene['scene'];
        if ($record[0]===$record[1]) continue; // Confidence alone does not establish which direction to recommend.
        $out[]=['type'=>$record[0]>$record[1] ? 'good' : 'avoid','slug'=>$slug,'confidence'=>$confidence,'ownSets'=>$n,'sceneGames'=>$scene['sceneGames'],
            'reasonData'=>['own'=>$own,'scene'=>$scene['scene'],'opponentSlug'=>$opponent,'basis'=>$basis]];
    }
    usort($out,static fn($a,$b)=>($strength[$b['confidence']]<=>$strength[$a['confidence']]) ?: ($b['ownSets']<=>$a['ownSets']) ?: ($b['sceneGames']<=>$a['sceneGames']) ?: strcmp($a['slug'],$b['slug']));
    return array_slice($out,0,2);
}
function smash_analisis_full(PDO $db, array $public, array $base, array $user, string $rival, string $scope): array {
    $me=$user['playerId']; $views=['intl'=>$public,'gt'=>$public['localRanking']]; $view=$views[$scope];
    $catalog=smash_analisis_catalog($db); $data=smash_analisis_games($db,$public);
    $chars=smash_analisis_set_characters($data['games'],$public['results'] ?? [],$catalog);
    foreach (['me'=>$me,'rival'=>$rival] as $key=>$id) $base[$key]+=smash_analisis_detection($public,$id,$catalog);
    $chosen=[]; foreach ($user['chosen'] as $id) if ((string)$id!=='1746' && isset($catalog[$id])) $chosen[]=$catalog[$id]['slug'];
    $base['me']['chosen']=$chosen;
    $mine=$chosen ?: smash_analisis_pool($base['me']['detected']); $his=smash_analisis_pool($base['rival']['detected']);
    $h2h=array_values(array_filter($view['results'] ?? [],static fn($r)=>in_array($me,$r['playerIds'],true) && in_array($rival,$r['playerIds'],true)));
    $events=[]; foreach ($public['events'] as $e) $events[(string)$e['id']]=$e;
    usort($h2h,static function($a,$b) use($events,$data) {
        return strcmp($events[(string)$b['eventId']]['date'],$events[(string)$a['eventId']]['date'])
            ?: strcmp($data['completed'][(string)$b['id']] ?? '',$data['completed'][(string)$a['id']] ?? '') ?: strcmp((string)$a['id'],(string)$b['id']);
    });
    $history=[]; foreach (array_slice($h2h,0,200) as $r) {
        $event=$events[(string)$r['eventId']]; [$a,$b]=smash_analisis_score($r,$me); $country=$event['country'] ?? null;
        $history[]=['setId'=>(string)$r['id'],'eventId'=>(string)$event['id'],'event'=>$event['name'],'date'=>$event['date'],'countryCode'=>$country,
            'intl'=>$country===null ? null : $country!=='GT','myGames'=>$a,'theirGames'=>$b,'won'=>$r['playerIds'][0]===$me,
            'myChar'=>$chars[(string)$r['id']][$me] ?? null,'theirChar'=>$chars[(string)$r['id']][$rival] ?? null,'url'=>$event['url'] ?? null];
    }
    $streak=null;
    $times=array_map(static fn($r)=>$data['completed'][(string)$r['id']] ?? null,$h2h);
    if (count($h2h)>=2 && !in_array(null,$times,true) && count(array_unique($times))===count($times)) {
        $ordered=$h2h;
        usort($ordered,static fn($a,$b)=>strcmp($data['completed'][(string)$b['id']],$data['completed'][(string)$a['id']]));
        $won=$ordered[0]['playerIds'][0]===$me; $n=0;
        foreach ($ordered as $r) { if (($r['playerIds'][0]===$me)!==$won) break; $n++; }
        $streak=['won'=>$won,'sets'=>$n];
    }
    $form=[]; foreach ($view['results'] ?? [] as $r) if (in_array($rival,$r['playerIds'],true)) {
        $eid=(string)$r['eventId']; $e=$events[$eid]; $country=$e['country'] ?? null;
        if (!isset($form[$eid])) $form[$eid]=['eventId'=>$eid,'event'=>$e['name'],'date'=>$e['date'],'countryCode'=>$country,'intl'=>$country===null ? null : $country!=='GT',
            'placement'=>null,'entrants'=>null,'setsWon'=>0,'setsLost'=>0,'url'=>$e['url'] ?? null];
        $form[$eid][$r['playerIds'][0]===$rival ? 'setsWon' : 'setsLost']++;
    }
    $form=array_values($form); usort($form,static fn($a,$b)=>strcmp($b['date'],$a['date']) ?: strcmp($a['eventId'],$b['eventId']));
    $tiers=[];
    foreach ($views as $key=>$v) {
        $ranks=[]; foreach ($v['players'] as $p) $ranks[(string)$p['id']]=$p['rank'];
        $tiers[$key]=['top10'=>[0,0],'t11_50'=>[0,0],'t51_100'=>[0,0],'unranked'=>[0,0],'outsideTop100'=>[0,0]];
        foreach ($v['results'] ?? [] as $r) {
            $pos=array_search($rival,$r['playerIds'],true); if ($pos===false) continue;
            $rank=$ranks[(string)$r['playerIds'][1-$pos]] ?? null;
            $tier=$rank===null ? 'unranked' : ($rank<=10 ? 'top10' : ($rank<=50 ? 't11_50' : ($rank<=100 ? 't51_100' : 'outsideTop100')));
            $tiers[$key][$tier][$pos===0 ? 0 : 1]++;
        }
    }
    $meVs=[]; $himVs=[];
    foreach ($public['results'] ?? [] as $r) foreach (['me'=>$me,'him'=>$rival] as $kind=>$pid) {
        $pos=array_search($pid,$r['playerIds'],true); if ($pos===false) continue;
        $slug=$chars[(string)$r['id']][(string)$r['playerIds'][1-$pos]] ?? null; if ($slug===null) continue;
        if ($kind==='me') { if (!isset($meVs[$slug])) $meVs[$slug]=[0,0]; $meVs[$slug][$pos===0 ? 0 : 1]++; }
        else { if (!isset($himVs[$slug])) $himVs[$slug]=[0,0]; $himVs[$slug][$pos===0 ? 0 : 1]++; }
    }
    $matrix=(array)smash_analisis_matrix($data['games'],$catalog,$mine,$his,$me,$rival);
    // Character records deliberately use the combined cut in BOTH views, as requested by design.
    $allH2h=array_values(array_filter($public['results'] ?? [],static fn($r)=>in_array($me,$r['playerIds'],true) && in_array($rival,$r['playerIds'],true)));
    $base+=['h2h'=>$history,'h2hTruncated'=>count($h2h)>200,'streak'=>$streak,'rivalForm'=>array_slice($form,0,5),'rivalFormTotal'=>count($form),
        'rivalTiers'=>$tiers,'meVsChar'=>(object)$meVs,'himVsChar'=>(object)$himVs,'gameMatrix'=>(object)$matrix,'gameDataStatus'=>$data['status'],'setDataScope'=>'published_ledger',
        'recommendations'=>smash_analisis_recommendations($chosen,$his,$allH2h,$chars,$matrix,$me),
        'probability'=>['p'=>smash_analisis_probability($base['me']['points'][$scope],$base['rival']['points'][$scope],$public['methodVersion']),'scale'=>400,'methodVersion'=>$public['methodVersion']]];
    return $base;
}
function smash_analisis_response(PDO $db, array $public, array $user, array $input, ?array $config, int $now, ?string $avatar = null): array {
    $allowed=['rival','buscar','scope']; if (array_diff(array_keys($input),$allowed)) throw new SmashAnalisisError('invalid_parameters');
    $scope=smash_analisis_scope($input['scope'] ?? 'intl'); $access=smash_analisis_access($db,$user,$config,$now);
    $base=['ok'=>true,'scope'=>$scope,'generatedAt'=>$public['generatedAt'],'seasonYear'=>$public['seasonYear']]+$access;
    if ($user['playerId']===null) return $base+['state'=>'sinJugador','me'=>null,'rival'=>null,'record'=>null];
    if (isset($input['rival'])===isset($input['buscar'])) throw new SmashAnalisisError('invalid_parameters');
    $index=smash_analisis_index($public); $me=$user['playerId'];
    if (!isset($index[$me])) $index[$me]=['playerId'=>$me,'tag'=>$user['tag'],'avatarUrl'=>null,'country'=>$user['country'],'url'=>$user['url'],'rank'=>['gt'=>null,'intl'=>null],'points'=>['gt'=>null,'intl'=>null]];
    if (isset($input['buscar'])) {
        $query=$input['buscar'];
        if (!is_string($query) || !mb_check_encoding($query,'UTF-8') || mb_strlen($query,'UTF-8')>80) throw new SmashAnalisisError('invalid_search');
        $query=trim($query); if ($query!=='' && mb_strlen($query,'UTF-8')<2) throw new SmashAnalisisError('search_too_short');
        $needle=smash_analisis_normalize($query); $found=[];
        if ($query!=='' && $needle==='') throw new SmashAnalisisError('invalid_search');
        foreach ($index as $id=>$player) {
            $id=(string)$id; if ($id===$me) continue;
            $record=smash_analisis_record($public['results'] ?? [],$me,$id);
            if ($needle!=='' ? strpos(smash_analisis_normalize($player['tag']),$needle)===false : $record['sets']===0) continue;
            $player['record']=smash_analisis_record(($scope==='gt' ? $public['localRanking'] : $public)['results'] ?? [],$me,$id); $found[$id]=$player;
        }
        uasort($found,static fn($a,$b)=>($b['record']['sets']<=>$a['record']['sets']) ?: (($a['rank'][$scope] ?? PHP_INT_MAX)<=>($b['rank'][$scope] ?? PHP_INT_MAX)) ?: strcmp($a['tag'],$b['tag']) ?: strcmp($a['playerId'],$b['playerId']));
        $truncated=count($found)>20; $found=array_slice($found,0,20,true); smash_analisis_enrich_players($db,$found);
        return $base+['state'=>'elegir','results'=>array_values($found),'truncated'=>$truncated];
    }
    $rival=smash_account_external_id($input['rival']);
    if ($rival===null || $rival===$me) throw new SmashAnalisisError('invalid_rival');
    if (!isset($index[$rival])) {
        $rows=smash_analisis_query($db,'SELECT tag,country_code,profile_url FROM players WHERE id=?',[$rival]);
        if (!$rows) throw new SmashAnalisisError('rival_not_found');
        $index[$rival]=['playerId'=>$rival,'tag'=>$rows[0]['tag'],'avatarUrl'=>null,'country'=>$rows[0]['country_code'],'url'=>$rows[0]['profile_url'],
            'rank'=>['gt'=>null,'intl'=>null],'points'=>['gt'=>null,'intl'=>null]];
    }
    $players=[$me=>$index[$me],$rival=>$index[$rival]]; smash_analisis_enrich_players($db,$players); $players[$me]['avatarUrl']=smash_account_safe_image($avatar);
    $records=['gt'=>smash_analisis_record($public['localRanking']['results'] ?? [],$me,$rival),'intl'=>smash_analisis_record($public['results'] ?? [],$me,$rival)];
    $base+=['state'=>$access['access']['full'] ? 'listo' : ($access['premium']['expiredAt']===null ? 'bloqueado' : 'vencido'),
        'me'=>$players[$me],'rival'=>$players[$rival],'record'=>$records[$scope],'records'=>$records];
    // Gate BEFORE reading characters/games or building ANY premium response field.
    return $access['access']['full'] ? smash_analisis_full($db,$public,$base,$user,$rival,$scope) : $base;
}
