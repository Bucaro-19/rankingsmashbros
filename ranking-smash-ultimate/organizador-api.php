<?php
declare(strict_types=1);
ini_set('display_errors', '0');
require_once __DIR__ . '/database.php';
require_once __DIR__ . '/accounts.php';
require_once __DIR__ . '/stats.php';
require_once __DIR__ . '/premium.php';
require_once __DIR__ . '/organizador.php';
require_once __DIR__ . '/organizer-slides.php';
smash_account_session_start();
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, private');
header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: no-referrer');
function org_response(int $status, array $data): void {
    http_response_code($status); echo json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES); exit;
}
function org_pdo(): PDO {
    static $pdo = null;
    return $pdo ?? ($pdo = smash_account_connect(__DIR__));
}
if (!in_array($_SERVER['REQUEST_METHOD'], ['GET', 'POST'], true)) { header('Allow: GET, POST'); org_response(405, ['ok' => false, 'reason' => 'method_not_allowed']); }
try {
    $now = time(); $post = $_SERVER['REQUEST_METHOD'] === 'POST';
    $body = [];
    if ($post) {
        if (!smash_account_csrf_valid($_SESSION, $_SERVER['HTTP_X_CSRF_TOKEN'] ?? null)) org_response(403, ['ok' => false, 'reason' => 'csrf_invalid']);
        if ((int)($_SERVER['CONTENT_LENGTH'] ?? 0) > 1024) org_response(413, ['ok' => false, 'reason' => 'body_too_large']);
        if (strtolower(trim(explode(';', $_SERVER['CONTENT_TYPE'] ?? '')[0])) !== 'application/json') org_response(415, ['ok' => false, 'reason' => 'json_required']);
        $body = json_decode((string)file_get_contents('php://input', false, null, 0, 1025), true);
        if (!is_array($body) || !is_string($body['action'] ?? null)) org_response(400, ['ok' => false, 'reason' => 'invalid_action']);
    }
    $inviteToken = $post ? null : ($_GET['invita'] ?? null);
    if (!smash_account_resume('org_pdo', $now)) {
        if ($post) org_response(401, ['ok' => false, 'reason' => 'login_required']);
        // An invitation shows who invites even before signing in; nothing else is readable.
        $invite = $inviteToken === null ? null : smash_org_invite_peek(org_pdo(), $inviteToken, $now);
        org_response(200, ['ok' => true, 'authenticated' => false, 'state' => 'login', 'csrf' => $_SESSION['smash_account_csrf'],
            'invite' => $inviteToken === null ? null : ($invite === null ? ['valid' => false] : ['valid' => true, 'organizer' => $invite['name']])]);
    }
    $pdo = org_pdo(); $user = smash_account_current($pdo);
    $admin = smash_stats_is_owner($pdo, $user['id']);
    $config = smash_premium_config(__DIR__);
    $contexts = smash_org_contexts($pdo, $user['id']);
    // The organizer being looked at: one this account may open, its own by default. Never taken on trust.
    $wanted = $post ? ($body['organizer'] ?? null) : ($_GET['organizador'] ?? null);
    $context = $contexts[0];
    foreach ($contexts as $candidate) if (is_string($wanted) && $candidate['id'] === $wanted) $context = $candidate;
    if ($wanted !== null && (!is_string($wanted) || $context['id'] !== $wanted)) org_response(403, ['ok' => false, 'reason' => 'forbidden']);
    $owner = $context['role'] === 'owner';
    // Each account pays for itself: the viewer's own premium opens the tab, also for a co-organizer.
    $premium = smash_org_premium($pdo, $user['id'], $config, $now);
    $allowed = $admin || $premium['active'];

    if ($post) {
        $action = $body['action'];
        if ($action === 'join') {
            // Joining is free and credits the account as co-organizer; seeing the top needs its own premium.
            $joined = smash_org_join($pdo, $user['id'], $body['token'] ?? null, $now);
            org_response(200, ['ok' => true, 'organizer' => $joined]);
        }
        if ($action === 'leave') {
            if ($owner) org_response(400, ['ok' => false, 'reason' => 'invalid_action']);
            smash_org_remove_member($pdo, $context['id'], $user['id']);
            org_response(200, ['ok' => true]);
        }
        if ($action === 'resolve') {
            if (!$admin) org_response(403, ['ok' => false, 'reason' => 'forbidden']);
            smash_org_resolve($pdo, $user['id'], $body['claim'] ?? null, $body['approve'] ?? null, $body['message'] ?? null, $now);
            org_response(200, ['ok' => true, 'pendingReviews' => smash_org_pending_claims($pdo)]);
        }
        if (!$allowed) org_response(403, ['ok' => false, 'reason' => 'premium_required']);
        if ($action === 'review') {
            smash_org_claim($pdo, $context['id'], $user['id'], $body['url'] ?? null, $now);
            org_response(200, ['ok' => true]);
        }
        // From here on, decisions that belong to the organizer alone.
        if (!$owner) org_response(403, ['ok' => false, 'reason' => 'forbidden']);
        if ($action === 'settings') {
            smash_org_settings($pdo, $context['id'], array_intersect_key($body, ['publicEnabled' => 1, 'topSize' => 1]), $now);
            org_response(200, ['ok' => true, 'organizer' => smash_org_profile($pdo, $context['id'], $now, false)]);
        }
        if ($action === 'invite') {
            org_response(200, ['ok' => true, 'inviteUrl' => 'https://rankingsmashbros.com/cuenta.html?invita=' . smash_org_invite($pdo, $context['id'], $now) . '#torneos',
                'expiresInDays' => intdiv(SMASH_ORG_INVITE_AGE, 86400)]);
        }
        if ($action === 'removeMember') {
            smash_org_remove_member($pdo, $context['id'], $body['member'] ?? null);
            org_response(200, ['ok' => true, 'members' => smash_org_members($pdo, $context['id'])]);
        }
        org_response(400, ['ok' => false, 'reason' => 'invalid_action']);
    }

    $base = ['ok' => true, 'authenticated' => true, 'csrf' => $_SESSION['smash_account_csrf'], 'role' => $context['role'],
        'contexts' => array_map(static function (array $c): array { return ['id' => $c['id'], 'name' => $c['name'] ?? 'Organizador', 'role' => $c['role']]; }, $contexts)];
    if ($inviteToken !== null) {
        $invite = smash_org_invite_peek($pdo, $inviteToken, $now);
        $base['invite'] = $invite === null ? ['valid' => false] : ['valid' => true, 'organizer' => $invite['name'], 'own' => $invite['organizerId'] === $user['id'],
            'member' => in_array($invite['organizerId'], array_column($contexts, 'id'), true) && $invite['organizerId'] !== $user['id']];
    }
    if ($admin) $base['pendingReviews'] = smash_org_pending_claims($pdo);
    // Access order of the design: interest, then premium, then data. A co-organizer was invited: no interest needed.
    if ($owner && !$admin && !in_array('organizer', $user['roles'], true)) org_response(200, $base + ['state' => 'interest']);
    if (!$allowed) {
        $teaser = null;
        try { $teaser = smash_org_teaser($pdo, $context['id'], $now); } catch (SmashOrganizerError $error) {}
        org_response(200, $base + ['state' => $premium['expiredAt'] !== null ? 'expired' : 'premium', 'expiredAt' => $premium['expiredAt'],
            'premiumAvailable' => $config !== null, 'teaser' => $teaser]);
    }
    $public = null;
    try { $public = smash_account_public(__DIR__)['generatedAt']; } catch (SmashAccountError $error) {}
    $view = smash_org_view($pdo, $context['id'], $public, $now, $owner, true);
    org_response(200, $base + ['state' => 'data', 'data' => $view, 'members' => $owner ? smash_org_members($pdo, $context['id']) : null,
        'publicUrl' => $view['organizer']['slug'] === null ? null : 'https://rankingsmashbros.com/top/' . $view['organizer']['slug']]);
} catch (SmashAccountError $error) {
    if ($error->reason === 'login_required') { unset($_SESSION['smash_account']); org_response(401, ['ok' => false, 'reason' => 'login_required']); }
    org_response(503, ['ok' => false, 'reason' => 'organizer_unavailable']);
} catch (SmashOrganizerError $error) {
    if ($error->reason === 'login_required') org_response(401, ['ok' => false, 'reason' => 'login_required']);
    $invalid = strpos($error->reason, 'invalid_') === 0;
    org_response($invalid ? 400 : 503, ['ok' => false, 'reason' => $invalid ? $error->reason : 'organizer_unavailable']);
} catch (Throwable $error) {
    org_response(503, ['ok' => false, 'reason' => 'organizer_unavailable']);
}
