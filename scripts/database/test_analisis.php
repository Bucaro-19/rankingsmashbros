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
echo "Analysis pure contracts: OK\n";
