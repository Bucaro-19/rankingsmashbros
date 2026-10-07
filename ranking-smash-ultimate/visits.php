<?php
declare(strict_types=1);

// Library only. Apache blocks direct access; nothing is read or written on inclusion.
// Private visit statistics for the owner. Stored: page views per day, one row per visitor
// per day (hash of an own signed cookie) and one row per network per day (keyed hash of the
// IP). Never stored or logged: the IP itself, the cookie value, user agent, referrer or account.

const SMASH_VISIT_COOKIE = 'smash_visita';
const SMASH_VISIT_COOKIE_AGE = 34560000; // 400 days, renewed on every counted visit
// The anonymous survey and the private panel are deliberately not counted.
const SMASH_VISIT_PAGES = ['inicio', 'metodologia', 'cuenta', 'analisis-top20', 'analisis-torneos'];
// Past these limits a browser or a network stops adding to the totals for that day.
const SMASH_VISIT_DAILY_VIEWS = 300;
const SMASH_VISIT_DAILY_NEW_PER_NETWORK = 50;

final class SmashVisitError extends RuntimeException
{
    public $reason;
    public function __construct(string $reason) { $this->reason = $reason; parent::__construct('No se pudo registrar la visita.'); }
}

// The day of a visit is the calendar day of Guatemala (UTC-6, no daylight saving).
function smash_visit_day(int $now): string
{
    return gmdate('Y-m-d', $now - 21600);
}

function smash_visit_page($value): ?string
{
    return is_string($value) && in_array($value, SMASH_VISIT_PAGES, true) ? $value : null;
}

// Only the site's own pages may count a visit: browsers state where a POST comes from.
function smash_visit_same_origin(array $server): bool
{
    $site = $server['HTTP_SEC_FETCH_SITE'] ?? null;
    if ($site !== null) return $site === 'same-origin';
    $origin = $server['HTTP_ORIGIN'] ?? null; $host = $server['HTTP_HOST'] ?? null;
    if (!is_string($origin) || !is_string($host) || $host === '') return false;
    $parts = parse_url($origin);
    if (!is_array($parts) || !isset($parts['host'])) return false;
    return strcasecmp($parts['host'] . (isset($parts['port']) ? ':' . $parts['port'] : ''), $host) === 0;
}

// Read to skip automated clients; never stored.
function smash_visit_automated($userAgent): bool
{
    return !is_string($userAgent) || trim($userAgent) === ''
        || preg_match('/bot|crawl|spider|slurp|preview|monitor|headless|curl|wget|python|scrapy|lighthouse|facebookexternalhit|whatsapp/i', $userAgent) === 1;
}

// Private key of the counter, created once beside the other private files, outside the site.
function smash_visit_key(string $siteRoot): string
{
    $root = realpath($siteRoot);
    if ($root === false) throw new SmashVisitError('key_unavailable');
    $directory = dirname($root) . '/private-smash'; $path = $directory . '/visits.key';
    for ($attempt = 0; $attempt < 2; $attempt++) {
        if (is_file($path)) {
            $key = @file_get_contents($path);
            if (is_string($key) && preg_match('/\A[0-9a-f]{64}\z/D', $key) === 1) return $key;
            throw new SmashVisitError('key_unavailable');
        }
        if (!is_dir($directory)) throw new SmashVisitError('key_unavailable');
        // Complete file first, then an atomic link: a concurrent request never reads half a key.
        $temporary = $path . '.' . bin2hex(random_bytes(8)) . '.tmp';
        $previous = umask(0077);
        try { $written = @file_put_contents($temporary, bin2hex(random_bytes(32))); } finally { umask($previous); }
        if ($written !== 64) { @unlink($temporary); throw new SmashVisitError('key_unavailable'); }
        @link($temporary, $path); @unlink($temporary);
    }
    throw new SmashVisitError('key_unavailable');
}

function smash_visit_network_hash(string $key, string $address): string
{
    return hash_hmac('sha256', "smashgt-red-v1\n" . $address, $key);
}

// Cookie value: random identifier plus its signature, so only identifiers this server issued count.
function smash_visit_token_issue(string $key): string
{
    $id = bin2hex(random_bytes(16));
    return $id . substr(hash_hmac('sha256', "smashgt-visitante-v1\n" . $id, $key), 0, 32);
}

function smash_visit_token_valid(string $key, $token): bool
{
    return is_string($token) && preg_match('/\A[0-9a-f]{64}\z/D', $token) === 1
        && hash_equals(substr(hash_hmac('sha256', "smashgt-visitante-v1\n" . substr($token, 0, 32), $key), 0, 32), substr($token, 32));
}

function smash_visit_cookie_set(string $token, int $now): void
{
    setcookie(SMASH_VISIT_COOKIE, $token, ['expires' => $now + SMASH_VISIT_COOKIE_AGE, 'path' => '/',
        'secure' => !empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off', 'httponly' => true, 'samesite' => 'Lax']);
}

// Counts one page view. $token is a cookie already verified with smash_visit_token_valid, or null.
// Returns ['status' => 'counted'|'limited', 'token' => cookie value to send, or null].
function smash_visit_record(PDO $pdo, string $key, string $day, string $page, ?string $token, string $networkHash, bool $cookies, bool $signedIn): array
{
    if (smash_visit_page($page) === null || !preg_match('/\A\d{4}-\d{2}-\d{2}\z/D', $day)
        || !preg_match('/\A[0-9a-f]{64}\z/D', $networkHash)) throw new SmashVisitError('invalid_visit');
    if ($pdo->inTransaction()) throw new SmashVisitError('transaction_already_active');
    try {
        $pdo->beginTransaction();
        // Always the same lock order: network, visitor, page.
        $q = $pdo->prepare('INSERT INTO site_network_days (day, network_hash, views) VALUES (?, ?, 0) ON DUPLICATE KEY UPDATE views = views');
        $q->execute([$day, $networkHash]);
        $q = $pdo->prepare('SELECT views, new_visitors FROM site_network_days WHERE day = ? AND network_hash = ? FOR UPDATE');
        $q->execute([$day, $networkHash]); $network = $q->fetch(PDO::FETCH_ASSOC);
        $issued = null; $new = 0;
        if ($token === null && $cookies && (int)$network['new_visitors'] < SMASH_VISIT_DAILY_NEW_PER_NETWORK) {
            $issued = $token = smash_visit_token_issue($key); $new = 1;
        }
        // Without a usable cookie the network itself is the visitor.
        $visitor = $token === null ? $networkHash : hash('sha256', "smashgt-visitante\n" . $token);
        $q = $pdo->prepare('SELECT views FROM site_visitor_days WHERE day = ? AND visitor_hash = ? FOR UPDATE');
        $q->execute([$day, $visitor]); $views = $q->fetchColumn();
        if ($views !== false && (int)$views >= SMASH_VISIT_DAILY_VIEWS) { $pdo->rollBack(); return ['status' => 'limited', 'token' => null]; }
        $q = $pdo->prepare('UPDATE site_network_days SET views = views + 1, new_visitors = new_visitors + ? WHERE day = ? AND network_hash = ?');
        $q->execute([$new, $day, $networkHash]);
        $q = $pdo->prepare('INSERT INTO site_visitor_days (day, visitor_hash, views, signed_in) VALUES (?, ?, 1, ?)
            ON DUPLICATE KEY UPDATE views = views + 1, signed_in = GREATEST(signed_in, ?)');
        $q->execute([$day, $visitor, $signedIn ? 1 : 0, $signedIn ? 1 : 0]);
        $q = $pdo->prepare('INSERT INTO site_visit_days (day, page, views) VALUES (?, ?, 1) ON DUPLICATE KEY UPDATE views = views + 1');
        $q->execute([$day, $page]);
        $pdo->commit();
        return ['status' => 'counted', 'token' => $token];
    } catch (PDOException $error) {
        if ($pdo->inTransaction()) $pdo->rollBack();
        throw new SmashVisitError('visit_write_failed');
    }
}

// Whether this browser carries a live «keep me signed in» cookie. Reads only; creates no session.
function smash_visit_signed_in(PDO $pdo, $remember, int $now): bool
{
    if (!is_string($remember) || preg_match('/\A[0-9a-f]{64}\z/D', $remember) !== 1) return false;
    try {
        $q = $pdo->prepare('SELECT 1 FROM user_sessions WHERE token_hash = ? AND revoked_at IS NULL AND expires_at > ?');
        $q->execute([hash('sha256', $remember), gmdate('Y-m-d H:i:s', $now)]);
        return $q->fetchColumn() !== false;
    } catch (PDOException $error) { return false; }
}
