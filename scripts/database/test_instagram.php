<?php
declare(strict_types=1);
require_once __DIR__.'/../../ranking-smash-ultimate/instagram.php';
set_error_handler(static function($severity){if(!(error_reporting()&$severity))return true;throw new SmashInstagramError('instagram_runtime_error');});
function check_ig($ok,$label): void {if(!$ok)throw new RuntimeException($label);}
const IG_FAKE_NOW=1792540800;
const IG_FAKE_ID='17890000000000000';
const IG_FAKE_TOKEN='IGAA_FAKE_ONLY_NotARealCredential_12345678901234567890';
const IG_FAKE_NEW='IGAA_FAKE_ONLY_RenewedCredential_12345678901234567890';
function ig_remove_test(string $path): void {
    foreach(scandir($path) as $name)if($name!=='.'&&$name!=='..') { $f=$path.'/'.$name;if(is_dir($f)&&!is_link($f))ig_remove_test($f);else unlink($f); }rmdir($path);
}
function ig_fixture(): array {
    $base=sys_get_temp_dir().'/smash-ig-'.bin2hex(random_bytes(8));mkdir($base,0700);$root=$base.'/site';$private=$base.'/private-smash';
    mkdir($root);mkdir($root.'/data');mkdir($root.'/assets');mkdir($root.'/assets/instagram');mkdir($private,0700);
    $c=['enabled'=>true,'account_id'=>IG_FAKE_ID,'access_token'=>IG_FAKE_TOKEN,'issued_at'=>gmdate('Y-m-d\TH:i:s\Z',IG_FAKE_NOW-3600)];
    ig_save_test_config($private,$c);return [$base,$root,$private,$c];
}
function ig_save_test_config(string $private,array $c): void {file_put_contents($private.'/instagram.local.php','<?php return '.var_export($c,true).';');chmod($private.'/instagram.local.php',0600);}
function ig_pixels(): string {
    $image=imagecreatetruecolor(1600,1200);imagefill($image,0,0,imagecolorallocate($image,73,166,233));ob_start();imagepng($image);$bytes=ob_get_clean();if(PHP_VERSION_ID<80000)imagedestroy($image);return $bytes;
}
function ig_post(string $id='123',string $type='IMAGE'): array {return ['id'=>$id,'media_type'=>$type,'caption'=>"Comunidad 📸\nUn torneo más para Guate",'permalink'=>'https://www.instagram.com/p/TEST_'.$id.'/','timestamp'=>'2026-10-20T12:30:00+0000','media_url'=>'https://scontent.cdninstagram.com/image-'.$id.'.jpg?expires=FAKE_ONLY','thumbnail_url'=>'https://scontent.fbcdn.net/thumb-'.$id.'.jpg'];}
function ig_wire(array &$seen,array $posts=[],?callable $special=null): callable {
    $png=ig_pixels();
    return static function($url,$headers,$limit)use(&$seen,$posts,$special,$png){
        $seen[]=[$url,$headers,$limit];if($special){$r=$special($url,$headers,$limit);if($r!==null)return $r;}
        $p=parse_url($url);$path=$p['path'];
        if($p['host']==='graph.instagram.com') {
            if($path==='/v25.0/me')$d=['user_id'=>IG_FAKE_ID];
            elseif($path==='/refresh_access_token')$d=['access_token'=>IG_FAKE_NEW,'expires_in'=>60*86400];
            elseif($path==='/v25.0/me/media')$d=['data'=>$posts];
            elseif(substr($path,-9)==='/children')$d=['data'=>[['media_type'=>'IMAGE','media_url'=>'https://scontent.cdninstagram.com/first-child.jpg']]];
            else throw new RuntimeException('Unexpected test route');
            return ['status'=>200,'body'=>json_encode($d,JSON_UNESCAPED_UNICODE),'location'=>null];
        }
        check_ig(count($headers)===1 && stripos($headers[0],'Authorization')===false,'no credential to CDN');
        return ['status'=>200,'body'=>$png,'location'=>null];
    };
}
function ig_no_public_secret(string $root,array $report): void {
    $b=ig_json($report);foreach(new RecursiveIteratorIterator(new RecursiveDirectoryIterator($root,FilesystemIterator::SKIP_DOTS)) as $file)if($file->isFile())$b.=file_get_contents($file->getPathname());
    check_ig(strpos($b,IG_FAKE_TOKEN)===false && strpos($b,IG_FAKE_NEW)===false,'credential never public');
    check_ig(strpos($b,'cdninstagram.com')===false && strpos($b,'fbcdn.net')===false,'no expiring URLs public');
}
$tests=[];
$tests['images_video_carousel_optimized'] = static function($root,$private,$c){
    $seen=[];$posts=[ig_post('123'),ig_post('124','VIDEO'),ig_post('125','CAROUSEL_ALBUM')];$r=ig_run($root,IG_FAKE_NOW,ig_wire($seen,$posts));check_ig($r['ok'] && $r['posts']===3,'published three');
    $p=json_decode(file_get_contents($root.'/data/instagram.json'),true);ig_validate_public($p);
    foreach($p['posts'] as $post){check_ig($post['image']['width']<=1080 && $post['image']['thumbnailWidth']<=360,'dimensions');$info=getimagesize($root.'/'.$post['image']['src']);check_ig($info[0]===$post['image']['width'],'real encoded dimensions');}
    $urls=array_column($seen,0);check_ig(count(array_filter($urls,static fn($u)=>strpos($u,'thumb-124.jpg')!==false))===1,'video uses thumbnail');check_ig(count(array_filter($urls,static fn($u)=>strpos($u,'image-124.jpg')!==false))===0,'no video bytes');
    check_ig(count(array_filter($urls,static fn($u)=>strpos($u,'125/children')!==false))===1,'first carousel child');check_ig($p['posts'][0]['timestamp']==='2026-10-20T12:30:00Z','Meta offset normalized');ig_no_public_secret($root,$r);
};
$tests['image_failure_keeps_gallery_and_previous_picture']=static function($root,$private,$c){
    $seen=[];ig_run($root,IG_FAKE_NOW,ig_wire($seen,[ig_post('123')]));$old=json_decode(file_get_contents($root.'/data/instagram.json'),true)['posts'][0]['image'];
    $seen=[];$bad=static function($url){if(strpos($url,'graph.instagram.com')===false)return ['status'=>404,'body'=>'','location'=>null];return null;};
    $r=ig_run($root,IG_FAKE_NOW+1,ig_wire($seen,[ig_post('123'),ig_post('124')],$bad));check_ig($r['ok'] && $r['posts']===2 && $r['missingImages']===1,'one failed image remains usable');
    $p=json_decode(file_get_contents($root.'/data/instagram.json'),true);$by=array_column($p['posts'],null,'id');check_ig($by[123]['image']===$old && $by[124]['image']===null,'old image or text fallback');ig_no_public_secret($root,$r);
};
$tests['api_failure_preserves_last_good_and_sanitizes']=static function($root,$private,$c){
    $seen=[];ig_run($root,IG_FAKE_NOW,ig_wire($seen,[ig_post()]));$before=file_get_contents($root.'/data/instagram.json');
    $seen=[];$bad=static function($u){if(strpos($u,'/me/media')!==false)throw new SmashInstagramError(IG_FAKE_TOKEN);return null;};
    $r=ig_run($root,IG_FAKE_NOW+1,ig_wire($seen,[],$bad));check_ig(!$r['ok'] && $r['code']==='instagram_capture_failed','safe error enum');check_ig(file_get_contents($root.'/data/instagram.json')===$before,'last good unchanged');ig_no_public_secret($root,$r);
};
$tests['refresh_persisted_and_reused_after_media_failure']=static function($root,$private,$c){
    $c['issued_at']=gmdate('Y-m-d\TH:i:s\Z',IG_FAKE_NOW-8*86400);ig_save_test_config($private,$c);$seen=[];
    $bad=static function($u){if(strpos($u,'/me/media')!==false)return ['status'=>500,'body'=>'{}','location'=>null];return null;};
    $r=ig_run($root,IG_FAKE_NOW,ig_wire($seen,[],$bad));check_ig(!$r['ok'],'capture error');$state=json_decode(file_get_contents($private.'/instagram-token.json'),true);check_ig($state['accessToken']===IG_FAKE_NEW && $state['expiresAt']===IG_FAKE_NOW+60*86400,'new credential durable');check_ig((fileperms($private.'/instagram-token.json')&0077)===0,'private 600');
    $seen=[];$r=ig_run($root,IG_FAKE_NOW+7200,ig_wire($seen,[ig_post()]));check_ig($r['ok'],'next attempt');check_ig(strpos($seen[0][1][0],IG_FAKE_NEW)!==false,'uses renewed token');check_ig(count(array_filter(array_column($seen,0),static fn($u)=>strpos($u,'refresh_access_token')!==false))===0,'no unnecessary renewal');ig_no_public_secret($root,$r);
};
$tests['refresh_failure_and_expiry_red_without_replacing_feed']=static function($root,$private,$c){
    $seen=[];ig_run($root,IG_FAKE_NOW,ig_wire($seen,[ig_post()]));$before=file_get_contents($root.'/data/instagram.json');
    $seen=[];$bad=static function($u){if(strpos($u,'refresh_access_token')!==false)return ['status'=>400,'body'=>json_encode(['error'=>['message'=>IG_FAKE_TOKEN]]),'location'=>null];return null;};
    $r=ig_run($root,IG_FAKE_NOW+8*86400,ig_wire($seen,[],$bad));check_ig(!$r['ok'] && $r['code']==='instagram_refresh_failed','renewal failure');check_ig(file_get_contents($root.'/data/instagram.json')===$before,'feed retained');
    $r=ig_run($root,IG_FAKE_NOW+61*86400,ig_wire($seen));check_ig(!$r['ok'] && $r['code']==='instagram_token_expired','expired rejected');ig_no_public_secret($root,$r);
};
$tests['empty_disabled_and_wrong_account']=static function($root,$private,$c){
    $seen=[];$c['enabled']=false;ig_save_test_config($private,$c);$r=ig_run($root,IG_FAKE_NOW,ig_wire($seen));check_ig($r['status']==='not_configured' && !$seen && !is_file($root.'/data/instagram.json'),'disabled no source');
    $c['enabled']=true;ig_save_test_config($private,$c);$r=ig_run($root,IG_FAKE_NOW,ig_wire($seen));check_ig($r['ok'] && $r['posts']===0,'honest empty');
    $seen=[];$bad=static fn($u)=>strpos($u,'/me?')!==false?['status'=>200,'body'=>'{"user_id":"999999999"}','location'=>null]:null;
    $r=ig_run($root,IG_FAKE_NOW,ig_wire($seen,[],$bad));check_ig(!$r['ok'] && $r['code']==='instagram_account_mismatch','only configured owner');
};
$tests['secret_caption_and_hostile_url_never_publish']=static function($root,$private,$c){
    $seen=[];$p=ig_post();$p['caption']=IG_FAKE_TOKEN;$r=ig_run($root,IG_FAKE_NOW,ig_wire($seen,[$p]));check_ig(!$r['ok'] && !is_file($root.'/data/instagram.json'),'secret rejected');ig_no_public_secret($root,$r);
    foreach(['http://scontent.fbcdn.net/a','https://127.0.0.1/a','https://cdninstagram.com.evil.test/a','https://user@scontent.fbcdn.net/a','https://scontent.fbcdn.net:8443/a'] as $url){$rejected=false;try{ig_cdn($url);}catch(SmashInstagramError $e){$rejected=true;}check_ig($rejected,'CDN allowlist');}
    $bad=ig_post();$bad['permalink']='https://evil.test/p/a';$r=ig_run($root,IG_FAKE_NOW,ig_wire($seen,[$bad]));check_ig(!$r['ok'],'permalink allowlist');
    $bad['permalink']='https://user@www.instagram.com/p/a';$r=ig_run($root,IG_FAKE_NOW,ig_wire($seen,[$bad]));check_ig(!$r['ok'],'permalink userinfo');
};
$tests['caption_optional_fallback_and_removed_posts']=static function($root,$private,$c){
    $seen=[];$special=static function($u){if(strpos($u,'/me/media')!==false && strpos($u,'caption')!==false)return ['status'=>400,'body'=>'{"error":{"code":100,"message":"Unknown field caption"}}','location'=>null];return null;};
    $p=ig_post();unset($p['caption']);$r=ig_run($root,IG_FAKE_NOW,ig_wire($seen,[$p],$special));check_ig($r['ok'],'caption support optional');$feed=json_decode(file_get_contents($root.'/data/instagram.json'),true);check_ig($feed['posts'][0]['caption']==='','no invented caption');
    $seen=[];ig_run($root,IG_FAKE_NOW+1,ig_wire($seen,[]));$feed=json_decode(file_get_contents($root.'/data/instagram.json'),true);check_ig($feed['posts']===[],'deleted posts leave snapshot');
};
$tests['malformed_image_and_unsafe_redirect_are_text_cards']=static function($root,$private,$c){
    foreach(['bytes','redirect'] as $kind){$seen=[];$special=static function($u)use($kind){if(strpos($u,'graph.instagram.com')===false)return $kind==='bytes'?['status'=>200,'body'=>'<svg onload=alert(1)>','location'=>null]:['status'=>302,'body'=>'','location'=>'http://127.0.0.1/private'];return null;};
        $r=ig_run($root,IG_FAKE_NOW,ig_wire($seen,[ig_post()],$special));check_ig($r['ok'] && $r['missingImages']===1,'bad picture harmless');$feed=json_decode(file_get_contents($root.'/data/instagram.json'),true);check_ig($feed['posts'][0]['image']===null,'no unsafe picture');}
};
$tests['lock_and_private_config_guards']=static function($root,$private,$c){
    $seen=[];$h=fopen($private.'/instagram.lock','c');flock($h,LOCK_EX);$r=ig_run($root,IG_FAKE_NOW,ig_wire($seen));check_ig($r['status']==='busy' && !$seen,'no overlapping capture');flock($h,LOCK_UN);fclose($h);
    chmod($private.'/instagram.local.php',0644);clearstatcache();$r=ig_run($root,IG_FAKE_NOW,ig_wire($seen));check_ig(!$r['ok'] && $r['code']==='instagram_config_invalid','private file permission');
};
$tests['rolling_twelve_sorted_and_old_assets_grace_period']=static function($root,$private,$c){
    $posts=[];for($i=1;$i<=15;$i++){$r=ig_post((string)$i);$r['timestamp']='2026-10-'.str_pad((string)$i,2,'0',STR_PAD_LEFT).'T12:00:00Z';$posts[]=$r;}
    $orphan=$root.'/assets/instagram/'.str_repeat('a',64).'-full.jpg';file_put_contents($orphan,'old');touch($orphan,IG_FAKE_NOW-8*86400);
    $seen=[];$r=ig_run($root,IG_FAKE_NOW,ig_wire($seen,$posts));check_ig($r['ok'] && $r['posts']===12,'bounded twelve');$feed=json_decode(file_get_contents($root.'/data/instagram.json'),true);check_ig($feed['posts'][0]['id']==='15' && $feed['posts'][11]['id']==='4','sorted latest');check_ig(!file_exists($orphan),'old unreferenced asset GC');
};
try {
    check_ig(extension_loaded('gd'),'GD required for real optimization tests');
    foreach($tests as $name=>$test){[$base,$root,$private,$c]=ig_fixture();try{$test($root,$private,$c);}finally{ig_remove_test($base);}}
    echo json_encode(['ok'=>true,'tests'=>count($tests),'fixturesOnly'=>true])."\n";
}catch(Throwable $error){fwrite(STDERR,'Instagram fixture assertion failed: '.($error instanceof SmashInstagramError?$error->reason:$error->getMessage())."\n");exit(1);}
