<?php
declare(strict_types=1);
// Visit counter contracts. SQL part runs only against a local disposable database.
require_once __DIR__ . '/../../ranking-smash-ultimate/database.php';
require_once __DIR__ . '/../../ranking-smash-ultimate/visits.php';
function check_visit($condition, string $description): void { if (!$condition) throw new RuntimeException($description); }
function visit_rejects(callable $operation, string $reason): void {
    try { $operation(); } catch (SmashVisitError $error) { check_visit($error->reason === $reason, 'Unexpected rejection: ' . $error->reason); return; }
    throw new RuntimeException('Expected rejection: ' . $reason);
}
// 2026-10-08 05:59:59 UTC is still 7 October in Guatemala; one second later it is the 8th.
check_visit(smash_visit_day(gmmktime(5, 59, 59, 10, 8, 2026)) === '2026-10-07' && smash_visit_day(gmmktime(6, 0, 0, 10, 8, 2026)) === '2026-10-08', 'Guatemala calendar day');
check_visit(smash_visit_page('inicio') === 'inicio' && smash_visit_page('encuesta') === null && smash_visit_page('opiniones') === null
    && smash_visit_page(['inicio']) === null && smash_visit_page('inicio ') === null, 'Only known public pages, never the survey or the panel');
check_visit(smash_visit_same_origin(['HTTP_SEC_FETCH_SITE' => 'same-origin']) && !smash_visit_same_origin(['HTTP_SEC_FETCH_SITE' => 'cross-site'])
    && !smash_visit_same_origin(['HTTP_SEC_FETCH_SITE' => 'same-site', 'HTTP_ORIGIN' => 'https://rankingsmashbros.com', 'HTTP_HOST' => 'rankingsmashbros.com']), 'Fetch metadata decides when present');
check_visit(smash_visit_same_origin(['HTTP_ORIGIN' => 'https://rankingsmashbros.com', 'HTTP_HOST' => 'rankingsmashbros.com'])
    && smash_visit_same_origin(['HTTP_ORIGIN' => 'http://127.0.0.1:8080', 'HTTP_HOST' => '127.0.0.1:8080'])
    && !smash_visit_same_origin(['HTTP_ORIGIN' => 'https://rankingsmashbros.com.evil.test', 'HTTP_HOST' => 'rankingsmashbros.com'])
    && !smash_visit_same_origin(['HTTP_ORIGIN' => 'null', 'HTTP_HOST' => 'rankingsmashbros.com'])
    && !smash_visit_same_origin(['HTTP_HOST' => 'rankingsmashbros.com']) && !smash_visit_same_origin([]), 'Origin must match the host; no origin is not counted');
check_visit(smash_visit_automated('Mozilla/5.0 (compatible; Googlebot/2.1)') && smash_visit_automated('curl/8.4') && smash_visit_automated('') && smash_visit_automated(null)
    && !smash_visit_automated('Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1'), 'Automated clients are skipped');
$root = sys_get_temp_dir() . '/smash-visits-' . bin2hex(random_bytes(6));
mkdir($root); mkdir($root . '/site');
try {
    visit_rejects(static fn() => smash_visit_key($root . '/site'), 'key_unavailable');
    mkdir($root . '/private-smash');
    $key = smash_visit_key($root . '/site');
    check_visit(preg_match('/\A[0-9a-f]{64}\z/D', $key) === 1 && smash_visit_key($root . '/site') === $key, 'Key is created once and reused');
    check_visit((fileperms($root . '/private-smash/visits.key') & 0777) === 0600 && glob($root . '/private-smash/*.tmp') === [], 'Key file is private and leaves no temporary file');
    file_put_contents($root . '/private-smash/visits.key', 'damaged');
    visit_rejects(static fn() => smash_visit_key($root . '/site'), 'key_unavailable');
    check_visit(file_get_contents($root . '/private-smash/visits.key') === 'damaged', 'A damaged key is never replaced silently: identities would reset');
} finally { @unlink($root . '/private-smash/visits.key'); @rmdir($root . '/private-smash'); rmdir($root . '/site'); rmdir($root); }
$other = str_repeat('ab', 32);
$token = smash_visit_token_issue($key);
check_visit(smash_visit_token_valid($key, $token) && smash_visit_token_issue($key) !== $token, 'Issued identifiers verify and differ');
check_visit(!smash_visit_token_valid($other, $token) && !smash_visit_token_valid($key, str_repeat('0', 64)) && !smash_visit_token_valid($key, strtoupper($token))
    && !smash_visit_token_valid($key, substr($token, 0, 63)) && !smash_visit_token_valid($key, [$token]) && !smash_visit_token_valid($key, null), 'Identifiers this server did not sign are rejected');
$network = smash_visit_network_hash($key, '203.0.113.7');
check_visit(preg_match('/\A[0-9a-f]{64}\z/D', $network) === 1 && $network === smash_visit_network_hash($key, '203.0.113.7')
    && $network !== smash_visit_network_hash($key, '203.0.113.8') && $network !== smash_visit_network_hash($other, '203.0.113.7')
    && $network !== hash('sha256', '203.0.113.7'), 'Network hash is keyed: not a plain hash of the address');
echo "Visit counter contracts passed.\n";
$db = getenv('SMASH_SCHEMA_TEST_DB');
if (!$db) { echo "SQL tests skipped: no disposable database configured.\n"; exit; }
if (strpos($db, 'smash_schema_test') !== 0 || !in_array(getenv('SMASH_SCHEMA_TEST_HOST') ?: '127.0.0.1', ['127.0.0.1', 'localhost'], true)) throw new RuntimeException('Disposable database required');
$pdo = smash_database_connect(['host' => '127.0.0.1', 'port' => (int)(getenv('SMASH_SCHEMA_TEST_PORT') ?: 3306), 'name' => $db, 'user' => 'root', 'password' => getenv('SMASH_SCHEMA_TEST_PASSWORD')]);
$days = "'2001-01-01','2001-01-02'";
$clean = static function () use ($pdo, $days) { foreach (['site_visit_days', 'site_visitor_days', 'site_network_days'] as $table) $pdo->exec("DELETE FROM $table WHERE day IN ($days)"); };
$one = static fn(string $sql) => $pdo->query($sql)->fetchColumn();
try {
    $clean(); $day = '2001-01-01'; $net2 = smash_visit_network_hash($key, '203.0.113.8');
    // First visit of a browser: a signed identifier is issued and counted at once.
    $first = smash_visit_record($pdo, $key, $day, 'inicio', null, $network, true, false);
    check_visit($first['status'] === 'counted' && smash_visit_token_valid($key, $first['token']), 'New browser receives a signed identifier');
    // Same browser, more pages, later signed in, from another network.
    smash_visit_record($pdo, $key, $day, 'metodologia', $first['token'], $network, true, false);
    smash_visit_record($pdo, $key, $day, 'cuenta', $first['token'], $net2, true, true);
    smash_visit_record($pdo, $key, $day, 'inicio', $first['token'], $net2, true, false);
    check_visit((int)$one("SELECT COUNT(*) FROM site_visitor_days WHERE day='$day'") === 1, 'One browser is one visitor, whatever its network');
    check_visit($pdo->query("SELECT views, signed_in FROM site_visitor_days WHERE day='$day'")->fetch(PDO::FETCH_NUM) == [4, 1], 'Views add up and signed-in is remembered for the day');
    check_visit($pdo->query("SELECT page, views FROM site_visit_days WHERE day='$day' ORDER BY page")->fetchAll(PDO::FETCH_KEY_PAIR) == ['cuenta' => 1, 'inicio' => 2, 'metodologia' => 1], 'Views per page');
    check_visit((int)$one("SELECT COUNT(*) FROM site_network_days WHERE day='$day'") === 2 && (int)$one("SELECT SUM(new_visitors) FROM site_network_days WHERE day='$day'") === 1, 'Two networks, one new identifier');
    $stored = json_encode($pdo->query("SELECT * FROM site_visitor_days WHERE day='$day'")->fetchAll(PDO::FETCH_ASSOC)) . json_encode($pdo->query("SELECT * FROM site_network_days WHERE day='$day'")->fetchAll(PDO::FETCH_ASSOC));
    check_visit(strpos($stored, $first['token']) === false && strpos($stored, substr($first['token'], 0, 32)) === false && strpos($stored, '203.0.113') === false, 'Neither the cookie value nor the address is stored');
    // A second browser on the same network is a second visitor.
    $second = smash_visit_record($pdo, $key, $day, 'inicio', null, $network, true, false);
    check_visit($second['token'] !== $first['token'] && (int)$one("SELECT COUNT(*) FROM site_visitor_days WHERE day='$day'") === 2, 'Second browser, second visitor');
    // The same browser on another day is counted in that day too, and once over the period.
    smash_visit_record($pdo, $key, '2001-01-02', 'inicio', $first['token'], $network, true, false);
    check_visit((int)$one("SELECT COUNT(DISTINCT visitor_hash) FROM site_visitor_days WHERE day IN ($days)") === 2 && (int)$one("SELECT COUNT(*) FROM site_visitor_days WHERE day IN ($days)") === 3, 'Distinct visitors over a period');
    // Browsers without cookies are one visitor per network, and receive no identifier.
    $clean();
    foreach ([1, 2, 3] as $_) $none = smash_visit_record($pdo, $key, $day, 'inicio', null, $network, false, false);
    check_visit($none === ['status' => 'counted', 'token' => null] && (int)$one("SELECT COUNT(*) FROM site_visitor_days WHERE day='$day'") === 1
        && $one("SELECT visitor_hash FROM site_visitor_days WHERE day='$day'") === $network && (int)$one("SELECT views FROM site_visit_days WHERE day='$day'") === 3, 'Cookieless browsers fall back to the network');
    // A client that keeps discarding cookies cannot mint unlimited visitors from one network.
    $clean();
    for ($i = 0; $i < SMASH_VISIT_DAILY_NEW_PER_NETWORK + 5; $i++) $flood = smash_visit_record($pdo, $key, $day, 'inicio', null, $network, true, false);
    check_visit($flood['token'] === null && (int)$one("SELECT COUNT(*) FROM site_visitor_days WHERE day='$day'") === SMASH_VISIT_DAILY_NEW_PER_NETWORK + 1
        && (int)$one("SELECT new_visitors FROM site_network_days WHERE day='$day'") === SMASH_VISIT_DAILY_NEW_PER_NETWORK, 'New identifiers per network are limited');
    check_visit(smash_visit_record($pdo, $key, $day, 'inicio', null, $net2, true, false)['token'] !== null, 'Other networks are unaffected');
    // One browser cannot inflate the totals without limit either.
    $clean(); $mine = smash_visit_record($pdo, $key, $day, 'inicio', null, $network, true, false)['token'];
    $pdo->exec("UPDATE site_visitor_days SET views=" . SMASH_VISIT_DAILY_VIEWS . " WHERE day='$day'");
    check_visit(smash_visit_record($pdo, $key, $day, 'inicio', $mine, $network, true, false) === ['status' => 'limited', 'token' => null]
        && (int)$one("SELECT views FROM site_visit_days WHERE day='$day'") === 1 && (int)$one("SELECT views FROM site_network_days WHERE day='$day'") === 1, 'Past the daily limit nothing is added');
    // Invalid input and a failing write leave nothing behind.
    $clean();
    visit_rejects(static fn() => smash_visit_record($pdo, $key, $day, 'encuesta', null, $network, true, false), 'invalid_visit');
    visit_rejects(static fn() => smash_visit_record($pdo, $key, '2001-1-1', 'inicio', null, $network, true, false), 'invalid_visit');
    visit_rejects(static fn() => smash_visit_record($pdo, $key, $day, 'inicio', null, '203.0.113.7', true, false), 'invalid_visit');
    $pdo->exec("CREATE TRIGGER smash_visit_fixture_failure BEFORE INSERT ON site_visit_days FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='fixture failure'");
    visit_rejects(static fn() => smash_visit_record($pdo, $key, $day, 'inicio', null, $network, true, false), 'visit_write_failed');
    $pdo->exec('DROP TRIGGER smash_visit_fixture_failure');
    check_visit(!$pdo->inTransaction() && (int)$one("SELECT COUNT(*) FROM site_visitor_days WHERE day='$day'") === 0 && (int)$one("SELECT COUNT(*) FROM site_network_days WHERE day='$day'") === 0, 'A failed visit rolls back every table');
    $pdo->beginTransaction();
    visit_rejects(static fn() => smash_visit_record($pdo, $key, $day, 'inicio', null, $network, true, false), 'transaction_already_active');
    check_visit($pdo->inTransaction(), 'Caller transaction remains owned by caller'); $pdo->rollBack();
    check_visit(!smash_visit_signed_in($pdo, str_repeat('f', 64), time()) && !smash_visit_signed_in($pdo, null, time()) && !smash_visit_signed_in($pdo, 'x', time()), 'Unknown keep-me-signed-in cookies are not signed in');
    echo "Visit counting, limits, privacy and rollback passed on " . $one('SELECT VERSION()') . ".\n";
} finally {
    if ($pdo->inTransaction()) $pdo->rollBack();
    $pdo->exec('DROP TRIGGER IF EXISTS smash_visit_fixture_failure');
    $clean();
}
