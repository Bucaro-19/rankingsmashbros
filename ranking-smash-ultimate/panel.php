<?php
declare(strict_types=1);
ini_set('display_errors', '0');
require_once __DIR__ . '/database.php';
require_once __DIR__ . '/accounts.php';
require_once __DIR__ . '/stats.php';
smash_account_session_start();
header('Cache-Control: no-store, private');
header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: no-referrer');
header('X-Robots-Tag: noindex, nofollow');
function panel_page_pdo(): PDO {
    static $pdo = null;
    return $pdo ?? ($pdo = smash_account_connect(__DIR__));
}
// owner: the panel. expired: sign in again. denied: nothing about the page. error: try again.
$state = 'expired';
try {
    if (smash_account_resume('panel_page_pdo', time())) {
        $user = smash_account_current(panel_page_pdo());
        $state = smash_stats_is_owner(panel_page_pdo(), $user['id']) ? 'owner' : 'denied';
    }
} catch (SmashAccountError $error) {
    $state = $error->reason === 'login_required' ? 'expired' : 'error';
    if ($state === 'expired') unset($_SESSION['smash_account']);
} catch (Throwable $error) {
    $state = 'error';
}
http_response_code(['owner' => 200, 'expired' => 401, 'denied' => 403, 'error' => 503][$state]);
$csrf = htmlspecialchars($_SESSION['smash_account_csrf'], ENT_QUOTES, 'UTF-8');
?><!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex, nofollow">
  <title>Smash GT</title>
  <link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700;800&family=Big+Shoulders+Display:wght@800;900&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="./panel.css?v=20261009-1">
<?php if ($state === 'owner'): ?>
  <script src="./panel-model.js?v=20261008-1" defer></script><script src="./panel.js?v=20261007-2" defer></script>
<?php endif; ?>
</head>
<body data-state="<?= $state ?>">
  <a class="skip-link" href="#panel-content">Saltar al contenido</a>
  <header class="panel-header"><a class="panel-brand" href="./"><span class="brand-mark">GT</span><span>SMASH GT</span></a>
    <div><a href="./">Volver al sitio</a><?php if ($state === 'owner'): ?><form class="panel-opinions" action="./opiniones-acceso.php" method="post"><input type="hidden" name="csrf" value="<?= $csrf ?>"><button class="outline" type="submit">Opiniones ↗</button></form><button id="panel-logout" class="outline" type="button">Cerrar sesión</button><?php endif; ?></div>
  </header>
<?php if ($state === 'denied'): ?>
  <main id="panel-content" class="sober" tabindex="-1"><div><h1>Sin acceso.</h1><p>Esta página no está disponible para tu cuenta.</p><a class="primary" href="./"><span>Volver al sitio</span></a></div></main>
<?php elseif ($state === 'expired'): ?>
  <main id="panel-content" class="sober" tabindex="-1"><div><h1>Tu sesión<br><span>venció.</span></h1><p>Por seguridad, vuelve a entrar con start.gg para continuar.</p>
    <div class="button-row"><form id="panel-login" action="./oauth.php" method="post"><input type="hidden" name="csrf" value="<?= $csrf ?>"><button class="primary" type="submit"><span>Entrar con start.gg ↗</span></button></form><a class="outline" href="./">Volver al sitio</a></div>
    <script>document.getElementById('panel-login').addEventListener('submit',function(){try{sessionStorage.setItem('smashgt.volver','panel');}catch(e){}});</script>
  </div></main>
<?php elseif ($state === 'error'): ?>
  <main id="panel-content" class="sober" tabindex="-1"><div><h1>Fuera de<br><span>servicio.</span></h1><p>No pudimos abrir esta página ahora. Vuelve a intentarlo en un momento.</p><div class="button-row"><a class="primary" href="./panel.php"><span>Reintentar</span></a><a class="outline" href="./">Volver al sitio</a></div></div></main>
<?php else: ?>
  <main id="panel-content" class="panel" tabindex="-1">
    <div class="panel-title"><div><p class="kicker">Panel privado</p><h1>Visitas y registros</h1></div><p id="updated" class="note" role="status"></p></div>
    <div id="panel-loading" class="loading" role="status" aria-live="polite"><div class="load-bar"><span></span></div><p class="note">Consultando los datos…</p>
      <div class="cards"><div class="sk wide"></div><div class="sk"></div><div class="sk"></div><div class="sk wide"></div></div><div class="sk selector"></div><div class="cards"><div class="sk wide tall"></div><div class="sk tall"></div><div class="sk tall"></div><div class="sk wide tall"></div></div><div class="sk chart"></div></div>
    <div id="panel-error" class="error" hidden><div class="alert" role="alert"><span aria-hidden="true">×</span><div><strong>No pudimos consultar los datos.</strong><p>El contador sigue registrando; solo falló esta consulta. Vuelve a intentarlo en un momento.</p><small>Código de referencia: <span id="error-code">STATS-503</span></small></div></div><button id="panel-retry" class="primary" type="button"><span>Reintentar</span></button></div>
    <div id="panel-ready" hidden>
      <section aria-labelledby="glance-title"><h2 id="glance-title" class="kicker muted">De un vistazo</h2><div id="glance" class="cards"></div></section>
      <div class="period-bar"><div id="periods" class="segmented" role="group" aria-label="Periodo"></div></div>
      <section id="period" class="period" aria-labelledby="period-title"></section>
      <section id="chart" class="chart" aria-labelledby="chart-title" hidden></section>
      <section id="pages" class="pages" aria-labelledby="pages-title" hidden></section>
    </div>
  </main>
<?php endif; ?>
</body>
</html>
