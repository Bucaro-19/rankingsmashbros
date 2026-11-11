<?php
declare(strict_types=1);

// Read model for the linked player. The caller supplies trusted IDs and a bounded transport.
const MT_LIVE_PAGE_SIZE = 12;
const MT_LIVE_MAX_PAGES = 2;
const MT_LIVE_ENTRY = <<<'GRAPHQL'
query MiTorneoInscripcion($event: ID!, $user: ID!) {
  event(id: $event) {
    id type state videogame { id }
    userEntrant(userId: $user) { id participants { player { id } } }
  }
}
GRAPHQL;
const MT_LIVE_SETS = <<<'GRAPHQL'
query MiTorneoSets($event: ID!, $entrant: ID!, $page: Int!, $size: Int!) {
  event(id: $event) {
    id
    sets(page: $page, perPage: $size, filters: {entrantIds: [$entrant]}) {
      pageInfo { total totalPages }
      nodes {
        id state winnerId completedAt fullRoundText displayScore
        slots(includeByes: true) { entrant { id name participants { player { id } } } }
      }
    }
  }
}
GRAPHQL;

function mt_live_id($value): ?string
{
    if (!is_string($value) && !is_int($value)) return null;
    return preg_match('/^[1-9][0-9]{0,19}$/D', (string)$value) ? (string)$value : null;
}

function mt_live_text($value): ?string
{
    return is_string($value) && strlen($value) <= 512 && !preg_match('/[\x00-\x1f]/', $value) ? $value : null;
}

// Never trust a roster tag or the transport's entrant filter as proof of identity.
function mt_live_entry(callable $query, string $eventId, string $userId, string $playerId): ?array
{
    if (mt_live_id($eventId) === null || mt_live_id($userId) === null || mt_live_id($playerId) === null) {
        throw new InvalidArgumentException('live_invalid_identity');
    }
    $event = $query(MT_LIVE_ENTRY, ['event' => $eventId, 'user' => $userId])['event'] ?? null;
    if (!is_array($event) || mt_live_id($event['id'] ?? null) !== $eventId || ($event['type'] ?? null) !== 1
        || mt_live_id($event['videogame']['id'] ?? null) !== '1386' || !array_key_exists('userEntrant', $event)) {
        throw new UnexpectedValueException('live_event_unavailable');
    }
    $entry = $event['userEntrant'];
    if ($entry === null) return null;
    $entrantId = mt_live_id($entry['id'] ?? null);
    $people = $entry['participants'] ?? null;
    if ($entrantId === null || !is_array($people) || count($people) !== 1
        || mt_live_id($people[0]['player']['id'] ?? null) !== $playerId) {
        throw new UnexpectedValueException('live_entry_mismatch');
    }
    return ['id' => $entrantId, 'finished' => ($event['state'] ?? null) === 'COMPLETED'];
}

function mt_live_read(callable $query, string $eventId, string $userId, string $playerId): array
{
    $empty = ['status' => 'registration_unverified', 'lastResult' => null, 'nextSet' => null, 'pendingSets' => 0];
    $entry = mt_live_entry($query, $eventId, $userId, $playerId);
    if ($entry === null) return $empty;
    if ($entry['finished']) return ['status' => 'event_finished'] + $empty;
    $entrantId = $entry['id'];

    $nodes = [];
    $expected = null;
    for ($page = 1; $page <= MT_LIVE_MAX_PAGES; $page++) {
        $event = $query(MT_LIVE_SETS, ['event' => $eventId, 'entrant' => $entrantId, 'page' => $page, 'size' => MT_LIVE_PAGE_SIZE])['event'] ?? null;
        $sets = $event['sets'] ?? null;
        $info = $sets['pageInfo'] ?? null;
        $items = $sets['nodes'] ?? null;
        $total = $info['total'] ?? null;
        $pages = $info['totalPages'] ?? null;
        if (mt_live_id($event['id'] ?? null) !== $eventId || !is_array($items) || !is_int($total)
            || $total < 0 || !is_int($pages) || $pages < 0) {
            throw new UnexpectedValueException('live_sets_unavailable');
        }
        if ($pages > MT_LIVE_MAX_PAGES || $total > MT_LIVE_MAX_PAGES * MT_LIVE_PAGE_SIZE) {
            return ['status' => 'coverage_incomplete'] + $empty;
        }
        $left = max(0, $total - ($page - 1) * MT_LIVE_PAGE_SIZE);
        if (($total > 0 && $pages !== (int)ceil($total / MT_LIVE_PAGE_SIZE)) || ($total === 0 && $pages > 1)
            || ($expected !== null && $expected !== [$total, $pages]) || count($items) !== min($left, MT_LIVE_PAGE_SIZE)) {
            throw new UnexpectedValueException('live_pagination_changed');
        }
        $expected = [$total, $pages];
        $nodes = array_merge($nodes, $items);
        if ($page >= $pages) break;
    }
    return mt_live_project($nodes, $entrantId, $empty);
}

function mt_live_project(array $nodes, string $entrantId, array $out): array
{
    $seen = [];
    $pending = [];
    $latest = null;
    foreach ($nodes as $match) {
        $id = $match['id'] ?? null;
        $slots = $match['slots'] ?? null;
        if (!is_array($match) || (!is_string($id) && !is_int($id)) || !preg_match('/^[A-Za-z0-9_-]{1,100}$/D', (string)$id)
            || isset($seen[$id]) || !is_array($slots) || count($slots) !== 2) {
            throw new UnexpectedValueException('live_set_invalid');
        }
        $seen[$id] = true;
        $sides = array_column($slots, 'entrant');
        if (count($sides) !== 2) throw new UnexpectedValueException('live_set_invalid');
        $ids = array_map(static fn($side) => mt_live_id($side['id'] ?? null), $sides);
        $mine = array_search($entrantId, $ids, true);
        if ($mine === false || $ids[0] === $ids[1]) throw new UnexpectedValueException('live_set_not_for_entrant');
        $other = $sides[1 - $mine];
        $people = $other['participants'] ?? null;
        $opponent = $ids[1 - $mine] === null ? null : [
            'playerId' => is_array($people) && count($people) === 1 ? mt_live_id($people[0]['player']['id'] ?? null) : null,
            'tag' => mt_live_text($other['name'] ?? null),
        ];
        $summary = ['id' => (string)$id, 'round' => mt_live_text($match['fullRoundText'] ?? null), 'opponent' => $opponent];
        $winner = $match['winnerId'] ?? null;
        $state = $match['state'] ?? null;
        if ($winner !== null && (!in_array(mt_live_id($winner), $ids, true) || mt_live_id($winner) === null)) {
            throw new UnexpectedValueException('live_winner_invalid');
        }
        if ($winner !== null || $state === 3) {
            $completedAt = $match['completedAt'] ?? null;
            if ($winner !== null && $opponent !== null && is_int($completedAt) && $completedAt > ($latest['completedAt'] ?? 0)) {
                $latest = $summary + ['won' => (string)$winner === $entrantId, 'completedAt' => $completedAt,
                    'score' => mt_live_text($match['displayScore'] ?? null)];
            }
        } elseif (is_int($state)) {
            $pending[] = $summary;
        }
    }
    $out['lastResult'] = $latest;
    $out['pendingSets'] = count($pending);
    if (count($pending) === 1) {
        $out['nextSet'] = $pending[0];
        $out['status'] = $pending[0]['opponent'] === null ? 'opponent_pending' : 'opponent_confirmed';
    } else {
        $out['status'] = $pending ? 'several_assigned' : 'awaiting_assignment';
    }
    return $out;
}

// A missing or disabled private config keeps the published snapshot behavior.
function mt_live_config(string $site, int $now): ?array
{
    $private = dirname($site) . '/private-smash';
    $path = $private . '/mi-torneo-live.local.php';
    if (!is_file($path)) return null;
    if (is_link($private) || is_link($path)) throw new RuntimeException('live_config_invalid');
    $config = require $path;
    if (!is_array($config) || ($config['enabled'] ?? false) !== true) return null;
    $token = $config['token'] ?? null;
    $events = $config['events'] ?? null;
    if (!is_string($token) || !preg_match('/^[\x21-\x7e]{1,8192}$/D', $token)
        || !is_array($events) || count($events) > 3) {
        throw new RuntimeException('live_config_invalid');
    }
    $active = [];
    $seen = [];
    foreach ($events as $item) {
        $id = mt_live_id($item['id'] ?? null);
        $name = mt_live_text($item['name'] ?? null);
        $url = $item['url'] ?? null;
        $start = $item['startAt'] ?? null;
        $end = $item['endAt'] ?? null;
        if ($id === null || $id === MT_EVENT || isset($seen[$id]) || $name === null || trim($name) === ''
            || !is_string($url) || strlen($url) > 512
            || !preg_match('~\Ahttps://(?:www\.)?start\.gg/tournament/[A-Za-z0-9_-]+/event/[A-Za-z0-9_-]+\z~D', $url)
            || !is_int($start) || !is_int($end) || $start <= 0 || $end <= $start || $end - $start > 7 * 86400) {
            throw new RuntimeException('live_config_invalid');
        }
        $seen[$id] = true;
        if ($end <= $now || $start > $now + 14 * 86400) continue;
        $active[$id] = ['id' => $id, 'name' => $name, 'url' => $url, 'startAt' => $start,
            'endAt' => $end, 'inProgress' => $start <= $now];
    }
    uasort($active, static fn($a, $b) => [!$a['inProgress'], $a['startAt']] <=> [!$b['inProgress'], $b['startAt']]);
    return $active ? ['token' => $token, 'events' => $active, 'private' => $private] : null;
}

final class MiTorneoLiveBusy extends RuntimeException {}

function mt_live_store(string $path, array $state): void
{
    $json = json_encode($state, JSON_THROW_ON_ERROR | JSON_INVALID_UTF8_SUBSTITUTE | JSON_UNESCAPED_UNICODE);
    $temp = $path . '.' . bin2hex(random_bytes(8)) . '.tmp';
    try {
        if (file_put_contents($temp, $json) !== strlen($json) || !chmod($temp, 0600) || !rename($temp, $path)) {
            throw new RuntimeException('live_cache_unavailable');
        }
    } finally {
        if (is_file($temp)) unlink($temp);
    }
}

// One process can use the provider at a time. Count attempts before making a network request.
function mt_live_cached(string $private, string $key, int $ttl, int $budget, callable $load, callable $transport): array
{
    $path = $private . '/mi-torneo-live-state.json';
    $lockPath = $path . '.lock';
    if (is_link($path) || is_link($lockPath)) throw new RuntimeException('live_cache_unavailable');
    $lock = fopen($lockPath, 'c');
    if (!$lock) throw new RuntimeException('live_cache_unavailable');
    try {
        if (!flock($lock, LOCK_EX | LOCK_NB)) throw new MiTorneoLiveBusy();
        chmod($lockPath, 0600);
        $state = ['attempts' => [], 'cache' => []];
        if (is_file($path)) {
            if (filesize($path) > 524288) throw new RuntimeException('live_cache_unavailable');
            $state = json_decode(file_get_contents($path), true, 16, JSON_THROW_ON_ERROR);
            if (!is_array($state['attempts'] ?? null) || !is_array($state['cache'] ?? null)) {
                throw new RuntimeException('live_cache_unavailable');
            }
        }
        $now = microtime(true);
        $state['cache'] = array_filter($state['cache'], static fn($row) => $row['until'] > $now);
        if (isset($state['cache'][$key])) return $state['cache'][$key]['value'];
        $state['attempts'] = array_values(array_filter($state['attempts'], static fn($at) => $at > $now - 60));
        if (count($state['attempts']) + $budget > 12) throw new MiTorneoLiveBusy();

        $value = $load(static function (string $document, array $variables) use (&$state, &$budget, $path, $transport): array {
            if ($budget-- < 1) throw new LogicException('live_query_budget_exhausted');
            $last = end($state['attempts']);
            if ($last !== false) {
                $delay = (int)ceil(($last + 1 - microtime(true)) * 1000000);
                if ($delay > 0) usleep($delay);
            }
            $state['attempts'][] = microtime(true);
            mt_live_store($path, $state);
            return $transport($document, $variables);
        });
        $state['cache'][$key] = ['until' => time() + $ttl, 'value' => $value];
        $state['cache'] = array_slice($state['cache'], -50, null, true);
        mt_live_store($path, $state);
        return $value;
    } finally {
        fclose($lock);
    }
}
