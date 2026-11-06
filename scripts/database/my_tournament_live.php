<?php
declare(strict_types=1);

// Read model for the future live endpoint. The caller supplies trusted IDs and a bounded transport.
const MT_LIVE_PAGE_SIZE = 12;
const MT_LIVE_MAX_PAGES = 2;
const MT_LIVE_ENTRY = <<<'GRAPHQL'
query MiTorneoInscripcion($event: ID!, $user: ID!) {
  event(id: $event) {
    id type videogame { id }
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
function mt_live_read(callable $query, string $eventId, string $userId, string $playerId): array
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
    $empty = ['status' => 'registration_unverified', 'lastResult' => null, 'nextSet' => null, 'pendingSets' => 0];
    if ($entry === null) return $empty;
    $entrantId = mt_live_id($entry['id'] ?? null);
    $people = $entry['participants'] ?? null;
    if ($entrantId === null || !is_array($people) || count($people) !== 1
        || mt_live_id($people[0]['player']['id'] ?? null) !== $playerId) {
        throw new UnexpectedValueException('live_entry_mismatch');
    }

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
