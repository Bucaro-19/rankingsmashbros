<?php
declare(strict_types=1);
// Library only: public directory, SELECTs only; nothing happens on inclusion.
// Candidate SQL is a bounded prefilter. smash_org_public remains the access authority.
const SMASH_TOPS_LIMIT = 12;
const SMASH_TOPS_CACHE_SECONDS = 30;

function smash_tops_directory(PDO $pdo, ?array $config, int $now, int $limit = SMASH_TOPS_LIMIT, string $after = ''): array
{
    if ($limit < 1 || $limit > SMASH_TOPS_LIMIT || ($after !== '' && !preg_match('/\A[a-z0-9-]{1,60}\z/', $after))) {
        throw new InvalidArgumentException('invalid_query');
    }
    $cut = smash_org_cut($pdo);
    if ($cut === null) return ['ok' => true, 'schemaVersion' => 1, 'items' => [], 'nextCursor' => null];
    // The latest non-pending period uses the same ordering/status/end rules as
    // smash_premium_status. An admin has the same exception as /top/{slug}.
    // This excludes closed tops BEFORE the limit, so an empty page is honest.
    $rows = smash_org_rows($pdo, "SELECT p.slug FROM organizer_profiles p
        JOIN users u ON u.id = p.user_id AND u.status = 'active'
        LEFT JOIN premium_subscriptions ps ON ps.id = (
            SELECT s.id FROM premium_subscriptions s WHERE s.user_id = u.id AND s.live_mode = ? AND s.status <> 'pending'
            ORDER BY (s.current_period_end IS NULL), s.current_period_end DESC, s.id DESC LIMIT 1)
        WHERE p.public_enabled = 1 AND p.slug > ? AND (
            EXISTS (SELECT 1 FROM user_roles r WHERE r.user_id = u.id AND r.role = 'admin') OR
            (? = 1 AND ps.current_period_end > ? AND ps.status IN ('active', 'past_due', 'canceled')))
        AND EXISTS (SELECT 1 FROM cut_events ce JOIN events e ON e.id = ce.event_id
            WHERE ce.cut_id = ? AND ce.scope = 'combined' AND ce.active_players >= 20 AND (
                EXISTS (SELECT 1 FROM tournament_catalog c WHERE c.tournament_id = e.tournament_id AND c.owner_startgg_user_id = u.startgg_user_id) OR
                EXISTS (SELECT 1 FROM organizer_claims c WHERE c.organizer_user_id = u.id AND c.tournament_id = e.tournament_id AND c.status = 'approved')))
        ORDER BY p.slug LIMIT " . ($limit + 1),
        [$config !== null && $config['live'] ? 1 : 0, $after, $config !== null ? 1 : 0, smash_org_stamp($now), $cut['id']]);
    $hasMore = count($rows) > $limit; $items = []; $last = null;
    $premium = static function (string $id) use ($pdo, $config, $now): bool {
        return smash_org_premium($pdo, $id, $config, $now)['active'];
    };
    foreach (array_slice($rows, 0, $limit) as $row) {
        $view = smash_org_public($pdo, (string)$row['slug'], null, $premium, $now);
        if ($view['state'] !== 'open') continue;
        $last = (string)$row['slug'];
        // Explicit allowlist: no IDs, contacts, account/payment state, reviews,
        // per-player detail, scores, or fields added to the full view in future.
        $items[] = ['name' => $view['organizer']['name'], 'coorganizers' => $view['coorganizers'],
            'topSize' => $view['organizer']['topSize'], 'tournaments' => $view['summary']['eventsCounted'],
            'cutDate' => $view['summary']['cutDate'],
            'top' => array_map(static function (array $player): array {
                return ['rank' => $player['rank'], 'alias' => $player['alias']];
            }, array_slice($view['top'], 0, 3)), 'url' => '/top/' . $last];
    }
    return ['ok' => true, 'schemaVersion' => 1, 'items' => $items, 'nextCursor' => $hasMore ? $last : null];
}
