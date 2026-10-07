<?php
declare(strict_types=1);
// Library only. OAuth credentials stay outside the document root; tokens are used once
// to verify identity and then discarded. No email, passwords or reporter scopes.
const SMASH_ACCOUNT_CALLBACK = 'https://rankingsmashbros.com/oauth.php';
const SMASH_ACCOUNT_MAX_AGE = 28800;
// «Keep me signed in»: an own random identifier in a cookie, only its SHA-256 in SQL.
// Ninety days, renewed while the browser keeps visiting. Never a provider token.
const SMASH_ACCOUNT_REMEMBER_COOKIE = 'smash_recordar';
const SMASH_ACCOUNT_REMEMBER_AGE = 7776000;

final class SmashAccountError extends RuntimeException
{
    public $reason;
    public function __construct(string $reason) { $this->reason = $reason; parent::__construct('No se pudo completar la operación de cuenta.'); }
}

function smash_account_session_start(): void
{
    ini_set('session.use_strict_mode', '1');
    ini_set('session.cookie_httponly', '1');
    ini_set('session.cookie_secure', !empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off' ? '1' : '0');
    ini_set('session.cookie_samesite', 'Lax');
    session_start();
    if (!isset($_SESSION['smash_account_csrf'])) $_SESSION['smash_account_csrf'] = bin2hex(random_bytes(24));
}

function smash_account_session_valid(array $session, int $now): bool
{
    $account = $session['smash_account'] ?? null;
    return is_array($account) && is_string($account['id'] ?? null)
        && preg_match('/\A[1-9][0-9]{0,19}\z/D', $account['id']) === 1
        && is_int($account['at'] ?? null) && $account['at'] > 0 && $account['at'] <= $now
        && $now - $account['at'] < SMASH_ACCOUNT_MAX_AGE;
}

function smash_account_csrf_valid(array $session, $token): bool
{
    return is_string($token) && is_string($session['smash_account_csrf'] ?? null)
        && hash_equals($session['smash_account_csrf'], $token);
}

function smash_account_oauth_config(string $siteRoot): ?array
{
    $root = realpath($siteRoot);
    if ($root === false) throw new SmashAccountError('config_invalid');
    $path = dirname($root) . '/private-smash/oauth.local.php';
    if (!is_file($path)) return null;
    if (realpath($path) !== $path || !is_readable($path)) throw new SmashAccountError('config_invalid');
    $level = ob_get_level(); ob_start();
    try { $config = (static function ($file) { return require $file; })($path); }
    catch (Throwable $error) { throw new SmashAccountError('config_invalid'); }
    finally { while (ob_get_level() > $level) ob_end_clean(); }
    if (!is_array($config)) throw new SmashAccountError('config_invalid');
    if (($config['enabled'] ?? false) !== true) return null;
    if (!is_string($config['client_id'] ?? null) || !preg_match('/\A[A-Za-z0-9_-]{1,128}\z/D', $config['client_id'])
        || !is_string($config['client_secret'] ?? null) || strlen($config['client_secret']) < 8
        || strlen($config['client_secret']) > 1024 || preg_match('/[\x00-\x20\x7f]/', $config['client_secret'])
        || $config['client_secret'] === 'CLIENT_SECRET_AQUI' || $config['client_id'] === 'CLIENT_ID_AQUI'
        || ($config['redirect_uri'] ?? null) !== SMASH_ACCOUNT_CALLBACK) throw new SmashAccountError('config_invalid');
    return $config;
}

function smash_account_authorize(array &$session, array $config, int $now): string
{
    $state = bin2hex(random_bytes(32));
    $session['smash_oauth_pending'] = ['state' => $state, 'at' => $now];
    return 'https://start.gg/oauth/authorize?' . http_build_query(['response_type' => 'code',
        'client_id' => $config['client_id'], 'scope' => 'user.identity',
        'redirect_uri' => SMASH_ACCOUNT_CALLBACK, 'state' => $state], '', '&', PHP_QUERY_RFC3986);
}

function smash_account_consume_state(array &$session, $state, int $now): void
{
    $pending = $session['smash_oauth_pending'] ?? null;
    // Every callback consumes the attempt, including cancellation and invalid state.
    unset($session['smash_oauth_pending']);
    if (!is_array($pending) || !is_string($state) || !is_string($pending['state'] ?? null)
        || !is_int($pending['at'] ?? null) || $pending['at'] > $now || $now - $pending['at'] > 600
        || !hash_equals($pending['state'], $state)) throw new SmashAccountError('oauth_state_invalid');
}

function smash_account_http(string $endpoint, array $body, ?string $token = null): array
{
    if (!in_array($endpoint, ['https://api.start.gg/oauth/access_token', 'https://api.start.gg/gql/alpha'], true)
        || !extension_loaded('curl')) throw new SmashAccountError('provider_unavailable');
    $headers = ['Content-Type: application/json', 'Accept: application/json'];
    if ($token !== null) {
        if ($token === '' || strlen($token) > 8192 || preg_match('/[\x00-\x20\x7f]/', $token)) throw new SmashAccountError('provider_invalid');
        $headers[] = 'Authorization: Bearer ' . $token;
    }
    $response = ''; $handle = curl_init($endpoint);
    curl_setopt_array($handle, [CURLOPT_POST => true, CURLOPT_HTTPHEADER => $headers,
        CURLOPT_POSTFIELDS => json_encode($body), CURLOPT_CONNECTTIMEOUT => 5, CURLOPT_TIMEOUT => 15,
        CURLOPT_FOLLOWLOCATION => false, CURLOPT_PROTOCOLS => CURLPROTO_HTTPS,
        CURLOPT_SSL_VERIFYPEER => true, CURLOPT_SSL_VERIFYHOST => 2,
        CURLOPT_WRITEFUNCTION => static function ($curl, $chunk) use (&$response) {
            if (strlen($response) + strlen($chunk) > 1048576) return 0;
            $response .= $chunk; return strlen($chunk);
        }]);
    $ok = curl_exec($handle); $status = (int)curl_getinfo($handle, CURLINFO_HTTP_CODE); curl_close($handle);
    if ($ok === false || $status !== 200) throw new SmashAccountError('provider_unavailable');
    $data = json_decode($response, true);
    if (!is_array($data) || isset($data['errors']) || isset($data['error'])) throw new SmashAccountError('provider_invalid');
    return $data;
}

function smash_account_exchange(array $config, string $code, ?callable $transport = null): array
{
    if ($code === '' || strlen($code) > 4096 || preg_match('/[\x00-\x20\x7f]/', $code)) throw new SmashAccountError('oauth_code_invalid');
    $send = $transport ?? 'smash_account_http';
    $tokens = $send('https://api.start.gg/oauth/access_token', ['grant_type' => 'authorization_code',
        'client_id' => $config['client_id'], 'client_secret' => $config['client_secret'], 'code' => $code,
        'scope' => 'user.identity', 'redirect_uri' => SMASH_ACCOUNT_CALLBACK], null);
    $token = $tokens['access_token'] ?? null;
    if (!is_string($token) || $token === '' || strlen($token) > 8192 || preg_match('/[\x00-\x20\x7f]/', $token)
        || strcasecmp((string)($tokens['token_type'] ?? ''), 'Bearer') !== 0) throw new SmashAccountError('provider_invalid');
    $result = $send('https://api.start.gg/gql/alpha', ['query' =>
        'query SmashGTIdentity { currentUser { id slug player { id gamerTag } images(type: "profile") { url } } }'], $token);
    return smash_account_identity($result['data']['currentUser'] ?? null);
}

function smash_account_external_id($value): ?string
{
    $id = is_int($value) ? (string)$value : $value;
    if (!is_string($id) || !preg_match('/\A[1-9][0-9]{0,19}\z/D', $id)
        || (strlen($id) === 20 && strcmp($id, '18446744073709551615') > 0)) return null;
    return $id;
}

function smash_account_safe_image($url): ?string
{
    if (!is_string($url) || strlen($url) > 1024 || !filter_var($url, FILTER_VALIDATE_URL)) return null;
    $parts = parse_url($url); $host = strtolower($parts['host'] ?? '');
    return ($parts['scheme'] ?? '') === 'https' && !isset($parts['user']) && !isset($parts['pass'])
        && in_array($host, ['images.start.gg', 'images.smash.gg'], true) ? $url : null;
}

function smash_account_identity($user): array
{
    if (!is_array($user) || ($id = smash_account_external_id($user['id'] ?? null)) === null) throw new SmashAccountError('identity_invalid');
    $player = $user['player'] ?? null;
    if ($player !== null && (!is_array($player) || smash_account_external_id($player['id'] ?? null) === null
        || !is_string($player['gamerTag'] ?? null) || !mb_check_encoding($player['gamerTag'], 'UTF-8')
        || trim($player['gamerTag']) === '')) throw new SmashAccountError('identity_invalid');
    $slug = $user['slug'] ?? null;
    $url = is_string($slug) && preg_match('/\Auser\/[A-Za-z0-9_-]{1,80}\z/D', $slug) ? 'https://www.start.gg/' . $slug : null;
    $image = null;
    foreach (is_array($user['images'] ?? null) ? $user['images'] : [] as $candidate) {
        $image = smash_account_safe_image(is_array($candidate) ? ($candidate['url'] ?? null) : null);
        if ($image !== null) break;
    }
    return ['startggId' => $id, 'playerId' => $player === null ? null : smash_account_external_id($player['id']),
        'tag' => $player === null ? 'Mi cuenta start.gg' : mb_substr(trim($player['gamerTag']), 0, 100, 'UTF-8'),
        'url' => $url, 'avatarUrl' => $image];
}

function smash_account_connect(string $siteRoot): PDO
{
    $pdo = smash_database_connect(smash_database_config($siteRoot));
    $pdo->exec("SET SESSION sql_mode = CONCAT(@@sql_mode, ',STRICT_TRANS_TABLES')");
    $pdo->exec('SET SESSION innodb_lock_wait_timeout = 5, lock_wait_timeout = 5');
    return $pdo;
}

function smash_account_login(PDO $pdo, array $identity, int $now): string
{
    if ($pdo->inTransaction()) throw new SmashAccountError('transaction_already_active');
    try {
        $pdo->beginTransaction();
        $q = $pdo->prepare('SELECT id, player_id, status FROM users WHERE startgg_user_id = ? FOR UPDATE');
        $q->execute([$identity['startggId']]); $user = $q->fetch(PDO::FETCH_ASSOC);
        if ($user && $user['status'] !== 'active') throw new SmashAccountError('account_disabled');
        if ($user && $user['player_id'] !== null && (string)$user['player_id'] !== $identity['playerId']) throw new SmashAccountError('identity_changed');
        if ($identity['playerId'] !== null) {
            $q = $pdo->prepare('SELECT id FROM players WHERE id = ?'); $q->execute([$identity['playerId']]);
            if ($q->fetchColumn() === false) {
                $q = $pdo->prepare('INSERT INTO players (id, tag, profile_url) VALUES (?, ?, ?)');
                $q->execute([$identity['playerId'], $identity['tag'], $identity['url']]);
            }
        }
        $at = gmdate('Y-m-d H:i:s', $now);
        if (!$user) {
            $q = $pdo->prepare('INSERT INTO users (startgg_user_id, player_id, display_name, last_login_at) VALUES (?, ?, ?, ?)');
            $q->execute([$identity['startggId'], $identity['playerId'], $identity['tag'], $at]); $id = (string)$pdo->lastInsertId();
        } else {
            $id = (string)$user['id'];
            $q = $pdo->prepare('UPDATE users SET player_id = ?, display_name = ?, last_login_at = ? WHERE id = ?');
            $q->execute([$identity['playerId'], $identity['tag'], $at, $id]);
        }
        $q = $pdo->prepare("INSERT INTO oauth_connections (user_id, scopes, revoked_at) VALUES (?, 'user.identity', NULL)
            ON DUPLICATE KEY UPDATE scopes = 'user.identity',
            updated_at = IF(revoked_at IS NULL, updated_at, UTC_TIMESTAMP(6)), revoked_at = NULL"); $q->execute([$id]);
        $pdo->commit(); return $id;
    } catch (Throwable $error) {
        if ($pdo->inTransaction()) $pdo->rollBack();
        if ($error instanceof SmashAccountError) throw $error;
        throw new SmashAccountError('account_write_failed');
    }
}

// A second device signing in keeps the connection version (see the IF above, evaluated before
// revoked_at is cleared), so earlier browsers stay signed in. Disconnecting revokes the
// connection and re-linking starts a new version: every older session and cookie stops working.

function smash_account_remember_token($value): ?string
{
    return is_string($value) && preg_match('/\A[0-9a-f]{64}\z/D', $value) === 1 ? $value : null;
}

function smash_account_remember_set(?string $token, int $now): void
{
    setcookie(SMASH_ACCOUNT_REMEMBER_COOKIE, $token ?? '', ['expires' => $token === null ? 1 : $now + SMASH_ACCOUNT_REMEMBER_AGE,
        'path' => '/', 'secure' => !empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off', 'httponly' => true, 'samesite' => 'Lax']);
}

// Returns the cookie value, or null when it could not be stored (for example before migration
// 002 is installed): the visitor is still signed in for this browser session.
function smash_account_remember_create(PDO $pdo, array $account, int $now): ?string
{
    try {
        $token = bin2hex(random_bytes(32)); $at = gmdate('Y-m-d H:i:s', $now);
        $q = $pdo->prepare('DELETE FROM user_sessions WHERE user_id = ? AND (expires_at <= ? OR revoked_at IS NOT NULL)');
        $q->execute([$account['id'], $at]);
        $q = $pdo->prepare('INSERT INTO user_sessions (user_id, token_hash, connection_version, profile_url, avatar_url, created_at, last_used_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)');
        $q->execute([$account['id'], hash('sha256', $token), $account['version'], $account['url'] ?? null, $account['avatarUrl'] ?? null,
            $at, $at, gmdate('Y-m-d H:i:s', $now + SMASH_ACCOUNT_REMEMBER_AGE)]);
        return $q->rowCount() === 1 ? $token : null;
    } catch (PDOException $error) { return null; }
}

// Rebuilds the signed-in session from the cookie. Valid only while the user is active and the
// start.gg connection is the same one, not revoked, that existed when the cookie was issued.
function smash_account_remember_restore(PDO $pdo, $token, int $now): ?array
{
    $token = smash_account_remember_token($token);
    if ($token === null) return null;
    try {
        $at = gmdate('Y-m-d H:i:s', $now);
        $q = $pdo->prepare("SELECT s.id, s.user_id, s.profile_url, s.avatar_url, s.last_used_at, o.updated_at AS version
            FROM user_sessions s JOIN users u ON u.id = s.user_id AND u.status = 'active'
            JOIN oauth_connections o ON o.user_id = s.user_id AND o.revoked_at IS NULL AND o.updated_at = s.connection_version
            WHERE s.token_hash = ? AND s.revoked_at IS NULL AND s.expires_at > ?");
        $q->execute([hash('sha256', $token), $at]); $row = $q->fetch(PDO::FETCH_ASSOC);
        if (!$row) return null;
        // One write per day at most keeps the ninety days sliding without a write on every visit.
        if (strcmp(substr((string)$row['last_used_at'], 0, 10), substr($at, 0, 10)) < 0) {
            $q = $pdo->prepare('UPDATE user_sessions SET last_used_at = ?, expires_at = ? WHERE id = ?');
            $q->execute([$at, gmdate('Y-m-d H:i:s', $now + SMASH_ACCOUNT_REMEMBER_AGE), $row['id']]);
        }
        return ['id' => (string)$row['user_id'], 'at' => $now, 'url' => $row['profile_url'], 'avatarUrl' => $row['avatar_url'], 'version' => $row['version']];
    } catch (PDOException $error) {
        // A storage failure is not a rejected cookie: the caller must keep it and answer «unavailable».
        throw new SmashAccountError('account_unavailable');
    }
}

// Signed in for this browser session, or again through the «keep me signed in» cookie.
// $connect is called only when a cookie has to be checked, so anonymous visitors open no connection.
function smash_account_resume(callable $connect, int $now): bool
{
    if (smash_account_session_valid($_SESSION, $now)) return true;
    $token = $_COOKIE[SMASH_ACCOUNT_REMEMBER_COOKIE] ?? null;
    if ($token === null) return false;
    $account = smash_account_remember_token($token) === null ? null : smash_account_remember_restore($connect(), $token, $now);
    if ($account === null) { smash_account_remember_set(null, $now); return false; }
    session_regenerate_id(true);
    $_SESSION['smash_account'] = $account;
    smash_account_remember_set($token, $now);
    return true;
}

// The account of the current session, re-read from SQL: active user, live connection, same version.
function smash_account_current(PDO $pdo): array
{
    $user = smash_account_user($pdo, $_SESSION['smash_account']['id']);
    if (($_SESSION['smash_account']['version'] ?? null) !== $user['connectionVersion']) throw new SmashAccountError('login_required');
    unset($user['connectionVersion']); return $user;
}

// Signing out ends this browser's cookie; disconnecting ($userId) ends every one of the account.
function smash_account_remember_revoke(PDO $pdo, $token, ?string $userId = null): void
{
    try {
        $token = smash_account_remember_token($token);
        if ($token !== null) { $q = $pdo->prepare('DELETE FROM user_sessions WHERE token_hash = ?'); $q->execute([hash('sha256', $token)]); }
        if ($userId !== null) { $q = $pdo->prepare('DELETE FROM user_sessions WHERE user_id = ?'); $q->execute([$userId]); }
    } catch (PDOException $error) {}
}

function smash_account_user(PDO $pdo, string $id): array
{
    $q = $pdo->prepare('SELECT u.id, u.player_id, u.display_name, p.profile_url, p.country_code, o.revoked_at, o.updated_at AS connection_version
        FROM users u LEFT JOIN players p ON p.id = u.player_id LEFT JOIN oauth_connections o ON o.user_id = u.id
        WHERE u.id = ? AND u.status = ?'); $q->execute([$id, 'active']); $user = $q->fetch(PDO::FETCH_ASSOC);
    if (!$user || $user['revoked_at'] !== null || $user['connection_version'] === null) throw new SmashAccountError('login_required');
    $q = $pdo->prepare("SELECT role FROM user_roles WHERE user_id = ? AND role IN ('player', 'organizer') ORDER BY role");
    $q->execute([$id]); $roles = $q->fetchAll(PDO::FETCH_COLUMN);
    $q = $pdo->prepare('SELECT character_id FROM user_characters WHERE user_id = ? ORDER BY position');
    $q->execute([$id]); $chosen = array_map('strval', $q->fetchAll(PDO::FETCH_COLUMN));
    return ['id' => (string)$user['id'], 'playerId' => $user['player_id'] === null ? null : (string)$user['player_id'],
        'tag' => $user['display_name'] ?? 'Mi cuenta start.gg', 'country' => $user['country_code'],
        'url' => $user['profile_url'], 'roles' => $roles, 'chosen' => $chosen, 'connectionVersion' => $user['connection_version']];
}

function smash_account_preferences(PDO $pdo, string $id, string $action, array $input, string $connectionVersion): void
{
    if ($action === 'roles') {
        $roles = $input['roles'] ?? null;
        if (!is_array($roles) || !array_is_list_compat($roles) || count($roles) < 1 || count($roles) > 2
            || count(array_unique($roles, SORT_REGULAR)) !== count($roles)
            || count(array_filter($roles, static fn($r) => is_string($r) && in_array($r, ['player', 'organizer'], true))) !== count($roles)) throw new SmashAccountError('invalid_roles');
    } elseif ($action === 'characters') {
        $ids = $input['characters'] ?? null;
        if (!is_array($ids) || !array_is_list_compat($ids) || count($ids) < 1 || count($ids) > 3
            || count(array_filter($ids, static fn($v) => smash_account_external_id($v) !== null)) !== count($ids)
            || count(array_unique(array_map('strval', $ids))) !== count($ids)) throw new SmashAccountError('invalid_characters');
        $ids = array_map('strval', $ids);
        $q = $pdo->prepare('SELECT id FROM characters WHERE id IN (' . implode(',', array_fill(0, count($ids), '?')) . ') AND id <> 1746');
        $q->execute($ids); if (count($q->fetchAll()) !== count($ids)) throw new SmashAccountError('invalid_characters');
    } elseif ($action !== 'disconnect') throw new SmashAccountError('invalid_action');
    if ($pdo->inTransaction()) throw new SmashAccountError('transaction_already_active');
    try {
        $pdo->beginTransaction();
        $q = $pdo->prepare('SELECT id FROM users WHERE id = ? AND status = ? FOR UPDATE'); $q->execute([$id, 'active']);
        if ($q->fetchColumn() === false) throw new SmashAccountError('login_required');
        // Recheck authorization while holding the same user lock as login/disconnect.
        $q = $pdo->prepare('SELECT updated_at, revoked_at FROM oauth_connections WHERE user_id = ? FOR UPDATE');
        $q->execute([$id]); $connection = $q->fetch(PDO::FETCH_ASSOC);
        if (!$connection || $connection['revoked_at'] !== null || $connection['updated_at'] !== $connectionVersion) throw new SmashAccountError('login_required');
        if ($action === 'roles') {
            $q = $pdo->prepare("DELETE FROM user_roles WHERE user_id = ? AND role IN ('player', 'organizer')"); $q->execute([$id]);
            $q = $pdo->prepare('INSERT INTO user_roles (user_id, role) VALUES (?, ?)'); foreach ($roles as $role) $q->execute([$id, $role]);
        } elseif ($action === 'characters') {
            $q = $pdo->prepare('DELETE FROM user_characters WHERE user_id = ?'); $q->execute([$id]);
            $q = $pdo->prepare('INSERT INTO user_characters (user_id, position, character_id) VALUES (?, ?, ?)');
            foreach ($ids as $index => $character) $q->execute([$id, $index + 1, $character]);
        } else {
            $q = $pdo->prepare('UPDATE oauth_connections SET revoked_at = UTC_TIMESTAMP(6), access_token_encrypted = NULL,
                refresh_token_encrypted = NULL, encryption_key_id = NULL WHERE user_id = ?'); $q->execute([$id]);
        }
        $pdo->commit();
    } catch (Throwable $error) {
        if ($pdo->inTransaction()) $pdo->rollBack();
        if ($error instanceof SmashAccountError) throw $error;
        throw new SmashAccountError('account_write_failed');
    }
}

function array_is_list_compat(array $value): bool
{
    return $value === [] || array_keys($value) === range(0, count($value) - 1);
}

function smash_account_public(string $siteRoot): array
{
    $path = $siteRoot . '/data/public.json';
    if (!is_file($path) || filesize($path) > 33554432) throw new SmashAccountError('ranking_unavailable');
    $content = @file_get_contents($path); $data = is_string($content) ? json_decode($content, true) : null;
    if (!is_array($data) || !is_array($data['players'] ?? null) || !is_array($data['localRanking']['players'] ?? null)
        || !is_string($data['generatedAt'] ?? null) || ($data['rankingComputed'] ?? false) !== true) throw new SmashAccountError('ranking_unavailable');
    return $data;
}

function smash_account_profile(array $public, ?string $playerId): array
{
    $profiles = [];
    foreach (['combined' => $public, 'guatemala' => $public['localRanking']] as $scope => $view) {
        $player = null;
        foreach ($view['players'] as $candidate) if ((string)$candidate['id'] === $playerId) { $player = $candidate; break; }
        $ledger = [];
        // Results include opponents outside the classified list. Missing rank is not evidence
        // of inactivity or proof that a country/nationality requirement has been checked.
        foreach ($view['results'] ?? [] as $set) {
            $position = array_search($playerId, $set['playerIds'], true);
            if ($position === false || $playerId === null) continue;
            $event = (string)$set['eventId'];
            if (!isset($ledger[$event])) $ledger[$event] = ['wins' => 0, 'losses' => 0];
            $ledger[$event][$position === 0 ? 'wins' : 'losses']++;
        }
        $events = [];
        foreach ($public['events'] as $event) {
            // Retain foreign attendance from the other view, with an explicit exclusion reason.
            $record = $ledger[(string)$event['id']] ?? null;
            if ($record === null && $scope === 'guatemala') {
                foreach ($public['results'] ?? [] as $set) if ((string)$set['eventId'] === (string)$event['id']) {
                    $position = array_search($playerId, $set['playerIds'], true);
                    if ($position !== false && $playerId !== null) {
                        if ($record === null) $record = ['wins' => 0, 'losses' => 0];
                        $record[$position === 0 ? 'wins' : 'losses']++;
                    }
                }
            }
            if ($record === null) continue;
            $counts = isset($ledger[(string)$event['id']]);
            $events[] = ['id' => (string)$event['id'], 'name' => $event['name'], 'eventName' => $event['eventName'],
                'date' => $event['date'], 'country' => $event['country'], 'url' => $event['url'],
                'wins' => $record['wins'], 'losses' => $record['losses'], 'counts' => $counts,
                'reason' => $counts ? null : 'Torneo internacional: no entra en la vista Solo Guatemala.'];
        }
        usort($events, static fn($a, $b) => strcmp($b['date'], $a['date']) ?: strcmp($a['id'], $b['id']));
        $wins = array_sum(array_column($ledger, 'wins')); $losses = array_sum(array_column($ledger, 'losses'));
        $profiles[$scope] = ['rank' => $player['rank'] ?? null, 'points' => $player['rating'] ?? null,
            'previousRank' => $player['previousRank'] ?? null, 'previousCutAt' => $view['previousCutAt'] ?? null,
            'total' => count($view['players']), 'top100Points' => $view['players'][99]['rating'] ?? null,
            'wins' => $player['wins'] ?? $wins, 'losses' => $player['losses'] ?? $losses,
            'countedEvents' => $player['events'] ?? count($ledger), 'events' => $events,
            'results' => array_values(array_filter($view['results'] ?? [], static fn($set) => $playerId !== null && in_array($playerId, $set['playerIds'], true))),
            'detected' => $player['mains'] ?? [], 'mainCoverage' => $player['mainCoverage'] ?? null];
    }
    // Opponents this player met, with their place in each view of the same published cut.
    // A rival outside a view has no entry there: no place is not a weak rival, and nothing is invented.
    $rivals = [];
    if ($playerId !== null) {
        $index = ['combined' => [], 'guatemala' => []];
        foreach (['combined' => $public, 'guatemala' => $public['localRanking']] as $scope => $view) {
            foreach ($view['players'] as $candidate) $index[$scope][(string)$candidate['id']] = $candidate;
        }
        foreach ([$public['results'] ?? [], $public['localRanking']['results'] ?? []] as $sets) {
            foreach ($sets as $set) {
                $position = array_search($playerId, $set['playerIds'], true);
                if ($position === false) continue;
                $other = $set['playerIds'][1 - $position] ?? null;
                if (!is_string($other) || $other === '' || $other === $playerId || isset($rivals[$other])) continue;
                $entry = ['tag' => is_string($set['playerTags'][1 - $position] ?? null) ? $set['playerTags'][1 - $position] : null, 'url' => null, 'main' => null];
                foreach (['combined', 'guatemala'] as $scope) {
                    $ranked = $index[$scope][$other] ?? null;
                    $entry[$scope] = $ranked === null ? null : ['rank' => $ranked['rank'] ?? null, 'points' => $ranked['rating'] ?? null];
                    if ($ranked === null) continue;
                    $entry['tag'] = $ranked['tag'] ?? $entry['tag']; $entry['url'] = $entry['url'] ?? ($ranked['url'] ?? null);
                    $entry['main'] = $entry['main'] ?? ($ranked['mains'][0]['characterId'] ?? null);
                }
                $rivals[$other] = $entry;
            }
        }
    }
    return ['rivals' => (object)$rivals, 'generatedAt' => $public['generatedAt'], 'seasonYear' => $public['seasonYear'],
        'methodVersion' => $public['methodVersion'], 'eligibilityRules' => $public['eligibilityRules'],
        'historyCoverage' => 'Resultados disponibles en el corte publicado. No es tu historial completo de start.gg.', 'views' => $profiles];
}
