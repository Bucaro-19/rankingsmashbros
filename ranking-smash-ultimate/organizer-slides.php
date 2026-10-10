<?php
declare(strict_types=1);
// Called ONLY after organizer-api's session, membership and viewer-premium/admin gate.
// Read existing context; never change a published ranking or call start.gg.
const SMASH_ORG_SLIDE_GAME_ROWS = 150000;

function smash_org_slide_context(PDO $pdo, array $cut, array $ledger, array $playerIds): array
{
    $eventIds = array_map('strval', array_keys($ledger['events']));
    if (!$eventIds || !$playerIds) return ['mains' => [], 'placements' => []];
    $snapshot = smash_org_rows($pdo, 'SELECT public_snapshot FROM cuts WHERE id = ?', [$cut['id']]);
    $public = $snapshot ? json_decode($snapshot[0]['public_snapshot'], true) : null;
    $captured = $public['characterCapturedAt'] ?? $public['generatedAt'] ?? $cut['generatedAt'];
    $at = (new DateTimeImmutable($captured, new DateTimeZone('UTC')))->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d H:i:s.u');
    $marks = smash_org_marks($eventIds);
    // Both singles entrants must still match the cut. Corrections, DQs and ambiguous
    // participant mappings cannot attribute a character to an old result.
    $rows = smash_org_rows($pdo, "SELECT g.id AS game_id, ep.player_id, c.id AS character_id, c.name, c.slug
        FROM cut_set_results r JOIN sets s ON s.id=r.set_id AND s.event_id=r.event_id
            AND s.status='completed' AND s.outcome_type='competitive' AND s.source_hash <=> r.source_hash
        JOIN set_slots sw ON sw.set_id=s.id AND sw.entrant_id=s.winner_entrant_id AND sw.is_dq=0 AND sw.score <=> r.winner_score
        JOIN entrant_players ew ON ew.entrant_id=sw.entrant_id AND ew.player_id=r.winner_id
        JOIN set_slots sl ON sl.set_id=s.id AND sl.entrant_id<>sw.entrant_id AND sl.is_dq=0 AND sl.score <=> r.loser_score
        JOIN entrant_players el ON el.entrant_id=sl.entrant_id AND el.player_id=r.loser_id
        JOIN games g ON g.set_id=s.id AND g.winner_entrant_id IN (sw.entrant_id,sl.entrant_id) AND g.synced_at<=?
        JOIN game_selections gs ON gs.game_id=g.id AND gs.set_id=s.id
        JOIN entrant_players ep ON ep.entrant_id=gs.entrant_id
        JOIN characters c ON c.id=gs.character_id
        WHERE r.cut_id=? AND r.scope='combined' AND r.event_id IN ($marks)
            AND ep.player_id IN (" . smash_org_marks($playerIds) . ")
            AND NOT EXISTS (SELECT 1 FROM entrant_players ex WHERE ex.entrant_id=sw.entrant_id AND ex.player_id<>ew.player_id)
            AND NOT EXISTS (SELECT 1 FROM entrant_players ex WHERE ex.entrant_id=sl.entrant_id AND ex.player_id<>el.player_id)
        ORDER BY g.id, ep.player_id, c.id LIMIT " . (SMASH_ORG_SLIDE_GAME_ROWS + 1), array_merge([$at, $cut['id']], $eventIds, $playerIds));
    if (count($rows) > SMASH_ORG_SLIDE_GAME_ROWS) throw new SmashOrganizerError('slide_context_limit');
    $picks = []; $catalog = [];
    foreach ($rows as $r) {
        $pid = (string)$r['player_id']; $cid = (string)$r['character_id'];
        $picks[$pid][(string)$r['game_id']][$cid] = true;
        $catalog[$cid] = ['characterId' => $cid, 'name' => $r['name'], 'slug' => $r['slug']];
    }
    $mains = [];
    foreach ($picks as $pid => $games) {
        $counts = [];
        foreach ($games as $characters) if (count($characters) === 1) {
            $cid = (string)array_key_first($characters); $counts[$cid] = ($counts[$cid] ?? 0) + 1;
        }
        $list = [];
        foreach ($counts as $cid => $n) if ((string)$cid !== '1746') $list[] = $catalog[$cid] + ['games' => $n];
        usort($list, static function (array $a, array $b): int { return $b['games'] <=> $a['games'] ?: strcmp($a['characterId'], $b['characterId']); });
        $mains[(string)$pid] = array_slice($list, 0, 3);
    }
    // A placement is supplied only when exactly one singles entry records it,
    // synchronized no later than this cut's captured context. No inferred placements.
    $placements = [];
    foreach (smash_org_rows($pdo, "SELECT ep.player_id, e.event_id, COUNT(*) AS entries, MIN(e.final_placement) AS placement
        FROM entrants e JOIN entrant_players ep ON ep.entrant_id=e.id
        WHERE e.event_id IN ($marks) AND ep.player_id IN (" . smash_org_marks($playerIds) . ")
            AND e.synced_at<=? AND NOT EXISTS (SELECT 1 FROM entrant_players ex WHERE ex.entrant_id=e.id AND ex.player_id<>ep.player_id)
        GROUP BY ep.player_id,e.event_id", array_merge($eventIds, $playerIds, [$at])) as $r) {
        if ((int)$r['entries'] === 1 && $r['placement'] !== null) $placements[(string)$r['player_id']][(string)$r['event_id']] = (int)$r['placement'];
    }
    return ['mains' => $mains, 'placements' => $placements];
}

function smash_org_slides(PDO $pdo, ?array $cut, array $ledger, array $top, array $profile, array $coorganizers, int $season): array
{
    $ids = array_map('strval', array_column($top, 'id'));
    $context = $cut === null ? ['mains' => [], 'placements' => []] : smash_org_slide_context($pdo, $cut, $ledger, $ids);
    $rank = []; $tags = [];
    foreach ($top as $row) { $rank[(string)$row['id']] = $row['rank']; $tags[(string)$row['id']] = $row['alias']; }
    $records = []; $wins = []; $played = [];
    foreach ($ledger['sets'] as $set) {
        $w = (string)$set['winner']; $l = (string)$set['loser']; $event = (string)$set['event_id'];
        foreach ([[$w,$l,'won'],[$l,$w,'lost']] as $side) if (isset($rank[$side[0]])) {
            $played[$side[0]][$event] = true;
            if (isset($rank[$side[1]]) && $rank[$side[1]] <= 5) {
                if (!isset($records[$side[0]])) $records[$side[0]] = ['won' => 0, 'lost' => 0];
                $records[$side[0]][$side[2]]++;
            }
        }
        if (isset($rank[$w], $rank[$l])) $wins[$w][$event][$l] = ($wins[$w][$event][$l] ?? 0) + 1;
    }
    $names = [];
    if ($ledger['events']) foreach (smash_org_rows($pdo, 'SELECT event_id,event_name FROM cut_events WHERE cut_id=? AND scope=\'combined\' AND event_id IN (' . smash_org_marks($ledger['events']) . ')', array_merge([$cut['id']], array_map('strval', array_keys($ledger['events'])))) as $e) $names[(string)$e['event_id']] = $e['event_name'];
    $multiples = [];
    foreach ($ledger['events'] as $e) $multiples[$e['tournamentId']] = ($multiples[$e['tournamentId']] ?? 0) + 1;
    $players = [];
    foreach ($top as $row) {
        $pid = (string)$row['id']; $results = [];
        foreach ($ledger['events'] as $eid => $event) {
            if (!isset($played[$pid][$eid], $context['placements'][$pid][$eid])) continue;
            $notable = [];
            foreach ($wins[$pid][$eid] ?? [] as $other => $n) $notable[] = ['rank' => $rank[$other], 'tag' => $tags[$other], 'won' => $n, 'mainSlug' => $context['mains'][$other][0]['slug'] ?? null];
            usort($notable, static function (array $a, array $b): int { return $a['rank'] <=> $b['rank']; });
            $results[] = ['name' => $event['name'] . ($multiples[$event['tournamentId']] > 1 ? ' · ' . ($names[$eid] ?? 'Singles') : ''),
                'date' => $event['date'], 'placement' => $context['placements'][$pid][$eid], 'wins' => array_slice($notable, 0, 4)];
        }
        usort($results, static function (array $a, array $b): int { return $a['placement'] <=> $b['placement'] ?: strcmp($b['date'], $a['date']) ?: strcmp($a['name'], $b['name']); });
        $players[] = ['rank' => $row['rank'], 'tag' => $row['alias'], 'mains' => $context['mains'][$pid] ?? [],
            'setsWon' => $row['setsWon'], 'setsLost' => $row['setsLost'], 'vsTop5' => $records[$pid] ?? null, 'results' => $results];
    }
    return ['schemaVersion' => 1, 'organizer' => ['name' => $profile['name'], 'topSize' => $profile['topSize'], 'coorganizers' => $coorganizers,
        'seasonYear' => $season, 'cutDate' => $cut === null ? null : smash_org_day($cut['generatedAt'])], 'players' => $players];
}
