<?php
declare(strict_types=1);

// Library only. Apache blocks direct access; nothing is read, written or requested on inclusion.
// Premium is a subscription paid on Recurrente's hosted page. This site never sees a card and
// stores only Recurrente's identifiers and the state of the subscription: no name, e-mail,
// phone or tax id of the payer. Paying never changes points, rank or eligibility.

const SMASH_PREMIUM_API = 'https://app.recurrente.com/api';
const SMASH_PREMIUM_RETURN = 'https://rankingsmashbros.com/cuenta.html';
const SMASH_PREMIUM_PLANS = [
    'monthly' => ['name' => 'Smash GT Premium · mensual', 'cents' => 300, 'interval' => 'month'],
    'annual' => ['name' => 'Smash GT Premium · anual', 'cents' => 2400, 'interval' => 'year'],
];
// A checkout nobody paid stops blocking a new attempt after this long.
const SMASH_PREMIUM_PENDING_AGE = 3600;

final class SmashPremiumError extends RuntimeException
{
    public $reason;
    public function __construct(string $reason) { $this->reason = $reason; parent::__construct('No se pudo completar la operación de premium.'); }
}

// Private keys beside the other private files. Missing or disabled means premium is simply off.
function smash_premium_config(string $siteRoot): ?array
{
    $root = realpath($siteRoot);
    if ($root === false) throw new SmashPremiumError('config_invalid');
    $path = dirname($root) . '/private-smash/recurrente.local.php';
    if (!is_file($path)) return null;
    if (realpath($path) !== $path || !is_readable($path)) throw new SmashPremiumError('config_invalid');
    $level = ob_get_level(); ob_start();
    try { $config = (static function ($file) { return require $file; })($path); }
    catch (Throwable $error) { throw new SmashPremiumError('config_invalid'); }
    finally { while (ob_get_level() > $level) ob_end_clean(); }
    if (!is_array($config)) throw new SmashPremiumError('config_invalid');
    if (($config['enabled'] ?? false) !== true) return null;
    $key = $config['secret_key'] ?? null; $webhook = $config['webhook_secret'] ?? null;
    if (!is_string($key) || preg_match('/\Ask_(test|live)_[A-Za-z0-9_-]{16,200}\z/D', $key, $mode) !== 1
        || !is_string($webhook) || preg_match('/\Awhsec_[A-Za-z0-9+\/=]{16,200}\z/D', $webhook) !== 1) throw new SmashPremiumError('config_invalid');
    return ['secret_key' => $key, 'webhook_secret' => $webhook, 'live' => $mode[1] === 'live'];
}

// One request to Recurrente's fixed API. Only the path varies and it is built from validated
// identifiers; no URL comes from a visitor or from a webhook. Errors never carry response bodies.
function smash_premium_request(array $config, string $method, string $path, ?array $body = null, ?callable $transport = null): array
{
    if (preg_match('/\A\/[a-z_]+(\/[A-Za-z0-9_]{4,80})?(\?[a-z_]+=[A-Za-z0-9_]{1,80})?\z/D', $path) !== 1) throw new SmashPremiumError('provider_request_invalid');
    if ($transport !== null) $result = $transport($method, $path, $body);
    else {
        $handle = curl_init(SMASH_PREMIUM_API . $path);
        $headers = ['X-SECRET-KEY: ' . $config['secret_key'], 'Accept: application/json'];
        $options = [CURLOPT_CUSTOMREQUEST => $method, CURLOPT_RETURNTRANSFER => true, CURLOPT_FOLLOWLOCATION => false,
            CURLOPT_CONNECTTIMEOUT => 5, CURLOPT_TIMEOUT => 15, CURLOPT_PROTOCOLS => CURLPROTO_HTTPS];
        if ($body !== null) { $headers[] = 'Content-Type: application/json'; $options[CURLOPT_POSTFIELDS] = json_encode($body, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES); }
        $options[CURLOPT_HTTPHEADER] = $headers;
        curl_setopt_array($handle, $options);
        $raw = curl_exec($handle); $status = (int)curl_getinfo($handle, CURLINFO_RESPONSE_CODE); unset($handle);
        $result = ['status' => $status, 'body' => is_string($raw) ? json_decode($raw, true) : null];
    }
    if (!is_array($result) || !is_int($result['status'] ?? null)) throw new SmashPremiumError('provider_unavailable');
    if ($result['status'] === 404) throw new SmashPremiumError('provider_not_found');
    if ($result['status'] < 200 || $result['status'] > 299 || !is_array($result['body'] ?? null)) throw new SmashPremiumError('provider_unavailable');
    return $result['body'];
}

function smash_premium_id($value, string $prefix): ?string
{
    return is_string($value) && preg_match('/\A' . $prefix . '_[A-Za-z0-9]{4,70}\z/D', $value) === 1 ? $value : null;
}

// Recurrente sends ISO 8601 with an offset; SQL keeps UTC.
function smash_premium_time($value): ?string
{
    if (!is_string($value) || $value === '') return null;
    $time = strtotime($value);
    return $time === false ? null : gmdate('Y-m-d H:i:s', $time);
}

function smash_premium_connect(string $siteRoot): PDO
{
    $pdo = smash_database_connect(smash_database_config($siteRoot));
    $pdo->exec("SET SESSION sql_mode = CONCAT(@@sql_mode, ',STRICT_TRANS_TABLES')");
    $pdo->exec('SET SESSION innodb_lock_wait_timeout = 5, lock_wait_timeout = 5');
    return $pdo;
}

// What this account has right now. Premium lasts while a paid period is running: a cancelled or
// past-due subscription keeps access until the end of what was already paid, and no longer.
function smash_premium_status(PDO $pdo, string $userId, bool $live, int $now): array
{
    try {
        $q = $pdo->prepare("SELECT plan, status, current_period_end, cancel_requested_at FROM premium_subscriptions
            WHERE user_id = ? AND live_mode = ? AND status <> 'pending' ORDER BY (current_period_end IS NULL), current_period_end DESC, id DESC LIMIT 1");
        $q->execute([$userId, $live ? 1 : 0]); $row = $q->fetch(PDO::FETCH_ASSOC);
        $q = $pdo->prepare("SELECT COUNT(*) FROM premium_subscriptions WHERE user_id = ? AND live_mode = ? AND status = 'pending' AND created_at > ?");
        $q->execute([$userId, $live ? 1 : 0, gmdate('Y-m-d H:i:s', $now - SMASH_PREMIUM_PENDING_AGE)]); $pending = (int)$q->fetchColumn() > 0;
    } catch (PDOException $error) { throw new SmashPremiumError('premium_read_failed'); }
    if (!$row) return ['premium' => false, 'plan' => null, 'status' => 'none', 'currentPeriodEnd' => null, 'cancelRequested' => false, 'pending' => $pending];
    $end = $row['current_period_end'] === null ? null : substr((string)$row['current_period_end'], 0, 19);
    $running = $end !== null && strcmp($end, gmdate('Y-m-d H:i:s', $now)) > 0 && in_array($row['status'], ['active', 'past_due', 'canceled'], true);
    return ['premium' => $running, 'plan' => $row['plan'], 'status' => $running ? $row['status'] : 'ended',
        'currentPeriodEnd' => $end === null ? null : str_replace(' ', 'T', $end) . '+00:00',
        'cancelRequested' => $row['cancel_requested_at'] !== null || $row['status'] === 'canceled', 'pending' => $pending];
}

// Opens a hosted checkout for one plan and remembers it as pending. Returns the URL to send the browser to.
function smash_premium_start(PDO $pdo, array $config, string $userId, $plan, int $now, ?callable $transport = null): string
{
    if (!is_string($plan) || !isset(SMASH_PREMIUM_PLANS[$plan])) throw new SmashPremiumError('invalid_plan');
    $current = smash_premium_status($pdo, $userId, $config['live'], $now);
    if ($current['premium'] && !$current['cancelRequested']) throw new SmashPremiumError('invalid_already_premium');
    $item = SMASH_PREMIUM_PLANS[$plan];
    $checkout = smash_premium_request($config, 'POST', '/checkouts', [
        'items' => [['name' => $item['name'], 'currency' => 'USD', 'amount_in_cents' => $item['cents'], 'quantity' => 1,
            'charge_type' => 'recurring', 'billing_interval' => $item['interval'], 'billing_interval_count' => 1]],
        'success_url' => SMASH_PREMIUM_RETURN . '#premium-pago', 'cancel_url' => SMASH_PREMIUM_RETURN . '#premium-cancelado',
        // Our own account number only; it is not personal data and lets a payment be traced back.
        'metadata' => ['smash_user' => $userId, 'smash_plan' => $plan],
    ], $transport);
    $id = smash_premium_id($checkout['id'] ?? null, 'ch'); $url = $checkout['checkout_url'] ?? null;
    if ($id === null || !is_string($url) || preg_match('/\Ahttps:\/\/app\.recurrente\.com\/[A-Za-z0-9_\/-]{1,200}\z/D', $url) !== 1
        || ($checkout['live_mode'] ?? null) !== $config['live']) throw new SmashPremiumError('provider_invalid');
    try {
        $at = gmdate('Y-m-d H:i:s', $now);
        $q = $pdo->prepare("INSERT INTO premium_subscriptions (user_id, plan, live_mode, provider_checkout_id, status, created_at, updated_at) VALUES (?, ?, ?, ?, 'pending', ?, ?)");
        $q->execute([$userId, $plan, $config['live'] ? 1 : 0, $id, $at, $at]);
    } catch (PDOException $error) { throw new SmashPremiumError('premium_write_failed'); }
    return $url;
}

// Copies the state of one subscription from Recurrente into our row. Recurrente is the source of
// truth: a webhook or a browser returning from the checkout only tells us to come and look.
function smash_premium_sync(PDO $pdo, array $config, string $subscriptionId, int $now, ?callable $transport = null): string
{
    if (smash_premium_id($subscriptionId, 'su') === null) throw new SmashPremiumError('provider_invalid');
    $remote = smash_premium_request($config, 'GET', '/subscriptions/' . $subscriptionId, null, $transport);
    $checkout = smash_premium_id($remote['checkout']['id'] ?? null, 'ch');
    if (smash_premium_id($remote['id'] ?? null, 'su') !== $subscriptionId || $checkout === null) return 'unrelated';
    $map = ['active' => 'active', 'past_due' => 'past_due', 'canceled' => 'canceled', 'cancelled' => 'canceled', 'paused' => 'past_due'];
    $status = $map[$remote['status'] ?? ''] ?? 'ended';
    $end = smash_premium_time($remote['current_period_end'] ?? null);
    try {
        $q = $pdo->prepare('UPDATE premium_subscriptions SET provider_subscription_id = ?, status = ?, current_period_end = COALESCE(?, current_period_end), updated_at = ?
            WHERE provider_checkout_id = ? AND live_mode = ?');
        $q->execute([$subscriptionId, $status, $end, gmdate('Y-m-d H:i:s', $now), $checkout, $config['live'] ? 1 : 0]);
        if ($q->rowCount() > 0) return 'synced';
        $q = $pdo->prepare('SELECT 1 FROM premium_subscriptions WHERE provider_checkout_id = ? AND live_mode = ?');
        $q->execute([$checkout, $config['live'] ? 1 : 0]);
        // Subscriptions of the same Recurrente account that this site did not start are not ours.
        return $q->fetchColumn() === false ? 'unrelated' : 'synced';
    } catch (PDOException $error) { throw new SmashPremiumError('premium_write_failed'); }
}

// Looks again at what this account has open: a checkout that may have been paid, or a paid
// period that ended and may have renewed. Used when the browser returns and on normal reads, so
// premium does not depend on a webhook arriving.
function smash_premium_refresh(PDO $pdo, array $config, string $userId, int $now, ?callable $transport = null): void
{
    try {
        $at = gmdate('Y-m-d H:i:s', $now);
        $q = $pdo->prepare("SELECT provider_checkout_id, provider_subscription_id, status FROM premium_subscriptions WHERE user_id = ? AND live_mode = ?
            AND ((status = 'pending' AND created_at > ?) OR (status IN ('active', 'past_due') AND current_period_end <= ?)) ORDER BY id DESC LIMIT 3");
        $q->execute([$userId, $config['live'] ? 1 : 0, gmdate('Y-m-d H:i:s', $now - SMASH_PREMIUM_PENDING_AGE), $at]);
        $rows = $q->fetchAll(PDO::FETCH_ASSOC);
    } catch (PDOException $error) { throw new SmashPremiumError('premium_read_failed'); }
    foreach ($rows as $row) {
        try {
            $subscription = $row['provider_subscription_id'];
            if ($subscription === null) {
                $checkout = smash_premium_request($config, 'GET', '/checkouts/' . $row['provider_checkout_id'], null, $transport);
                if (($checkout['status'] ?? null) !== 'paid') continue;
                $subscription = smash_premium_id($checkout['subscription']['id'] ?? null, 'su');
                if ($subscription === null) {
                    $list = smash_premium_request($config, 'GET', '/subscriptions', null, $transport);
                    foreach ($list as $candidate) {
                        if (is_array($candidate) && ($candidate['checkout']['id'] ?? null) === $row['provider_checkout_id']) $subscription = smash_premium_id($candidate['id'] ?? null, 'su');
                    }
                }
                if ($subscription === null) continue;
            }
            smash_premium_sync($pdo, $config, $subscription, $now, $transport);
        } catch (SmashPremiumError $error) {
            // Recurrente being slow must not break the account page: the last known state stands.
            if (!in_array($error->reason, ['provider_unavailable', 'provider_not_found'], true)) throw $error;
        }
    }
}

// Stops future charges. Access continues until the end of the period already paid.
function smash_premium_cancel(PDO $pdo, array $config, string $userId, int $now, ?callable $transport = null): void
{
    try {
        $q = $pdo->prepare("SELECT id, provider_subscription_id FROM premium_subscriptions WHERE user_id = ? AND live_mode = ? AND status IN ('active', 'past_due')
            AND provider_subscription_id IS NOT NULL ORDER BY id DESC LIMIT 1");
        $q->execute([$userId, $config['live'] ? 1 : 0]); $row = $q->fetch(PDO::FETCH_ASSOC);
    } catch (PDOException $error) { throw new SmashPremiumError('premium_read_failed'); }
    if (!$row) throw new SmashPremiumError('invalid_no_subscription');
    try { smash_premium_request($config, 'DELETE', '/subscriptions/' . $row['provider_subscription_id'], null, $transport); }
    catch (SmashPremiumError $error) { if ($error->reason !== 'provider_not_found') throw $error; }
    try {
        $at = gmdate('Y-m-d H:i:s', $now);
        $q = $pdo->prepare("UPDATE premium_subscriptions SET status = 'canceled', cancel_requested_at = ?, updated_at = ? WHERE id = ?");
        $q->execute([$at, $at, $row['id']]);
    } catch (PDOException $error) { throw new SmashPremiumError('premium_write_failed'); }
}

// Svix signature of a webhook: HMAC-SHA256 over «id.timestamp.body» with the endpoint's secret.
function smash_premium_webhook_valid(string $secret, $id, $timestamp, $signatures, string $body, int $now): bool
{
    if (!is_string($id) || preg_match('/\A[A-Za-z0-9_-]{1,120}\z/D', $id) !== 1 || !is_string($timestamp) || preg_match('/\A[0-9]{1,12}\z/D', $timestamp) !== 1
        || abs($now - (int)$timestamp) > 300 || !is_string($signatures) || strpos($secret, 'whsec_') !== 0) return false;
    $key = base64_decode(substr($secret, 6), true);
    if ($key === false || $key === '') return false;
    $expected = base64_encode(hash_hmac('sha256', $id . '.' . $timestamp . '.' . $body, $key, true));
    $valid = false;
    // The header may carry several signatures while a secret is being rotated.
    foreach (explode(' ', $signatures) as $candidate) {
        if (strpos($candidate, 'v1,') === 0 && hash_equals($expected, substr($candidate, 3))) $valid = true;
    }
    return $valid;
}

// Processes one verified webhook once. The body is used only to learn which subscription to look
// up at Recurrente; nothing else from it is trusted or stored.
function smash_premium_event(PDO $pdo, array $config, string $eventId, $payload, int $now, ?callable $transport = null): string
{
    $type = is_array($payload) && is_string($payload['event_type'] ?? null) && preg_match('/\A[a-z0-9_.-]{1,80}\z/D', $payload['event_type']) === 1 ? $payload['event_type'] : 'unknown';
    try {
        $q = $pdo->prepare('SELECT outcome FROM premium_events WHERE event_id = ?'); $q->execute([$eventId]);
        if ($q->fetchColumn() !== false) return 'duplicate';
    } catch (PDOException $error) { throw new SmashPremiumError('premium_read_failed'); }
    $outcome = 'ignored';
    $subscription = strpos($type, 'subscription.') === 0 ? smash_premium_id($payload['id'] ?? null, 'su') : null;
    if ($subscription !== null) $outcome = smash_premium_sync($pdo, $config, $subscription, $now, $transport);
    try {
        // Recorded only after the work succeeded, so a failed delivery is processed when Recurrente retries.
        $q = $pdo->prepare('INSERT IGNORE INTO premium_events (event_id, event_type, outcome, received_at) VALUES (?, ?, ?, ?)');
        $q->execute([$eventId, $type, $outcome, gmdate('Y-m-d H:i:s', $now)]);
    } catch (PDOException $error) { throw new SmashPremiumError('premium_write_failed'); }
    return $outcome;
}
