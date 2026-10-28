<?php
declare(strict_types=1);
// Owner panel figures against invented rows in a local disposable database only.
require_once __DIR__ . '/../../ranking-smash-ultimate/database.php';
require_once __DIR__ . '/../../ranking-smash-ultimate/stats.php';
function check_stats($condition, string $description): void { if (!$condition) throw new RuntimeException($description); }
check_stats(smash_stats_shift('2026-03-01', -1) === '2026-02-28' && smash_stats_shift('2026-12-31', 1) === '2027-01-01' && smash_stats_span('2026-10-01', '2026-10-07') === 7, 'Calendar arithmetic');
check_stats(SMASH_STATS_PAGES['analisis-torneos'] === 'torneos' && SMASH_STATS_PAGES['torneos'] === 'agendaTorneos'
    && count(array_unique(SMASH_STATS_PAGES)) === count(SMASH_STATS_PAGES), 'Additive panel keys preserve historical meaning without duplicate aliases');
echo "Statistics calendar contracts passed.\n";
// Synthetic committed progress: prior context is NOT counted as a newly completed history.
$progressNow=strtotime('2026-10-20T00:00:00Z');
$progressState=['revision'=>str_repeat('a',64),'lastResult'=>['status'=>'imported'],'checkpoint'=>[
    'stateVersion'=>1,'seasonYear'=>2026,'roster'=>['event'=>['id'=>1687524],
        'capturedAt'=>'2026-10-19T23:54:00+00:00','registrations'=>5,'players'=>[
            '11'=>['id'=>'11','gamerTag'=>'DO NOT EXPOSE NAME'],'12'=>['id'=>'12'],
            '13'=>['id'=>'13'],'14'=>['id'=>'14'],'15'=>['id'=>'15']]],
    'knownPlayerIds'=>['11','12','13'],'coverage'=>[
        '12'=>['nextPage'=>3,'totalPages'=>2,'complete'=>true],
        '13'=>['nextPage'=>4,'totalPages'=>10,'complete'=>false],
        '14'=>['nextPage'=>1,'totalPages'=>null,'complete'=>false],
        '15'=>['nextPage'=>1,'totalPages'=>null,'complete'=>false]],'pages'=>[]]];
$progress=smash_stats_analysis_summary($progressState,$progressNow,$progressNow-60);
check_stats([$progress['registered'],$progress['preexisting'],$progress['targets'],$progress['completed'],$progress['partial'],$progress['notStarted'],$progress['pending'],$progress['percentage'],$progress['pagesConfirmed']] === [5,1,4,1,1,2,3,25.0,5], 'Real coverage counts and numerator, not known SQL identities');
check_stats($progress['status']==='pending' && !$progress['stale'] && $progress['rosterCapturedAt']==='2026-10-19T17:54:00-06:00', 'Progress uses Guatemala timestamps');
check_stats(smash_stats_analysis_summary($progressState,$progressNow,$progressNow-13*3600)['stale'], 'Old committed file warns without claiming a failed run');
check_stats(smash_stats_analysis_summary($progressState,strtotime('2026-10-28T06:00:00Z'),$progressNow)['status']==='pending', 'Owner renewal resumes pending coverage after original deadline');
check_stats($progress['authorizationEndsAt']==='2027-01-01T00:00:00-06:00', 'Renewed deadline shown in Guatemala time');
check_stats(smash_stats_analysis_summary($progressState,strtotime(SMASH_STATS_ANALYSIS_UNTIL),$progressNow)['status']==='expired', 'Renewed deadline still stops the panel at exact boundary');
$completeState=$progressState;
foreach($completeState['checkpoint']['coverage'] as &$cov) $cov=['nextPage'=>2,'totalPages'=>1,'complete'=>true];unset($cov);
check_stats(smash_stats_analysis_summary($completeState,$progressNow,$progressNow)['percentage']===100.0, '100 only when every planned history finished');
$noTargets=$progressState;$noTargets['checkpoint']['coverage']=[];$noTargets['checkpoint']['knownPlayerIds']=['11','12','13','14','15'];
check_stats(smash_stats_analysis_summary($noTargets,$progressNow,$progressNow)['status']==='complete', 'No targeted histories is a satisfied plan, not an invented historical capture');
$more=$progressState;$more['checkpoint']['roster']['players']['16']=['id'=>'16'];$more['checkpoint']['roster']['registrations']=6;$more['checkpoint']['coverage']['16']=['nextPage'=>1,'totalPages'=>null,'complete'=>false];
check_stats(smash_stats_analysis_summary($more,$progressNow,$progressNow)['percentage']===20.0, 'New registrant may reduce percentage without losing confirmed progress');
$raw=json_encode($progress);
foreach(['DO NOT EXPOSE NAME','gamerTag','knownPlayerIds','revision','nextPage','players','checkpoint','lastResult','token','private-smash'] as $secret) check_stats(strpos($raw,'"'.$secret.'"')===false,'Closed aggregate projection: '.$secret);
$progressRoot=sys_get_temp_dir().'/smash-progress-'.bin2hex(random_bytes(6));mkdir($progressRoot);mkdir($progressRoot.'/site');mkdir($progressRoot.'/private-smash');mkdir($progressRoot.'/private-smash/analysis-context');
$progressFile=$progressRoot.'/private-smash/analysis-context/1687524.json';
try {
    check_stats(smash_stats_analysis_progress($progressRoot.'/site',$progressNow)['status']==='not_started','Missing file is unknown, never 0 percent');
    file_put_contents($progressFile.'.pending',json_encode($progressState));
    check_stats(smash_stats_analysis_progress($progressRoot.'/site',$progressNow)['registered']===null,'Pending import never contributes progress');
    mkdir($progressFile);check_stats(smash_stats_analysis_progress($progressRoot.'/site',$progressNow)['status']==='unavailable','No special-directory reads');rmdir($progressFile);
    file_put_contents($progressFile,json_encode($progressState));touch($progressFile,$progressNow-60);clearstatcache();
    $before=hash_file('sha256',$progressFile);
    check_stats(smash_stats_analysis_progress($progressRoot.'/site',$progressNow)['percentage']===25.0,'Reads only the active checkpoint');
    check_stats(hash_file('sha256',$progressFile)===$before,'Reader never writes checkpoint');
    file_put_contents($progressFile,'{');check_stats(smash_stats_analysis_progress($progressRoot.'/site',$progressNow)['status']==='unavailable','Corrupt progress isolated from the rest of the panel');
    file_put_contents($progressFile,str_repeat('x',2*1024*1024+1));check_stats(smash_stats_analysis_progress($progressRoot.'/site',$progressNow)['status']==='unavailable','Hard file size limit');
    unlink($progressFile);symlink($progressFile.'.pending',$progressFile);check_stats(smash_stats_analysis_progress($progressRoot.'/site',$progressNow)['status']==='unavailable','No symlink traversal');unlink($progressFile);
} finally {if(file_exists($progressFile)||is_link($progressFile))unlink($progressFile);unlink($progressFile.'.pending');rmdir(dirname($progressFile));rmdir($progressRoot.'/private-smash');rmdir($progressRoot.'/site');rmdir($progressRoot);}
$invalid=$progressState;$invalid['checkpoint']['coverage']['12']['complete']=false;
try {smash_stats_analysis_summary($invalid,$progressNow,$progressNow);throw new RuntimeException('Invalid completed/next-page relationship accepted');}catch(SmashStatsError $expected){}
echo "Legends progress aggregate/read-only contracts passed.\n";
$db = getenv('SMASH_SCHEMA_TEST_DB');
if (!$db) { echo "SQL tests skipped: no disposable database configured.\n"; exit; }
if (strpos($db, 'smash_schema_test') !== 0 || !in_array(getenv('SMASH_SCHEMA_TEST_HOST') ?: '127.0.0.1', ['127.0.0.1', 'localhost'], true)) throw new RuntimeException('Disposable database required');
$pdo = smash_database_connect(['host' => '127.0.0.1', 'port' => (int)(getenv('SMASH_SCHEMA_TEST_PORT') ?: 3306), 'name' => $db, 'user' => 'root', 'password' => getenv('SMASH_SCHEMA_TEST_PASSWORD')]);
$clean = static function () use ($pdo) {
    foreach (['site_visit_days', 'site_visitor_days', 'site_network_days'] as $table) $pdo->exec("DELETE FROM $table");
    $pdo->exec('DELETE FROM users WHERE startgg_user_id BETWEEN 8999300 AND 8999399');
};
// «Now» is 2026-10-21 15:30 in Guatemala (21:30 UTC): today is the 21st, yesterday the 20th.
$now = gmmktime(21, 30, 0, 10, 21, 2026);
$h = static fn(string $name) => hash('sha256', $name);
try {
    $clean();
    $empty = smash_stats_report($pdo, $now, 2026);
    check_stats($empty['counterStartedAt'] === null && $empty['daily'] === [] && $empty['yesterday'] === null && $empty['today']['visitors'] === 0
        && $empty['periods']['30']['daysWithData'] === 0 && !isset($empty['periods']['30']['visitors']) && $empty['updatedAt'] === '2026-10-21T15:30-06:00', 'Before the counter: no days, no zeros presented as data');
    // Counter starts on 10 October. A visits 10, 15, 20 and today; B visits 15 and 20 signed in; C only today.
    $visitor = $pdo->prepare('INSERT INTO site_visitor_days (day, visitor_hash, views, signed_in) VALUES (?, ?, ?, ?)');
    foreach ([['2026-10-10', 'A', 2, 0], ['2026-10-15', 'A', 1, 0], ['2026-10-15', 'B', 3, 1], ['2026-10-20', 'A', 1, 0], ['2026-10-20', 'B', 1, 0], ['2026-10-21', 'A', 1, 0], ['2026-10-21', 'C', 2, 0]] as $row) $visitor->execute([$row[0], $h($row[1]), $row[2], $row[3]]);
    $network = $pdo->prepare('INSERT INTO site_network_days (day, network_hash, views, new_visitors) VALUES (?, ?, ?, 0)');
    foreach ([['2026-10-10', 'N1', 2], ['2026-10-15', 'N1', 4], ['2026-10-20', 'N1', 1], ['2026-10-20', 'N2', 1], ['2026-10-21', 'N1', 3]] as $row) $network->execute([$row[0], $h($row[1]), $row[2]]);
    $page = $pdo->prepare('INSERT INTO site_visit_days (day, page, views) VALUES (?, ?, ?)');
    foreach ([['2026-10-10', 'inicio', 2], ['2026-10-15', 'inicio', 3], ['2026-10-15', 'cuenta', 1], ['2026-10-20', 'analisis-top20', 2], ['2026-10-21', 'inicio', 3]] as $row) $page->execute($row);
    // Registrations: 05:59 UTC on the 16th is still the 15th in Guatemala; 06:00 UTC is the 16th.
    $user = $pdo->prepare('INSERT INTO users (startgg_user_id, created_at) VALUES (?, ?)');
    foreach ([[8999301, '2026-10-16 05:59:59'], [8999302, '2026-10-16 06:00:00'], [8999303, '2026-10-21 20:00:00'], [8999304, '2026-09-01 12:00:00']] as $row) $user->execute($row);
    $id = static fn(int $startgg) => (int)$pdo->query("SELECT id FROM users WHERE startgg_user_id=$startgg")->fetchColumn();
    $pdo->exec("INSERT INTO oauth_connections (user_id, scopes) VALUES ({$id(8999301)}, 'user.identity'), ({$id(8999302)}, 'user.identity')");
    $pdo->exec("UPDATE oauth_connections SET revoked_at = UTC_TIMESTAMP(6) WHERE user_id = {$id(8999302)}");
    $baseUsers = (int)$pdo->query('SELECT COUNT(*) FROM users')->fetchColumn() - 4;
    $baseLinked = (int)$pdo->query('SELECT COUNT(*) FROM oauth_connections WHERE revoked_at IS NULL')->fetchColumn() - 1;
    $r = smash_stats_report($pdo, $now, 2026);
    check_stats($r['counterStartedAt'] === '2026-10-10' && $r['today'] === ['date' => '2026-10-21', 'visitors' => 2, 'pageviews' => 3, 'registrations' => 1] && $r['yesterday'] === ['visitors' => 2, 'registrations' => 0], 'Today is partial and separate; yesterday is the last complete day');
    $p7 = $r['periods']['7']; $p30 = $r['periods']['30'];
    check_stats([$p7['from'], $p7['to'], $p7['days'], $p7['daysWithData']] === ['2026-10-14', '2026-10-20', 7, 7], 'Seven complete days ending yesterday');
    check_stats([$p7['visitors'], $p7['loggedVisitors'], $p7['networks'], $p7['pageviews'], $p7['registrations']] === [2, 1, 2, 6, 2], 'Distinct visitors over the range, not a sum of days; today excluded');
    check_stats($p7['pages'] === ['home' => 3, 'metodologia' => 0, 'cuenta' => 1, 'top20' => 2, 'torneos' => 0, 'agendaTorneos' => 0], 'Views per page with fixed names; absent agenda remains zero');
    check_stats($p7['previous'] === null, 'No comparison: the previous seven days are not fully measured');
    check_stats([$p30['from'], $p30['days'], $p30['daysWithData'], $p30['visitors'], $p30['pageviews']] === ['2026-09-21', 30, 11, 2, 8] && $p30['previous'] === null, 'A period longer than the history says how many days have data');
    check_stats($r['periods']['season']['from'] === '2026-01-01' && $r['periods']['season']['daysWithData'] === 11 && $r['periods']['season']['registrations'] === 2, 'Season counts registrations only where visits are measured');
    check_stats(count($r['daily']) === 11 && $r['daily'][0] === ['date' => '2026-10-10', 'visitors' => 1, 'loggedVisitors' => 0, 'networks' => 1, 'pageviews' => 2, 'registrations' => 0]
        && $r['daily'][5] === ['date' => '2026-10-15', 'visitors' => 2, 'loggedVisitors' => 1, 'networks' => 1, 'pageviews' => 4, 'registrations' => 1]
        && $r['daily'][6]['registrations'] === 1 && $r['daily'][1]['visitors'] === 0 && end($r['daily'])['date'] === '2026-10-20', 'Daily rows: measured days without visits are real zeros; Guatemala day for registrations');
    $weeks = $r['weekly']['90'];
    check_stats(count($weeks) === 2 && $weeks[1] === ['from' => '2026-10-14', 'to' => '2026-10-20', 'visitors' => 2, 'pageviews' => 6, 'registrations' => 2, 'partial' => false]
        && $weeks[0] === ['from' => '2026-10-10', 'to' => '2026-10-13', 'visitors' => 1, 'pageviews' => 2, 'registrations' => 0, 'partial' => true], 'Weeks counted back from yesterday; the oldest one is clipped and partial');
    check_stats($r['accounts'] === ['total' => $baseUsers + 4, 'linked' => $baseLinked + 1, 'premium' => 0, 'premiumList' => []], 'Accounts: total, still linked and premium');
    // Drilldowns use exactly the same clipped days, including UTC/Guatemala midnight.
    foreach (['7', '30', '90', 'season'] as $scope) {
        $list = smash_stats_registration_list($pdo, $scope, '2026-10-21', 2026);
        check_stats($list['total'] === $r['periods'][$scope]['registrations'] && count($list['items']) === $list['total'], 'Period total/list parity: ' . $scope);
    }
    foreach ($r['weekly']['90'] as $week) check_stats(smash_stats_registration_list($pdo, $week['from'] . '_' . $week['to'], '2026-10-21', 2026)['total'] === $week['registrations'], 'Week/list parity');
    foreach ($r['daily'] as $day) check_stats(smash_stats_registration_list($pdo, $day['date'] . '_' . $day['date'], '2026-10-21', 2026)['total'] === $day['registrations'], 'Day/list parity');
    $todayList = smash_stats_registration_list($pdo, 'today', '2026-10-21', 2026);
    check_stats($todayList['total'] === $r['today']['registrations'] && $todayList['items'][0] === ['tag' => 'Cuenta sin jugador vinculado', 'registeredAt' => '2026-10-21T14:00:00-06:00', 'linked' => false], 'No player: exact fallback, local datetime and closed projection');
    check_stats(smash_stats_registration_list($pdo, 'yesterday', '2026-10-21', 2026) === ['total' => 0, 'items' => [], 'nextOffset' => null], 'Empty period');
    $boundary = smash_stats_registration_list($pdo, '2026-10-15_2026-10-15', '2026-10-21', 2026);
    check_stats($boundary['total'] === 1 && $boundary['items'][0]['registeredAt'] === '2026-10-15T23:59:59-06:00' && $boundary['items'][0]['linked'], 'Last second before Guatemala midnight');
    $boundary = smash_stats_registration_list($pdo, '2026-10-16_2026-10-16', '2026-10-21', 2026);
    check_stats($boundary['total'] === 1 && $boundary['items'][0]['registeredAt'] === '2026-10-16T00:00:00-06:00' && !$boundary['items'][0]['linked'], 'Revoked connection and first second after midnight');
    try { smash_stats_registration_list($pdo, 'sql injection', '2026-10-21', 2026); throw new RuntimeException('Invalid scope accepted'); }
    catch (SmashStatsError $error) { check_stats($error->reason === 'invalid_registration_query', 'Invalid scope rejected'); }
    // Historical analysis rows remain unchanged; new agenda rows are distinct and counted once.
    $page->execute(['2026-10-20', 'analisis-torneos', 3]);
    $page->execute(['2026-10-20', 'torneos', 5]);
    $mixed = smash_stats_report($pdo, $now, 2026);
    check_stats($mixed['periods']['7']['pages']['torneos'] === 3 && $mixed['periods']['7']['pages']['agendaTorneos'] === 5
        && $mixed['periods']['7']['pageviews'] === 14 && $mixed['weekly']['90'][1]['pageviews'] === 14
        && end($mixed['daily'])['pageviews'] === 10 && $mixed['periods']['7']['visitors'] === 2, 'Agenda/analysis split reconciles daily, weekly and period totals without aliases or added visitors');
    $page->execute(['2026-10-21', 'torneos', 2]);
    check_stats(smash_stats_report($pdo, $now, 2026)['today']['pageviews'] === 5
        && smash_stats_report($pdo, $now, 2026)['periods']['7']['pageviews'] === 14, 'Today agenda views stay outside complete-day periods');
    $sub = $pdo->prepare("INSERT INTO premium_subscriptions (user_id, plan, live_mode, provider_checkout_id, status, current_period_end, created_at, updated_at) VALUES (?, 'annual', ?, ?, ?, ?, '2026-10-01', '2026-10-01')");
    foreach ([[8999301, 1, 'ch_stats1', 'active', '2027-10-01'], [8999301, 1, 'ch_stats2', 'canceled', '2026-12-01'], [8999302, 1, 'ch_stats3', 'canceled', '2026-10-20'], [8999303, 0, 'ch_stats4', 'active', '2027-10-01'], [8999304, 1, 'ch_stats5', 'pending', null]] as $row) $sub->execute([$id($row[0]), $row[1], $row[2], $row[3], $row[4]]);
    check_stats(smash_stats_report($pdo, $now, 2026)['accounts']['premium'] === 1, 'Premium counts accounts with a real paid period running: no tests, no ended, no pending, no double count');
    $list = smash_stats_report($pdo, $now, 2026)['accounts']['premiumList'];
    check_stats(count($list) === 1 && $list[0]['plan'] === 'annual' && array_keys($list[0]) === ['tag', 'plan', 'renews', 'until'], 'Premium list names each paying account once, with plan and period end only');
    // Once the previous window is fully measured, the comparison appears.
    $visitor->execute(['2026-10-02', $h('D'), 1, 0]); $visitor->execute(['2026-10-08', $h('A'), 1, 0]); $visitor->execute(['2026-10-08', $h('E'), 1, 0]);
    $again = smash_stats_report($pdo, $now, 2026);
    check_stats($again['counterStartedAt'] === '2026-10-02' && $again['periods']['7']['previous'] === ['visitors' => 2] && $again['periods']['30']['previous'] === null, 'Comparison uses the complete previous window only');
    $raw = json_encode($again);
    check_stats(strpos($raw, $h('A')) === false && strpos($raw, $h('N1')) === false && strpos($raw, '8999301') === false, 'The report never lists visitors, networks or accounts');
    // Owner check.
    check_stats(!smash_stats_is_owner($pdo, (string)$id(8999301)), 'A normal account is not the owner');
    $pdo->exec("INSERT INTO user_roles (user_id, role) VALUES ({$id(8999301)}, 'player'), ({$id(8999301)}, 'organizer')");
    check_stats(!smash_stats_is_owner($pdo, (string)$id(8999301)), 'Player and organizer interests do not open the panel');
    $pdo->exec("INSERT INTO user_roles (user_id, role) VALUES ({$id(8999301)}, 'admin')");
    check_stats(smash_stats_is_owner($pdo, (string)$id(8999301)) && !smash_stats_is_owner($pdo, (string)$id(8999302)), 'Only the admin role opens the panel');
    echo "Panel figures, periods, weeks, comparison and owner check passed on " . $pdo->query('SELECT VERSION()')->fetchColumn() . ".\n";
} finally {
    $clean();
}
