<?php
declare(strict_types=1);
require __DIR__.'/../../ranking-smash-ultimate/bracket-store.php';
require __DIR__.'/../../ranking-smash-ultimate/mi-torneo-live.php';

function live_assert(bool $value, string $label): void {
    if (!$value) throw new RuntimeException($label);
}
function live_side(string $entrant, string $player): array {
    return ['id' => $entrant, 'name' => 'Jugador '.$player, 'participants' => [['player' => ['id' => $player]]]];
}
function live_match(string $id, ?array $opponent, ?string $winner = null, int $at = 0): array {
    return ['id' => $id, 'state' => $winner === null ? 1 : 3, 'winnerId' => $winner,
        'completedAt' => $at ?: null, 'fullRoundText' => 'Ronda de prueba', 'displayScore' => null,
        'slots' => [['entrant' => live_side('10', '20')], ['entrant' => $opponent]]];
}
function live_source(array $sets, int &$calls, bool $registered = true): callable {
    return static function (string $query, array $args) use ($sets, &$calls, $registered): array {
        $calls++;
        if ($query === MT_LIVE_ENTRY) {
            live_assert($args === ['event' => '1687524', 'user' => '40'], 'Registration uses the linked user');
            return ['event' => ['id' => '1687524', 'type' => 1, 'videogame' => ['id' => 1386],
                'userEntrant' => $registered ? live_side('10', '20') : null]];
        }
        live_assert($query === MT_LIVE_SETS && $args['entrant'] === '10' && $args['event'] === '1687524',
            'Sets use the verified entrant and event');
        $size = $args['size'];
        return ['event' => ['id' => '1687524', 'sets' => [
            'pageInfo' => ['total' => count($sets), 'totalPages' => (int)ceil(count($sets) / $size)],
            'nodes' => array_slice($sets, ($args['page'] - 1) * $size, $size),
        ]]];
    };
}
function live_read_fixture(array $sets, int &$calls, bool $registered = true, string $player = '20'): array {
    return mt_live_read(live_source($sets, $calls, $registered), '1687524', '40', $player);
}

$calls = 0;
$before = live_read_fixture([live_match('101', live_side('11', '21'))], $calls);
live_assert($calls === 2 && $before['nextSet']['opponent']['playerId'] === '21', 'Original rival');

$calls = 0;
$result = live_match('101', live_side('11', '21'), '10', 1790000000);
$pending = live_read_fixture([$result, live_match('102', null)], $calls);
live_assert($pending['lastResult']['won'] && $pending['status'] === 'opponent_pending'
    && $pending['nextSet']['opponent'] === null, 'Reported win with an unassigned next rival');
$confirmed = live_read_fixture([$result, live_match('102', live_side('12', '22'))], $calls);
live_assert($confirmed['status'] === 'opponent_confirmed' && $confirmed['nextSet']['opponent']['playerId'] === '22', 'Updated rival');

$calls = 0;
$loss = live_read_fixture([live_match('101', live_side('11', '21'), '11', 1790000000)], $calls);
live_assert($loss['lastResult']['won'] === false && $loss['status'] === 'awaiting_assignment', 'No inferred elimination');
$bye = live_read_fixture([live_match('101', null, '10', 1790000000)], $calls);
live_assert($bye['lastResult'] === null, 'A bye is not a reported fight');
$many = live_read_fixture([live_match('101', live_side('11', '21')), live_match('102', live_side('12', '22'))], $calls);
live_assert($many['status'] === 'several_assigned' && $many['nextSet'] === null, 'Do not guess the order of two assigned sets');

$calls = 0;
$hidden = live_read_fixture([], $calls, false);
live_assert($calls === 1 && $hidden['status'] === 'registration_unverified', 'No sets query when registration is unverified');
try {
    live_read_fixture([], $calls, true, '99');
    throw new RuntimeException('Accepted a mismatched participant');
} catch (UnexpectedValueException $error) {
    live_assert($error->getMessage() === 'live_entry_mismatch', 'Reject an entrant for another player');
}
$calls = 0;
$foreign = live_match('101', live_side('11', '21'));
$foreign['slots'][0]['entrant'] = live_side('12', '22');
try {
    live_read_fixture([$foreign], $calls);
    throw new RuntimeException('Accepted a set belonging to someone else');
} catch (UnexpectedValueException $error) {
    live_assert($error->getMessage() === 'live_set_not_for_entrant', 'Do not trust the provider filter alone');
}
$all = [];
for ($i = 0; $i < 25; $i++) $all[] = live_match((string)(200+$i), live_side('11', '21'), '10', 1790000000+$i);
$calls = 0;
$pages = live_read_fixture(array_slice($all, 0, 13), $calls);
live_assert($calls === 3 && $pages['lastResult']['id'] === '212', 'Second page read and completed result verified');
$calls = 0;
$limited = live_read_fixture($all, $calls);
live_assert($calls === 2 && $limited['status'] === 'coverage_incomplete' && $limited['lastResult'] === null, 'Never publish partial coverage');
echo "Mi torneo live contracts: OK\n";
