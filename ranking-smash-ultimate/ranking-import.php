<?php
declare(strict_types=1);

// Included by the private CLI worker only. No HTTP entry point or connection on inclusion.
final class SmashRankingError extends RuntimeException {
    public $reason;
    public function __construct(string $reason) { $this->reason = $reason; parent::__construct($reason); }
}
function sr_require(bool $ok, string $reason = 'package_invalid'): void {
    if (!$ok) throw new SmashRankingError($reason);
}
function sr_json($value): string {
    // The SQL transport admits integer/string/null/bool JSON, as emitted by the current exporter.
    // Reject floats instead of silently using a PHP/Python-dependent representation in hashes.
    if ($value instanceof stdClass) {
        $values = get_object_vars($value); ksort($values, SORT_STRING); $parts = [];
        foreach ($values as $key => $item) $parts[] = sr_json((string)$key) . ':' . sr_json($item);
        return '{' . implode(',', $parts) . '}';
    }
    if (is_array($value)) return '[' . implode(',', array_map('sr_json', $value)) . ']';
    sr_require(!is_float($value));
    return json_encode($value, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_LINE_TERMINATORS);
}
function sr_id($value): int {
    sr_require((is_int($value) || is_string($value)) && preg_match('/\A[1-9][0-9]*\z/D', (string)$value) === 1);
    sr_require(strlen((string)$value) < 19 || (strlen((string)$value) === 19 && strcmp((string)$value, (string)PHP_INT_MAX) <= 0));
    return (int)$value;
}
function sr_int($value, int $min = 0, int $max = 4294967295): int {
    sr_require(is_int($value) && $value >= $min && $value <= $max); return $value;
}
function sr_text($value, int $max, bool $optional = false): void {
    if ($optional && $value === null) return;
    sr_require(is_string($value) && trim($value) !== '' && mb_strlen($value, 'UTF-8') <= $max);
}
function sr_at($value): string {
    sr_require(is_string($value) && preg_match('/\A\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?(?:Z|[+-]\d\d:\d\d)\z/D', $value) === 1);
    $d = new DateTimeImmutable($value); $errors = DateTimeImmutable::getLastErrors();
    sr_require(($errors === false || (!$errors['warning_count'] && !$errors['error_count'])) && (int)$d->format('Y') >= 1970);
    return $d->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d H:i:s.u');
}
function sr_index(array $rows): array {
    $out = [];
    foreach ($rows as $row) { $id = sr_id($row['id']); sr_require(!isset($out[$id])); $out[$id] = $row; }
    return $out;
}
function sr_view(array $v, bool $local): void {
    sr_require($v['schemaVersion'] === 3 && $v['rankingComputed'] === true && $v['rankingCoverage'] === 'all_eligible'
        && $v['status'] === ($local ? 'local_pilot' : 'international_pilot') && $v['rankingScope'] === ($local ? 'guatemala' : 'combined'));
    sr_at($v['generatedAt']); sr_at($v['characterCapturedAt']); sr_int($v['seasonYear'], 1970, 9999);
    sr_text($v['seasonLabel'], 80); sr_text($v['methodVersion'], 80);
    $events = sr_index($v['events']); $players = sr_index($v['players']); $seen = []; $ledger = []; $valid = [];
    sr_require(count($players) > 0 && $v['counts']['players'] === count($players)
        && $v['counts']['eligiblePlayers'] === count($players) && $v['counts']['top100'] === min(100, count($players))
        && $v['counts']['events'] === count($events) && count($events) > 0);
    foreach ($events as $id => $e) {
        sr_int($e['validSets'], 1); sr_int($e['activePlayers']); sr_text($e['name'], 255); sr_text($e['eventName'], 255);
        sr_require(preg_match('/\A\d{4}-\d\d-\d\d\z/D', $e['date']) === 1);
        sr_require(!$local || $e['country'] === 'GT');
    }
    foreach ($v['results'] as $r) {
        $sid = sr_id($r['id']); $eid = sr_id($r['eventId']);
        sr_require(!isset($seen[$sid]) && isset($events[$eid]) && count($r['playerIds']) === 2 && count($r['playerTags']) === 2);
        $seen[$sid] = true; $a = sr_id($r['playerIds'][0]); $b = sr_id($r['playerIds'][1]); sr_require($a !== $b);
        sr_require(!$local || $r['country'] === 'GT'); $valid[$eid] = ($valid[$eid] ?? 0) + 1;
        foreach ([$a, $b] as $i => $pid) {
            if (!isset($ledger[$pid][$eid])) $ledger[$pid][$eid] = ['wins' => 0, 'losses' => 0];
            $ledger[$pid][$eid][$i === 0 ? 'wins' : 'losses']++;
        }
    }
    // Results are the ranked players' ledger, not every competitive set in each event.
    sr_require(array_sum(array_column($events, 'validSets')) === $v['counts']['sets'] && $v['counts']['sets'] > 0);
    foreach ($events as $id => $e) sr_require(($valid[$id] ?? 0) <= $e['validSets']);
    foreach ($v['players'] as $i => $p) {
        $id = sr_id($p['id']); sr_require($p['rank'] === $i + 1); sr_text($p['tag'], 100);
        sr_int($p['rating'], -2147483648, 2147483647);
        foreach (['wins', 'losses', 'events', 'sets'] as $key) sr_int($p[$key]);
        if (($p['previousRank'] ?? null) !== null) { sr_int($p['previousRank'], 1); sr_require(sr_at($v['previousCutAt']) < sr_at($v['generatedAt'])); }
        $activity = []; $wins = 0; $losses = 0; $months = [];
        foreach ($p['activity']['events'] as $a) {
            $eid = sr_id($a['id']); sr_require(isset($events[$eid]) && !isset($activity[$eid]));
            sr_int($a['wins']); sr_int($a['losses']);
            $activity[$eid] = ['wins' => $a['wins'], 'losses' => $a['losses']];
            $wins += $a['wins']; $losses += $a['losses']; $months[substr($events[$eid]['date'], 0, 7)] = true;
        }
        $actual = $ledger[$id] ?? []; ksort($actual); ksort($activity); $months = array_keys($months); sort($months);
        sr_require($activity === $actual && count($activity) === $p['events'] && $wins === $p['wins'] && $losses === $p['losses']
            && $p['sets'] === $wins + $losses && $p['activity']['months'] === $months);
        $coverage = $p['mainCoverage'];
        foreach (['setsQueried', 'setsWithSelections', 'gamesWithSelections', 'ambiguousGames'] as $key) sr_int($coverage[$key]);
        sr_require($coverage['setsQueried'] === $p['sets'] && $coverage['setsWithSelections'] <= $p['sets']);
        $mains = []; $sum = 0; $previous = null;
        foreach ($p['mains'] as $m) {
            $mid = sr_id($m['characterId']); sr_require(!isset($mains[$mid])); $mains[$mid] = true;
            sr_text($m['name'], 255); sr_int($m['games'], 1); $sum += $m['games'];
            if ($previous !== null) sr_require($previous['games'] > $m['games'] || ($previous['games'] === $m['games'] && strcmp($previous['characterId'], $m['characterId']) < 0));
            $previous = $m;
        }
        sr_require($sum === $coverage['gamesWithSelections']);
    }
}
function sr_character_ids(): array {
    // Same catalog as the installed seed; no API calls, including real Random ID.
    preg_match_all('/"characterId":\s*"([0-9]+)"/', file_get_contents(__DIR__ . '/characters.js'), $matches);
    return array_fill_keys(array_merge(array_map('intval', $matches[1]), [1746]), true);
}
function sr_context_set_ids(array $p, array $tables): array {
    $admitted = array_fill_keys(array_map('sr_id', array_column($p['events'], 'id')), true);
    $ranked = []; foreach (sr_scopes($p) as $v) foreach ($v['players'] as $r) $ranked[sr_id($r['id'])] = true;
    $entrants = []; foreach ($tables['entrant_players'] as $r) if (isset($ranked[$r['player_id']])) $entrants[$r['entrant_id']] = true;
    $relevant = []; foreach ($tables['set_slots'] as $r) if (isset($entrants[$r['entrant_id']])) $relevant[$r['set_id']] = true;
    $out = []; foreach ($tables['sets'] as $r) if ($r['outcome_type'] !== 'competitive' || (isset($admitted[$r['event_id']], $relevant[$r['id']]))) $out[] = $r['id'];
    sort($out, SORT_NUMERIC); return $out;
}
function sr_game_context(array $c, array $ids, array $slots): void {
    $t = $c['entities']; $covered = $c['gameContextSetIds'] ?? null;
    sr_require($covered === sr_context_set_ids($c['public'], $t));
    $games = sr_index($t['games']); $numbers = []; $seen = []; $known = sr_character_ids();
    foreach ($t['games'] as $g) {
        $keys = array_keys($g); sort($keys); sr_require($keys === ['game_number','id','set_id','stage_id','synced_at','winner_entrant_id']);
        $sid = sr_id($g['set_id']); $winner = sr_id($g['winner_entrant_id']);
        sr_require(in_array($sid, $covered, true) && ($ids['sets'][$sid]['outcome_type'] ?? null) === 'competitive');
        sr_require(in_array($winner, [$slots["$sid:0"]['entrant_id'], $slots["$sid:1"]['entrant_id']], true));
        $number = sr_int($g['game_number'], 1, 65535); $key = "$sid:$number"; sr_require(!isset($numbers[$key])); $numbers[$key] = true;
        sr_require($g['stage_id'] === null && $g['synced_at'] === sr_at($c['public']['characterCapturedAt']));
    }
    foreach ($t['game_selections'] as $r) {
        $keys = array_keys($r); sort($keys); sr_require($keys === ['character_id','entrant_id','game_id','set_id']);
        $gid = sr_id($r['game_id']); $sid = sr_id($r['set_id']); $en = sr_id($r['entrant_id']); $cid = sr_id($r['character_id']);
        sr_require(isset($games[$gid]) && $games[$gid]['set_id'] === $sid && isset($known[$cid]));
        sr_require(in_array($en, [$slots["$sid:0"]['entrant_id'], $slots["$sid:1"]['entrant_id']], true));
        $key = "$gid:$en"; sr_require(!isset($seen[$key])); $seen[$key] = true;
    }
    $players = []; foreach ($t['entrant_players'] as $r) $players[$r['entrant_id']] = $r['player_id'];
    foreach (sr_scopes($c['public']) as $v) {
        $events = array_fill_keys(array_map('sr_id', array_column($v['events'], 'id')), true); $counts = [];
        foreach ($t['game_selections'] as $r) if (isset($events[$ids['sets'][$r['set_id']]['event_id']])) {
            $pid = $players[$r['entrant_id']]; $cid = $r['character_id']; $counts[$pid][$cid] = ($counts[$pid][$cid] ?? 0) + 1;
        }
        foreach ($v['players'] as $r) {
            $wanted = []; foreach ($r['mains'] as $m) $wanted[sr_id($m['characterId'])] = $m['games'];
            $actual = $counts[sr_id($r['id'])] ?? []; ksort($actual); ksort($wanted); sr_require($actual === $wanted);
        }
    }
}

function sr_catalog_columns(): string {
    return 'tournament_id event_id owner_startgg_user_id tournament_name slug starts_at city event_name entrants reason captured_at';
}
function sr_catalog(array $c): void {
    $rows = $c['tournamentCatalog'] ?? null;
    sr_require(is_array($rows)); $events = []; $tournaments = [];
    $columns = explode(' ', sr_catalog_columns()); sort($columns);
    foreach ($rows as $row) {
        sr_require(is_array($row)); $keys = array_keys($row); sort($keys); sr_require($keys === $columns);
        foreach (['tournament_id', 'event_id', 'owner_startgg_user_id'] as $key) {
            if ($key === 'owner_startgg_user_id' && $row[$key] === null) continue;
            sr_require(is_int($row[$key])); sr_id($row[$key]);
        }
        sr_require(!isset($events[$row['event_id']])); $events[$row['event_id']] = true;
        sr_text($row['tournament_name'], 255); sr_text($row['city'], 120, true); sr_text($row['event_name'], 255, true);
        $slug = $row['slug'];
        sr_require($slug === null || (is_string($slug) && strlen($slug) <= 255 && strpos($slug, 'tournament/') === 0
            && preg_match('/\A[\x20-\x7e]+\z/D', $slug) === 1));
        if ($row['entrants'] !== null) sr_int($row['entrants']);
        sr_require(in_array($row['reason'], [null, 'not_singles', 'online_or_unknown', 'unfinished_event', 'under_20_entrants', 'outside_window'], true));
        foreach (['starts_at', 'captured_at'] as $key) {
            $value = $row[$key]; if ($key === 'starts_at' && $value === null) continue;
            sr_require(is_string($value) && preg_match('/\A\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{6}\z/D', $value) === 1);
            sr_require(sr_at(str_replace(' ', 'T', $value) . 'Z') === $value);
        }
        sr_require($row['captured_at'] === sr_at($c['capturedAt']));
        $identity = array_map(static function ($key) use ($row) { return $row[$key]; }, ['owner_startgg_user_id', 'tournament_name', 'slug', 'starts_at', 'city']);
        sr_require(!isset($tournaments[$row['tournament_id']]) || $tournaments[$row['tournament_id']] === $identity);
        $tournaments[$row['tournament_id']] = $identity;
    }
}
function sr_package(string $raw): array {
    sr_require(strlen($raw) <= 32 * 1024 * 1024);
    $obj = json_decode($raw, false, 512, JSON_THROW_ON_ERROR);
    sr_require($obj instanceof stdClass && sr_json($obj) === $raw); // Reject duplicate keys, floats, lossy IDs and noncanonical encoding.
    sr_require(array_keys(get_object_vars($obj)) === ['content', 'sha256'] && is_string($obj->sha256)
        && hash_equals(hash('sha256', sr_json($obj->content)), $obj->sha256));
    $p = json_decode($raw, true, 512, JSON_THROW_ON_ERROR); $c = $p['content']; $v = $c['public']; $tables = $c['entities'];
    sr_require(in_array($c['packageVersion'], [1, 2, 3], true) && $c['capturedAt'] === $v['generatedAt']);
    if ($c['packageVersion'] === 3) {
        // Preserve the JSON array/object distinction, including an empty catalog.
        sr_require(is_array($obj->content->tournamentCatalog ?? null)); sr_catalog($c);
    } else sr_require(!array_key_exists('tournamentCatalog', $c));
    sr_view($v, false); sr_view($v['localRanking'], true);
    foreach (['generatedAt', 'seasonYear', 'seasonLabel', 'methodVersion', 'eligibilityRules'] as $key)
        sr_require(($v[$key] ?? null) === ($v['localRanking'][$key] ?? null));
    $gt = array_values(array_filter($v['events'], static function ($e) { return $e['country'] === 'GT'; }));
    $gtIds = array_keys(sr_index($gt)); $localIds = array_keys(sr_index($v['localRanking']['events'])); sort($gtIds); sort($localIds); sr_require($gtIds === $localIds);
    $wantedNames = ['entrant_players', 'entrants', 'events', 'players', 'set_slots', 'sets', 'tournaments'];
    if ($c['packageVersion'] >= 2) { $wantedNames[] = 'games'; $wantedNames[] = 'game_selections'; }
    $names = array_keys($tables); sort($names); sort($wantedNames); sr_require($names === $wantedNames);
    $ids = []; foreach (['players', 'tournaments', 'events', 'entrants', 'sets'] as $table) $ids[$table] = sr_index($tables[$table]);
    foreach ($tables['players'] as $r) { sr_text($r['tag'], 100); sr_text($r['known_as'] ?? null, 100, true); sr_text($r['country_basis'] ?? null, 255, true); }
    $links = []; $slots = [];
    foreach ($tables['entrant_players'] as $r) {
        $en = sr_id($r['entrant_id']); $pl = sr_id($r['player_id']); $key = "$en:$pl";
        sr_require(!isset($links[$key]) && isset($ids['entrants'][$en], $ids['players'][$pl])); $links[$key] = true;
    }
    foreach ($tables['set_slots'] as $r) {
        $sid = sr_id($r['set_id']); $i = sr_int($r['slot_index'], 0, 1); $key = "$sid:$i";
        sr_require(!isset($slots[$key]) && isset($ids['sets'][$sid])); $slots[$key] = $r;
    }
    foreach ($tables['events'] as $r) sr_require(isset($ids['tournaments'][sr_id($r['tournament_id'])]));
    foreach ($tables['entrants'] as $r) sr_require(isset($ids['events'][sr_id($r['event_id'])]));
    foreach ($tables['sets'] as $r) {
        $sid = sr_id($r['id']); $eid = sr_id($r['event_id']); sr_require(isset($ids['events'][$eid])); $pair = [];
        for ($i = 0; $i < 2; $i++) {
            $slot = $slots["$sid:$i"] ?? null; sr_require($slot !== null && $slot['event_id'] === $eid);
            if ($slot['entrant_id'] !== null) sr_require(($ids['entrants'][sr_id($slot['entrant_id'])]['event_id'] ?? null) === $eid);
            $pair[] = $slot['entrant_id'];
        }
        sr_require($r['winner_entrant_id'] === null || in_array($r['winner_entrant_id'], $pair, true));
    }
    foreach ([$v, $v['localRanking']] as $view) {
        foreach ($view['events'] as $e) sr_require(isset($ids['events'][sr_id($e['id'])]));
        foreach ($view['players'] as $r) sr_require(isset($ids['players'][sr_id($r['id'])]));
        foreach ($view['results'] as $r) {
            $sid = sr_id($r['id']); $s = $ids['sets'][$sid] ?? null;
            sr_require($s !== null && $s['event_id'] === sr_id($r['eventId']) && $s['display_score'] === $r['score'] && $s['outcome_type'] === 'competitive');
            $winner = $s['winner_entrant_id']; $pair = [$slots["$sid:0"]['entrant_id'], $slots["$sid:1"]['entrant_id']];
            sr_require($winner !== null && $pair[0] !== $pair[1]); $loser = $pair[0] === $winner ? $pair[1] : $pair[0];
            sr_require(isset($links[$winner . ':' . sr_id($r['playerIds'][0])], $links[$loser . ':' . sr_id($r['playerIds'][1])]));
        }
    }
    if ($c['packageVersion'] >= 2) sr_game_context($c, $ids, $slots);
    $p['_public_json'] = sr_json($obj->content->public);
    return $p;
}
function sr_query(PDO $db, string $sql, array $values = []): array {
    $s = $db->prepare($sql); $s->execute($values); return $s->fetchAll(PDO::FETCH_NUM);
}
function sr_insert(PDO $db, string $table, string $columns, array $rows, bool $keep = false): void {
    $cols = explode(' ', $columns);
    $sql = 'INSERT INTO `' . $table . '` (`' . implode('`,`', $cols) . '`) VALUES (' . implode(',', array_fill(0, count($cols), '?')) . ')';
    if ($keep) $sql .= ' ON DUPLICATE KEY UPDATE `' . $cols[0] . '`=`' . $cols[0] . '`';
    $s = $db->prepare($sql);
    foreach ($rows as $r) $s->execute(array_map(static function ($k) use ($r) { return $r[$k] ?? null; }, $cols));
}
function sr_scopes(array $public): array { return ['combined' => $public, 'guatemala' => $public['localRanking']]; }
function sr_equal_rows(array $found, array $wanted): void {
    // PDO/MySQL types vary; normalize numeric scalars, preserve NULL and compare duplicates as well.
    $normalize = static function ($rows) {
        $out = []; foreach ($rows as $r) $out[] = json_encode(array_map(static function ($v) { return $v === null ? null : (string)$v; }, $r), JSON_THROW_ON_ERROR);
        sort($out, SORT_STRING); return $out;
    };
    sr_require($normalize($found) === $normalize($wanted), 'parity_failed');
}
function sr_parity(PDO $db, array $public, int $cut, string $publicJson): void {
    $snapshot = sr_query($db, 'SELECT public_snapshot FROM cuts WHERE id=?', [$cut])[0][0];
    sr_require(sr_json(json_decode($snapshot, false, 512, JSON_THROW_ON_ERROR)) === $publicJson, 'parity_failed');
    foreach (sr_scopes($public) as $scope => $v) {
        $wanted = []; $mains = []; $events = []; $results = [];
        foreach ($v['players'] as $p) {
            $c = $p['mainCoverage']; $at = ($p['previousRank'] ?? null) !== null ? sr_at($v['previousCutAt']) : null;
            $wanted[] = [sr_id($p['id']), $p['tag'], $p['rank'], $p['rating'], $p['wins'], $p['losses'], $p['events'], $p['previousRank'] ?? null, $at,
                $c['setsQueried'], $c['setsWithSelections'], $c['gamesWithSelections'], $c['ambiguousGames']];
            foreach ($p['mains'] as $m) $mains[] = [sr_id($p['id']), sr_id($m['characterId']), $m['games']];
        }
        foreach ($v['events'] as $e) $events[] = [sr_id($e['id']), $e['name'], $e['eventName'], $e['date'], $e['country'], $e['activePlayers'], $e['url']];
        foreach ($v['results'] as $r) $results[] = [sr_id($r['id']), sr_id($r['eventId']), sr_id($r['playerIds'][0]), sr_id($r['playerIds'][1]), $r['playerTags'][0], $r['playerTags'][1], $r['score'], null, null];
        sr_equal_rows(sr_query($db, 'SELECT player_id,player_tag,rank_position,rating,wins,losses,events_count,previous_rank,previous_cut_at,sets_queried,sets_with_selections,games_with_selections,ambiguous_games FROM rankings WHERE cut_id=? AND scope=?', [$cut, $scope]), $wanted);
        sr_equal_rows(sr_query($db, 'SELECT player_id,character_id,games FROM player_characters WHERE cut_id=? AND scope=?', [$cut, $scope]), $mains);
        sr_equal_rows(sr_query($db, 'SELECT event_id,tournament_name,event_name,event_date,country_code,active_players,url FROM cut_events WHERE cut_id=? AND scope=?', [$cut, $scope]), $events);
        sr_equal_rows(sr_query($db, 'SELECT set_id,event_id,winner_id,loser_id,winner_tag,loser_tag,display_score,winner_score,loser_score FROM cut_set_results WHERE cut_id=? AND scope=?', [$cut, $scope]), $results);
    }
}
function sr_context_rows(PDO $db, string $table, string $columns, array $ids, string $idColumn = "set_id"): array {
    $out = [];
    foreach (array_chunk($ids, 500) as $batch) $out = array_merge($out, sr_query($db,
        'SELECT `' . implode('`,`', explode(' ', $columns)) . '` FROM `' . $table . '` WHERE `' . $idColumn . '` IN (' . implode(',', array_fill(0, count($batch), '?')) . ')', $batch));
    return $out;
}
function sr_replace_game_context(PDO $db, array $c): void {
    if ($c['packageVersion'] === 1) return;
    $t = $c['entities']; $covered = $c['gameContextSetIds'];
    $owners = array_column(sr_context_rows($db, 'games', 'id set_id', array_column($t['games'], 'id'), 'id'), 1, 0);
    foreach ($t['games'] as $r) sr_require(!isset($owners[$r['id']]) || (int)$owners[$r['id']] === $r['set_id'], 'game_identity_conflict');
    $wanted = []; foreach ($t['set_slots'] as $r) $wanted[$r['set_id']][] = $r['entrant_id'];
    $actual = []; foreach (sr_context_rows($db, 'set_slots', 'set_id entrant_id', $covered) as $r) $actual[$r[0]][] = $r[1] === null ? null : (int)$r[1];
    $sets = sr_index($t['sets']);
    foreach ($covered as $sid) if ($sets[$sid]['outcome_type'] === 'competitive') {
        $a = $actual[$sid] ?? []; $b = $wanted[$sid]; sort($a); sort($b); sr_require($a === $b, 'set_slots_changed');
    }
    foreach (array_chunk($covered, 500) as $batch) {
        $placeholders = implode(',', array_fill(0, count($batch), '?'));
        sr_query($db, 'DELETE FROM game_selections WHERE set_id IN (' . $placeholders . ')', $batch);
        sr_query($db, 'DELETE FROM games WHERE set_id IN (' . $placeholders . ')', $batch);
    }
    foreach (['games' => 'id set_id game_number winner_entrant_id stage_id synced_at',
              'game_selections' => 'game_id set_id entrant_id character_id'] as $table => $cols) {
        sr_insert($db, $table, $cols, $t[$table]);
        $expected = []; foreach ($t[$table] as $r) $expected[] = array_map(static function ($k) use ($r) { return $r[$k]; }, explode(' ', $cols));
        sr_equal_rows(sr_context_rows($db, $table, $cols, $covered), $expected);
    }
}

function sr_catalog_plan(PDO $db, array $c): array {
    if ($c['packageVersion'] !== 3) return ['status' => 'not_in_package', 'rows' => 0];
    $count = count($c['tournamentCatalog']);
    if (!sr_query($db, "SELECT version FROM schema_migrations WHERE version='005_organizer_tops'"))
        return ['status' => 'migration_missing', 'rows' => $count];
    sr_require(sr_query($db, "SELECT ENGINE FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name='tournament_catalog'") === [['InnoDB']], 'schema_invalid');
    $columns = array_column(sr_query($db, 'SHOW COLUMNS FROM tournament_catalog'), 0);
    sr_require(!array_diff(explode(' ', sr_catalog_columns()), $columns), 'schema_invalid');
    return ['status' => 'ready', 'rows' => $count];
}
function sr_replace_catalog(PDO $db, array $c, array &$plan): void {
    if ($plan['status'] !== 'ready') return;
    $db->exec('DELETE FROM tournament_catalog');
    sr_insert($db, 'tournament_catalog', sr_catalog_columns(), $c['tournamentCatalog']);
    $columns = explode(' ', sr_catalog_columns());
    $expected = array_map(static function ($row) use ($columns) {
        return array_map(static function ($key) use ($row) { return $row[$key]; }, $columns);
    }, $c['tournamentCatalog']);
    sr_equal_rows(sr_query($db, 'SELECT ' . implode(',', $columns) . ' FROM tournament_catalog'), $expected);
    $plan['status'] = 'replaced';
}
function sr_import(PDO $db, array $package, bool $apply = false): array {
    sr_require(!$db->inTransaction(), 'transaction_already_active');
    $c = $package['content']; $p = $c['public']; $identity = [sr_at($p['generatedAt']), $p['seasonYear'], $p['methodVersion']];
    $lock = 'smash-ranking-import-v1'; sr_require((int)sr_query($db, 'SELECT GET_LOCK(?,0)', [$lock])[0][0] === 1, 'import_busy');
    try {
        sr_require(sr_query($db, "SELECT version FROM schema_migrations WHERE version='001_accounts_competition'") === [['001_accounts_competition']], 'schema_invalid');
        $columns = [
            'players' => 'id tag known_as country_code country_basis profile_url synced_at',
            'tournaments' => 'id name slug country_code url synced_at',
            'events' => 'id tournament_id name videogame_id entrant_size starts_at registered_entrants active_players url synced_at',
            'entrants' => 'id event_id name competitive_sets final_placement synced_at',
            'entrant_players' => 'entrant_id player_id registered_tag',
            'sets' => 'id event_id source_state status outcome_type winner_entrant_id display_score completed_at source_updated_at synced_at source_hash',
            'set_slots' => 'set_id slot_index event_id entrant_id score is_dq'];
        $engines = array_column(sr_query($db, 'SELECT TABLE_NAME,ENGINE FROM information_schema.tables WHERE table_schema=DATABASE()'), 1, 0);
        foreach (array_merge(array_keys($columns), ['cuts', 'cut_events', 'cut_set_results', 'rankings', 'player_characters', 'characters', 'games', 'game_selections']) as $t)
            sr_require(($engines[$t] ?? null) === 'InnoDB', 'schema_invalid');
        $db->exec("SET time_zone='+00:00'"); $db->exec("SET SESSION sql_mode=CONCAT(@@sql_mode,',STRICT_TRANS_TABLES')");
        $catalog = sr_catalog_plan($db, $c);
        $existing = sr_query($db, 'SELECT id,source_hash,status FROM cuts WHERE generated_at=? AND season_year=? AND method_version=?', $identity);
        if ($existing) {
            sr_require($existing[0][1] === $package['sha256'] && $existing[0][2] === 'published', 'cut_conflict');
            sr_parity($db, $p, (int)$existing[0][0], $package['_public_json']);
            if ($catalog['status'] === 'ready') $catalog['status'] = 'not_reapplied';
            return ['status' => 'already_imported', 'cutId' => (int)$existing[0][0], 'catalog' => $catalog];
        }
        $cuts = sr_query($db, 'SELECT generated_at,status FROM cuts ORDER BY generated_at'); $moments = [];
        foreach ($cuts as $cut) { sr_require($cut[1] === 'published', 'unfinished_cut_present'); $moments[] = $cut[0]; }
        sr_require(!$moments || $identity[0] > max($moments), 'older_than_stored_cut');
        foreach (sr_scopes($p) as $view) if ($moments && ($view['previousCutAt'] ?? null) !== null)
            sr_require(in_array(sr_at($view['previousCutAt']), $moments, true), 'previous_cut_missing');
        $known = array_flip(array_column(sr_query($db, 'SELECT id FROM characters'), 0));
        foreach (sr_scopes($p) as $view) foreach ($view['players'] as $r) foreach ($r['mains'] as $m)
            sr_require(isset($known[sr_id($m['characterId'])]), 'character_missing');
        foreach ($c['entities']['game_selections'] ?? [] as $r) sr_require(isset($known[sr_id($r['character_id'])]), 'character_missing');
        if (!$apply) return ['status' => 'validated_no_writes', 'catalog' => $catalog];
        $db->beginTransaction();
        $s = $db->prepare('INSERT INTO cuts(generated_at,season_year,method_version,season_label,schema_version,character_captured_at,public_snapshot,source_hash) VALUES (?,?,?,?,?,?,?,?)');
        $s->execute(array_merge($identity, [$p['seasonLabel'], $p['schemaVersion'], sr_at($p['characterCapturedAt']), $package['_public_json'], $package['sha256']]));
        $cut = (int)$db->lastInsertId();
        foreach ($columns as $table => $cols) {
            if (in_array($table, ['events', 'entrants', 'sets'], true)) {
                $parent = $table === 'events' ? 'tournament_id' : 'event_id';
                $parents = array_column(sr_query($db, 'SELECT id,`' . $parent . '` FROM `' . $table . '`'), 1, 0);
                foreach ($c['entities'][$table] as $r) sr_require(!isset($parents[$r['id']]) || (int)$parents[$r['id']] === $r[$parent], 'identity_conflict');
            }
            if ($table === 'entrant_players') {
                $links = []; foreach (sr_query($db, 'SELECT entrant_id,player_id FROM entrant_players') as $r) $links[$r[0]][] = (int)$r[1];
                foreach ($c['entities'][$table] as $r) sr_require(!isset($links[$r['entrant_id']]) || $links[$r['entrant_id']] === [$r['player_id']], 'identity_conflict');
            }
            sr_insert($db, $table, $cols, $c['entities'][$table], true);
        }
        sr_replace_game_context($db, $c);
        sr_replace_catalog($db, $c, $catalog);
        $events = []; $results = []; $rankings = []; $mains = []; $hashes = array_column($c['entities']['sets'], 'source_hash', 'id');
        foreach (sr_scopes($p) as $scope => $v) {
            foreach ($v['events'] as $e) $events[] = ['cut_id' => $cut, 'scope' => $scope, 'event_id' => sr_id($e['id']), 'tournament_name' => $e['name'], 'event_name' => $e['eventName'], 'event_date' => $e['date'], 'country_code' => $e['country'], 'active_players' => $e['activePlayers'], 'url' => $e['url']];
            foreach ($v['results'] as $r) $results[] = ['cut_id' => $cut, 'scope' => $scope, 'set_id' => sr_id($r['id']), 'event_id' => sr_id($r['eventId']), 'winner_id' => sr_id($r['playerIds'][0]), 'loser_id' => sr_id($r['playerIds'][1]), 'winner_tag' => $r['playerTags'][0], 'loser_tag' => $r['playerTags'][1], 'display_score' => $r['score'], 'source_hash' => $hashes[sr_id($r['id'])]];
            foreach ($v['players'] as $r) {
                $id = sr_id($r['id']); $previous = null; $at = ($r['previousRank'] ?? null) !== null ? sr_at($v['previousCutAt']) : null;
                if ($at !== null) {
                    $found = sr_query($db, "SELECT c.id,r.rank_position FROM cuts c JOIN rankings r ON r.cut_id=c.id WHERE c.generated_at=? AND c.season_year=? AND c.method_version=? AND c.status='published' AND r.scope=? AND r.player_id=?", [$at, $p['seasonYear'], $p['methodVersion'], $scope, $id]);
                    if ($found) { sr_require(count($found) === 1 && (int)$found[0][1] === $r['previousRank'], 'previous_rank_conflict'); $previous = (int)$found[0][0]; }
                }
                $coverage = $r['mainCoverage'];
                $rankings[] = ['cut_id' => $cut, 'scope' => $scope, 'player_id' => $id, 'player_tag' => $r['tag'], 'rank_position' => $r['rank'], 'previous_rank' => $r['previousRank'] ?? null, 'previous_cut_at' => $at, 'previous_cut_id' => $previous, 'rating' => $r['rating'], 'wins' => $r['wins'], 'losses' => $r['losses'], 'events_count' => $r['events'], 'sets_queried' => $coverage['setsQueried'], 'sets_with_selections' => $coverage['setsWithSelections'], 'games_with_selections' => $coverage['gamesWithSelections'], 'ambiguous_games' => $coverage['ambiguousGames']];
                foreach ($r['mains'] as $m) $mains[] = ['cut_id' => $cut, 'scope' => $scope, 'player_id' => $id, 'character_id' => sr_id($m['characterId']), 'games' => $m['games']];
            }
        }
        sr_insert($db, 'cut_events', 'cut_id scope event_id tournament_name event_name event_date country_code active_players url', $events);
        sr_insert($db, 'cut_set_results', 'cut_id scope set_id event_id winner_id loser_id winner_tag loser_tag display_score source_hash', $results);
        sr_insert($db, 'rankings', 'cut_id scope player_id player_tag rank_position previous_rank previous_cut_at previous_cut_id rating wins losses events_count sets_queried sets_with_selections games_with_selections ambiguous_games', $rankings);
        sr_insert($db, 'player_characters', 'cut_id scope player_id character_id games', $mains);
        sr_parity($db, $p, $cut, $package['_public_json']); sr_query($db, "UPDATE cuts SET status='published' WHERE id=?", [$cut]); $db->commit();
        return ['status' => 'imported', 'cutId' => $cut, 'catalog' => $catalog];
    } catch (Throwable $e) { if ($db->inTransaction()) $db->rollBack(); throw $e; }
    finally { sr_query($db, 'SELECT RELEASE_LOCK(?)', [$lock]); }
}
