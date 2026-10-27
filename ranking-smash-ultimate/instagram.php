<?php
declare(strict_types=1);
// CLI library only. No account/database dependency and no I/O on inclusion.
if(PHP_SAPI!=='cli'){http_response_code(403);exit;}
final class SmashInstagramError extends RuntimeException {
    public $reason;
    public function __construct(string $reason) { $this->reason=$reason; parent::__construct($reason); }
}
const IG_API_VERSION = 'v25.0';
const IG_POST_LIMIT = 12;
const IG_JSON_MAX = 524288;
const IG_IMAGE_MAX = 12582912;
function ig_require(bool $ok, string $reason='instagram_source_invalid'): void { if(!$ok)throw new SmashInstagramError($reason); }
function ig_time(string $value): int {
    ig_require(preg_match('/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?(?:Z|[+-]\d\d:?\d\d)$/D',$value)===1);
    $d=new DateTimeImmutable($value);$errors=DateTimeImmutable::getLastErrors();
    ig_require($errors===false || (!$errors['warning_count'] && !$errors['error_count']));return $d->getTimestamp();
}
function ig_token($value): string {
    ig_require(is_string($value) && preg_match('/^[\x21-\x7e]{20,4096}$/D',$value)===1,'instagram_config_invalid');return $value;
}
function ig_json(array $value): string { return json_encode($value,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES|JSON_THROW_ON_ERROR)."\n"; }
function ig_atomic(string $path,string $body,int $mode): void {
    ig_require(!is_link($path),'instagram_storage_unavailable');$tmp=$path.'.'.bin2hex(random_bytes(12)).'.tmp';
    try {
        ig_require(file_put_contents($tmp,$body,LOCK_EX)===strlen($body) && chmod($tmp,$mode) && rename($tmp,$path),'instagram_storage_unavailable');
    } finally {if(is_file($tmp))unlink($tmp);}
}
function ig_private(string $root): string {
    $dir=dirname($root).'/private-smash';
    ig_require(is_dir($dir) && realpath($dir)===$dir && is_writable($dir),'instagram_not_configured');return $dir;
}
function ig_config(string $private,int $now): ?array {
    $file=$private.'/instagram.local.php';if(!is_file($file))return null;
    ig_require(!is_link($file) && filesize($file)<=16384 && (fileperms($file)&0077)===0,'instagram_config_invalid');
    $level=ob_get_level();ob_start();try {$c=(static function($p){return require $p;})($file);} finally {while(ob_get_level()>$level)ob_end_clean();}
    ig_require(is_array($c),'instagram_config_invalid');if(($c['enabled'] ?? false)!==true)return null;
    ig_require(is_string($c['account_id'] ?? null) && preg_match('/^[1-9][0-9]{4,30}$/D',$c['account_id'])===1,'instagram_config_invalid');
    $c['access_token']=ig_token($c['access_token'] ?? null);
    ig_require(is_string($c['issued_at'] ?? null),'instagram_config_invalid');$c['issued']=ig_time($c['issued_at']);
    ig_require($c['issued']<=$now+300 && $c['issued']>0,'instagram_config_invalid');return $c;
}
function ig_http(string $url,array $headers,int $limit): array {
    ig_require(function_exists('curl_init'),'instagram_curl_required');$body='';$location=null;$size=0;
    $ch=curl_init($url);ig_require($ch!==false,'instagram_network_failed');
    try {
        $options=[CURLOPT_FOLLOWLOCATION=>false,CURLOPT_CONNECTTIMEOUT=>5,CURLOPT_TIMEOUT=>15,
            CURLOPT_SSL_VERIFYPEER=>true,CURLOPT_SSL_VERIFYHOST=>2,CURLOPT_HTTPHEADER=>$headers,
            CURLOPT_USERAGENT=>'SmashGT-InstagramSync/1.0',CURLOPT_VERBOSE=>false,
            CURLOPT_WRITEFUNCTION=>static function($curl,$chunk)use(&$body,$limit){if(strlen($body)+strlen($chunk)>$limit)return 0;$body.=$chunk;return strlen($chunk);},
            CURLOPT_HEADERFUNCTION=>static function($curl,$line)use(&$location,&$size){$size+=strlen($line);if($size>32768)return 0;if(stripos($line,'Location:')===0)$location=trim(substr($line,9));return strlen($line);}];
        if(defined('CURLOPT_PROTOCOLS_STR'))$options[constant('CURLOPT_PROTOCOLS_STR')]='https';else $options[CURLOPT_PROTOCOLS]=CURLPROTO_HTTPS;
        curl_setopt_array($ch,$options);$ok=curl_exec($ch);ig_require($ok!==false,'instagram_network_failed');
        return ['status'=>(int)curl_getinfo($ch,CURLINFO_HTTP_CODE),'body'=>$body,'location'=>$location];
    } finally {if(PHP_VERSION_ID<80000)curl_close($ch);unset($ch);}
}
function ig_api(string $path,array $params,string $token,callable $request): array {
    ig_require(preg_match('~^(?:me(?:/media)?|[0-9]+/children)$~D',$path)===1);
    $url='https://graph.instagram.com/'.IG_API_VERSION.'/'.$path.'?'.http_build_query($params,'','&',PHP_QUERY_RFC3986);
    $r=$request($url,['Authorization: Bearer '.$token,'Accept: application/json'],IG_JSON_MAX);
    $d=json_decode($r['body'],true,64,JSON_THROW_ON_ERROR);
    if(isset($d['error'])) {
        $e=$d['error'];$msg=$e['message'] ?? '';
        if(($e['code'] ?? null)===100 && is_string($msg) && stripos($msg,'caption')!==false)throw new SmashInstagramError('instagram_caption_unsupported');
        throw new SmashInstagramError('instagram_api_unavailable');
    }
    ig_require($r['status']===200 && is_array($d),'instagram_api_unavailable');return $d;
}
function ig_credentials(string $private,array $config,int $now,callable $request): array {
    $seed=hash('sha256',$config['access_token']);$path=$private.'/instagram-token.json';
    $state=['schemaVersion'=>1,'accountId'=>$config['account_id'],'seedHash'=>$seed,'accessToken'=>$config['access_token'],'issuedAt'=>$config['issued'],'expiresAt'=>$config['issued']+60*86400];
    if(is_file($path)) {
        ig_require(!is_link($path) && filesize($path)<=16384 && (fileperms($path)&0077)===0,'instagram_storage_unavailable');
        $old=json_decode(file_get_contents($path),true,32,JSON_THROW_ON_ERROR);
        ig_require(is_array($old) && ($old['schemaVersion'] ?? null)===1,'instagram_token_state_invalid');
        if(($old['seedHash'] ?? null)===$seed && ($old['accountId'] ?? null)===$config['account_id'])$state=$old;
    }
    $token=ig_token($state['accessToken']);
    ig_require(is_int($state['issuedAt']) && is_int($state['expiresAt']) && $state['issuedAt']<=$now+300 && $state['expiresAt']>$state['issuedAt'],'instagram_token_state_invalid');
    ig_require($state['expiresAt']>$now,'instagram_token_expired');
    $identity=ig_api('me',['fields'=>'user_id'],$token,$request);
    ig_require((string)($identity['user_id'] ?? '')===$config['account_id'],'instagram_account_mismatch');
    // Renew weekly, with a full week of safety, never before Meta's minimum age of 24h.
    if($now-$state['issuedAt']>=7*86400 || $state['expiresAt']-$now<=7*86400) {
        ig_require($now-$state['issuedAt']>=86400,'instagram_token_too_young');
        $url='https://graph.instagram.com/refresh_access_token?'.http_build_query(['grant_type'=>'ig_refresh_token','access_token'=>$token],'','&',PHP_QUERY_RFC3986);
        $r=$request($url,['Accept: application/json'],IG_JSON_MAX);$d=json_decode($r['body'],true,32,JSON_THROW_ON_ERROR);
        ig_require($r['status']===200 && !isset($d['error']) && is_int($d['expires_in'] ?? null) && $d['expires_in']>=86400 && $d['expires_in']<=60*86400,'instagram_refresh_failed');
        $state['accessToken']=ig_token($d['access_token'] ?? null);$state['issuedAt']=$now;$state['expiresAt']=$now+$d['expires_in'];
    }
    // Persist a refreshed credential BEFORE fetching media; an unrelated CDN failure must not lose it.
    ig_atomic($path,ig_json($state),0600);return $state+['_priorToken'=>$token];
}
function ig_media(string $token,callable $request): array {
    $rows=[];$after=null;$caption=true;
    for($page=0;$page<3;$page++) {
        $fields='id,media_type,permalink,media_url,thumbnail_url,timestamp'.($caption?',caption':'');
        $params=['fields'=>$fields,'limit'=>12];if($after!==null)$params['after']=$after;
        try {$d=ig_api('me/media',$params,$token,$request);} catch(SmashInstagramError $e) {
            if($e->reason!=='instagram_caption_unsupported' || !$caption)throw $e;
            unset($params['fields']);$caption=false;$params['fields']='id,media_type,permalink,media_url,thumbnail_url,timestamp';$d=ig_api('me/media',$params,$token,$request);
        }
        ig_require(isset($d['data']) && is_array($d['data']) && count($d['data'])<=50);
        foreach($d['data'] as $row) {
            ig_require(is_array($row) && is_string($row['id'] ?? null) && preg_match('/^[1-9][0-9]{0,39}$/D',$row['id'])===1 && !isset($rows[$row['id']]));$rows[$row['id']]=$row;
        }
        if(count($rows)>=12 || empty($d['paging']['next']))break;
        $after=$d['paging']['cursors']['after'] ?? null;ig_require(is_string($after) && strlen($after)>0 && strlen($after)<=2048);
        if($page===2)throw new SmashInstagramError('instagram_pagination_incomplete');
    }
    $rows=array_values($rows);
    foreach($rows as $row)ig_require(is_string($row['timestamp'] ?? null));
    usort($rows,static fn($a,$b)=>ig_time($b['timestamp'])<=>ig_time($a['timestamp']) ?: strcmp($b['id'],$a['id']));return array_slice($rows,0,12);
}
function ig_permalink($url): string {
    ig_require(is_string($url));$u=parse_url($url);
    ig_require(is_array($u) && ($u['scheme'] ?? '')==='https' && in_array($u['host'] ?? '',['www.instagram.com','instagram.com'],true) && !isset($u['user']) && !isset($u['pass']) && !isset($u['port']) && !isset($u['fragment']) && !isset($u['query']) && preg_match('~^/(?:p|reel|tv)/[A-Za-z0-9_-]+/?$~D',$u['path'] ?? '')===1);
    return 'https://www.instagram.com/'.ltrim($u['path'],'/');
}
function ig_cdn($url): string {
    ig_require(is_string($url) && strlen($url)<=8192,'instagram_image_unavailable');$u=parse_url($url);
    ig_require(is_array($u) && ($u['scheme'] ?? '')==='https' && !isset($u['user']) && !isset($u['pass']) && !isset($u['fragment']) && (!isset($u['port']) || $u['port']===443) && preg_match('/(?:^|\.)(?:cdninstagram\.com|fbcdn\.net)$/Di',$u['host'] ?? '')===1,'instagram_image_unavailable');return $url;
}
function ig_image_bytes(string $url,callable $request): string {
    for($i=0;$i<3;$i++) {
        $r=$request(ig_cdn($url),['Accept: image/jpeg,image/png,image/webp'],IG_IMAGE_MAX);
        if($r['status']===200) {ig_require(is_string($r['body']) && strlen($r['body'])<=IG_IMAGE_MAX,'instagram_image_unavailable');return $r['body'];}
        ig_require(in_array($r['status'],[301,302,303,307,308],true) && is_string($r['location'] ?? null),'instagram_image_unavailable');$url=$r['location'];
    }
    throw new SmashInstagramError('instagram_image_unavailable');
}
function ig_managed_path($path): bool {return is_string($path) && preg_match('~^assets/instagram/[a-f0-9]{64}-(?:full|thumb)\.(?:webp|jpg)$~D',$path)===1;}
function ig_optimize(string $bytes,string $root,array $secrets): array {
    ig_require(extension_loaded('gd'),'instagram_gd_required');$info=@getimagesizefromstring($bytes);
    ig_require(is_array($info) && in_array($info[2],[IMAGETYPE_JPEG,IMAGETYPE_PNG,IMAGETYPE_WEBP],true) && $info[0]>0 && $info[1]>0 && $info[0]*$info[1]<=12000000,'instagram_image_unavailable');
    $source=@imagecreatefromstring($bytes);ig_require($source!==false,'instagram_image_unavailable');$result=[];
    try {
        foreach(['full'=>1080,'thumb'=>360] as $kind=>$max) {
            $ratio=min(1,$max/max($info[0],$info[1]));$w=max(1,(int)round($info[0]*$ratio));$h=max(1,(int)round($info[1]*$ratio));
            $image=imagecreatetruecolor($w,$h);ig_require($image!==false,'instagram_image_unavailable');
            try {
                imagefill($image,0,0,imagecolorallocate($image,255,255,255));imagecopyresampled($image,$source,0,0,0,0,$w,$h,$info[0],$info[1]);
                ob_start();try {if(function_exists('imagewebp')){$ok=imagewebp($image,null,82);$ext='webp';}else{$ok=imagejpeg($image,null,85);$ext='jpg';}$out=ob_get_contents();}finally{ob_end_clean();}
                ig_require($ok && is_string($out) && strlen($out)<=3145728,'instagram_image_unavailable');
                foreach($secrets as $secret)ig_require(strpos($out,$secret)===false,'instagram_secret_in_content');
                $path='assets/instagram/'.hash('sha256',$out).'-'.$kind.'.'.$ext;
                if(!is_file($root.'/'.$path))ig_atomic($root.'/'.$path,$out,0644);
                else ig_require(!is_link($root.'/'.$path) && hash_file('sha256',$root.'/'.$path)===hash('sha256',$out),'instagram_storage_unavailable');
                $result[$kind]=['src'=>$path,'width'=>$w,'height'=>$h];
            }finally{if(PHP_VERSION_ID<80000)imagedestroy($image);unset($image);}
        }
    }finally{if(PHP_VERSION_ID<80000)imagedestroy($source);unset($source);}
    return ['src'=>$result['full']['src'],'thumbnail'=>$result['thumb']['src'],'width'=>$result['full']['width'],'height'=>$result['full']['height'],'thumbnailWidth'=>$result['thumb']['width'],'thumbnailHeight'=>$result['thumb']['height']];
}
function ig_validate_public(array $feed): void {
    ig_require(array_keys($feed)===['schemaVersion','generatedAt','posts'] && $feed['schemaVersion']===1 && is_string($feed['generatedAt']) && is_array($feed['posts']) && count($feed['posts'])<=12);
    ig_time($feed['generatedAt']);$ids=[];
    foreach($feed['posts'] as $p) {
        ig_require(array_keys($p)===['id','type','caption','permalink','timestamp','image'] && is_string($p['id']) && preg_match('/^[1-9][0-9]{0,39}$/D',$p['id'])===1 && !isset($ids[$p['id']]));$ids[$p['id']]=true;
        ig_require(in_array($p['type'],['IMAGE','VIDEO','CAROUSEL_ALBUM'],true) && is_string($p['caption']) && mb_check_encoding($p['caption'],'UTF-8') && mb_strlen($p['caption'],'UTF-8')<=2200);ig_permalink($p['permalink']);ig_time($p['timestamp']);
        if($p['image']!==null) {
            ig_require(is_array($p['image']) && array_keys($p['image'])===['src','thumbnail','width','height','thumbnailWidth','thumbnailHeight'] && ig_managed_path($p['image']['src'] ?? null) && ig_managed_path($p['image']['thumbnail'] ?? null));
            foreach(['width','height','thumbnailWidth','thumbnailHeight'] as $k)ig_require(is_int($p['image'][$k] ?? null) && $p['image'][$k]>0 && $p['image'][$k]<=($k==='width'||$k==='height'?1080:360));
        }
    }
}
function ig_previous(string $root): array {
    $file=$root.'/data/instagram.json';if(!is_file($file))return [];
    ig_require(!is_link($file) && filesize($file)<=131072,'instagram_storage_unavailable');
    $p=json_decode(file_get_contents($file),true,64,JSON_THROW_ON_ERROR);ig_validate_public($p);return array_column($p['posts'],null,'id');
}
function ig_gc(string $root,array $feed,int $now): void {
    $keep=[];foreach($feed['posts'] as $p)if($p['image'])foreach(['src','thumbnail'] as $k)$keep[$p['image'][$k]]=true;
    foreach(glob($root.'/assets/instagram/*') ?: [] as $file) {
        $path='assets/instagram/'.basename($file);
        if(ig_managed_path($path) && !isset($keep[$path]) && !is_link($file) && is_file($file) && filemtime($file)<$now-7*86400)@unlink($file);
    }
}
function ig_sync(string $root,int $now,?callable $transport=null): array {
    $root=realpath($root);ig_require(is_string($root),'instagram_storage_unavailable');$private=ig_private($root);
    foreach(['data','assets','assets/instagram'] as $dir)ig_require(is_dir($root.'/'.$dir) && realpath($root.'/'.$dir)===$root.'/'.$dir && is_writable($root.'/'.$dir),'instagram_storage_unavailable');
    $lock=$private.'/instagram.lock';ig_require(!is_link($lock),'instagram_storage_unavailable');$handle=fopen($lock,'c');ig_require($handle!==false,'instagram_storage_unavailable');chmod($lock,0600);
    if(!flock($handle,LOCK_EX|LOCK_NB)){fclose($handle);return ['ok'=>true,'status'=>'busy'];}
    try {
        $config=ig_config($private,$now);if($config===null)return ['ok'=>true,'status'=>'not_configured'];
        ig_require(extension_loaded('gd') && function_exists('mb_check_encoding'),'instagram_gd_required');
        $start=microtime(true);$calls=0;$wire=$transport ?? 'ig_http';
        $request=static function($url,$headers,$limit)use($start,&$calls,$wire){ig_require(++$calls<=70 && microtime(true)-$start<240,'instagram_capture_budget');return $wire($url,$headers,$limit);};
        $state=ig_credentials($private,$config,$now,$request);$token=$state['accessToken'];$secrets=array_unique([$token,$config['access_token'],$state['_priorToken']]);$old=ig_previous($root);$posts=[];$missing=0;
        foreach(ig_media($token,$request) as $r) {
            $type=$r['media_type'] ?? '';ig_require(in_array($type,['IMAGE','VIDEO','CAROUSEL_ALBUM'],true));
            $caption=$r['caption'] ?? '';ig_require(is_string($caption) && mb_check_encoding($caption,'UTF-8'));$caption=mb_substr($caption,0,2200,'UTF-8');
            $p=['id'=>$r['id'],'type'=>$type,'caption'=>$caption,'permalink'=>ig_permalink($r['permalink'] ?? null),'timestamp'=>gmdate('Y-m-d\TH:i:s\Z',ig_time($r['timestamp'])),'image'=>null];
            $media=$r;
            if($type==='CAROUSEL_ALBUM') {
                $child=ig_api($r['id'].'/children',['fields'=>'media_type,media_url,thumbnail_url','limit'=>1],$token,$request);
                ig_require(is_array($child['data'] ?? null));$media=$child['data'][0] ?? [];
            }
            $url=($media['media_type'] ?? null)==='VIDEO'?($media['thumbnail_url'] ?? null):($media['media_url'] ?? null);
            try {ig_require(is_string($url),'instagram_image_unavailable');$p['image']=ig_optimize(ig_image_bytes($url,$request),$root,$secrets);}
            catch(Throwable $error) {
                if($error instanceof SmashInstagramError && in_array($error->reason,['instagram_storage_unavailable','instagram_secret_in_content','instagram_capture_budget','instagram_gd_required','instagram_runtime_error'],true))throw $error;
                $prior=$old[$r['id']]['image'] ?? null;
                if($prior!==null && is_file($root.'/'.$prior['src']) && !is_link($root.'/'.$prior['src']) && is_file($root.'/'.$prior['thumbnail']) && !is_link($root.'/'.$prior['thumbnail']))$p['image']=$prior;
                else $missing++;
            }
            $posts[]=$p;
        }
        $feed=['schemaVersion'=>1,'generatedAt'=>gmdate('Y-m-d\TH:i:s\Z',$now),'posts'=>$posts];ig_validate_public($feed);$json=ig_json($feed);ig_require(strlen($json)<=131072);
        foreach($secrets as $secret)ig_require(strpos($json,$secret)===false,'instagram_secret_in_content');
        ig_atomic($root.'/data/instagram.json',$json,0644);ig_gc($root,$feed,$now);
        return ['ok'=>true,'status'=>'ready','posts'=>count($posts),'missingImages'=>$missing,'requests'=>$calls];
    }finally{flock($handle,LOCK_UN);fclose($handle);}
}
function ig_safe_reason(Throwable $error): string {
    $allowed=['instagram_not_configured','instagram_config_invalid','instagram_storage_unavailable','instagram_token_state_invalid','instagram_token_expired','instagram_token_too_young','instagram_account_mismatch','instagram_api_unavailable','instagram_caption_unsupported','instagram_refresh_failed','instagram_pagination_incomplete','instagram_network_failed','instagram_capture_budget','instagram_source_invalid','instagram_secret_in_content','instagram_gd_required','instagram_curl_required','instagram_runtime_error'];
    return $error instanceof SmashInstagramError && in_array($error->reason,$allowed,true)?$error->reason:'instagram_capture_failed';
}
function ig_run(string $root,int $now,?callable $transport=null): array {
    try {$result=ig_sync($root,$now,$transport);}catch(Throwable $error){$result=['ok'=>false,'status'=>'failed','code'=>ig_safe_reason($error)];}
    // Never replace the feed on error. Public health contains only our bounded codes, no source responses.
    if(($result['status'] ?? '')!=='busy') {
        $health=['schemaVersion'=>1,'checkedAt'=>gmdate('Y-m-d\TH:i:s\Z',$now),'ok'=>$result['ok'],'status'=>$result['status'],'code'=>$result['code'] ?? null];
        try {ig_atomic($root.'/data/instagram-status.json',ig_json($health),0644);}catch(Throwable $error){return ['ok'=>false,'status'=>'failed','code'=>'instagram_status_unavailable'];}
    }
    return $result;
}
