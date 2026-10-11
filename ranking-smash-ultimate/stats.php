<?php
declare(strict_types=1);

// Library only. Apache blocks direct access; nothing is read or written on inclusion.
// Read-only figures for the owner's private panel: visits (see visits.php) and registrations.
// Visitors/networks are aggregates only. Account drilldowns are owner-only, never public.

// Additive contract: legacy panel key "torneos" stays the historical analysis; no SQL
// renames or duplicate aliases in totals. The new stored page "torneos" is the agenda.
const SMASH_STATS_PAGES = ['inicio' => 'home', 'metodologia' => 'metodologia', 'cuenta' => 'cuenta', 'analisis-top20' => 'top20', 'analisis-torneos' => 'torneos', 'torneos' => 'agendaTorneos'];

final class SmashStatsError extends RuntimeException
{
    public $reason;
    public function __construct(string $reason) { $this->reason = $reason; parent::__construct('No se pudieron consultar las estadísticas.'); }
}

// The panel belongs to accounts holding the admin role, which only the owner grants in SQL.
function smash_stats_is_owner(PDO $pdo, string $userId): bool
{
    try {
        $q = $pdo->prepare("SELECT 1 FROM user_roles WHERE user_id = ? AND role = 'admin'");
        $q->execute([$userId]);
        return $q->fetchColumn() !== false;
    } catch (PDOException $error) { throw new SmashStatsError('stats_read_failed'); }
}

function smash_stats_shift(string $day, int $days): string
{
    return gmdate('Y-m-d', strtotime($day . ' 00:00:00 UTC') + $days * 86400);
}

function smash_stats_span(string $from, string $to): int
{
    return (int)round((strtotime($to . ' 00:00:00 UTC') - strtotime($from . ' 00:00:00 UTC')) / 86400) + 1;
}

// Registrations use the same calendar as visits: the day of Guatemala (UTC-6, no daylight saving).
function smash_stats_registrations(PDO $pdo, string $from, string $to): array
{
    $q = $pdo->prepare('SELECT DATE(DATE_SUB(created_at, INTERVAL 6 HOUR)) AS day, COUNT(*) FROM users
        WHERE created_at >= DATE_ADD(?, INTERVAL 6 HOUR) AND created_at < DATE_ADD(DATE_ADD(?, INTERVAL 1 DAY), INTERVAL 6 HOUR) GROUP BY day');
    $q->execute([$from, $to]);
    return array_map('intval', $q->fetchAll(PDO::FETCH_KEY_PAIR));
}

// The same clipped ranges as the report. An anchor keeps a panel opened before midnight
// on its original Guatemala day. Scope keys carry dates, never account identifiers.
function smash_stats_registration_scopes(PDO $pdo, string $today, int $seasonYear): array
{
    $started = $pdo->query('SELECT MIN(day) FROM site_visitor_days')->fetchColumn();
    $yesterday = smash_stats_shift($today, -1);
    $scopes = ['all' => null, 'today' => [$today, $today], 'yesterday' => [$yesterday, $yesterday]];
    foreach (['7' => 7, '30' => 30, '90' => 90, 'season' => null] as $name => $length) {
        $from = $length === null ? $seasonYear . '-01-01' : smash_stats_shift($yesterday, -($length - 1));
        $from = is_string($started) ? max($from, $started) : null;
        $scopes[$name] = $from !== null && $from <= $yesterday ? [$from, $yesterday] : [];
        if ($from === null || $from > $yesterday) continue;
        for ($day = $from; $day <= $yesterday; $day = smash_stats_shift($day, 1)) $scopes[$day . '_' . $day] = [$day, $day];
        if ($name === '90' || $name === 'season') {
            for ($end = $yesterday; $end >= $from; $end = smash_stats_shift($end, -7)) {
                $start = max($from, smash_stats_shift($end, -6));
                $scopes[$start . '_' . $end] = [$start, $end];
            }
        }
    }
    return $scopes;
}

// Only called after smash_stats_is_owner in panel-api. Explicit projection: no private IDs.
// Read-only snapshot makes the total and this page agree even during a new registration.
function smash_stats_registration_list(PDO $pdo, string $scope, string $today, int $seasonYear, int $offset = 0, ?string $maximumId = null, ?array $scopes = null): array
{
    $scopes = $scopes ?? smash_stats_registration_scopes($pdo, $today, $seasonYear);
    if (!array_key_exists($scope, $scopes) || $offset < 0 || $offset > 10000000) throw new SmashStatsError('invalid_registration_query');
    $range = $scopes[$scope];
    if ($range === []) return ['total' => 0, 'items' => [], 'nextOffset' => null];
    $where = $range === null ? '' : ' WHERE u.created_at >= DATE_ADD(?, INTERVAL 6 HOUR) AND u.created_at < DATE_ADD(DATE_ADD(?, INTERVAL 1 DAY), INTERVAL 6 HOUR)';
    $params = $range ?? [];
    if ($maximumId !== null) { $where .= ($where === '' ? ' WHERE ' : ' AND ') . 'u.id <= ?'; $params[] = $maximumId; }
    try {
        $pdo->exec('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ');
        $pdo->exec('START TRANSACTION READ ONLY');
        $q = $pdo->prepare('SELECT COUNT(*) FROM users u' . $where); $q->execute($params);
        $total = (int)$q->fetchColumn();
        $q = $pdo->prepare('SELECT p.tag, u.created_at, EXISTS(SELECT 1 FROM oauth_connections o WHERE o.user_id = u.id AND o.revoked_at IS NULL) AS linked
            FROM users u LEFT JOIN players p ON p.id = u.player_id' . $where . ' ORDER BY u.created_at DESC, u.id DESC LIMIT 50 OFFSET ' . $offset);
        $q->execute($params); $items = [];
        foreach ($q->fetchAll(PDO::FETCH_ASSOC) as $row) {
            $items[] = ['tag' => is_string($row['tag']) && $row['tag'] !== '' ? $row['tag'] : 'Cuenta sin jugador vinculado',
                'registeredAt' => gmdate('Y-m-d\TH:i:s', strtotime($row['created_at'] . ' UTC') - 21600) . '-06:00', 'linked' => (bool)$row['linked']];
        }
        $pdo->commit();
        return ['total' => $total, 'items' => $items, 'nextOffset' => $offset + count($items) < $total ? $offset + count($items) : null];
    } catch (Throwable $error) {
        if ($pdo->inTransaction()) $pdo->rollBack();
        throw new SmashStatsError('stats_read_failed');
    }
}

// Totals of a range of complete days. Distinct visitors are counted over the whole range by the
// database; they are not the sum of the daily figures.
function smash_stats_totals(PDO $pdo, string $from, string $to): array
{
    $q = $pdo->prepare('SELECT COUNT(DISTINCT visitor_hash), COUNT(DISTINCT CASE WHEN signed_in = 1 THEN visitor_hash END) FROM site_visitor_days WHERE day BETWEEN ? AND ?');
    $q->execute([$from, $to]); [$visitors, $logged] = $q->fetch(PDO::FETCH_NUM);
    $q = $pdo->prepare('SELECT COUNT(DISTINCT network_hash) FROM site_network_days WHERE day BETWEEN ? AND ?');
    $q->execute([$from, $to]); $networks = $q->fetchColumn();
    $q = $pdo->prepare('SELECT page, SUM(views) FROM site_visit_days WHERE day BETWEEN ? AND ? GROUP BY page');
    $q->execute([$from, $to]); $byPage = $q->fetchAll(PDO::FETCH_KEY_PAIR);
    $pages = [];
    foreach (SMASH_STATS_PAGES as $stored => $name) $pages[$name] = (int)($byPage[$stored] ?? 0);
    return ['visitors' => (int)$visitors, 'loggedVisitors' => (int)$logged, 'networks' => (int)$networks, 'pageviews' => array_sum($pages),
        'registrations' => array_sum(smash_stats_registrations($pdo, $from, $to)), 'pages' => $pages];
}

// Blocks of seven days counted back from $to. The oldest block is clipped at $from and marked partial.
function smash_stats_weeks(PDO $pdo, string $from, string $to): array
{
    $q = $pdo->prepare('SELECT FLOOR(DATEDIFF(?, day) / 7) AS week, COUNT(DISTINCT visitor_hash) FROM site_visitor_days WHERE day BETWEEN ? AND ? GROUP BY week');
    $q->execute([$to, $from, $to]); $visitors = $q->fetchAll(PDO::FETCH_KEY_PAIR);
    $q = $pdo->prepare('SELECT FLOOR(DATEDIFF(?, day) / 7) AS week, SUM(views) FROM site_visit_days WHERE day BETWEEN ? AND ? GROUP BY week');
    $q->execute([$to, $from, $to]); $views = $q->fetchAll(PDO::FETCH_KEY_PAIR);
    $registered = smash_stats_registrations($pdo, $from, $to);
    $weeks = [];
    for ($index = 0, $end = $to; $end >= $from; $index++, $end = smash_stats_shift($end, -7)) {
        $start = max($from, smash_stats_shift($end, -6)); $count = 0;
        foreach ($registered as $day => $n) if ($day >= $start && $day <= $end) $count += $n;
        $weeks[] = ['from' => $start, 'to' => $end, 'visitors' => (int)($visitors[$index] ?? 0), 'pageviews' => (int)($views[$index] ?? 0),
            'registrations' => $count, 'partial' => smash_stats_span($start, $end) < 7];
    }
    return array_reverse($weeks);
}

// Accounts with a paid period running, real charges only. Null while premium is not installed.
function smash_stats_premium(PDO $pdo, int $now): ?int
{
    try {
        $q = $pdo->prepare("SELECT COUNT(DISTINCT user_id) FROM premium_subscriptions WHERE live_mode = 1 AND status IN ('active', 'past_due', 'canceled') AND current_period_end > ?");
        $q->execute([gmdate('Y-m-d H:i:s', $now)]);
        return (int)$q->fetchColumn();
    } catch (PDOException $error) { return null; }
}

// Who those premium accounts are, for the owner's panel only: tag, plan and the day the paid period ends.
function smash_stats_premium_list(PDO $pdo, int $now): array
{
    try {
        $q = $pdo->prepare("SELECT COALESCE(p.tag, u.display_name) AS tag, s.plan, s.status, s.current_period_end AS until
            FROM premium_subscriptions s JOIN users u ON u.id = s.user_id LEFT JOIN players p ON p.id = u.player_id
            WHERE s.live_mode = 1 AND s.status IN ('active', 'past_due', 'canceled') AND s.current_period_end > ?
            ORDER BY s.current_period_end DESC LIMIT 200");
        $q->execute([gmdate('Y-m-d H:i:s', $now)]);
        $list = []; $seen = [];
        foreach ($q->fetchAll(PDO::FETCH_ASSOC) as $row) {
            $tag = is_string($row['tag']) && $row['tag'] !== '' ? $row['tag'] : 'Cuenta sin jugador';
            if (isset($seen[$tag])) continue;
            $seen[$tag] = true;
            $list[] = ['tag' => $tag, 'plan' => $row['plan'], 'renews' => $row['status'] === 'active',
                'until' => gmdate('Y-m-d', strtotime($row['until'] . ' UTC') - 21600)];
        }
        return $list;
    } catch (PDOException $error) { return []; }
}

function smash_stats_report(PDO $pdo, int $now, int $seasonYear): array
{
    try {
        $today = gmdate('Y-m-d', $now - 21600); $yesterday = smash_stats_shift($today, -1);
        $started = $pdo->query('SELECT MIN(day) FROM site_visitor_days')->fetchColumn();
        $started = is_string($started) ? $started : null;
        $q = $pdo->prepare('SELECT COUNT(*) FROM site_visitor_days WHERE day = ?'); $q->execute([$today]); $todayVisitors = (int)$q->fetchColumn();
        $q = $pdo->prepare('SELECT COALESCE(SUM(views), 0) FROM site_visit_days WHERE day = ?'); $q->execute([$today]); $todayViews = (int)$q->fetchColumn();
        $registrationScopes = smash_stats_registration_scopes($pdo, $today, $seasonYear);
        $report = ['updatedAt' => gmdate('Y-m-d\TH:i', $now - 21600) . '-06:00', 'counterStartedAt' => $started, 'seasonYear' => $seasonYear,
            'today' => ['date' => $today, 'visitors' => $todayVisitors, 'pageviews' => $todayViews,
                'registrations' => array_sum(smash_stats_registrations($pdo, $today, $today))],
            'yesterday' => null, 'daily' => [], 'periods' => [], 'weekly' => []];
        $total = (int)$pdo->query('SELECT COUNT(*) FROM users')->fetchColumn();
        $linked = (int)$pdo->query('SELECT COUNT(*) FROM oauth_connections WHERE revoked_at IS NULL')->fetchColumn();
        $report['accounts'] = ['total' => $total, 'linked' => $linked, 'premium' => smash_stats_premium($pdo, $now), 'premiumList' => smash_stats_premium_list($pdo, $now)];
        $season = $seasonYear . '-01-01';
        foreach (['7' => 7, '30' => 30, '90' => 90, 'season' => null] as $name => $length) {
            $from = $length === null ? $season : smash_stats_shift($yesterday, -($length - 1));
            // Days before the counter existed are «no data», never zero: the range starts where data starts.
            $dataFrom = $registrationScopes[$name][0] ?? null;
            $period = ['from' => $from, 'to' => $yesterday, 'days' => $yesterday >= $from ? smash_stats_span($from, $yesterday) : 0,
                'daysWithData' => $dataFrom !== null && $dataFrom <= $yesterday ? smash_stats_span($dataFrom, $yesterday) : 0, 'previous' => null];
            if ($period['daysWithData'] > 0) {
                $period += smash_stats_totals($pdo, $dataFrom, $yesterday);
                // Compared only with a previous window that is complete and entirely measured.
                if ($length !== null && $started <= smash_stats_shift($from, -$length)) {
                    $q = $pdo->prepare('SELECT COUNT(DISTINCT visitor_hash) FROM site_visitor_days WHERE day BETWEEN ? AND ?');
                    $q->execute([smash_stats_shift($from, -$length), smash_stats_shift($from, -1)]);
                    $period['previous'] = ['visitors' => (int)$q->fetchColumn()];
                }
                if ($length === null || $length === 90) $report['weekly'][$name] = smash_stats_weeks($pdo, $dataFrom, $yesterday);
            }
            $report['periods'][$name] = $period;
        }
        $first = $started === null ? null : max($season, $started);
        if ($first !== null && $first <= $yesterday) {
            $q = $pdo->prepare('SELECT day, COUNT(*), SUM(signed_in) FROM site_visitor_days WHERE day BETWEEN ? AND ? GROUP BY day');
            $q->execute([$first, $yesterday]); $visitors = [];
            foreach ($q->fetchAll(PDO::FETCH_NUM) as $row) $visitors[$row[0]] = [(int)$row[1], (int)$row[2]];
            $q = $pdo->prepare('SELECT day, COUNT(*) FROM site_network_days WHERE day BETWEEN ? AND ? GROUP BY day');
            $q->execute([$first, $yesterday]); $networks = $q->fetchAll(PDO::FETCH_KEY_PAIR);
            $q = $pdo->prepare('SELECT day, SUM(views) FROM site_visit_days WHERE day BETWEEN ? AND ? GROUP BY day');
            $q->execute([$first, $yesterday]); $views = $q->fetchAll(PDO::FETCH_KEY_PAIR);
            $registered = smash_stats_registrations($pdo, $first, $yesterday);
            for ($day = $first; $day <= $yesterday; $day = smash_stats_shift($day, 1)) {
                $report['daily'][] = ['date' => $day, 'visitors' => $visitors[$day][0] ?? 0, 'loggedVisitors' => $visitors[$day][1] ?? 0,
                    'networks' => (int)($networks[$day] ?? 0), 'pageviews' => (int)($views[$day] ?? 0), 'registrations' => $registered[$day] ?? 0];
            }
            if ($started <= $yesterday) $report['yesterday'] = ['visitors' => $visitors[$yesterday][0] ?? 0, 'registrations' => $registered[$yesterday] ?? 0];
        }
        return $report;
    } catch (PDOException $error) {
        throw new SmashStatsError('stats_read_failed');
    }
}
