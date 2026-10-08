<?php
declare(strict_types=1);
// Organizer tops against invented rows in a local disposable database only.
require_once __DIR__ . '/../../ranking-smash-ultimate/database.php';
require_once __DIR__ . '/../../ranking-smash-ultimate/organizador.php';
require_once __DIR__ . '/organizer_fixture.php';
function check_org($condition, string $description): void { if (!$condition) throw new RuntimeException($description); }
function org_fails(callable $call, string $reason): bool { try { $call(); } catch (SmashOrganizerError $e) { return $e->reason === $reason; } return false; }

// The fit itself needs no database: more wins against the same field means more points, and it is symmetric.
$fit = smash_org_fit([['1', '2', 'e'], ['1', '3', 'e'], ['2', '3', 'e']], ['e' => 32]);
check_org($fit['1'] > $fit['2'] && $fit['2'] > $fit['3'] && $fit['2'] === 1500 && $fit['1'] - 1500 === 1500 - $fit['3'], 'Bradley-Terry order, scale and symmetry');
$repeat = smash_org_fit([['1', '2', 'e'], ['1', '2', 'e'], ['1', '2', 'e'], ['1', '2', 'e']], ['e' => 32]);
$single = smash_org_fit([['1', '2', 'e']], ['e' => 32]);
check_org($repeat['1'] > $single['1'] && $repeat['1'] - 1500 < 2 * ($single['1'] - 1500) + 1, 'Repeated pairs count less than new opponents');
check_org(smash_org_fit([], []) === [] && smash_org_reason('not_singles') === 'doubles' && smash_org_reason('under_20_entrants') === 'small' && smash_org_reason('online_or_unknown') === 'format', 'Empty fit and capture reasons');
check_org(smash_org_day('2026-10-05 05:59:59.000000') === '2026-10-04' && smash_org_day('2026-10-05 06:00:00') === '2026-10-05', 'Guatemala day');
echo "Organizer contracts passed.\n";

$db = getenv('SMASH_SCHEMA_TEST_DB');
if (!$db) { echo "SQL tests skipped: no disposable database configured.\n"; exit; }
if (strpos($db, 'smash_schema_test') !== 0 || !in_array(getenv('SMASH_SCHEMA_TEST_HOST') ?: '127.0.0.1', ['127.0.0.1', 'localhost'], true)) throw new RuntimeException('Disposable database required');
$pdo = smash_database_connect(['host' => '127.0.0.1', 'port' => (int)(getenv('SMASH_SCHEMA_TEST_PORT') ?: 3306), 'name' => $db, 'user' => 'root', 'password' => getenv('SMASH_SCHEMA_TEST_PASSWORD')]);
$B = ORGANIZER_FIXTURE_BASE;
$clean = static function () use ($pdo) { organizer_fixture_clean($pdo); };
$now = gmmktime(18, 0, 0, 10, 7, 2026);
try {
    $clean();
    [$org, $co, $other, $twin] = organizer_fixture_seed($pdo);
    $owned = smash_org_tournament_ids($pdo, $org);
    check_org(count($owned) === 5 && !isset($owned[(string)($B + 5)]), 'Tournaments come from the start.gg creator, not from the profile interest');
    $view = smash_org_view($pdo, $org, '2098-10-04T06:00:00+00:00', $now, true);
    check_org($view['coorganizers'] === [] && $view['organizer'] === ['name' => 'Árena Xelá', 'slug' => 'arena-xela', 'publicEnabled' => false, 'topSize' => 15], 'Profile is created with a readable stable address, private by default');
    check_org($view['summary'] === ['eventsCounted' => 2, 'distinctPlayers' => 4, 'validSets' => 7, 'rankedPlayers' => 3, 'periodFrom' => '2026-08-30', 'periodTo' => '2026-09-27', 'cutDate' => '2098-10-04', 'isStale' => false],
        'Summary uses only this organizer\'s counting tournaments; DQ sets and other tournaments stay out');
    check_org(array_column($view['top'], 'alias') === ['Kenji', 'Vlad', 'Momo'] && array_column($view['top'], 'rank') === [1, 2, 3] && $view['rest'] === [], 'Order by points; one-set player does not appear');
    $kenji = $view['top'][0];
    check_org([$kenji['setsWon'], $kenji['setsLost'], $kenji['events'], $kenji['mainCharId']] === [4, 0, 2, null] && $kenji['points'] > 1500 && !isset($kenji['id']), 'Record ignores the loss in a tournament that does not count; no player id leaves');
    check_org($kenji['detail']['events'] === [['name' => 'Torneo 2', 'date' => '2026-09-27', 'url' => 'https://www.start.gg/tournament/torneo-2/event/singles', 'won' => 2, 'lost' => 0], ['name' => 'Torneo 1', 'date' => '2026-08-30', 'url' => 'https://www.start.gg/tournament/torneo-1/event/singles', 'won' => 2, 'lost' => 0]]
        && $kenji['detail']['opponents'] === [['alias' => 'Momo', 'won' => 2, 'lost' => 0], ['alias' => 'Vlad', 'won' => 2, 'lost' => 0]], 'Detail: tournaments newest first and opponents with their record');
    $by = []; foreach ($view['events'] as $e) $by[$e['name']] = $e;
    check_org(array_keys($by) === ['Torneo 2', 'Torneo 1', 'Torneo 3', 'Torneo 4', 'Torneo 6'], 'Newest first');
    check_org([$by['Torneo 1']['status'], $by['Torneo 1']['validSets'], $by['Torneo 1']['activePlayers'], $by['Torneo 1']['place'], $by['Torneo 1']['date'], $by['Torneo 1']['url']] === ['counts', 4, 24, 'Quetzaltenango', '2026-08-30', 'https://www.start.gg/tournament/torneo-1'], 'A counting tournament with its figures');
    check_org([$by['Torneo 3']['status'], $by['Torneo 3']['reason'], $by['Torneo 3']['validSets']] === ['excluded', 'doubles', null] && $by['Torneo 4']['reason'] === 'small' && $by['Torneo 4']['activePlayers'] === 12 && $by['Torneo 6']['reason'] === 'out_of_season' && $by['Torneo 2']['place'] === null, 'Why each excluded tournament does not count');

    // Settings.
    smash_org_settings($pdo, $org, ['topSize' => 5, 'publicEnabled' => true], $now);
    check_org(org_fails(static fn() => smash_org_settings($pdo, $org, ['topSize' => 7], $now), 'invalid_setting') && org_fails(static fn() => smash_org_settings($pdo, $org, ['publicEnabled' => 'yes'], $now), 'invalid_setting'), 'Only 5, 10 or 15 and a real boolean');
    $pdo->exec("UPDATE organizer_profiles SET top_size = 5 WHERE user_id = $org");
    check_org(smash_org_profile($pdo, $twin, $now, true)['slug'] === 'arena-xela-2', 'Same name, different address');

    // Public address.
    $yes = static fn(string $id) => true; $no = static fn(string $id) => false;
    $public = smash_org_public($pdo, 'arena-xela', null, $yes, $now);
    check_org($public['state'] === 'open' && $public['organizer'] === ['name' => 'Árena Xelá', 'topSize' => 5] && count($public['top']) === 3 && !isset($public['top'][0]['detail']) && count($public['events']) === 2 && !isset($public['events'][0]['id']), 'Public view: top, summary and tournaments used; no detail, no account');
    check_org(smash_org_public($pdo, 'arena-xela', null, $no, $now) === ['state' => 'paused'] && smash_org_public($pdo, 'arena-xela-2', null, $yes, $now) === ['state' => 'disabled']
        && smash_org_public($pdo, 'nadie', null, $yes, $now) === ['state' => 'missing'] && smash_org_public($pdo, "x' OR 1=1", null, $yes, $now) === ['state' => 'missing'], 'Closed states never show a top');
    smash_org_settings($pdo, $twin, ['publicEnabled' => true], $now);
    check_org(smash_org_public($pdo, 'arena-xela-2', null, $yes, $now) === ['state' => 'paused'], 'No counting tournament: nothing to show');
    check_org(smash_org_view($pdo, $org, '2098-10-11T06:00:00+00:00', $now, false)['summary']['isStale'] === true, 'A newer public cut than SQL is announced as stale');

    // Co-organizers by one-use invitation.
    $token = smash_org_invite($pdo, $org, $now);
    check_org(preg_match('/\A[a-f0-9]{48}\z/', $token) === 1 && (int)$pdo->query("SELECT COUNT(*) FROM organizer_invites WHERE token_hash = '$token'")->fetchColumn() === 0, 'Only the hash of the code is stored');
    check_org(smash_org_invite_peek($pdo, $token, $now) === ['organizerId' => $org, 'name' => 'Árena Xelá'] && smash_org_invite_peek($pdo, $token, $now + SMASH_ORG_INVITE_AGE) === null && smash_org_invite_peek($pdo, ['x'], $now) === null, 'An invitation names the organizer and expires');
    check_org(org_fails(static fn() => smash_org_join($pdo, $org, $token, $now), 'invalid_invite_own'), 'Nobody joins their own team');
    check_org(smash_org_join($pdo, $co, $token, $now) === $org && org_fails(static fn() => smash_org_join($pdo, $other, $token, $now), 'invalid_invite'), 'One use');
    check_org(array_column(smash_org_contexts($pdo, $co), 'role') === ['owner', 'member'] && smash_org_contexts($pdo, $co)[1]['slug'] === 'arena-xela' && count(smash_org_contexts($pdo, $other)) === 1, 'The co-organizer can open the organizer\'s top; a stranger cannot');
    check_org(smash_org_members($pdo, $org) === [['id' => $co, 'name' => 'Coorganizador', 'since' => '2026-10-07']], 'Members list');
    check_org(smash_org_view($pdo, $org, null, $now, false)['coorganizers'] === ['Coorganizador'] && smash_org_public($pdo, 'arena-xela', null, $yes, $now)['coorganizers'] === ['Coorganizador'], 'Co-organizers are credited by name, also on the public page');
    $second = smash_org_invite($pdo, $org, $now); $third = smash_org_invite($pdo, $org, $now);
    check_org(smash_org_invite_peek($pdo, $second, $now) === null && smash_org_invite_peek($pdo, $third, $now) !== null, 'A new invitation replaces the previous one');
    smash_org_remove_member($pdo, $org, $co);
    check_org(smash_org_members($pdo, $org) === [] && org_fails(static fn() => smash_org_remove_member($pdo, $org, '1 OR 1=1'), 'invalid_member'), 'Removing a co-organizer');

    // Reviews.
    check_org(org_fails(static fn() => smash_org_claim($pdo, $org, $org, 'https://evil.example/tournament/torneo-5', $now), 'invalid_tournament_url') && org_fails(static fn() => smash_org_claim($pdo, $org, $org, 'https://www.start.gg/tournament/torneo-1/details', $now), 'invalid_already_yours'), 'Only start.gg tournaments that are not already yours');
    smash_org_claim($pdo, $org, $org, 'https://www.start.gg/tournament/Torneo-5/event/singles', $now);
    smash_org_claim($pdo, $org, $org, 'https://start.gg/tournament/desconocido', $now);
    check_org(org_fails(static fn() => smash_org_claim($pdo, $org, $org, 'https://www.start.gg/tournament/torneo-5', $now), 'invalid_already_sent'), 'No duplicate request');
    $view = smash_org_view($pdo, $org, null, $now, false); $by = []; foreach ($view['events'] as $e) $by[$e['name']] = $e;
    check_org($by['Torneo 5']['status'] === 'unconfirmed' && $by['Torneo 5']['review']['status'] === 'sent' && $by['Torneo 5']['validSets'] === null && $by['desconocido']['status'] === 'unconfirmed' && $by['desconocido']['id'] === null && $view['summary']['eventsCounted'] === 2, 'A requested tournament is listed as unconfirmed and does not count');
    $pending = smash_org_pending_claims($pdo);
    $mine = array_values(array_filter($pending, static fn($c) => $c['organizer'] === 'Árena Xelá'));
    check_org(count($mine) === 2 && $mine[0]['tournament'] === 'Torneo 5' && $mine[0]['inCatalog'] === true && $mine[1]['inCatalog'] === false, 'The owner sees what is waiting');
    check_org(org_fails(static fn() => smash_org_resolve($pdo, $other, $mine[1]['id'], true, '', $now), 'invalid_review_unknown_tournament') && org_fails(static fn() => smash_org_resolve($pdo, $other, $mine[1]['id'], false, ' ', $now), 'invalid_review_message'), 'Cannot approve an unknown tournament or reject without a reason');
    smash_org_resolve($pdo, $other, $mine[1]['id'], false, 'start.gg muestra a otra cuenta como dueña.', $now);
    smash_org_resolve($pdo, $other, $mine[0]['id'], true, null, $now);
    check_org(org_fails(static fn() => smash_org_resolve($pdo, $other, $mine[0]['id'], false, 'x', $now), 'invalid_review'), 'A resolved review is final');
    $view = smash_org_view($pdo, $org, null, $now, false); $by = []; foreach ($view['events'] as $e) $by[$e['name']] = $e;
    check_org($by['Torneo 5']['status'] === 'counts' && $by['Torneo 5']['review']['status'] === 'approved' && $view['summary']['eventsCounted'] === 3 && $view['summary']['validSets'] === 9 && $view['summary']['distinctPlayers'] === 5
        && $by['desconocido']['review'] === ['id' => $mine[1]['id'], 'status' => 'rejected', 'message' => 'start.gg muestra a otra cuenta como dueña.'], 'Approved tournament counts from then on; rejection carries the reason');
    $aliases = array_column($view['top'], 'alias'); sort($aliases);
    check_org($aliases === ['Ajeno', 'Kenji', 'Momo', 'Vlad'] && $view['top'][0]['alias'] === 'Ajeno' && $view['rest'] === [], 'The approved tournament\'s sets enter the fit: who beat the leaders is first');
    smash_org_claim($pdo, $org, $co, 'https://www.start.gg/tournament/desconocido', $now);
    check_org((string)$pdo->query("SELECT status FROM organizer_claims WHERE id = {$mine[1]['id']}")->fetchColumn() === 'sent', 'Asking again after a rejection reopens the same request');
    check_org(smash_org_view($pdo, $other, null, $now, true)['organizer']['slug'] !== null && smash_org_view($pdo, $co, null, $now, true)['organizer']['slug'] === null && smash_org_view($pdo, $co, null, $now, true)['top'] === [], 'No tournaments: no top and no address reserved');
    echo "Organizer SQL tests passed.\n";
} finally { $clean(); }
