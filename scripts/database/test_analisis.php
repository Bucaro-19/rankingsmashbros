<?php
declare(strict_types=1);
require __DIR__.'/../../ranking-smash-ultimate/analisis.php';
function analysis_check($value,string $why): void { if (!$value) throw new RuntimeException($why); }
foreach ([0,1,2,3,4,7,8] as $own) foreach ([0,79,80,149,150,199,200] as $scene) {
    $expected=$own>=8 || ($own>=4 && $scene>=200) ? 'alta' : ($own>=4 || ($own>=2 && $scene>=80) ? 'media' : ($own>=2 || $scene>=150 ? 'baja' : null));
    analysis_check(smash_analisis_confidence($own,$scene)===$expected,"Confidence $own/$scene");
}
analysis_check(smash_analisis_probability(1500,1500,'BT-PILOTO-3')===.5,'Equal strength');
analysis_check(abs(smash_analisis_probability(1900,1500,'BT-PILOTO-3')-10/11)<1e-12,'400 point advantage: model odds 10:1');
analysis_check(smash_analisis_probability(null,1500,'BT-PILOTO-3')===null && smash_analisis_probability(1500,1500,'UNKNOWN')===null,'Do not invent a model');
$session=[]; for ($i=0;$i<30;$i++) smash_analisis_rate($session,100);
try { smash_analisis_rate($session,159); throw new RuntimeException('Limit did not reject'); } catch (SmashAnalisisError $e) { analysis_check($e->reason==='rate_limited','Rate reason'); }
smash_analisis_rate($session,160);
analysis_check(smash_analisis_normalize('JUGADOR ÁÑ')==='jugador an','Search accents');
$catalog=['1302'=>['slug'=>'mario'],'1296'=>['slug'=>'link'],'1746'=>['slug'=>'random']];
function analysis_game(string $id,string $winner,string $a='1302',string $b='1296'): array {
    return ['id'=>$id,'number'=>(int)$id,'setId'=>'500','winner'=>$winner,'picks'=>['1001'=>['players'=>['1'=>true],'characters'=>[$a=>true]],'1002'=>['players'=>['2'=>true],'characters'=>[$b=>true]]]];
}
$games=[analysis_game('1','1001'),analysis_game('2','1002'),analysis_game('3','1001','1302','1302'),analysis_game('4','1001','1746')];
$ambiguous=analysis_game('5','1001'); $ambiguous['picks']['1001']['characters']['1296']=true; $games[]=$ambiguous;
$matrix=(array)smash_analisis_matrix($games,$catalog,['mario'],['link','mario'],'1','2');
analysis_check($matrix['mario|link']['me']===[1,1] && $matrix['mario|link']['him']===[1,1] && $matrix['mario|link']['scene']===[1,1] && $matrix['mario|link']['sceneGames']===2,'Game direction and exclusion');
analysis_check($matrix['mario|mario']['scene']===[1,1] && $matrix['mario|mario']['sceneGames']===1,'Mirror: one distinct game');
$set=['id'=>'500','playerIds'=>['1','2'],'score'=>'Persona 2 - Otro 0'];
$clean=[analysis_game('1','1001'),analysis_game('2','1001')];
analysis_check(smash_analisis_set_characters($clean,[$set],$catalog)===[500=>[1=>'mario',2=>'link']],'Uniform full set characters');
analysis_check(smash_analisis_set_characters([$clean[0]],[$set],$catalog)===[],'A partial 2-0 is not a whole set');
$gap=$clean; $gap[1]['number']=3;
analysis_check(smash_analisis_set_characters($gap,[$set],$catalog)===[],'A numbering gap does not prove complete games');
$unknown=$set; $unknown['score']='Sin marcador';
analysis_check(smash_analisis_set_characters($clean,[$unknown],$catalog)===[],'Unknown score cannot prove full set coverage');
$mixed=$clean; $mixed[1]['picks']['1001']['characters']=['1296'=>true];
analysis_check(smash_analisis_set_characters($mixed,[$set],$catalog)===[500=>[2=>'link']],'Mixed characters: unknown for switching player');
$bad=$clean; $bad[1]['picks']['1001']['players']['3']=true;
analysis_check(smash_analisis_set_characters($bad,[$set],$catalog)===[],'Ambiguous participants invalidate set attribution');
foreach ([149,150] as $n) {
    $rec=smash_analisis_recommendations(['mario'],['link'],[],[],['mario|link'=>['scene'=>[$n,0],'sceneGames'=>$n]],'1');
    analysis_check(count($rec)===($n===150?1:0),'150 scene-only threshold');
}
analysis_check(smash_analisis_recommendations([],['link'],[],[],[],'1')===[],'No selected character: no advice');
analysis_check(smash_analisis_recommendations(['mario'],[],[],[],[],'1')===[],'No rival detected: no advice');
analysis_check(smash_analisis_recommendations(['mario'],['link'],[],[],['mario|link'=>['scene'=>[100,100],'sceneGames'=>200]],'1')===[],'Tied record gives no direction');
// «Prepara el set»: measured from sets and games only. Me = 1 (Mario), rival = 2 (Link main), others 3 (Pikachu) and 4 (Fox).
$deepCatalog=['1302'=>['slug'=>'mario'],'1296'=>['slug'=>'link'],'1338'=>['slug'=>'pikachu'],'1286'=>['slug'=>'fox'],'1746'=>['slug'=>'random']];
$ids=['mario'=>'1302','link'=>'1296','pikachu'=>'1338','fox'=>'1286'];
$dg=static function (string $set,int $n,array $a,array $b,string $winner) use ($ids): array {
    $pick=static fn(array $x)=>['players'=>[$x[0]=>true]]+($x[1]===null ? [] : ['characters'=>[$ids[$x[1]]=>true]]);
    return ['id'=>$set.$n,'number'=>$n,'setId'=>$set,'winner'=>'e'.$winner,'picks'=>['e'.$a[0]=>$pick($a),'e'.$b[0]=>$pick($b)]];
};
$R=['2','link']; $P=['3','pikachu']; $F=['4','fox']; $M=['1','mario'];
$deepGames=[$dg('S1',1,$R,$P,'2'),$dg('S1',2,$R,$P,'3'),$dg('S1',3,$R,$P,'3'), $dg('S2',1,$R,$P,'3'),$dg('S2',2,$R,$P,'3'),
    $dg('S3',1,$M,$R,'1'),$dg('S3',2,$M,$R,'1'), $dg('S4',1,$R,$F,'2'),$dg('S4',2,$R,$F,'2'),
    $dg('S6',1,$R,$F,'4'),$dg('S6',2,['2','mario'],$F,'2'),$dg('S6',3,['2','mario'],$F,'2')];
$deepResults=[['id'=>'S1','playerIds'=>['3','2'],'score'=>'Pika 2 - Rival 1'],['id'=>'S2','playerIds'=>['3','2'],'score'=>'Pika 2 - Rival 0'],
    ['id'=>'S3','playerIds'=>['1','2'],'score'=>'Yo 2 - Rival 0'],['id'=>'S4','playerIds'=>['2','4'],'score'=>'Rival 2 - Zorro 0'],
    ['id'=>'S5','playerIds'=>['1','3'],'score'=>'Yo 2 - Pika 1'],['id'=>'S6','playerIds'=>['2','4'],'score'=>'Rival 2 - Zorro 1'],
    ['id'=>'S7','playerIds'=>['2','9'],'score'=>'DQ']];
$deepPublic=['results'=>$deepResults]; $deepView=['results'=>$deepResults,'players'=>[['id'=>'3','rank'=>5],['id'=>'1','rank'=>20],['id'=>'4','rank'=>40]]];
$lite=new PDO('sqlite::memory:'); $lite->setAttribute(PDO::ATTR_ERRMODE,PDO::ERRMODE_EXCEPTION);
$lite->exec("CREATE TABLE players (id TEXT PRIMARY KEY, tag TEXT); INSERT INTO players VALUES ('3','Pika'),('4','Zorro')");
$deepChars=smash_analisis_set_characters($deepGames,$deepResults,$deepCatalog);
$deep=smash_analisis_deep($lite,$deepPublic,$deepView,['games'=>$deepGames],$deepCatalog,$deepChars,'1','2',['mario'],'link');
analysis_check($deep['rival']===['main'=>'link','mainShare'=>0.8333,'coveredSets'=>5,'totalSets'=>6],'Main share over registered games; sets with a known opposing character');
analysis_check($deep['vsChars']===['hard'=>[['slug'=>'mario','won'=>0,'lost'=>2],['slug'=>'pikachu','won'=>1,'lost'=>4]],'good'=>[['slug'=>'fox','won'=>4,'lost'=>1]]],'His games against each character, worst first');
analysis_check(array_column($deep['counters'],'slug')===['pikachu','mario'] && array_column($deep['avoid'],'slug')===['fox'],'Counters and avoid, strongest evidence first');
analysis_check($deep['counters'][0]===['slug'=>'pikachu','mine'=>false,'mySets'=>null,'hisGames'=>[1,4],'sceneGames'=>[4,1],'confidence'=>'media','guide'=>null],'A counter from his own games: his record, the scene and no invented guide');
analysis_check($deep['counters'][1]===['slug'=>'mario','mine'=>true,'mySets'=>[1,0],'hisGames'=>[0,2],'sceneGames'=>[2,0],'confidence'=>'baja','guide'=>null],'My own sets come first as evidence; a single set is low confidence');
analysis_check($deep['avoid'][0]['hisGames']===[2,1] && $deep['avoid'][0]['sceneGames']===[1,2] && !isset($deep['counters'][0]['edge']),'Avoid: his main wins that matchup; internal score does not leave');
$pattern=$deep['setPattern'];
analysis_check($pattern['setsScored']===5 && $pattern['setsWithScores']===5 && $pattern['game1']===[2,3] && $pattern['decider']===[1,1] && $pattern['close21']===[1,1] && $pattern['close32']===[0,0],'Set pattern: first game, deciding game and close sets; a DQ is not a set');
analysis_check($pattern['afterLoss']===['total'=>4,'kept'=>3,'switched'=>[['slug'=>'mario','n'=>1]]],'After losing a game: keeps or switches, and to whom');
analysis_check($deep['common']===[['alias'=>'Pika','me'=>[1,0],'him'=>[0,2]]] && $deep['commonTotal']===1,'Common opponents with both records, no ids');
analysis_check($deep['byTier']===['top10'=>[0,2],'t11_30'=>[0,1],'rest'=>[2,0]],'Sets by rank band; unranked opponents left out');
analysis_check($deep['toolkit']===null && $deep['punishable']===null,'No frame data without a licensed source');
$none=smash_analisis_deep($lite,['results'=>[]],['results'=>[],'players'=>[]],['games'=>[]],$deepCatalog,[],'1','2',['mario'],null);
analysis_check($none['counters']===[] && $none['avoid']===[] && $none['vsChars']===['hard'=>[],'good'=>[]] && $none['setPattern']===null && $none['common']===[] && $none['byTier']===null && $none['rival']['mainShare']===null,'No data: empty lists and nulls, never zeros presented as records');
$tied=smash_analisis_deep($lite,$deepPublic,$deepView,['games'=>[$dg('S4',1,$R,$F,'2'),$dg('S4',2,$R,$F,'4')]],$deepCatalog,[],'1','2',[],'link');
analysis_check($tied['counters']===[] && $tied['avoid']===[],'A tied record takes no side');
analysis_check(smash_analisis_deep_confidence([4,0],[0,0],[0,0])==='alta' && smash_analisis_deep_confidence(null,[6,4],[0,0])==='alta' && smash_analisis_deep_confidence([1,1],[0,0],[0,0])==='media'
    && smash_analisis_deep_confidence(null,[0,0],[12,8])==='media' && smash_analisis_deep_confidence(null,[2,2],[5,5])==='baja','Confidence thresholds');
// Free teaser: one measured finding in full, and only counts of the rest.
$teaser=smash_analisis_teaser_from($deep,'link');
analysis_check($teaser===['headline'=>['kind'=>'hard','slug'=>'pikachu','won'=>1,'lost'=>4],'main'=>'link',
    'locked'=>['counters'=>3,'characters'=>2,'common'=>1,'sets'=>5,'coveredSets'=>5,'totalSets'=>6]],'Teaser: the first finding with a real sample (Pikachu, 5 games), not the two-game one; counts only');
analysis_check(strpos(json_encode($teaser),'Pika')===false && strpos(json_encode($teaser),'mario')===false && strpos(json_encode($teaser),'fox')===false,'No opponent, counter or other character of the paid sections leaves in the teaser');
$few=$deep; $few['vsChars']['hard']=[['slug'=>'mario','won'=>0,'lost'=>2]];
analysis_check(smash_analisis_teaser_from($few,'link')['headline']===['kind'=>'game1','won'=>2,'lost'=>3],'Without a character sample, the first-game record (5 sets) is the finding');
$few['setPattern']['game1']=[1,1];
analysis_check(smash_analisis_teaser_from($few,'link')['headline']===null,'Two sets against the top 10 are not a finding: nothing is shown rather than a thin figure');
$few['byTier']['top10']=[1,2];
analysis_check(smash_analisis_teaser_from($few,'link')['headline']===['kind'=>'top10','won'=>1,'lost'=>2],'Three sets against the top 10 are');
analysis_check(smash_analisis_teaser_from($none,null)===['headline'=>null,'main'=>null,'locked'=>['counters'=>0,'characters'=>0,'common'=>0,'sets'=>0,'coveredSets'=>0,'totalSets'=>0]],'No data: no finding and real zeros in the counts');
echo "Analysis pure contracts: OK\n";
