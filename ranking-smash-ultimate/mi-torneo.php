<?php
declare(strict_types=1);
require_once __DIR__.'/bracket-store.php';
function mt_time(?int $at,?string $zone,?string $source): array {
    $format=static function(int $t,string $z): string{return (new DateTimeImmutable('@'.$t))->setTimezone(new DateTimeZone($z))->format('d/m/Y H:i');};
    return ['timestamp'=>$at,'guatemala'=>$at===null?null:$format($at,'America/Guatemala'),'local'=>$at===null||$zone===null?null:$format($at,$zone),'timezone'=>$zone,'source'=>$source];
}
function mt_member(array $en,array $seed,array $ranks): array {
    $pid=$en['playerId'];return ['playerId'=>$pid,'tag'=>$en['tag'],'seed'=>$seed['seed']??$en['initialSeed'],'groupSeed'=>$seed['groupSeed'],'rank'=>$ranks[$pid]['rank']??null,
        'analysisUrl'=>$pid===null?null:'./analisis.html?rival='.rawurlencode($pid),'prepareUrl'=>$pid===null?null:'./preparar.html?rival='.rawurlencode($pid)];
}
// Follow only published slot prerequisites. Never manufacture a standard bracket.
function mt_bracket(array $g,string $me,array $members,?string $zone): array {
    $sets=[];$seeds=[];$byeSeeds=[];foreach($g['sets'] as $s)$sets[$s['id']]=$s;foreach($g['seeds'] as $s){$seeds[$s['id']]=$s['entrantId'];if($s['isBye']===true)$byeSeeds[$s['id']]=true;}
    $bye=static function(array $s)use($byeSeeds): bool {foreach($s['slots'] as $v)if($v['seedId']!==null&&isset($byeSeeds[$v['seedId']]))return true;return false;};
    $choose=static function(array $ids)use($members): ?string {
        $ids=array_values(array_unique(array_filter($ids,static fn($id)=>$id!==null)));if(count($ids)!==2)return null;
        $a=$members[$ids[0]]['seed']??null;$b=$members[$ids[1]]['seed']??null;return $a===null||$b===null||$a===$b?null:($a<$b?$ids[0]:$ids[1]);
    };
    $resolve=null;$slot=null;$memo=[];$visiting=[];
    $slot=static function(array $v,int $depth)use(&$resolve,$seeds): ?string {
        if($v['entrantId']!==null)return $v['entrantId'];
        if($v['prereqType']==='set'&&$v['prereqId']!==null){$r=$resolve($v['prereqId'],$depth+1);return $v['prereqPlacement']===1?$r[0]:($v['prereqPlacement']===2?$r[1]:null);}
        // A seed is direct only when no unresolved set prerequisite exists.
        return $v['prereqType']!=='set'&&$v['seedId']!==null?($seeds[$v['seedId']]??null):null;
    };
    $resolve=static function(string $id,int $depth)use(&$resolve,&$slot,&$memo,&$visiting,$sets,$choose,$bye): array {
        if(isset($memo[$id]))return $memo[$id];if($depth>64||isset($visiting[$id])||!isset($sets[$id]))return [null,null];$visiting[$id]=true;$s=$sets[$id];$ids=[];
        foreach($s['slots'] as $v)$ids[]=$slot($v,$depth);$known=array_values(array_filter($ids,static fn($v)=>$v!==null));$winner=$s['winnerId']??($bye($s)&&count($known)===1?$known[0]:$choose($ids));$loser=null;
        if(count($ids)===2&&$ids[0]!==null&&$ids[1]!==null&&$winner!==null)$loser=$winner===$ids[0]?$ids[1]:$ids[0];
        unset($visiting[$id]);return $memo[$id]=[$winner,$loser];
    };
    // Only confirmed advancement identifies the player's next actual set. A
    // predicted win never makes a later round become their first match.
    $confirmed=null;$confirmedMemo=[];$confirming=[];
    $confirmed=static function(array $v,int $depth=0)use(&$confirmed,$sets,$seeds,$bye,&$confirmedMemo,&$confirming): ?string {
        if($v['entrantId']!==null)return $v['entrantId'];
        if($v['prereqType']!=='set')return $v['seedId']===null?null:($seeds[$v['seedId']]??null);
        $key=($v['prereqId']??'').':'.($v['prereqPlacement']??'');
        if(array_key_exists($key,$confirmedMemo))return $confirmedMemo[$key];
        if($depth>64||isset($confirming[$key])||!isset($sets[$v['prereqId']??'']))return null;$confirming[$key]=true;$prior=$sets[$v['prereqId']];$ids=[];foreach($prior['slots'] as $part)$ids[]=$confirmed($part,$depth+1);
        $known=array_values(array_filter($ids,static fn($id)=>$id!==null));$winner=$prior['winnerId']??($bye($prior)&&count($known)===1?$known[0]:null);
        $result=null;if($v['prereqPlacement']===1)$result=$winner;
        if($v['prereqPlacement']===2&&count($known)===2&&$winner!==null)$result=$known[0]===$winner?$known[1]:$known[0];unset($confirming[$key]);return $confirmedMemo[$key]=$result;
    };
    $candidates=[];
    foreach($sets as $s){if($s['state']===3||$s['winnerId']!==null||$bye($s))continue;$ids=[];foreach($s['slots'] as $v)$ids[]=$confirmed($v);
        if(in_array($me,$ids,true))$candidates[]=$s;
    }
    usort($candidates,static function($a,$b){return [abs($a['round']??99999),$a['id']]<=>[abs($b['round']??99999),$b['id']];});
    $first=null;
    foreach($candidates as $s){$ids=[];foreach($s['slots'] as $v)$ids[]=$slot($v,0);$other=array_values(array_filter($ids,static fn($v)=>$v!==null&&$v!==$me));
        // A missing slot is not proof of a bye. Keep the first match as unknown.
        $first=['id'=>$s['id'],'round'=>$s['roundText'],'opponent'=>count($other)===1?($members[$other[0]]??null):null,'opponentConfirmed'=>count(array_filter($s['slots'],static fn($v)=>($confirmed($v)!==null&&$confirmed($v)!==$me)))===1,'time'=>mt_time($s['startAt']??$g['startAt'],$zone,$s['startAt']!==null?'set_or_round':$g['timeSource'])];break;
    }
    $path=[];$seen=[];$current=$first['id']??null;
    while($current!==null&&count($path)<20&&!isset($seen[$current])){
        $seen[$current]=true;$next=null;$side=null;
        foreach($sets as $s)foreach($s['slots'] as $i=>$v)if($v['prereqType']==='set'&&$v['prereqId']===$current&&$v['prereqPlacement']===1){$next=$s;$side=$i;break 2;}
        if($next===null)break;$opponent=null;foreach($next['slots'] as $i=>$v)if($i!==$side){$en=$slot($v,0);$opponent=$en===null?null:($members[$en]??null);}
        $path[]=['round'=>$next['roundText'],'opponent'=>$opponent,'time'=>mt_time($next['startAt']??$g['startAt'],$zone,$next['startAt']!==null?'set_or_round':$g['timeSource'])];$current=$next['id'];
    }
    return ['firstSet'=>$first,'probablePath'=>$path];
}
function mt_response(?array $p,?string $playerId,array $public,int $now): array {
    $out=['ok'=>true,'status'=>'snapshot_unavailable','capturedAt'=>null,'event'=>null,'upcoming'=>false,'pools'=>[]];if($p===null)return $out;
    mt_validate($p);$e=$p['event'];$out['capturedAt']=$p['capturedAt'];$out['event']=['name'=>$e['tournamentName'],'url'=>'https://www.start.gg/'.$e['slug'],'start'=>mt_time($e['startAt'],$e['timezone'],'event'),'endAt'=>$e['endAt']];
    if($p['registrationState']!=='published'){$out['status']='registrations_unavailable';return $out;}
    $entrant=null;foreach($p['entrants'] as $v)if($playerId!==null&&$v['playerId']===$playerId){$entrant=$v;break;}
    if($entrant===null){$out['status']='not_registered';return $out;}
    $out['upcoming']=$e['startAt']!==null&&$e['startAt']-$now<=7*86400&&$now<min($e['endAt']??MT_END,MT_END);
    $ranks=[];foreach($public['players']??[] as $r)if(isset($r['id'])&&is_int($r['rank']??null))$ranks[(string)$r['id']]=$r;
    $entrants=[];foreach($p['entrants'] as $v)$entrants[$v['id']]=$v;
    foreach($p['groups'] as $g){$mine=false;foreach($g['seeds'] as $s)if($s['entrantId']===$entrant['id'])$mine=true;if(!$mine||!$g['dataAvailable'])continue;
        $members=[];$rivals=[];foreach($g['seeds'] as $s)if($s['entrantId']!==null){$m=mt_member($entrants[$s['entrantId']],$s,$ranks);$members[$s['entrantId']]=$m;if($s['entrantId']!==$entrant['id'])$rivals[]=$m;}
        $ranked=array_values(array_filter($rivals,static fn($m)=>$m['rank']!==null));$eligible=$ranked?:array_values(array_filter($rivals,static fn($m)=>$m['seed']!==null));$basis=$ranked?'rank':'seed';
        usort($eligible,static fn($a,$b)=>[$a[$basis],$a['tag']]<=>[$b[$basis],$b['tag']]);$strongest=$eligible[0]??null;
        $list=array_values($members);usort($list,static fn($a,$b)=>[$a['seed']??PHP_INT_MAX,$a['tag']]<=>[$b['seed']??PHP_INT_MAX,$b['tag']]);
        $out['pools'][]=['phase'=>$g['phaseName'],'phaseOrder'=>$g['phaseOrder'],'group'=>$g['identifier'],'start'=>mt_time($g['startAt'],$e['timezone'],$g['timeSource']),'members'=>$list,'strongest'=>$strongest,'strongestBasis'=>$strongest===null?null:$basis]+mt_bracket($g,$entrant['id'],$members,$e['timezone']);
    }
    usort($out['pools'],static fn($a,$b)=>($a['phaseOrder']??PHP_INT_MAX)<=>($b['phaseOrder']??PHP_INT_MAX));$out['status']=$out['pools']?'ready':'pools_unpublished';return $out;
}
