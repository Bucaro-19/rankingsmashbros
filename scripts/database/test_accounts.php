<?php
declare(strict_types=1);
require_once __DIR__ . '/../../ranking-smash-ultimate/database.php';
require_once __DIR__ . '/../../ranking-smash-ultimate/accounts.php';
function check_account($condition, string $description): void {
    if (!$condition) throw new RuntimeException($description);
}
function account_rejects(callable $operation, string $reason): void {
    try { $operation(); } catch (SmashAccountError $error) { check_account($error->reason === $reason, 'Unexpected rejection'); return; }
    throw new RuntimeException('Expected rejection: ' . $reason);
}
$config = ['client_id' => 'fixture-id', 'client_secret' => 'fixture-secret-only'];
$session = [];
$url = smash_account_authorize($session, $config, 1000);
parse_str(parse_url($url, PHP_URL_QUERY), $query);
check_account($query['scope'] === 'user.identity' && !isset($query['client_secret']), 'Authorization must not expose a secret or ask for email/reporting');
check_account($query['redirect_uri'] === SMASH_ACCOUNT_CALLBACK && strlen($query['state']) === 64, 'Fixed redirect and random state');
smash_account_consume_state($session, $query['state'], 1001);
account_rejects(function () use (&$session, $query) { smash_account_consume_state($session, $query['state'], 1002); }, 'oauth_state_invalid');
foreach ([['wrong',1001],['same',1601],['same',999]] as $case) {
    $s = ['smash_oauth_pending' => ['state'=>'same','at'=>1000]];
    account_rejects(function () use (&$s, $case) { smash_account_consume_state($s, $case[0], $case[1]); }, 'oauth_state_invalid');
    check_account(!isset($s['smash_oauth_pending']), 'Invalid/cancelled callbacks consume the attempt');
}
check_account(smash_account_csrf_valid(['smash_account_csrf'=>'a'], 'a') && !smash_account_csrf_valid(['smash_account_csrf'=>'a'], ['a']), 'CSRF types');
check_account(!smash_account_session_valid(['smash_account'=>['id'=>'1','at'=>1000]], 1000+28800), 'Absolute session expiry');
check_account(!smash_account_session_valid(['smash_account'=>['id'=>'1','at'=>1001]], 1000), 'Future sessions');
$calls = 0;
$identity = smash_account_exchange($config, 'fixture-code', function ($endpoint, $body, $token) use (&$calls) {
    $calls++;
    if ($calls === 1) {
        check_account($endpoint === 'https://api.start.gg/oauth/access_token' && $body['scope'] === 'user.identity' && $token === null, 'Token exchange');
        return ['access_token'=>'fixture-token-only','token_type'=>'Bearer','refresh_token'=>'fixture-refresh-only'];
    }
    check_account($endpoint === 'https://api.start.gg/gql/alpha' && $token === 'fixture-token-only' && strpos($body['query'],'currentUser') !== false, 'Identity fetched from provider');
    return ['data'=>['currentUser'=>['id'=>'8999001','slug'=>'user/fixture','player'=>['id'=>'8999002','gamerTag'=>'Jugador QA'],'images'=>[['url'=>'https://images.start.gg/fixture.png']]]]];
});
check_account($calls === 2 && $identity['playerId'] === '8999002' && !isset($identity['access_token']), 'Tokens discarded after verified identity');
account_rejects(function () { smash_account_identity(['id'=>'2','player'=>['id'=>'3','gamerTag'=>'']]); }, 'identity_invalid');
account_rejects(function () use ($config) { smash_account_exchange($config, 'code', static fn() => ['access_token'=>'bad token','token_type'=>'Bearer']); }, 'provider_invalid');
check_account(smash_account_external_id('18446744073709551616') === null && smash_account_external_id('1e3') === null, 'IDs fit the SQL type');
check_account(smash_account_safe_image('https://images.start.gg.evil.test/x') === null && smash_account_safe_image('javascript:alert(1)') === null, 'Avatar allowlist');
check_account(smash_account_identity(['id'=>'1','slug'=>'//evil.test','player'=>null])['url'] === null, 'No open profile redirects');
$root = sys_get_temp_dir() . '/smash-oauth-config-' . bin2hex(random_bytes(6));
mkdir($root); mkdir($root.'/site'); mkdir($root.'/private-smash');
try {
    check_account(smash_account_oauth_config($root.'/site') === null, 'Missing config disables login');
    file_put_contents($root.'/private-smash/oauth.local.php', '<?php echo "DO_NOT_PRINT"; return ["enabled"=>false];');
    ob_start(); $missing=smash_account_oauth_config($root.'/site'); $output=ob_get_clean();
    check_account($missing === null && $output === '', 'Private config output suppressed');
    file_put_contents($root.'/private-smash/oauth.local.php', '<?php return '.var_export(['enabled'=>true,'client_id'=>'CLIENT_ID_AQUI','client_secret'=>'valid-fixture-secret','redirect_uri'=>SMASH_ACCOUNT_CALLBACK], true).';');
    account_rejects(static fn() => smash_account_oauth_config($root.'/site'), 'config_invalid');
} finally { unlink($root.'/private-smash/oauth.local.php'); rmdir($root.'/site'); rmdir($root.'/private-smash'); rmdir($root); }
$public=smash_account_public(__DIR__.'/../../ranking-smash-ultimate');
foreach ($public['players'] as $player) {
    $profile=smash_account_profile($public,$player['id']);
    foreach (['combined'=>$public,'guatemala'=>$public['localRanking']] as $scope=>$view) {
        $original=null; foreach ($view['players'] as $candidate) if ($candidate['id']===$player['id']) $original=$candidate;
        if (!$original) continue;
        $v=$profile['views'][$scope];
        check_account($v['rank']===$original['rank'] && $v['points']===$original['rating'], 'Exact ranking parity');
        check_account(array_sum(array_column($v['events'],'wins')) >= $v['wins'], 'Available attendance cannot undercount included wins');
        $included=array_filter($v['events'],static fn($e)=>$e['counts']);
        check_account(count($included)===$original['events'] && array_sum(array_column($included,'wins'))===$original['wins'] && array_sum(array_column($included,'losses'))===$original['losses'], 'Per-event parity');
    }
}
check_account(smash_account_profile($public,null)['views']['combined']['rank'] === null, 'Unlinked account has no fabricated rank');
check_account((array)smash_account_profile($public,null)['rivals'] === [], 'Unlinked account has no rivals');
$top=$public['players'][0]; $rivals=(array)smash_account_profile($public,$top['id'])['rivals']; $met=[];
foreach ($public['results'] as $set) if (in_array($top['id'],$set['playerIds'],true)) foreach ($set['playerIds'] as $other) if ($other!==$top['id']) $met[$other]=true;
check_account(count($rivals)>0 && array_keys($rivals)==array_keys($met) && !isset($rivals[$top['id']]), 'Rivals are exactly the opponents in the published sets');
foreach ($rivals as $other=>$rival) {
    $ranked=null; foreach ($public['players'] as $candidate) if ($candidate['id']===(string)$other) $ranked=$candidate;
    check_account($ranked===null ? $rival['combined']===null : ($rival['combined']===['rank'=>$ranked['rank'],'points'=>$ranked['rating']] && $rival['tag']===$ranked['tag']), 'Rival place and points match the cut; unranked rivals have none');
}
echo "OAuth, identity, configuration and published ranking contracts passed.\n";
$db = getenv('SMASH_SCHEMA_TEST_DB');
if (!$db) { echo "SQL tests skipped: no disposable database configured.\n"; exit; }
if (strpos($db,'smash_schema_test')!==0 || !in_array(getenv('SMASH_SCHEMA_TEST_HOST') ?: '127.0.0.1',['127.0.0.1','localhost'],true)) throw new RuntimeException('Disposable database required');
$pdo = smash_database_connect(['host'=>'127.0.0.1','port'=>(int)(getenv('SMASH_SCHEMA_TEST_PORT') ?: 3306),'name'=>$db,'user'=>'root','password'=>getenv('SMASH_SCHEMA_TEST_PASSWORD')]);
$id=null;
try {
    $id=smash_account_login($pdo,$identity,time());
    $user=smash_account_user($pdo,$id); $version=$user['connectionVersion'];
    smash_account_preferences($pdo,$id,'roles',['roles'=>['player','organizer']],$version);
    check_account(count(smash_account_user($pdo,$id)['roles'])===2 && (int)$pdo->query('SELECT COUNT(*) FROM tournament_staff')->fetchColumn()===0, 'Roles do not grant tournament permissions');
    account_rejects(function () use ($pdo,$id,$version) { smash_account_preferences($pdo,$id,'roles',['roles'=>['admin']],$version); }, 'invalid_roles');
    $pdo->exec("INSERT INTO user_roles(user_id,role) VALUES ($id,'admin')");
    smash_account_preferences($pdo,$id,'roles',['roles'=>['player']],$version);
    check_account((int)$pdo->query("SELECT COUNT(*) FROM user_roles WHERE user_id=$id AND role='admin'")->fetchColumn()===1,'Product preferences preserve externally granted admin');
    smash_account_preferences($pdo,$id,'characters',['characters'=>['1319','1766']],$version);
    foreach ([['1319','1319'],['1746'],['99999999'],[]] as $invalid) account_rejects(function () use ($pdo,$id,$version,$invalid) { smash_account_preferences($pdo,$id,'characters',['characters'=>$invalid],$version); }, 'invalid_characters');
    $pdo->exec("CREATE TRIGGER smash_account_fixture_failure BEFORE INSERT ON user_characters FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='fixture failure'");
    account_rejects(function () use ($pdo,$id,$version) { smash_account_preferences($pdo,$id,'characters',['characters'=>['1766']],$version); }, 'account_write_failed');
    $pdo->exec('DROP TRIGGER smash_account_fixture_failure');
    check_account(smash_account_user($pdo,$id)['chosen']===['1319','1766'],'Failed replacement rolls back the deletion');
    // «Keep me signed in»: own random identifier, only its hash stored, bound to the connection.
    $now=time(); $account=['id'=>$id,'version'=>$version,'url'=>'https://www.start.gg/user/fixture','avatarUrl'=>'https://images.start.gg/fixture.png'];
    $token=smash_account_remember_create($pdo,$account,$now);
    check_account(smash_account_remember_token($token)===$token,'Cookie value is 64 hexadecimal characters');
    $stored=$pdo->query("SELECT token_hash, profile_url, avatar_url FROM user_sessions WHERE user_id=$id")->fetchAll(PDO::FETCH_ASSOC);
    check_account(count($stored)===1 && $stored[0]['token_hash']===hash('sha256',$token) && strpos(json_encode($stored),$token)===false,'Only the hash of the cookie is stored');
    $restored=smash_account_remember_restore($pdo,$token,$now+60);
    check_account($restored===['id'=>$id,'at'=>$now+60,'url'=>$account['url'],'avatarUrl'=>$account['avatarUrl'],'version'=>$version],'Cookie restores the same verified account');
    check_account(smash_account_session_valid(['smash_account'=>$restored],$now+60),'Restored session is a normal session');
    foreach ([str_repeat('f',64),strtoupper($token),$token.'0',[$token],null,''] as $bad) check_account(smash_account_remember_restore($pdo,$bad,$now)===null,'Unknown or malformed cookies are rejected');
    $expiry=static fn()=>$pdo->query("SELECT expires_at FROM user_sessions WHERE user_id=$id")->fetchColumn();
    $first=$expiry(); smash_account_remember_restore($pdo,$token,$now+3600*3);
    $later=$now+86400*30; check_account(smash_account_remember_restore($pdo,$token,$later)!==null && $expiry()>$first,'Use on a later day renews the ninety days');
    check_account(smash_account_remember_restore($pdo,$token,$later+SMASH_ACCOUNT_REMEMBER_AGE-5)!==null,'Still valid just before the renewed expiry');
    $pdo->exec("UPDATE user_sessions SET last_used_at='2026-01-01 00:00:00', expires_at='2026-01-02 00:00:00' WHERE user_id=$id");
    check_account(smash_account_remember_restore($pdo,$token,$now)===null,'Expired cookies are rejected and not renewed');
    $token=smash_account_remember_create($pdo,$account,$now);
    check_account((int)$pdo->query("SELECT COUNT(*) FROM user_sessions WHERE user_id=$id")->fetchColumn()===1,'Expired rows are removed when a new cookie is issued');
    check_account(smash_account_login($pdo,$identity,$now)===$id && smash_account_user($pdo,$id)['connectionVersion']===$version,'A second device signing in keeps the connection version');
    check_account(smash_account_remember_restore($pdo,$token,$now)!==null,'The first device stays signed in');
    $second=smash_account_remember_create($pdo,$account,$now);
    smash_account_remember_revoke($pdo,$second);
    check_account(smash_account_remember_restore($pdo,$second,$now)===null && smash_account_remember_restore($pdo,$token,$now)!==null,'Signing out ends only that browser');
    $pdo->exec("UPDATE users SET status='disabled' WHERE id=$id");
    check_account(smash_account_remember_restore($pdo,$token,$now)===null,'Disabled accounts cannot resume');
    $pdo->exec("UPDATE users SET status='active' WHERE id=$id");
    $pdo->exec('RENAME TABLE user_sessions TO user_sessions_fixture_away');
    check_account(smash_account_remember_create($pdo,$account,$now)===null,'Without migration 002 sign-in still works, only without the cookie');
    account_rejects(static fn()=>smash_account_remember_restore($pdo,$token,$now),'account_unavailable');
    smash_account_remember_revoke($pdo,$token,$id);
    $pdo->exec('RENAME TABLE user_sessions_fixture_away TO user_sessions');
    check_account(smash_account_remember_restore($pdo,$token,$now)!==null,'A storage failure does not consume the cookie');
    smash_account_preferences($pdo,$id,'disconnect',[],$version);
    check_account(smash_account_remember_restore($pdo,$token,$now)===null,'Disconnecting ends every remembered browser');
    account_rejects(static fn() => smash_account_user($pdo,$id),'login_required');
    account_rejects(function () use ($pdo,$id,$version) { smash_account_preferences($pdo,$id,'roles',['roles'=>['organizer']],$version); },'login_required');
    check_account(smash_account_login($pdo,$identity,time())===$id,'Reauthorization reuses same account');
    check_account(smash_account_user($pdo,$id)['chosen']===['1319','1766'],'Reauthorization preserves preferences');
    check_account(smash_account_user($pdo,$id)['connectionVersion']!==$version && smash_account_remember_restore($pdo,$token,$now)===null,'Re-linking starts a new version: old cookies stay dead');
    smash_account_remember_create($pdo,$account,$now); smash_account_remember_revoke($pdo,null,$id);
    check_account((int)$pdo->query("SELECT COUNT(*) FROM user_sessions WHERE user_id=$id")->fetchColumn()===0,'All cookies of the account can be removed');
    account_rejects(function () use ($pdo,$id,$version) { smash_account_preferences($pdo,$id,'roles',['roles'=>['organizer']],$version); },'login_required');
    check_account((int)$pdo->query("SELECT COUNT(*) FROM oauth_connections WHERE user_id=$id AND access_token_encrypted IS NULL AND refresh_token_encrypted IS NULL")->fetchColumn()===1,'No provider tokens stored');
    $pdo->beginTransaction();
    account_rejects(static fn()=>smash_account_login($pdo,$identity,time()),'transaction_already_active');
    check_account($pdo->inTransaction(),'Caller transaction remains owned by caller'); $pdo->rollBack();
    $pdo->exec("UPDATE users SET status='disabled' WHERE id=$id");
    account_rejects(static fn()=>smash_account_login($pdo,$identity,time()),'account_disabled');
    echo "SQL linking, preferences, remembered sessions, rollback, role isolation, expiry and revocation passed.\n";
} finally {
    if ($pdo->inTransaction()) $pdo->rollBack();
    $pdo->exec('DROP TRIGGER IF EXISTS smash_account_fixture_failure');
    if ((int)$pdo->query("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name='user_sessions_fixture_away'")->fetchColumn()===1) $pdo->exec('RENAME TABLE user_sessions_fixture_away TO user_sessions');
    if ($id!==null) { foreach (['user_characters','user_roles','oauth_connections'] as $table) $pdo->exec("DELETE FROM $table WHERE user_id=$id"); $pdo->exec("DELETE FROM users WHERE id=$id"); }
    $pdo->exec('DELETE FROM players WHERE id=8999002');
}
