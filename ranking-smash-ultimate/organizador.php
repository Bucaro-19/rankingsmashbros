<?php
declare(strict_types=1);

// Library only. Apache blocks direct access; nothing is read or written on inclusion.
// Organizer tops: a separate ranking fitted only with the sets of one organizer's tournaments.
// It never changes the national ranking, and paying never changes points or positions here either.
// Whose tournament it is comes from start.gg (tournament_catalog) or from a review the site owner
// approved by hand; the «Organizador» interest of a profile decides nothing.

const SMASH_ORG_SIZES = [5, 10, 15];
// A player appears with at least this many valid sets in the tournaments that count.
const SMASH_ORG_MIN_SETS = 2;
const SMASH_ORG_INVITE_AGE = 604800;
const SMASH_ORG_MAX_MEMBERS = 10;
const SMASH_ORG_MAX_OPEN_CLAIMS = 10;
// Capture reasons (discover.py) and the ones derived here, most informative first.
const SMASH_ORG_REASONS = ['small', 'no_sets', 'unfinished', 'excluded', 'format', 'out_of_season', 'doubles'];

final class SmashOrganizerError extends RuntimeException
{
    public $reason;
    public function __construct(string $reason) { $this->reason = $reason; parent::__construct('No se pudo completar la operación del organizador.'); }
}

// Whether one account has premium running. Each account pays for itself: a co-organizer needs their own
// premium to open the tab, and the public address depends on the organizer's. Needs premium.php and
// stats.php loaded by the caller. $config null: premium is off, only the site owner passes.
function smash_org_premium(PDO $pdo, string $accountId, ?array $config, int $now): array
{
    if (smash_stats_is_owner($pdo, $accountId)) return ['active' => true, 'expiredAt' => null];
    $status = $config === null ? null : smash_premium_status($pdo, $accountId, $config['live'], $now);
    $active = $status !== null && $status['premium']; $end = $status['currentPeriodEnd'] ?? null;
    return ['active' => $active, 'expiredAt' => !$active && $end !== null && strtotime($end) <= $now ? $end : null];
}

function smash_org_rows(PDO $pdo, string $sql, array $params = []): array
{
    try { $q = $pdo->prepare($sql); $q->execute($params); return $q->fetchAll(PDO::FETCH_ASSOC); }
    catch (PDOException $error) { throw new SmashOrganizerError('organizer_read_failed'); }
}

function smash_org_write(PDO $pdo, string $sql, array $params = []): int
{
    try { $q = $pdo->prepare($sql); $q->execute($params); return $q->rowCount(); }
    catch (PDOException $error) { throw new SmashOrganizerError('organizer_write_failed'); }
}

function smash_org_marks(array $values): string
{
    return implode(',', array_fill(0, count($values), '?'));
}

function smash_org_stamp(int $now): string
{
    return gmdate('Y-m-d H:i:s', $now);
}

// Guatemala calendar day (UTC−6, no daylight saving) of a stored UTC instant.
function smash_org_day(?string $utc): ?string
{
    if ($utc === null) return null;
    $time = strtotime(substr($utc, 0, 19) . ' UTC');
    return $time === false ? null : gmdate('Y-m-d', $time - 21600);
}

// The organizers this account can open: itself first, then the ones that added it as co-organizer.
function smash_org_contexts(PDO $pdo, string $userId): array
{
    $own = smash_org_rows($pdo, 'SELECT u.id, u.display_name, p.slug FROM users u LEFT JOIN organizer_profiles p ON p.user_id = u.id WHERE u.id = ? AND u.status = ?', [$userId, 'active']);
    if (!$own) throw new SmashOrganizerError('login_required');
    $list = [['id' => (string)$own[0]['id'], 'name' => $own[0]['display_name'], 'slug' => $own[0]['slug'], 'role' => 'owner']];
    foreach (smash_org_rows($pdo, 'SELECT u.id, u.display_name, p.slug FROM organizer_members m JOIN users u ON u.id = m.organizer_user_id AND u.status = ?
        LEFT JOIN organizer_profiles p ON p.user_id = u.id WHERE m.member_user_id = ? ORDER BY m.created_at, u.id', ['active', $userId]) as $row) {
        $list[] = ['id' => (string)$row['id'], 'name' => $row['display_name'], 'slug' => $row['slug'], 'role' => 'member'];
    }
    return $list;
}

// Tournaments start.gg registers under this account, plus the ones a review approved.
function smash_org_tournament_ids(PDO $pdo, string $organizerId): array
{
    $ids = [];
    foreach (smash_org_rows($pdo, 'SELECT DISTINCT c.tournament_id FROM tournament_catalog c JOIN users u ON u.startgg_user_id = c.owner_startgg_user_id WHERE u.id = ?', [$organizerId]) as $row) $ids[(string)$row['tournament_id']] = 'owner';
    foreach (smash_org_rows($pdo, "SELECT tournament_id FROM organizer_claims WHERE organizer_user_id = ? AND status = 'approved' AND tournament_id IS NOT NULL", [$organizerId]) as $row) {
        if (!isset($ids[(string)$row['tournament_id']])) $ids[(string)$row['tournament_id']] = 'review';
    }
    return $ids;
}

function smash_org_cut(PDO $pdo): ?array
{
    $rows = smash_org_rows($pdo, "SELECT id, generated_at, season_year FROM cuts WHERE status = 'published' ORDER BY generated_at DESC, id DESC LIMIT 1");
    return $rows ? ['id' => (string)$rows[0]['id'], 'generatedAt' => (string)$rows[0]['generated_at'], 'seasonYear' => (int)$rows[0]['season_year']] : null;
}

function smash_org_reason(?string $capture): string
{
    if ($capture === 'not_singles') return 'doubles';
    if ($capture === 'online_or_unknown') return 'format';
    if ($capture === 'unfinished_event') return 'unfinished';
    if ($capture === 'outside_window') return 'out_of_season';
    if ($capture !== null && strpos($capture, 'under_') === 0) return 'small';
    return 'excluded';
}

// Regularized Bradley-Terry over the given sets: same prior, scale and repeated-pair rule as the
// national method (rank.py), with the event weight it uses when there is no TTS table.
// $sets: [winner, loser, eventId]; $active: active players per event.
function smash_org_fit(array $sets, array $active): array
{
    $pairs = [];
    foreach ($sets as $set) { $key = strcmp($set[0], $set[1]) < 0 ? $set[0] . '|' . $set[1] : $set[1] . '|' . $set[0]; $pairs[$key] = ($pairs[$key] ?? 0) + 1; }
    $games = []; $logits = []; $degrees = [];
    foreach ($sets as $set) {
        $key = strcmp($set[0], $set[1]) < 0 ? $set[0] . '|' . $set[1] : $set[1] . '|' . $set[0];
        $weight = min(2.0, sqrt(max(1, (int)($active[$set[2]] ?? 0)) / 32)) / sqrt($pairs[$key]);
        $games[] = [$set[0], $set[1], $weight];
        foreach ([$set[0], $set[1]] as $id) { $logits[$id] = 0.0; $degrees[$id] = ($degrees[$id] ?? 0.0) + $weight; }
    }
    $prior = 0.5;
    for ($iteration = 0; $iteration < 700 && $games; $iteration++) {
        $gradient = [];
        foreach ($logits as $id => $value) $gradient[$id] = -$prior * $value;
        foreach ($games as $game) {
            $difference = max(-30.0, min(30.0, $logits[$game[0]] - $logits[$game[1]]));
            $surprise = $game[2] / (1 + exp($difference));
            $gradient[$game[0]] += $surprise; $gradient[$game[1]] -= $surprise;
        }
        $maximum = 0.0;
        foreach ($logits as $id => $value) {
            $change = 1.2 * $gradient[$id] / ($degrees[$id] + 2 * $prior);
            $logits[$id] = $value + $change; $maximum = max($maximum, abs($change));
        }
        if ($maximum < 1e-7) break;
    }
    $ratings = [];
    foreach ($logits as $id => $value) $ratings[$id] = (int)round(1500 + 400 / log(10) * $value);
    return $ratings;
}

// Everything the top needs from SQL for one set of tournaments, at the latest published cut.
function smash_org_ledger(PDO $pdo, array $tournamentIds, ?array $cut, bool $withCharacters = true): array
{
    $empty = ['events' => [], 'sets' => [], 'tags' => [], 'characters' => []];
    if (!$tournamentIds || $cut === null) return $empty;
    $events = [];
    foreach (smash_org_rows($pdo, "SELECT ce.event_id, e.tournament_id, ce.tournament_name, ce.event_date, ce.active_players, ce.url
        FROM cut_events ce JOIN events e ON e.id = ce.event_id
        WHERE ce.cut_id = ? AND ce.scope = 'combined' AND ce.active_players >= 20 AND e.tournament_id IN (" . smash_org_marks($tournamentIds) . ') ORDER BY ce.event_date, ce.event_id',
        array_merge([$cut['id']], $tournamentIds)) as $row) {
        $events[(string)$row['event_id']] = ['id' => (string)$row['event_id'], 'tournamentId' => (string)$row['tournament_id'], 'name' => $row['tournament_name'],
            'date' => (string)$row['event_date'], 'activePlayers' => (int)$row['active_players'], 'url' => $row['url']];
    }
    if (!$events) return $empty;
    $ids = array_keys($events); $marks = smash_org_marks($ids);
    // Only results admitted in the published cut. Live corrections/new sets must not
    // change a top labelled with an older cut; small-event context is never admitted.
    $sets = smash_org_rows($pdo, "SELECT set_id AS id, event_id, winner_id AS winner, loser_id AS loser
        FROM cut_set_results WHERE cut_id = ? AND scope = 'combined' AND event_id IN ($marks) ORDER BY set_id",
        array_merge([$cut['id']], $ids));
    $players = [];
    foreach ($sets as $set) { $players[(string)$set['winner']] = true; $players[(string)$set['loser']] = true; }
    $tags = [];
    if ($players) foreach (smash_org_rows($pdo, 'SELECT id, tag FROM players WHERE id IN (' . smash_org_marks($players) . ')', array_map('strval', array_keys($players))) as $row) $tags[(string)$row['id']] = (string)$row['tag'];
    $characters = [];
    if ($withCharacters) foreach (smash_org_rows($pdo, "SELECT ep.player_id, gs.character_id, COUNT(*) AS games FROM game_selections gs
        JOIN cut_set_results r ON r.set_id = gs.set_id AND r.cut_id = ? AND r.scope = 'combined'
        JOIN entrant_players ep ON ep.entrant_id = gs.entrant_id
        WHERE r.event_id IN ($marks) GROUP BY ep.player_id, gs.character_id ORDER BY games DESC, gs.character_id", array_merge([$cut['id']], $ids)) as $row) {
        if (!isset($characters[(string)$row['player_id']])) $characters[(string)$row['player_id']] = (string)$row['character_id'];
    }
    return ['events' => $events, 'sets' => $sets, 'tags' => $tags, 'characters' => $characters];
}

// The ranking itself: every player with enough sets, best first, with the detail of each one.
function smash_org_ranking(array $ledger, bool $withIds = false): array
{
    $sets = []; $active = []; $stats = [];
    foreach ($ledger['sets'] as $set) {
        $winner = (string)$set['winner']; $loser = (string)$set['loser']; $event = (string)$set['event_id'];
        $sets[] = [$winner, $loser, $event];
        foreach ([[$winner, $loser, 'won'], [$loser, $winner, 'lost']] as $side) {
            $s = &$stats[$side[0]];
            if ($s === null) $s = ['won' => 0, 'lost' => 0, 'events' => [], 'opponents' => []];
            $s[$side[2]]++;
            if (!isset($s['events'][$event])) $s['events'][$event] = ['won' => 0, 'lost' => 0];
            $s['events'][$event][$side[2]]++;
            if (!isset($s['opponents'][$side[1]])) $s['opponents'][$side[1]] = ['won' => 0, 'lost' => 0];
            $s['opponents'][$side[1]][$side[2]]++;
            unset($s);
        }
    }
    foreach ($ledger['events'] as $id => $event) $active[$id] = $event['activePlayers'];
    $ratings = smash_org_fit($sets, $active);
    $rows = [];
    foreach ($stats as $id => $s) {
        if ($s['won'] + $s['lost'] < SMASH_ORG_MIN_SETS) continue;
        $events = [];
        foreach ($ledger['events'] as $eventId => $event) {
            if (isset($s['events'][$eventId])) $events[] = ['name' => $event['name'], 'date' => $event['date'], 'url' => $event['url'], 'won' => $s['events'][$eventId]['won'], 'lost' => $s['events'][$eventId]['lost']];
        }
        $opponents = [];
        foreach ($s['opponents'] as $other => $record) $opponents[] = ['alias' => $ledger['tags'][$other] ?? 'Sin alias', 'won' => $record['won'], 'lost' => $record['lost']];
        usort($opponents, static function (array $a, array $b): int { return [$b['won'] + $b['lost'], $b['won']] <=> [$a['won'] + $a['lost'], $a['won']] ?: strcasecmp($a['alias'], $b['alias']); });
        $rows[] = ['id' => (string)$id, 'alias' => $ledger['tags'][$id] ?? 'Sin alias', 'mainCharId' => $ledger['characters'][$id] ?? null,
            'points' => $ratings[$id], 'setsWon' => $s['won'], 'setsLost' => $s['lost'], 'events' => count($events),
            'detail' => ['events' => array_reverse($events), 'opponents' => array_slice($opponents, 0, 8)]];
    }
    usort($rows, static function (array $a, array $b): int {
        return [$b['points'], $b['setsWon'], $b['events']] <=> [$a['points'], $a['setsWon'], $a['events']] ?: (strcasecmp($a['alias'], $b['alias']) ?: strcmp($a['id'], $b['id']));
    });
    foreach ($rows as $index => &$row) { $row['rank'] = $index + 1; if (!$withIds) unset($row['id']); }
    unset($row);
    return ['rows' => $rows, 'distinctPlayers' => count($stats), 'validSets' => count($sets)];
}

// «Mis torneos»: every tournament of the organizer this season and why each one counts or not.
function smash_org_events(PDO $pdo, string $organizerId, array $owned, array $ledger, int $seasonYear): array
{
    $counting = []; $setsBy = [];
    foreach ($ledger['events'] as $event) $counting[$event['tournamentId']][] = $event;
    foreach ($ledger['sets'] as $set) { $t = $ledger['events'][(string)$set['event_id']]['tournamentId']; $setsBy[$t] = ($setsBy[$t] ?? 0) + 1; }
    $claims = [];
    foreach (smash_org_rows($pdo, 'SELECT id, tournament_slug, tournament_id, status, message FROM organizer_claims WHERE organizer_user_id = ? ORDER BY created_at DESC, id DESC', [$organizerId]) as $row) $claims[] = $row;
    $ids = array_keys($owned);
    foreach ($claims as $claim) if ($claim['tournament_id'] !== null && !isset($owned[(string)$claim['tournament_id']])) $ids[] = (string)$claim['tournament_id'];
    $catalog = [];
    if ($ids) foreach (smash_org_rows($pdo, 'SELECT c.tournament_id, c.event_id, c.tournament_name, c.slug, c.starts_at, c.city, c.entrants, c.reason, e.active_players,
        (SELECT COUNT(*) FROM sets s WHERE s.event_id = c.event_id AND s.outcome_type = ?) AS valid_sets
        FROM tournament_catalog c LEFT JOIN events e ON e.id = c.event_id WHERE c.tournament_id IN (' . smash_org_marks($ids) . ') ORDER BY c.tournament_id, c.event_id',
        array_merge(['competitive'], $ids)) as $row) $catalog[(string)$row['tournament_id']][] = $row;
    $list = []; $claimed = [];
    foreach ($claims as $claim) $claimed[$claim['tournament_id'] === null ? 'slug:' . $claim['tournament_slug'] : (string)$claim['tournament_id']] = $claim;
    foreach ($catalog as $tournamentId => $rows) {
        $first = $rows[0]; $date = smash_org_day($first['starts_at']);
        $claim = $claimed[$tournamentId] ?? null; unset($claimed[$tournamentId]);
        $review = $claim === null ? null : ['id' => (string)$claim['id'], 'status' => $claim['status'], 'message' => $claim['message']];
        $item = ['id' => $tournamentId, 'name' => $first['tournament_name'], 'date' => $date, 'place' => $first['city'],
            'url' => is_string($first['slug']) && preg_match('~\Atournament/[\w-]+\z~', $first['slug']) ? 'https://www.start.gg/' . $first['slug'] : null,
            'activePlayers' => null, 'validSets' => null, 'status' => 'excluded', 'reason' => null, 'review' => $review];
        if (!isset($owned[$tournamentId])) {
            // Asked for review and not (yet) approved: no figures, it is not this organizer's tournament.
            $item['status'] = 'unconfirmed';
            foreach ($rows as $row) if ($row['reason'] === null && $row['active_players'] !== null) $item['activePlayers'] = max((int)$item['activePlayers'], (int)$row['active_players']);
        } elseif (isset($counting[$tournamentId])) {
            $item['status'] = 'counts'; $item['validSets'] = $setsBy[$tournamentId] ?? 0;
            $item['activePlayers'] = array_sum(array_column($counting[$tournamentId], 'activePlayers'));
        } else {
            $best = null;
            foreach ($rows as $row) {
                if ($row['reason'] !== null) $reason = smash_org_reason($row['reason']);
                elseif ($date !== null && (int)substr($date, 0, 4) !== $seasonYear) $reason = 'out_of_season';
                elseif ((int)$row['valid_sets'] === 0) $reason = 'no_sets';
                elseif ($row['active_players'] !== null && (int)$row['active_players'] < 20) $reason = 'small';
                else $reason = 'excluded';
                if ($best === null || array_search($reason, SMASH_ORG_REASONS, true) < array_search($best, SMASH_ORG_REASONS, true)) {
                    $best = $reason; $item['activePlayers'] = $row['active_players'] === null ? ($row['entrants'] === null ? null : (int)$row['entrants']) : (int)$row['active_players'];
                }
            }
            $item['reason'] = $best;
        }
        $list[] = $item;
    }
    // Reviews of tournaments the weekly catalog does not know yet: only the address that was sent.
    foreach ($claimed as $claim) {
        $list[] = ['id' => null, 'name' => substr($claim['tournament_slug'], 11), 'date' => null, 'place' => null, 'url' => 'https://www.start.gg/' . $claim['tournament_slug'],
            'activePlayers' => null, 'validSets' => null, 'status' => 'unconfirmed', 'reason' => null,
            'review' => ['id' => (string)$claim['id'], 'status' => $claim['status'], 'message' => $claim['message']]];
    }
    usort($list, static function (array $a, array $b): int { return strcmp($b['date'] ?? '', $a['date'] ?? '') ?: strcasecmp((string)$a['name'], (string)$b['name']); });
    return $list;
}

function smash_org_slug(PDO $pdo, string $name): string
{
    $base = strtr(function_exists('mb_strtolower') ? mb_strtolower($name, 'UTF-8') : strtolower($name), ['á' => 'a', 'é' => 'e', 'í' => 'i', 'ó' => 'o', 'ú' => 'u', 'ü' => 'u', 'ñ' => 'n']);
    $base = substr(trim((string)preg_replace('/[^a-z0-9]+/', '-', $base), '-'), 0, 40);
    if ($base === '' || ctype_digit($base)) $base = 'organizador';
    for ($n = 1; $n < 200; $n++) {
        $slug = $n === 1 ? $base : $base . '-' . $n;
        if (!smash_org_rows($pdo, 'SELECT 1 FROM organizer_profiles WHERE slug = ?', [$slug])) return $slug;
    }
    throw new SmashOrganizerError('organizer_write_failed');
}

// The stable public address is fixed the first time the organizer has something to show.
function smash_org_profile(PDO $pdo, string $organizerId, int $now, bool $create): ?array
{
    $read = static function () use ($pdo, $organizerId): ?array {
        $rows = smash_org_rows($pdo, 'SELECT p.slug, p.public_enabled, p.top_size, u.display_name FROM organizer_profiles p JOIN users u ON u.id = p.user_id WHERE p.user_id = ?', [$organizerId]);
        return $rows ? ['name' => $rows[0]['display_name'] ?? 'Organizador', 'slug' => $rows[0]['slug'], 'publicEnabled' => (bool)$rows[0]['public_enabled'], 'topSize' => (int)$rows[0]['top_size']] : null;
    };
    $profile = $read();
    if ($profile !== null || !$create) return $profile;
    $user = smash_org_rows($pdo, 'SELECT display_name FROM users WHERE id = ?', [$organizerId]);
    if (!$user) throw new SmashOrganizerError('login_required');
    try {
        $q = $pdo->prepare('INSERT IGNORE INTO organizer_profiles (user_id, slug, created_at, updated_at) VALUES (?, ?, ?, ?)');
        $q->execute([$organizerId, smash_org_slug($pdo, (string)($user[0]['display_name'] ?? '')), smash_org_stamp($now), smash_org_stamp($now)]);
    } catch (PDOException $error) { throw new SmashOrganizerError('organizer_write_failed'); }
    return $read();
}

function smash_org_settings(PDO $pdo, string $organizerId, array $input, int $now): void
{
    if ((array_key_exists('publicEnabled', $input) && !is_bool($input['publicEnabled']))
        || (array_key_exists('topSize', $input) && !in_array($input['topSize'], SMASH_ORG_SIZES, true))) throw new SmashOrganizerError('invalid_setting');
    if (!$input) throw new SmashOrganizerError('invalid_setting');
    if (smash_org_profile($pdo, $organizerId, $now, true) === null) throw new SmashOrganizerError('organizer_write_failed');
    $changes = ['updated_at = ?']; $params = [smash_org_stamp($now)];
    if (array_key_exists('publicEnabled', $input)) { $changes[] = 'public_enabled = ?'; $params[] = $input['publicEnabled'] ? 1 : 0; }
    if (array_key_exists('topSize', $input)) { $changes[] = 'top_size = ?'; $params[] = $input['topSize']; }
    $params[] = $organizerId;
    smash_org_write($pdo, 'UPDATE organizer_profiles SET ' . implode(', ', $changes) . ' WHERE user_id = ?', $params);

}

// The whole view of one organizer: tournaments, top, summary. $publicCut is public.json's generatedAt.
function smash_org_view(PDO $pdo, string $organizerId, ?string $publicCut, int $now, bool $create, bool $withSlides = false): array
{
    $cut = smash_org_cut($pdo);
    $owned = smash_org_tournament_ids($pdo, $organizerId);
    $ledger = smash_org_ledger($pdo, array_map('strval', array_keys($owned)), $cut);
    $ranking = smash_org_ranking($ledger, $withSlides);
    $season = $cut['seasonYear'] ?? (int)gmdate('Y', $now - 21600);
    $events = smash_org_events($pdo, $organizerId, $owned, $ledger, $season);
    $profile = smash_org_profile($pdo, $organizerId, $now, $create && (bool)$events);
    if ($profile === null) {
        $user = smash_org_rows($pdo, 'SELECT display_name FROM users WHERE id = ?', [$organizerId]);
        $profile = ['name' => $user[0]['display_name'] ?? 'Organizador', 'slug' => null, 'publicEnabled' => false, 'topSize' => 15];
    }
    $slides = $withSlides ? smash_org_slides($pdo, $cut, $ledger, array_slice($ranking['rows'], 0, $profile['topSize']), $profile, array_column(smash_org_members($pdo, $organizerId), 'name'), $season) : null;
    if ($withSlides) foreach ($ranking['rows'] as &$row) { unset($row['id']); }
    unset($row);
    $dates = array_column($ledger['events'], 'date');
    $cutTime = $cut === null ? null : strtotime(substr($cut['generatedAt'], 0, 19) . ' UTC');
    $publicTime = $publicCut === null ? false : strtotime($publicCut);
    // Co-organizers are credited by name wherever the top is shown, whether or not they pay.
    $view = ['organizer' => $profile, 'coorganizers' => array_column(smash_org_members($pdo, $organizerId), 'name'), 'seasonYear' => $season, 'events' => $events,
        'top' => array_slice($ranking['rows'], 0, $profile['topSize']),
        'rest' => array_map(static function (array $row): array { unset($row['detail']); return $row; }, array_slice($ranking['rows'], $profile['topSize'])),
        'summary' => ['eventsCounted' => count(array_unique(array_column($ledger['events'], 'tournamentId'))), 'distinctPlayers' => $ranking['distinctPlayers'],
            'validSets' => $ranking['validSets'], 'rankedPlayers' => count($ranking['rows']),
            'periodFrom' => $dates ? min($dates) : null, 'periodTo' => $dates ? max($dates) : null,
            'cutDate' => $cutTime ? gmdate('Y-m-d', $cutTime - 21600) : null,
            // The site already shows a newer cut than the one SQL has: say so instead of looking current.
            'isStale' => $cutTime && $publicTime ? $publicTime - $cutTime > 60 : false],
        'sizes' => SMASH_ORG_SIZES,
        'minRule' => 'tener al menos ' . SMASH_ORG_MIN_SETS . ' sets válidos en los torneos que cuentan. Cuentan los torneos presenciales de singles que también entran al ranking nacional.'];
    if ($withSlides) $view['slides'] = $slides;
    return $view;
}

// Deliberate free projection: one tournament fact and aggregate counts only.
// Never fit a paid top, reserve a slug, or return players/points/records/reviews.
function smash_org_teaser(PDO $pdo, string $organizerId, int $now): array
{
    $cut = smash_org_cut($pdo); $owned = smash_org_tournament_ids($pdo, $organizerId);
    $ledger = smash_org_ledger($pdo, array_map('strval', array_keys($owned)), $cut, false);
    $events = smash_org_events($pdo, $organizerId, $owned, $ledger, $cut['seasonYear'] ?? (int)gmdate('Y', $now - 21600));
    $activity = [];
    foreach ($ledger['sets'] as $set) foreach (['winner', 'loser'] as $side) {
        $id = (string)$set[$side]; $activity[$id] = ($activity[$id] ?? 0) + 1;
    }
    $counted = array_values($ledger['events']);
    usort($counted, static function (array $a, array $b): int { return strcmp($b['date'], $a['date']) ?: strcmp($a['id'], $b['id']); });
    $last = $counted[0] ?? null;
    return ['headline' => $last === null ? null : ['kind' => 'latest_counted_tournament', 'name' => $last['name'], 'date' => $last['date'], 'url' => $last['url']],
        'locked' => ['tournaments' => count($events), 'countedTournaments' => count(array_unique(array_column($counted, 'tournamentId'))),
            'rankedPlayers' => count(array_filter($activity, static function (int $sets): bool { return $sets >= SMASH_ORG_MIN_SETS; })), 'validSets' => count($ledger['sets'])]];
}

// What a visitor of the public address gets: no account, no contact, no per-player detail.
function smash_org_public(PDO $pdo, string $slug, ?string $publicCut, callable $premium, int $now): array
{
    if (!preg_match('/\A[a-z0-9-]{1,60}\z/', $slug)) return ['state' => 'missing'];
    $rows = smash_org_rows($pdo, 'SELECT p.user_id, p.public_enabled FROM organizer_profiles p JOIN users u ON u.id = p.user_id AND u.status = ? WHERE p.slug = ?', ['active', $slug]);
    if (!$rows) return ['state' => 'missing'];
    if (!(bool)$rows[0]['public_enabled']) return ['state' => 'disabled'];
    if (!$premium((string)$rows[0]['user_id'])) return ['state' => 'paused'];
    $view = smash_org_view($pdo, (string)$rows[0]['user_id'], $publicCut, $now, false);
    if ($view['summary']['eventsCounted'] === 0) return ['state' => 'paused'];
    $used = [];
    foreach ($view['events'] as $event) if ($event['status'] === 'counts') $used[] = ['name' => $event['name'], 'date' => $event['date'], 'place' => $event['place'], 'url' => $event['url'], 'activePlayers' => $event['activePlayers'], 'validSets' => $event['validSets']];
    return ['state' => 'open', 'organizer' => ['name' => $view['organizer']['name'], 'topSize' => $view['organizer']['topSize']], 'coorganizers' => $view['coorganizers'], 'seasonYear' => $view['seasonYear'],
        'top' => array_map(static function (array $row): array { unset($row['detail']); return $row; }, $view['top']), 'summary' => $view['summary'], 'events' => $used];
}

// Co-organizers: the organizer hands over a one-use code; whoever opens it signed in joins.
function smash_org_members(PDO $pdo, string $organizerId): array
{
    return array_map(static function (array $row): array { return ['id' => (string)$row['id'], 'name' => $row['display_name'] ?? 'Cuenta start.gg', 'since' => smash_org_day($row['created_at'])]; },
        smash_org_rows($pdo, 'SELECT u.id, u.display_name, m.created_at FROM organizer_members m JOIN users u ON u.id = m.member_user_id WHERE m.organizer_user_id = ? ORDER BY m.created_at, u.id', [$organizerId]));
}

// Serialize invitation replacement/consumption and the member cap per organizer.
function smash_org_lock_owner(PDO $pdo, string $organizerId): void
{
    if (!smash_org_rows($pdo, "SELECT id FROM users WHERE id = ? AND status = 'active' FOR UPDATE", [$organizerId])) throw new SmashOrganizerError('invalid_invite');
}

function smash_org_invite(PDO $pdo, string $organizerId, int $now): string
{
    if ($pdo->inTransaction()) throw new SmashOrganizerError('organizer_write_failed');
    try {
        $pdo->beginTransaction();
        smash_org_lock_owner($pdo, $organizerId);
        if (count(smash_org_members($pdo, $organizerId)) >= SMASH_ORG_MAX_MEMBERS) throw new SmashOrganizerError('invalid_member_limit');
        smash_org_write($pdo, 'DELETE FROM organizer_invites WHERE organizer_user_id = ?', [$organizerId]);
        $token = bin2hex(random_bytes(24));
        smash_org_write($pdo, 'INSERT INTO organizer_invites (token_hash, organizer_user_id, created_at, expires_at) VALUES (?, ?, ?, ?)',
            [hash('sha256', $token), $organizerId, smash_org_stamp($now), smash_org_stamp($now + SMASH_ORG_INVITE_AGE)]);
        $pdo->commit(); return $token;
    } catch (Throwable $error) {
        if ($pdo->inTransaction()) $pdo->rollBack();
        if ($error instanceof SmashOrganizerError) throw $error;
        throw new SmashOrganizerError('organizer_write_failed');
    }

}

// Who is inviting, so the invited account can decide before joining. Reveals only the organizer's name.
function smash_org_invite_peek(PDO $pdo, $token, int $now): ?array
{
    if (!is_string($token) || !preg_match('/\A[a-f0-9]{48}\z/', $token)) return null;
    $rows = smash_org_rows($pdo, 'SELECT i.organizer_user_id, u.display_name FROM organizer_invites i JOIN users u ON u.id = i.organizer_user_id AND u.status = ? WHERE i.token_hash = ? AND i.expires_at > ?', ['active', hash('sha256', $token), smash_org_stamp($now)]);
    return $rows ? ['organizerId' => (string)$rows[0]['organizer_user_id'], 'name' => $rows[0]['display_name'] ?? 'Organizador'] : null;
}

function smash_org_join(PDO $pdo, string $userId, $token, int $now): string
{
    if ($pdo->inTransaction()) throw new SmashOrganizerError('organizer_write_failed');
    $invite = smash_org_invite_peek($pdo, $token, $now);
    if ($invite === null) throw new SmashOrganizerError('invalid_invite');
    if ($invite['organizerId'] === $userId) throw new SmashOrganizerError('invalid_invite_own');
    try {
        $pdo->beginTransaction();
        smash_org_lock_owner($pdo, $invite['organizerId']);
        $invite = smash_org_invite_peek($pdo, $token, $now);
        if ($invite === null) throw new SmashOrganizerError('invalid_invite');
        if (smash_org_rows($pdo, 'SELECT 1 FROM organizer_members WHERE organizer_user_id = ? AND member_user_id = ?', [$invite['organizerId'], $userId])) throw new SmashOrganizerError('invalid_invite_member');
        if (count(smash_org_members($pdo, $invite['organizerId'])) >= SMASH_ORG_MAX_MEMBERS) throw new SmashOrganizerError('invalid_member_limit');
        if (smash_org_write($pdo, 'DELETE FROM organizer_invites WHERE token_hash = ? AND expires_at > ?', [hash('sha256', $token), smash_org_stamp($now)]) !== 1) throw new SmashOrganizerError('invalid_invite');
        smash_org_write($pdo, 'INSERT INTO organizer_members (organizer_user_id, member_user_id, created_at) VALUES (?, ?, ?)', [$invite['organizerId'], $userId, smash_org_stamp($now)]);
        $pdo->commit(); return $invite['organizerId'];
    } catch (Throwable $error) {
        if ($pdo->inTransaction()) $pdo->rollBack();
        if ($error instanceof SmashOrganizerError) throw $error;
        throw new SmashOrganizerError('organizer_write_failed');
    }

}

// The organizer removes a co-organizer, or a co-organizer leaves.
function smash_org_remove_member(PDO $pdo, string $organizerId, $memberId): void
{
    if (!is_string($memberId) || !ctype_digit($memberId)) throw new SmashOrganizerError('invalid_member');
    smash_org_write($pdo, 'DELETE FROM organizer_members WHERE organizer_user_id = ? AND member_user_id = ?', [$organizerId, $memberId]);
}

// «Pedir revisión» with a start.gg address. Sending again after a rejection reopens the same request.
function smash_org_claim(PDO $pdo, string $organizerId, string $requestedBy, $url, int $now): void
{
    if (!is_string($url) || strlen($url) > 300 || !preg_match('~\Ahttps://(?:www\.)?start\.gg/(tournament/[a-z0-9][a-z0-9-]{0,200})(?:[/?#].*)?\z~i', trim($url), $match)) throw new SmashOrganizerError('invalid_tournament_url');
    $slug = strtolower($match[1]);
    $found = smash_org_rows($pdo, 'SELECT tournament_id FROM tournament_catalog WHERE slug = ? LIMIT 1', [$slug]);
    $tournamentId = $found ? (string)$found[0]['tournament_id'] : null;
    if ($tournamentId !== null && isset(smash_org_tournament_ids($pdo, $organizerId)[$tournamentId])) throw new SmashOrganizerError('invalid_already_yours');
    $existing = smash_org_rows($pdo, 'SELECT id, status FROM organizer_claims WHERE organizer_user_id = ? AND tournament_slug = ?', [$organizerId, $slug]);
    if ($existing && $existing[0]['status'] !== 'rejected') throw new SmashOrganizerError('invalid_already_sent');
    $open = smash_org_rows($pdo, "SELECT COUNT(*) AS n FROM organizer_claims WHERE organizer_user_id = ? AND status = 'sent'", [$organizerId]);
    if ((int)$open[0]['n'] >= SMASH_ORG_MAX_OPEN_CLAIMS) throw new SmashOrganizerError('invalid_claim_limit');
    if ($existing) {
        smash_org_write($pdo, "UPDATE organizer_claims SET status = 'sent', message = NULL, requested_by = ?, tournament_id = ?, created_at = ?, resolved_at = NULL, resolved_by = NULL WHERE id = ?",
            [$requestedBy, $tournamentId, smash_org_stamp($now), $existing[0]['id']]);
        return;
    }
    smash_org_write($pdo, 'INSERT INTO organizer_claims (organizer_user_id, requested_by, tournament_slug, tournament_id, created_at) VALUES (?, ?, ?, ?, ?)',
        [$organizerId, $requestedBy, $slug, $tournamentId, smash_org_stamp($now)]);
}

// Site owner only: the reviews waiting for a decision.
function smash_org_pending_claims(PDO $pdo): array
{
    return array_map(static function (array $row): array {
        return ['id' => (string)$row['id'], 'organizer' => $row['display_name'] ?? 'Cuenta start.gg', 'requestedBy' => $row['requester_name'] ?? 'Cuenta start.gg', 'url' => 'https://www.start.gg/' . $row['tournament_slug'],
            'tournament' => $row['tournament_name'], 'inCatalog' => $row['tournament_id'] !== null, 'sentAt' => smash_org_day($row['created_at'])];
    }, smash_org_rows($pdo, "SELECT c.id, c.tournament_slug, COALESCE(c.tournament_id, (SELECT MAX(t.tournament_id) FROM tournament_catalog t WHERE t.slug = c.tournament_slug)) AS tournament_id, c.created_at, u.display_name, requester.display_name AS requester_name,
        (SELECT MAX(t.tournament_name) FROM tournament_catalog t WHERE t.tournament_id = c.tournament_id OR (c.tournament_id IS NULL AND t.slug = c.tournament_slug)) AS tournament_name
        FROM organizer_claims c JOIN users u ON u.id = c.organizer_user_id LEFT JOIN users requester ON requester.id = c.requested_by WHERE c.status = 'sent' ORDER BY c.created_at, c.id LIMIT 100"));
}

function smash_org_resolve(PDO $pdo, string $adminId, $claimId, $approve, $message, int $now): void
{
    if (!is_string($claimId) || !ctype_digit($claimId) || !is_bool($approve)) throw new SmashOrganizerError('invalid_review');
    $message = is_string($message) ? trim($message) : '';
    if ((function_exists('mb_strlen') ? mb_strlen($message, 'UTF-8') : strlen($message)) > 255 || (!$approve && $message === '')) throw new SmashOrganizerError('invalid_review_message');
    $claim = smash_org_rows($pdo, 'SELECT tournament_slug, tournament_id FROM organizer_claims WHERE id = ? AND status = ?', [$claimId, 'sent']);
    if (!$claim) throw new SmashOrganizerError('invalid_review');
    $tournamentId = $claim[0]['tournament_id'];
    if ($tournamentId === null) {
        $found = smash_org_rows($pdo, 'SELECT tournament_id FROM tournament_catalog WHERE slug = ? LIMIT 1', [$claim[0]['tournament_slug']]);
        $tournamentId = $found ? $found[0]['tournament_id'] : null;
    }
    // A tournament the weekly catalog has never seen cannot count: it has no results here.
    if ($approve && $tournamentId === null) throw new SmashOrganizerError('invalid_review_unknown_tournament');
    $changed = smash_org_write($pdo, 'UPDATE organizer_claims SET status = ?, message = ?, tournament_id = ?, resolved_at = ?, resolved_by = ? WHERE id = ? AND status = ?',
        [$approve ? 'approved' : 'rejected', $message === '' ? null : $message, $tournamentId, smash_org_stamp($now), $adminId, $claimId, 'sent']);
    if ($changed !== 1) throw new SmashOrganizerError('invalid_review');
}
