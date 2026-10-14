<?php
declare(strict_types=1);
// One removal switch. No I/O on inclusion, no network, no user/provider configuration.
const SMASH_FRAME_FACTS_ENABLED = true;
function smash_frame_facts_document(): ?array {
    static $loaded=false, $document=null;
    if ($loaded) return $document;
    $loaded=true;
    $path=__DIR__.'/data/frame-facts-v1.json';
    if (!is_file($path) || filesize($path)>1048576) return null;
    $data=json_decode((string)file_get_contents($path),true);
    if (!is_array($data) || ($data['schemaVersion'] ?? null)!==1 || ($data['policy'] ?? null)!=='unambiguous-default-numerics-v1'
        || !is_array($data['characters'] ?? null) || count($data['characters'])>100
        || ($data['source']['name'] ?? null)!=='Ultimate Frame Data' || ($data['source']['url'] ?? null)!=='https://ultimateframedata.com/smash') return null;
    $name=static fn($x)=>is_string($x) && preg_match('/^[\p{L}\p{N} .–−-]{1,64}$/u',$x);
    $frame=static fn($n)=>is_int($n) && $n>=1 && $n<=200;
    foreach ($data['characters'] as $slug=>$sheet) {
        if (!is_string($slug) || !preg_match('/^[a-z_]{1,50}$/D',$slug) || !is_array($sheet) || !array_key_exists('fastest',$sheet)
            || count($sheet)!==3 || !is_array($sheet['oos'] ?? null) || count($sheet['oos'])>3 || !is_array($sheet['punishable'] ?? null) || count($sheet['punishable'])>3) return null;
        $f=$sheet['fastest'];
        if ($f!==null && (!is_array($f) || count($f)!==3 || !$name($f['name'] ?? null) || !$frame($f['frame'] ?? null)
            || (!is_int($f['damage'] ?? null) && !is_float($f['damage'] ?? null)) || $f['damage']<=0 || $f['damage']>200)) return null;
        foreach ($sheet['oos'] as $move) if (count($move)!==2 || !$name($move['name'] ?? null) || !$frame($move['frame'] ?? null)) return null;
        foreach ($sheet['punishable'] as $move) if (count($move)!==2 || !$name($move['name'] ?? null) || !is_int($move['onShield'] ?? null) || $move['onShield']>=0 || $move['onShield'] < -200) return null;
    }
    // Source does not declare a game build. Null is honest; never assume the handoff's example version.
    if (($data['source']['gameVersion'] ?? null)!==null && (!is_string($data['source']['gameVersion']) || !preg_match('/^\d+\.\d+\.\d+$/D',$data['source']['gameVersion']))) return null;
    $document=$data;
    return $document;
}
function smash_frame_facts(array $chosen, ?string $main, bool $authorized): array {
    $empty=['toolkit'=>null,'punishable'=>null,'frameDataSource'=>null];
    if (!$authorized || !SMASH_FRAME_FACTS_ENABLED) return $empty;
    $data=smash_frame_facts_document();
    if ($data===null) return $empty;
    $toolkit=[];
    foreach (array_slice(array_unique($chosen),0,3) as $slug) {
        $sheet=$data['characters'][$slug] ?? null;
        $toolkit[$slug]=$sheet!==null && $sheet['fastest']!==null ? ['fastest'=>$sheet['fastest'],'oos'=>$sheet['oos']] : null;
    }
    $moves=$main===null ? [] : ($data['characters'][$main]['punishable'] ?? []);
    return ['toolkit'=>$toolkit ?: null, 'punishable'=>$moves ? [$main=>$moves] : null,
        'frameDataSource'=>['name'=>'Ultimate Frame Data','url'=>'https://ultimateframedata.com/smash','gameVersion'=>$data['source']['gameVersion'] ?? null]];
}
