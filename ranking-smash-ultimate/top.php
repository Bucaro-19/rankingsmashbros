<?php
declare(strict_types=1);
// Public page of one organizer's top (/top/{slug}). Read-only, no session and no cookies.
// Shows what the organizer chose to share: the top, the summary and the tournaments used.
ini_set('display_errors', '0');
require_once __DIR__ . '/database.php';
require_once __DIR__ . '/accounts.php';
require_once __DIR__ . '/stats.php';
require_once __DIR__ . '/premium.php';
require_once __DIR__ . '/organizador.php';
header('Content-Type: text/html; charset=utf-8');
header('X-Robots-Tag: noindex, nofollow');
header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: no-referrer');
header('Cache-Control: no-store, private');
header("Content-Security-Policy: default-src 'none'; style-src 'self' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; img-src 'self' https://raw.githubusercontent.com; base-uri 'none'; form-action 'none'; frame-ancestors 'none'");
function top_e($value): string { return htmlspecialchars((string)$value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'); }
function top_day(?string $iso): string { return $iso !== null && preg_match('/\A(\d{4})-(\d{2})-(\d{2})/', $iso, $m) ? "$m[3]/$m[2]/$m[1]" : ''; }
function top_long(?string $iso): string {
    $months = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
    return $iso !== null && preg_match('/\A(\d{4})-(\d{2})-(\d{2})/', $iso, $m) ? (int)$m[3] . ' ' . $months[(int)$m[2] - 1] . ' ' . $m[1] : '';
}
// Same catalog the site's scripts use; only its fixed icon addresses are read.
function top_icons(): array {
    $source = @file_get_contents(__DIR__ . '/characters.js'); $icons = [];
    if (is_string($source) && preg_match_all('/"name":\s*"([^"]+)",\s*"slug":\s*"[^"]+",\s*"characterId":\s*"(\d+)",\s*"icon":\s*"(https:\/\/raw\.githubusercontent\.com\/[^"]+|\.\/assets\/[^"]+)"/', $source, $all, PREG_SET_ORDER)) {
        foreach ($all as $m) $icons[$m[2]] = ['name' => $m[1], 'icon' => $m[3][0] === '.' ? substr($m[3], 1) : $m[3]];
    }
    return $icons;
}
function top_start_url($url): ?string { return is_string($url) && preg_match('~\Ahttps://www\.start\.gg/tournament/[\w/-]+\z~', $url) ? $url : null; }

$view = ['state' => 'missing'];
if ($_SERVER['REQUEST_METHOD'] === 'GET' || $_SERVER['REQUEST_METHOD'] === 'HEAD') {
    try {
        $pdo = smash_account_connect(__DIR__); $config = smash_premium_config(__DIR__); $now = time();
        $cut = null;
        try { $cut = smash_account_public(__DIR__)['generatedAt']; } catch (SmashAccountError $error) {}
        $view = smash_org_public($pdo, is_string($_GET['o'] ?? null) ? $_GET['o'] : '', $cut,
            static function (string $id) use ($pdo, $config, $now): bool { return smash_org_premium($pdo, $id, $config, $now)['active']; }, $now);
    } catch (Throwable $error) { $view = ['state' => 'error']; }
} else { header('Allow: GET, HEAD'); http_response_code(405); $view = ['state' => 'error']; }
if ($view['state'] === 'missing') http_response_code(404);
if ($view['state'] === 'error' && http_response_code() === 200) http_response_code(503);
$closed = ['disabled' => ['○', 'Este enlace está desactivado', 'El organizador dejó de compartir su top por ahora. Si lo vuelve a activar, funcionará esta misma dirección.'],
    'paused' => ['‖', 'Este top está en pausa', 'Por ahora no está disponible. Volverá a esta misma dirección cuando el organizador lo reactive.'],
    'missing' => ['?', 'No encontramos este top', 'Revisa la dirección. Si te la compartió un organizador, pídele el enlace de nuevo.'],
    'error' => ['×', 'No pudimos cargar este top', 'Vuelve a intentarlo en un momento.']][$view['state']] ?? null;
$name = $closed ? '' : $view['organizer']['name'];
?><!doctype html>
<html lang="es-GT">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="theme-color" content="#0B0F1A"><meta name="robots" content="noindex,nofollow"><meta name="referrer" content="no-referrer">
  <title><?= $closed ? 'Ranking Smash Bros' : 'Top ' . (int)$view['organizer']['topSize'] . ' · ' . top_e($name) . ' — Ranking Smash Bros' ?></title>
  <link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@500;700;800;900&family=Archivo:wght@400;500;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/top.css?v=20261008-2">
  <link rel="icon" href="/favicon.svg" type="image/svg+xml"><link rel="icon" href="/favicon-32.png" sizes="32x32" type="image/png"><link rel="icon" href="/favicon-16.png" sizes="16x16" type="image/png"><link rel="apple-touch-icon" href="/apple-touch-icon.png">
</head>
<body>
<?php if ($closed): ?>
<main class="closed">
  <a class="brand" href="/" aria-label="Ranking Smash Bros, inicio"><span aria-hidden="true">GT</span>RANKING SMASH BROS</a>
  <span class="glyph" aria-hidden="true"><?= $closed[0] ?></span>
  <h1><?= $closed[1] ?></h1>
  <p><?= $closed[2] ?></p>
  <a class="cta" href="/#ranking"><span>Ver el ranking nacional</span></a>
</main>
<?php else:
    $s = $view['summary']; $n = (int)$s['eventsCounted']; $size = (int)$view['organizer']['topSize']; $icons = top_icons();
    $period = top_day($s['periodFrom']) . ' – ' . top_day($s['periodTo']); $cutLabel = 'Corte del ' . top_day($s['cutDate']);
?>
<main class="open">
  <section aria-labelledby="pt-title">
    <div class="top-line"><span class="kicker">Top <?= $size ?> · Temporada <?= (int)$view['seasonYear'] ?></span><a class="mark" href="/"><span aria-hidden="true">GT</span>Ranking Smash Bros</a></div>
    <h1 id="pt-title"><?= top_e($name) ?></h1>
<?php if ($view['coorganizers']): ?>
    <p class="team">Coorganizan: <?= top_e(implode(', ', $view['coorganizers'])) ?></p>
<?php endif; ?>
    <p class="line"><?= $period ?> · <?= $n === 1 ? '1 torneo' : $n . ' torneos' ?> · <?= (int)$s['distinctPlayers'] ?> jugadores</p>
<?php if ($n < 3): ?>
    <p class="small" role="note"><span aria-hidden="true">≈</span><span><strong>Muestra pequeña: <?= $n === 1 ? '1 torneo' : '2 torneos' ?>.</strong> Los puestos pueden cambiar mucho con el próximo. Solo torneos de <?= top_e($name) ?>; no es el ranking nacional.</span></p>
<?php else: ?>
    <p class="only">Solo torneos de <?= top_e($name) ?>. No es el ranking nacional de Ranking Smash Bros.</p>
<?php endif; ?>
    <div class="table" role="table" aria-label="Top <?= $size ?> de <?= top_e($name) ?>">
      <div class="head" role="row"><span role="columnheader">#</span><span role="columnheader" aria-label="Personaje"></span><span role="columnheader">Jugador</span><span role="columnheader">Sets</span><span role="columnheader">Pts</span></div>
<?php foreach ($view['top'] as $i => $row): $char = $icons[(string)($row['mainCharId'] ?? '')] ?? null; ?>
      <div class="row<?= $i === 0 ? ' first' : ($i < 3 ? ' podium' : '') ?>" role="row">
        <span role="cell" class="rank"><?= (int)$row['rank'] ?></span>
        <span role="cell" class="icon"><?php if ($char): ?><img src="<?= top_e($char['icon']) ?>" alt="<?= top_e($char['name']) ?>" width="24" height="24"><?php else: ?><span aria-label="Sin personaje registrado">—</span><?php endif; ?></span>
        <span role="cell" class="who"><b><?= top_e($row['alias']) ?></b><small><?= (int)$row['events'] ?>T</small></span>
        <span role="cell" class="sets"><?= (int)$row['setsWon'] ?>–<?= (int)$row['setsLost'] ?></span>
        <span role="cell" class="pts"><?= number_format((int)$row['points']) ?></span>
      </div>
<?php endforeach; ?>
    </div>
    <p class="legend">Sets ganados–perdidos · T = torneos jugados con <?= top_e($name) ?> · <?= $cutLabel ?></p>
  </section>
  <div class="side">
    <section class="box" aria-labelledby="pr-title"><h2 id="pr-title">Resumen</h2>
      <dl><div><dd><?= $n ?></dd><dt><?= $n === 1 ? 'torneo' : 'torneos' ?></dt></div><div><dd><?= (int)$s['distinctPlayers'] ?></dd><dt>jugadores distintos</dt></div><div><dd><?= (int)$s['validSets'] ?></dd><dt>sets válidos</dt></div></dl>
      <p>Periodo: <?= $period ?> · <?= $cutLabel ?></p></section>
    <section class="box" aria-labelledby="pu-title"><h2 id="pu-title">Torneos usados</h2><ul>
<?php foreach ($view['events'] as $event): $url = top_start_url($event['url']); $meta = trim(top_long($event['date']) . ($event['place'] ? ' · ' . $event['place'] : '')); ?>
      <li><<?= $url ? 'a href="' . top_e($url) . '" target="_blank" rel="noopener noreferrer"' : 'div' ?>><span><b><?= top_e($event['name']) ?><?= $url ? ' ↗' : '' ?></b><small><?= top_e($meta) ?></small></span><small><?= (int)$event['activePlayers'] ?> activos · <?= (int)$event['validSets'] ?> sets</small></<?= $url ? 'a' : 'div' ?>></li>
<?php endforeach; ?>
    </ul></section>
    <p class="foot">Calculado por Ranking Smash Bros con resultados públicos de start.gg, usando solo los torneos de este organizador. Pagar no da puntos ni cambia puestos. <a href="/#ranking">Ver el ranking nacional ↗</a></p>
  </div>
</main>
<?php endif; ?>
</body>
</html>
