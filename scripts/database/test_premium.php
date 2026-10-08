<?php
declare(strict_types=1);
// Premium contracts with an invented provider. Never contacts Recurrente; SQL part needs a local disposable database.
require_once __DIR__ . '/../../ranking-smash-ultimate/database.php';
require_once __DIR__ . '/../../ranking-smash-ultimate/premium.php';
function check_premium($condition, string $description): void { if (!$condition) throw new RuntimeException($description); }
function premium_rejects(callable $operation, string $reason): void {
    try { $operation(); } catch (SmashPremiumError $error) { check_premium($error->reason === $reason, 'Unexpected rejection: ' . $error->reason); return; }
    throw new RuntimeException('Expected rejection: ' . $reason);
}
check_premium(SMASH_PREMIUM_PLANS['monthly']['cents'] === 300 && SMASH_PREMIUM_PLANS['annual']['cents'] === 2400 && SMASH_PREMIUM_PLANS['annual']['interval'] === 'year', 'Prices decided by the owner: 3 USD a month, 24 USD a year');
// Private configuration.
$root = sys_get_temp_dir() . '/smash-premium-' . bin2hex(random_bytes(6));
mkdir($root); mkdir($root . '/site'); mkdir($root . '/private-smash'); $file = $root . '/private-smash/recurrente.local.php';
$write = static fn(array $config) => file_put_contents($file, '<?php echo "DO_NOT_PRINT"; return ' . var_export($config, true) . ';');
$testKey = 'sk_test_' . str_repeat('a', 40); $secret = 'whsec_' . base64_encode(str_repeat('k', 24));
try {
    check_premium(smash_premium_config($root . '/site') === null, 'Missing configuration turns premium off');
    $write(['enabled' => false, 'secret_key' => $testKey, 'webhook_secret' => $secret]);
    ob_start(); $off = smash_premium_config($root . '/site'); $printed = ob_get_clean();
    check_premium($off === null && $printed === '', 'Disabled configuration is off and prints nothing');
    $write(['enabled' => true, 'secret_key' => $testKey, 'webhook_secret' => $secret]);
    check_premium(smash_premium_config($root . '/site') === ['secret_key' => $testKey, 'webhook_secret' => $secret, 'live' => false], 'Test key means test mode');
    $write(['enabled' => true, 'secret_key' => 'sk_live_' . str_repeat('b', 40), 'webhook_secret' => $secret]);
    check_premium(smash_premium_config($root . '/site')['live'] === true, 'Live key means real charges');
    foreach ([['secret_key' => 'sk_test_LLAVE_AQUI'], ['secret_key' => 'pk_test_' . str_repeat('a', 40)], ['webhook_secret' => 'whsec_SECRETO AQUI'], ['webhook_secret' => 'secret']] as $bad) {
        $write($bad + ['enabled' => true, 'secret_key' => $testKey, 'webhook_secret' => $secret]);
        premium_rejects(static fn() => smash_premium_config($root . '/site'), 'config_invalid');
    }
} finally { @unlink($file); rmdir($root . '/private-smash'); rmdir($root . '/site'); rmdir($root); }
$config = ['secret_key' => $testKey, 'webhook_secret' => $secret, 'live' => false];
// Requests: fixed host, validated paths, no response body in errors.
premium_rejects(static fn() => smash_premium_request($config, 'GET', '/subscriptions/../account', null, static fn() => ['status' => 200, 'body' => []]), 'provider_request_invalid');
premium_rejects(static fn() => smash_premium_request($config, 'GET', 'https://evil.test/x', null, static fn() => ['status' => 200, 'body' => []]), 'provider_request_invalid');
premium_rejects(static fn() => smash_premium_request($config, 'GET', '/checkouts', null, static fn() => ['status' => 500, 'body' => ['error' => 'secret detail']]), 'provider_unavailable');
premium_rejects(static fn() => smash_premium_request($config, 'GET', '/checkouts', null, static fn() => ['status' => 200, 'body' => 'not json']), 'provider_unavailable');
premium_rejects(static fn() => smash_premium_request($config, 'GET', '/subscriptions/su_missing1', null, static fn() => ['status' => 404, 'body' => []]), 'provider_not_found');
check_premium(smash_premium_id('su_ab12cd34', 'su') === 'su_ab12cd34' && smash_premium_id('ch_ab12', 'su') === null && smash_premium_id('su_../x', 'su') === null && smash_premium_id(['su_ab12cd34'], 'su') === null, 'Provider identifiers are validated');
check_premium(smash_premium_time('2026-11-07T17:00:00-06:00') === '2026-11-07 23:00:00' && smash_premium_time('2026-11-07T23:00:00Z') === '2026-11-07 23:00:00' && smash_premium_time('') === null && smash_premium_time(null) === null, 'Provider times are stored in UTC');
// Webhook signature (Svix): id.timestamp.body with the base64 secret.
$now = 1791400000; $body = '{"event_type":"subscription.create","id":"su_ab12cd34"}';
$sign = static fn(string $id, int $at, string $payload, string $with) => 'v1,' . base64_encode(hash_hmac('sha256', $id . '.' . $at . '.' . $payload, base64_decode(substr($with, 6)), true));
$good = $sign('msg_1', $now, $body, $secret);
check_premium(smash_premium_webhook_valid($secret, 'msg_1', (string)$now, $good, $body, $now), 'A correctly signed webhook is accepted');
check_premium(smash_premium_webhook_valid($secret, 'msg_1', (string)$now, 'v1,AAAA ' . $good, $body, $now), 'One valid signature among several is enough (secret rotation)');
$other = 'whsec_' . base64_encode(str_repeat('z', 24));
foreach ([[$secret, 'msg_1', (string)$now, $good, $body . ' ', $now], [$secret, 'msg_2', (string)$now, $good, $body, $now], [$secret, 'msg_1', (string)($now + 1), $good, $body, $now],
    [$other, 'msg_1', (string)$now, $good, $body, $now], [$secret, 'msg_1', (string)$now, substr($good, 3), $body, $now], [$secret, 'msg_1', (string)$now, $good, $body, $now + 301],
    [$secret, 'msg_1', (string)$now, $good, $body, $now - 301], [$secret, null, (string)$now, $good, $body, $now], [$secret, 'msg_1', null, $good, $body, $now], [$secret, 'msg_1', (string)$now, null, $body, $now],
    ['whsec_', 'msg_1', (string)$now, $sign('msg_1', $now, $body, 'whsec_'), $body, $now]] as $case) {
    check_premium(!smash_premium_webhook_valid(...$case), 'Altered body, id, time, secret, format, stale or missing parts are rejected');
}
echo "Premium configuration, request, time and webhook signature contracts passed.\n";
$db = getenv('SMASH_SCHEMA_TEST_DB');
if (!$db) { echo "SQL tests skipped: no disposable database configured.\n"; exit; }
if (strpos($db, 'smash_schema_test') !== 0 || !in_array(getenv('SMASH_SCHEMA_TEST_HOST') ?: '127.0.0.1', ['127.0.0.1', 'localhost'], true)) throw new RuntimeException('Disposable database required');
$pdo = smash_database_connect(['host' => '127.0.0.1', 'port' => (int)(getenv('SMASH_SCHEMA_TEST_PORT') ?: 3306), 'name' => $db, 'user' => 'root', 'password' => getenv('SMASH_SCHEMA_TEST_PASSWORD')]);
$clean = static function () use ($pdo) { $pdo->exec('DELETE FROM users WHERE startgg_user_id BETWEEN 8999600 AND 8999699'); $pdo->exec("DELETE FROM premium_events WHERE event_id LIKE 'msg_fixture_%'"); };
// An invented Recurrente: checkouts and subscriptions kept in memory, every call recorded.
$remote = ['checkouts' => [], 'subscriptions' => [], 'calls' => [], 'down' => false];
$provider = static function (string $method, string $path, ?array $body) use (&$remote) {
    $remote['calls'][] = $method . ' ' . $path;
    if ($remote['down']) return ['status' => 503, 'body' => null];
    if ($method === 'POST' && $path === '/checkouts') {
        $id = 'ch_fixture' . (count($remote['checkouts']) + 1);
        $remote['checkouts'][$id] = ['id' => $id, 'status' => 'unpaid', 'live_mode' => false, 'request' => $body, 'checkout_url' => 'https://app.recurrente.com/checkout-session/' . $id];
        return ['status' => 201, 'body' => $remote['checkouts'][$id]];
    }
    if ($method === 'GET' && $path === '/subscriptions') return ['status' => 200, 'body' => array_values($remote['subscriptions'])];
    [, $kind, $id] = explode('/', $path) + [null, null, null];
    if ($method === 'DELETE' && $kind === 'subscriptions' && isset($remote['subscriptions'][$id])) { $remote['subscriptions'][$id]['status'] = 'cancelled'; return ['status' => 200, 'body' => ['message' => 'ok']]; }
    if ($method === 'GET' && isset($remote[$kind][$id])) return ['status' => 200, 'body' => $remote[$kind][$id]];
    return ['status' => 404, 'body' => []];
};
$pay = static function (string $checkout, string $subscription, string $end) use (&$remote) {
    $remote['checkouts'][$checkout]['status'] = 'paid';
    // Fields this site must never keep are present on purpose.
    $remote['subscriptions'][$subscription] = ['id' => $subscription, 'status' => 'active', 'current_period_end' => $end, 'checkout' => ['id' => $checkout],
        'subscriber' => ['full_name' => 'Persona Privada', 'email' => 'privada@example.com', 'phone_number' => '+50200000000'], 'tax_id' => 'NIT-PRIVADO',
        'default_payment_method' => ['card' => ['last4' => '4242', 'network' => 'visa']]];
};
try {
    $clean();
    $pdo->exec('INSERT INTO users (startgg_user_id) VALUES (8999601), (8999602)');
    $one = (string)$pdo->query('SELECT id FROM users WHERE startgg_user_id=8999601')->fetchColumn(); $two = (string)$pdo->query('SELECT id FROM users WHERE startgg_user_id=8999602')->fetchColumn();
    $now = gmmktime(12, 0, 0, 10, 8, 2026);
    $none = ['premium' => false, 'plan' => null, 'status' => 'none', 'currentPeriodEnd' => null, 'startedAt' => null, 'cancelRequested' => false, 'pending' => false];
    check_premium(smash_premium_status($pdo, $one, false, $now) === $none, 'An account without a subscription is not premium');
    premium_rejects(static fn() => smash_premium_start($pdo, $config, $one, 'lifetime', $now, $provider), 'invalid_plan');
    premium_rejects(static fn() => smash_premium_start($pdo, $config, $one, ['annual'], $now, $provider), 'invalid_plan');
    // Start the annual plan.
    $url = smash_premium_start($pdo, $config, $one, 'annual', $now, $provider);
    $sent = $remote['checkouts']['ch_fixture1']['request'];
    check_premium($url === 'https://app.recurrente.com/checkout-session/ch_fixture1' && $sent['items'][0]['amount_in_cents'] === 2400 && $sent['items'][0]['currency'] === 'USD'
        && $sent['items'][0]['charge_type'] === 'recurring' && $sent['items'][0]['billing_interval'] === 'year' && $sent['metadata'] === ['smash_user' => $one, 'smash_plan' => 'annual']
        && strpos($sent['success_url'], 'https://rankingsmashbros.com/cuenta.html#') === 0 && !isset($sent['user_id']) && !isset($sent['customer_id']), 'Checkout: fixed price and return address, only our account number as metadata');
    check_premium(smash_premium_status($pdo, $one, false, $now) == ['pending' => true] + $none, 'An unpaid checkout is pending, not premium');
    smash_premium_refresh($pdo, $config, $one, $now, $provider);
    check_premium(smash_premium_status($pdo, $one, false, $now)['premium'] === false, 'Returning from an unpaid checkout grants nothing');
    // Paid: the browser comes back before any webhook.
    $pay('ch_fixture1', 'su_fixture1', '2027-10-08T12:00:00Z');
    smash_premium_refresh($pdo, $config, $one, $now + 30, $provider);
    $status = smash_premium_status($pdo, $one, false, $now + 30);
    check_premium($status === ['premium' => true, 'plan' => 'annual', 'status' => 'active', 'currentPeriodEnd' => '2027-10-08T12:00:00+00:00', 'startedAt' => '2026-10-08T12:00:00+00:00', 'cancelRequested' => false, 'pending' => false], 'A paid checkout becomes premium on return, without a webhook');
    $stored = json_encode($pdo->query("SELECT * FROM premium_subscriptions WHERE user_id=$one")->fetchAll(PDO::FETCH_ASSOC));
    foreach (['Persona', 'privada@', '+502', 'NIT-PRIVADO', '4242', 'visa'] as $private) check_premium(strpos($stored, $private) === false, 'No payer name, e-mail, phone, tax id or card is stored');
    check_premium(smash_premium_status($pdo, $one, true, $now + 30) === $none && smash_premium_status($pdo, $two, false, $now + 30) === $none, 'A test subscription is not premium in live mode, nor for another account');
    premium_rejects(static fn() => smash_premium_start($pdo, $config, $one, 'monthly', $now + 60, $provider), 'invalid_already_premium');
    // Webhooks: processed once, the body only says where to look.
    $before = count($remote['calls']);
    check_premium(smash_premium_event($pdo, $config, 'msg_fixture_1', ['event_type' => 'subscription.create', 'id' => 'su_fixture1', 'customer_email' => 'privada@example.com'], $now + 40, $provider) === 'synced', 'A subscription webhook syncs from the provider');
    check_premium(smash_premium_event($pdo, $config, 'msg_fixture_1', ['event_type' => 'subscription.create', 'id' => 'su_fixture1'], $now + 41, $provider) === 'duplicate' && count($remote['calls']) === $before + 1, 'The same webhook is not processed twice');
    check_premium(smash_premium_event($pdo, $config, 'msg_fixture_2', ['event_type' => 'payment_intent.succeeded', 'id' => 'pa_fixture1', 'amount_in_cents' => 1], $now + 42, $provider) === 'ignored', 'Other events are acknowledged and ignored');
    check_premium(smash_premium_event($pdo, $config, 'msg_fixture_3', ['event_type' => 'subscription.cancel', 'id' => 'su_../etc'], $now + 43, $provider) === 'ignored'
        && smash_premium_event($pdo, $config, 'msg_fixture_4', 'not an object', $now + 43, $provider) === 'ignored', 'Malformed notices change nothing');
    // A forged notice claiming a cancellation cannot end premium: the provider still says active.
    smash_premium_event($pdo, $config, 'msg_fixture_5', ['event_type' => 'subscription.cancel', 'id' => 'su_fixture1', 'status' => 'cancelled'], $now + 44, $provider);
    check_premium(smash_premium_status($pdo, $one, false, $now + 45)['status'] === 'active', 'State comes from the provider, never from the notice');
    // Someone else's subscription on the same Recurrente account is not ours.
    $remote['subscriptions']['su_foreign1'] = ['id' => 'su_foreign1', 'status' => 'active', 'current_period_end' => '2030-01-01T00:00:00Z', 'checkout' => ['id' => 'ch_foreign1']];
    check_premium(smash_premium_event($pdo, $config, 'msg_fixture_6', ['event_type' => 'subscription.create', 'id' => 'su_foreign1'], $now + 46, $provider) === 'unrelated'
        && (int)$pdo->query('SELECT COUNT(*) FROM premium_subscriptions')->fetchColumn() === 1, 'Subscriptions this site did not start are not adopted');
    // A failed lookup is not recorded, so the provider's retry is processed.
    $remote['down'] = true;
    premium_rejects(static fn() => smash_premium_event($pdo, $config, 'msg_fixture_7', ['event_type' => 'subscription.update', 'id' => 'su_fixture1'], $now + 47, $provider), 'provider_unavailable');
    check_premium((int)$pdo->query("SELECT COUNT(*) FROM premium_events WHERE event_id='msg_fixture_7'")->fetchColumn() === 0, 'A notice that could not be processed is left for the retry');
    smash_premium_refresh($pdo, $config, $one, $now + 48, $provider);
    check_premium(smash_premium_status($pdo, $one, false, $now + 48)['premium'] === true, 'The provider being down does not take premium away');
    $remote['down'] = false;
    check_premium(smash_premium_event($pdo, $config, 'msg_fixture_7', ['event_type' => 'subscription.update', 'id' => 'su_fixture1'], $now + 49, $provider) === 'synced', 'The retry succeeds');
    check_premium(strpos(json_encode($pdo->query("SELECT * FROM premium_events WHERE event_id LIKE 'msg_fixture_%'")->fetchAll(PDO::FETCH_ASSOC)), 'privada') === false, 'Notices are remembered by id and type only');
    // Renewal: the period ended and the provider has a new one.
    $after = gmmktime(12, 0, 1, 10, 8, 2027);
    check_premium(smash_premium_status($pdo, $one, false, $after)['premium'] === false, 'Without a renewal the paid period ends');
    $remote['subscriptions']['su_fixture1']['current_period_end'] = '2028-10-08T12:00:00Z';
    smash_premium_refresh($pdo, $config, $one, $after, $provider);
    check_premium(smash_premium_status($pdo, $one, false, $after)['currentPeriodEnd'] === '2028-10-08T12:00:00+00:00', 'A renewal is picked up without a webhook');
    // Cancel: no more charges, access until the end of the paid period.
    smash_premium_cancel($pdo, $config, $one, $after + 10, $provider);
    $status = smash_premium_status($pdo, $one, false, $after + 20);
    check_premium(in_array('DELETE /subscriptions/su_fixture1', $remote['calls'], true) && $status['premium'] === true && $status['status'] === 'canceled' && $status['cancelRequested'] === true, 'Cancelling stops charges and keeps the paid period');
    check_premium(smash_premium_status($pdo, $one, false, gmmktime(12, 0, 1, 10, 8, 2028))['premium'] === false, 'After the paid period a cancelled subscription is over');
    premium_rejects(static fn() => smash_premium_cancel($pdo, $config, $one, $after + 30, $provider), 'invalid_no_subscription');
    premium_rejects(static fn() => smash_premium_cancel($pdo, $config, $two, $after + 30, $provider), 'invalid_no_subscription');
    // A cancelled member may subscribe again; a past-due one keeps access only while the period runs.
    check_premium(strpos(smash_premium_start($pdo, $config, $one, 'monthly', $after + 40, $provider), 'https://app.recurrente.com/') === 0, 'A cancelled member can subscribe again');
    smash_premium_start($pdo, $config, $two, 'monthly', $now, $provider); $second = array_key_last($remote['checkouts']);
    $pay($second, 'su_fixture2', '2026-11-08T12:00:00Z'); smash_premium_refresh($pdo, $config, $two, $now, $provider);
    $remote['subscriptions']['su_fixture2']['status'] = 'past_due';
    smash_premium_event($pdo, $config, 'msg_fixture_8', ['event_type' => 'subscription.past_due', 'id' => 'su_fixture2'], $now + 5, $provider);
    check_premium(smash_premium_status($pdo, $two, false, $now + 6)['status'] === 'past_due' && smash_premium_status($pdo, $two, false, $now + 6)['premium'] === true
        && smash_premium_status($pdo, $two, false, gmmktime(12, 0, 1, 11, 8, 2026))['premium'] === false, 'A failed renewal keeps access only until the paid period ends');
    // A provider answering with another mode or another host is refused.
    $wrong = static fn() => ['status' => 201, 'body' => ['id' => 'ch_fixture99', 'live_mode' => true, 'checkout_url' => 'https://app.recurrente.com/checkout-session/x']];
    premium_rejects(static fn() => smash_premium_start($pdo, $config, $two, 'annual', gmmktime(0, 0, 0, 1, 1, 2027), $wrong), 'provider_invalid');
    $evil = static fn() => ['status' => 201, 'body' => ['id' => 'ch_fixture98', 'live_mode' => false, 'checkout_url' => 'https://app.recurrente.com.evil.test/pay']];
    premium_rejects(static fn() => smash_premium_start($pdo, $config, $two, 'annual', gmmktime(0, 0, 0, 1, 1, 2027), $evil), 'provider_invalid');
    echo "Premium checkout, activation, webhooks, renewal, cancellation and privacy passed on " . $pdo->query('SELECT VERSION()')->fetchColumn() . ".\n";
} finally {
    $clean();
}
