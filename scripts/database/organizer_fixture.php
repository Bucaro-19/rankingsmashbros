<?php
declare(strict_types=1);
// Invented organizer, players, tournaments and sets for the organizer-top tests. Local disposable database only.
const ORGANIZER_FIXTURE_BASE = 8999500000;

function organizer_fixture_clean(PDO $pdo): void
{
    $B = ORGANIZER_FIXTURE_BASE;
    $r = "BETWEEN $B AND " . ($B + 99999);
    $pdo->exec("DELETE FROM cut_set_results WHERE event_id $r");
    $pdo->exec("DELETE FROM cut_events WHERE event_id $r");
    $pdo->exec("DELETE FROM cuts WHERE source_hash = '" . str_repeat('e', 64) . "'");
    foreach (['set_slots' => 'set_id', 'sets' => 'id', 'entrant_players' => 'entrant_id', 'entrants' => 'id', 'events' => 'id', 'tournaments' => 'id', 'tournament_catalog' => 'tournament_id'] as $table => $column) $pdo->exec("DELETE FROM $table WHERE $column $r");
    $pdo->exec("DELETE FROM users WHERE startgg_user_id $r");
    $pdo->exec("DELETE FROM players WHERE id $r");
}

// Returns the user ids: organizer, co-organizer, another account and a namesake.
function organizer_fixture_seed(PDO $pdo): array
{
    $B = ORGANIZER_FIXTURE_BASE;
    $user = $pdo->prepare('INSERT INTO users (startgg_user_id, display_name) VALUES (?, ?)');
    foreach ([[1, 'Árena Xelá'], [2, 'Coorganizador'], [3, 'Otra cuenta'], [4, 'Arena Xela']] as $u) $user->execute([$B + $u[0], $u[1]]);
    $uid = static fn(int $n) => (string)$pdo->query('SELECT id FROM users WHERE startgg_user_id=' . ($B + $n))->fetchColumn();
    [$org, $co, $other, $twin] = [$uid(1), $uid(2), $uid(3), $uid(4)];
    foreach ([1 => 'Kenji', 2 => 'Vlad', 3 => 'Momo', 4 => 'Solo', 5 => 'Ajeno'] as $n => $tag) $pdo->exec("INSERT INTO players (id, tag) VALUES (" . ($B + $n) . ", '$tag')");
    // T1 and T2 count; T3 is doubles (catalog only); T4 was captured but is not in the cut (12 active);
    // T5 belongs to another account; T6 is last season's.
    foreach ([1, 2, 4, 5] as $t) {
        $pdo->exec("INSERT INTO tournaments (id, name, slug) VALUES (" . ($B + $t) . ", 'Torneo $t', 'tournament/torneo-$t')");
        $pdo->exec("INSERT INTO events (id, tournament_id, name, active_players) VALUES (" . ($B + 10 + $t) . ", " . ($B + $t) . ", 'Singles', " . ($t === 4 ? 12 : 24) . ")");
    }
    $catalog = $pdo->prepare('INSERT INTO tournament_catalog (tournament_id, event_id, owner_startgg_user_id, tournament_name, slug, starts_at, city, event_name, entrants, reason, captured_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)');
    foreach ([[1, 11, 1, '2026-08-30 20:00:00', 'Quetzaltenango', 26, null], [2, 12, 1, '2026-09-27 20:00:00', null, 25, null], [3, 13, 1, '2026-08-30 20:00:00', 'Quetzaltenango', 16, 'not_singles'],
        [4, 14, 1, '2026-06-28 20:00:00', 'Quetzaltenango', 21, null], [5, 15, 3, '2026-07-12 20:00:00', 'Huehuetenango', 31, null], [6, 16, 1, '2025-12-20 20:00:00', null, 28, 'outside_window']] as $c) {
        $catalog->execute([$B + $c[0], $B + $c[1], $B + $c[2], 'Torneo ' . $c[0], 'tournament/torneo-' . $c[0], $c[3], $c[4], 'Singles', $c[5], $c[6], '2026-10-04 06:00:00']);
    }
    // One entrant per player and event; sets as [event, winner, loser].
    $set = 0;
    $play = static function (int $event, int $winner, int $loser, string $outcome = 'competitive') use ($pdo, $B, &$set) {
        $set++; $e = $B + $event; $ids = [];
        foreach ([$winner, $loser] as $p) {
            $ids[] = $en = $B + $event * 100 + $p;
            $pdo->exec("INSERT IGNORE INTO entrants (id, event_id, name) VALUES ($en, $e, 'x')");
            $pdo->exec("INSERT IGNORE INTO entrant_players (entrant_id, player_id) VALUES ($en, " . ($B + $p) . ")");
        }
        $sid = $B + 5000 + $set;
        $pdo->exec("INSERT INTO sets (id, event_id, status, outcome_type, winner_entrant_id) VALUES ($sid, $e, 'completed', '$outcome', {$ids[0]})");
        $pdo->exec("INSERT INTO set_slots (set_id, slot_index, event_id, entrant_id) VALUES ($sid, 0, $e, {$ids[0]}), ($sid, 1, $e, {$ids[1]})");
    };
    foreach ([[11, 1, 2], [11, 1, 3], [11, 2, 3], [11, 3, 4], [12, 1, 2], [12, 2, 3], [12, 1, 3], [14, 4, 1], [15, 5, 1], [15, 5, 2]] as $s) $play($s[0], $s[1], $s[2]);
    $play(11, 4, 1, 'dq');
    $pdo->exec("INSERT INTO cuts (generated_at, season_year, season_label, method_version, schema_version, public_snapshot, source_hash, status) VALUES ('2098-10-04 06:00:00', 2026, 'Prueba', 'BT-PRUEBA', 3, '{}', '" . str_repeat('e', 64) . "', 'published')");
    $cut = (string)$pdo->lastInsertId();
    foreach ([[11, '2026-08-30', 24], [12, '2026-09-27', 24], [15, '2026-07-12', 24]] as $e) $pdo->exec("INSERT INTO cut_events (cut_id, scope, event_id, tournament_name, event_name, event_date, active_players, url) VALUES ($cut, 'combined', " . ($B + $e[0]) . ", 'Torneo " . ($e[0] - 10) . "', 'Singles', '{$e[1]}', {$e[2]}, 'https://www.start.gg/tournament/torneo-" . ($e[0] - 10) . "/event/singles')");

    // Admitted results are an immutable ledger, distinct from live context and DQs.
    $pdo->exec("INSERT INTO cut_set_results (cut_id, scope, set_id, event_id, winner_id, loser_id, winner_tag, loser_tag)
        SELECT $cut, 'combined', s.id, s.event_id, w.player_id, l.player_id, pw.tag, pl.tag
        FROM sets s JOIN cut_events ce ON ce.cut_id=$cut AND ce.scope='combined' AND ce.event_id=s.event_id
        JOIN set_slots sw ON sw.set_id=s.id AND sw.entrant_id=s.winner_entrant_id
        JOIN set_slots sl ON sl.set_id=s.id AND sl.entrant_id<>s.winner_entrant_id
        JOIN entrant_players w ON w.entrant_id=sw.entrant_id JOIN entrant_players l ON l.entrant_id=sl.entrant_id
        JOIN players pw ON pw.id=w.player_id JOIN players pl ON pl.id=l.player_id WHERE s.outcome_type='competitive'");

    return [$org, $co, $other, $twin];
}

// A field larger than Top 15, with two admitted sets per added player.
function organizer_fixture_more_players(PDO $pdo): void
{
    $B = ORGANIZER_FIXTURE_BASE; $event = $B + 11;
    $cut = (string)$pdo->query("SELECT MAX(id) FROM cuts WHERE source_hash='" . str_repeat('e', 64) . "'")->fetchColumn();
    for ($n = 20; $n < 38; $n++) {
        $player = $B + $n; $entrant = $B + 1100 + $n;
        $pdo->exec("INSERT INTO players (id,tag) VALUES ($player,'Campo $n')");
        $pdo->exec("INSERT INTO entrants (id,event_id,name) VALUES ($entrant,$event,'Campo $n')");
        $pdo->exec("INSERT INTO entrant_players (entrant_id,player_id) VALUES ($entrant,$player)");
    }
    for ($n = 20; $n < 38; $n++) {
        $other = $n === 37 ? 20 : $n + 1; $sid = $B + 8000 + $n;
        $winner = $B + 1100 + $n; $loser = $B + 1100 + $other;
        $pdo->exec("INSERT INTO sets (id,event_id,status,outcome_type,winner_entrant_id) VALUES ($sid,$event,'completed','competitive',$winner)");
        $pdo->exec("INSERT INTO set_slots (set_id,slot_index,event_id,entrant_id) VALUES ($sid,0,$event,$winner),($sid,1,$event,$loser)");
        $pdo->exec("INSERT INTO cut_set_results (cut_id,scope,set_id,event_id,winner_id,loser_id,winner_tag,loser_tag) VALUES ($cut,'combined',$sid,$event," . ($B+$n) . "," . ($B+$other) . ",'Campo $n','Campo $other')");
    }
}
