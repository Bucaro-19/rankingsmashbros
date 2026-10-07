<?php
declare(strict_types=1);
ini_set('display_errors', '0');
require_once __DIR__ . '/database.php';
require_once __DIR__ . '/premium.php';
header('Cache-Control: no-store, private');
header('X-Content-Type-Options: nosniff');
// Receives Recurrente's notices. Answers with a status only; a failure makes Recurrente retry.
// Nothing from the notice is logged: it carries the payer's name and e-mail.
function webhook_end(int $status): void { http_response_code($status); exit; }
if ($_SERVER['REQUEST_METHOD'] !== 'POST') { header('Allow: POST'); webhook_end(405); }
if ((int)($_SERVER['CONTENT_LENGTH'] ?? 0) > 65536) webhook_end(413);
try {
    $config = smash_premium_config(__DIR__);
    if ($config === null) webhook_end(503);
    $body = (string)file_get_contents('php://input', false, null, 0, 65537);
    if (strlen($body) > 65536) webhook_end(413);
    $id = $_SERVER['HTTP_SVIX_ID'] ?? null;
    // The signature is checked over the exact bytes received, before the JSON is read.
    if (!smash_premium_webhook_valid($config['webhook_secret'], $id, $_SERVER['HTTP_SVIX_TIMESTAMP'] ?? null, $_SERVER['HTTP_SVIX_SIGNATURE'] ?? null, $body, time())) webhook_end(401);
    $payload = json_decode($body, true);
    if (!is_array($payload)) webhook_end(400);
    smash_premium_event(smash_premium_connect(__DIR__), $config, $id, $payload, time());
    webhook_end(204);
} catch (Throwable $error) {
    webhook_end(503);
}
