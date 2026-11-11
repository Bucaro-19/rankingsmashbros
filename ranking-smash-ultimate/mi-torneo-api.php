<?php
declare(strict_types=1);
ini_set('display_errors','0');
require_once __DIR__.'/database.php';
require_once __DIR__.'/accounts.php';
require_once __DIR__.'/mi-torneo.php';
require_once __DIR__.'/mi-torneo-live.php';
smash_account_session_start();
header('Content-Type: application/json; charset=utf-8');header('Cache-Control: no-store, private');header('X-Content-Type-Options: nosniff');header('Referrer-Policy: no-referrer');header('X-Robots-Tag: noindex, nofollow');
function mt_http(int $status,array $value): void {http_response_code($status);echo json_encode($value,JSON_THROW_ON_ERROR|JSON_UNESCAPED_UNICODE);exit;}
function mt_pdo(): PDO {static $db=null;return $db??($db=smash_account_connect(__DIR__));}
function mt_live_post(array $user, int $now): void
{
    if (!smash_account_csrf_valid($_SESSION, $_SERVER['HTTP_X_CSRF_TOKEN'] ?? null)) {
        mt_http(403, ['ok' => false, 'reason' => 'csrf_invalid']);
    }
    $body = file_get_contents('php://input', false, null, 0, 513);
    $input = is_string($body) && strlen($body) <= 512 ? json_decode($body, true, 4) : null;
    $action = $input['action'] ?? null;
    $eventId = mt_live_id($input['eventId'] ?? null);
    $discovery = $action === 'discover' && count($input) === 1;
    $refresh = $action === 'refresh' && $eventId !== null && count($input) === 2;
    if ($_GET || (!$discovery && !$refresh)) mt_http(400, ['ok' => false, 'reason' => 'parameters_not_allowed']);
    if ($user['playerId'] === null) mt_http(409, ['ok' => false, 'reason' => 'player_not_linked']);

    $config = mt_live_config(__DIR__, $now);
    if ($config === null) mt_http(409, ['ok' => false, 'reason' => 'live_disabled']);
    $events = $config['events'];
    $event = $events[$eventId] ?? null;
    if ($refresh && !($event['inProgress'] ?? false)) {
        mt_http(409, ['ok' => false, 'reason' => 'event_outside_window']);
    }
    $q = mt_pdo()->prepare("SELECT startgg_user_id FROM users WHERE id = ? AND player_id = ? AND status = 'active'");
    $q->execute([$user['id'], $user['playerId']]);
    $linked = mt_live_id($q->fetchColumn());
    if ($linked === null) mt_http(401, ['ok' => false, 'reason' => 'login_required']);
    session_write_close();

    $key = hash('sha256', json_encode([$user['id'], $linked, $user['playerId'], $action, $eventId, $events,
        hash('sha256', $config['token'])], JSON_THROW_ON_ERROR | JSON_INVALID_UTF8_SUBSTITUTE));
    $result = mt_live_cached($config['private'], $key, $discovery ? 120 : 30, $discovery ? count($events) : 3,
        static function (callable $query) use ($discovery, $events, $eventId, $event, $linked, $user): array {
            if ($discovery) {
                $confirmed = [];
                foreach ($events as $candidate) {
                    $entry = mt_live_entry($query, $candidate['id'], $linked, $user['playerId']);
                    if ($entry !== null && !$entry['finished']) $confirmed[] = $candidate;
                }
                return ['events' => $confirmed];
            }
            $result = mt_live_read($query, $eventId, $linked, $user['playerId']);
            return ['eventId' => $eventId, 'checkedAt' => gmdate('c')] + $result;
        }, static function (string $document, array $variables) use ($config): array {
            if (time() >= $config['events'][$variables['event']]['endAt']) {
                throw new RuntimeException('live_event_outside_window');
            }
            $response = smash_account_http('https://api.start.gg/gql/alpha', ['query' => $document, 'variables' => $variables], $config['token']);
            if (!is_array($response['data'] ?? null)) throw new UnexpectedValueException('live_provider_invalid');
            return $response['data'];
        });
    if ($discovery) $result['events'] = array_values(array_filter($result['events'], static fn($e) => $e['endAt'] > time()));
    if ($refresh && time() >= $event['endAt']) mt_http(409, ['ok' => false, 'reason' => 'event_outside_window']);
    mt_http(200, ['ok' => true] + $result);
}

$method = $_SERVER['REQUEST_METHOD'] ?? '';
if (!in_array($method, ['GET', 'POST'], true)) {
    header('Allow: GET, POST');
    mt_http(405, ['ok' => false, 'reason' => 'method_not_allowed']);
}
try{
    if(!smash_account_resume('mt_pdo',time()))mt_http(401,['ok'=>false,'reason'=>'login_required']);
    $user=smash_account_current(mt_pdo());
    if ($method === 'POST') mt_live_post($user, time());
    if($_GET&&(array_keys($_GET)!==['eventId']||$_GET['eventId']!==MT_EVENT))mt_http(400,['ok'=>false,'reason'=>'parameters_not_allowed']);
    $includeArchived=isset($_GET['eventId']);
    $snapshot=mt_read(__DIR__);$public=smash_account_public(__DIR__);$now=time();
    $response=mt_response($snapshot,$user['playerId'],$public,$now,[],$includeArchived);
    $chosen=mt_profile_characters(mt_pdo(),$response);
    if($chosen)$response=mt_response($snapshot,$user['playerId'],$public,$now,$chosen,$includeArchived);
    try {
        $response['liveAvailable'] = $user['playerId'] !== null && mt_live_config(__DIR__, $now) !== null;
    } catch (Throwable $e) {
        $response['liveAvailable'] = false;
    }
    mt_http(200,$response);
}catch(MiTorneoLiveBusy $e){header('Retry-After: 30');mt_http(429,['ok'=>false,'reason'=>'live_busy']);}
catch(SmashAccountError $e){if($e->reason==='login_required'){unset($_SESSION['smash_account']);mt_http(401,['ok'=>false,'reason'=>'login_required']);}mt_http(503,['ok'=>false,'reason'=>'tournament_unavailable']);}
catch(Throwable $e){mt_http(503,['ok'=>false,'reason'=>'tournament_unavailable']);}
