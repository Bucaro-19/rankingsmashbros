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
    check_stats($r['counterStartedAt'] === '2026-10-10' && $r['today'] === ['date' => '2026-10-21', 'visitors' => 2, 'pageviews' => 3, 'registrations' => 1] && $r['yesterday'] === ['visitors' => 2], 'Today is partial and separate; yesterday is the last complete day');
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
    check_stats($r['accounts'] === ['total' => $baseUsers + 4, 'linked' => $baseLinked + 1, 'premium' => 0], 'Accounts: total, still linked and premium');
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
