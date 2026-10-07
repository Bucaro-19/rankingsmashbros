<?php
declare(strict_types=1);

ini_set('display_errors', '0');
require_once __DIR__ . '/database.php';

ini_set('session.use_strict_mode', '1');
session_name('SMASHGT_ADMIN');
session_set_cookie_params([
    // Scope the cookie to wherever the site is served (domain root or a subfolder).
    'lifetime' => 0, 'path' => rtrim(str_replace('\\', '/', dirname($_SERVER['SCRIPT_NAME'] ?? '/')), '/') . '/',
    'secure' => PHP_SAPI !== 'cli-server',
    'httponly' => true, 'samesite' => 'Strict',
]);
session_start();
date_default_timezone_set('America/Guatemala');
header('Cache-Control: no-store, private');
header('X-Content-Type-Options: nosniff');
header('X-Frame-Options: DENY');
header('Referrer-Policy: no-referrer');
header('X-Robots-Tag: noindex, nofollow, noarchive');
header("Content-Security-Policy: default-src 'none'; style-src 'self' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; form-action 'self'; base-uri 'none'; frame-ancestors 'none'");

function h(string $value): string { return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'); }
function option_counts(array $rows, string $field, array $labels): array {
    $counts = array_fill_keys(array_keys($labels), 0);
    foreach ($rows as $row) {
        $value = $row[$field] ?? null;
        if (is_string($value) && array_key_exists($value, $counts)) $counts[$value]++;
    }
    return $counts;
}
function safe_source($value): ?string {
    if (!is_string($value) || !filter_var($value, FILTER_VALIDATE_URL)) return null;
    $parts = parse_url($value);
    return is_array($parts) && ($parts['scheme'] ?? '') === 'https'
        && in_array(strtolower($parts['host'] ?? ''), ['start.gg', 'www.start.gg'], true) ? $value : null;
}

$authFile = __DIR__ . '/feedback-data/admin-auth.php';
$passwordHash = is_file($authFile) ? require $authFile : null;
if (!is_string($passwordHash) || strlen($passwordHash) < 50) {
    http_response_code(503);
    exit('Panel temporalmente no disponible.');
}
if (!isset($_SESSION['smash_admin_nonce'])) $_SESSION['smash_admin_nonce'] = bin2hex(random_bytes(24));
$authenticated = smash_admin_session_valid($_SESSION, time());
// Read-only JSON for the existing administrator; no new login or UI is added.
if (($_GET['diagnostico'] ?? '') === 'base') {
    header('Content-Type: application/json; charset=utf-8');
    if (!$authenticated) {
        http_response_code(401);
        echo json_encode(['ok' => false, 'error' => ['code' => 'login_required', 'message' => 'Inicia sesión en el panel de opiniones.']]);
        exit;
    }
    if ($_SERVER['REQUEST_METHOD'] !== 'GET') {
        header('Allow: GET');
        http_response_code(405);
        echo json_encode(['ok' => false, 'error' => ['code' => 'method_not_allowed']]);
        exit;
    }
    session_write_close();
    try {
        $config = smash_database_config(__DIR__);
        $status = smash_database_status(smash_database_connect($config));
        echo json_encode($status, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    } catch (SmashDatabaseError $error) {
        http_response_code(503);
        echo json_encode(['ok' => false, 'error' => ['code' => $error->reason,
            'message' => smash_database_error_message($error->reason)]], JSON_UNESCAPED_UNICODE);
    } catch (Throwable $error) {
        http_response_code(503);
        echo json_encode(['ok' => false, 'error' => ['code' => 'diagnostic_failed', 'message' => 'No se pudo completar el diagnóstico.']]);
    }
    exit;
}
$error = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $nonce = $_POST['nonce'] ?? '';
    if (!is_string($nonce) || !hash_equals($_SESSION['smash_admin_nonce'], $nonce)
        || (int)($_SERVER['CONTENT_LENGTH'] ?? 0) > 4096) {
        http_response_code(400);
        exit('Solicitud inválida.');
    }
    if (($_POST['action'] ?? '') === 'logout' && $authenticated) {
        $_SESSION = [];
        session_regenerate_id(true);
        $_SESSION['smash_admin_nonce'] = bin2hex(random_bytes(24));
        $authenticated = false;
    } elseif (($_POST['action'] ?? '') === 'login' && !$authenticated) {
        $password = $_POST['password'] ?? '';
        $attempts = array_filter($_SESSION['smash_admin_attempts'] ?? [],
            static fn($timestamp) => is_int($timestamp) && $timestamp > time() - 900);
        if (count($attempts) >= 5) {
            $error = 'Demasiados intentos. Vuelve a probar en 15 minutos.';
        } elseif (is_string($password) && password_verify($password, $passwordHash)) {
            session_regenerate_id(true);
            $_SESSION['smash_admin'] = true;
            $_SESSION['smash_admin_at'] = time();
            $_SESSION['smash_admin_attempts'] = [];
            $_SESSION['smash_admin_nonce'] = bin2hex(random_bytes(24));
            header('Location: ./opiniones.php', true, 303);
            exit;
        } else {
            $attempts[] = time();
            $_SESSION['smash_admin_attempts'] = $attempts;
            $error = 'Clave incorrecta.';
        }
    }
}

$rows = [];
$readError = false;
if ($authenticated) {
    $dataFile = __DIR__ . '/feedback-data/respuestas-2026.php';
    if (is_file($dataFile)) {
        $handle = @fopen($dataFile, 'rb');
        if (!$handle || !flock($handle, LOCK_SH)) {
            $readError = true;
        } else {
            fgets($handle); // Guardia PHP, no es una respuesta.
            while (($line = fgets($handle)) !== false) {
                $entry = json_decode($line, true);
                if (!is_array($entry) || !isset($entry['submittedAt'])) continue;
                if (strpos((string)($entry['comment'] ?? ''), 'PRUEBA TÉCNICA INTERNA') === 0) continue;
                $rows[] = $entry;
            }
            flock($handle, LOCK_UN);
        }
        if ($handle) fclose($handle);
    }
    usort($rows, static fn($a, $b) => strcmp((string)$b['submittedAt'], (string)$a['submittedAt']));
}
$total = count($rows);
$ratingAverages = [];
foreach (['clarity', 'confidence'] as $field) {
    $scores = array_values(array_filter(array_map(static fn($row) => $row[$field] ?? null, $rows),
        static fn($value) => is_int($value) && $value >= 1 && $value <= 5));
    $ratingAverages[$field] = $scores ? number_format(array_sum($scores) / count($scores), 1, ',', '.') : '—';
}
$groups = [
    ['title' => 'Participación', 'field' => 'role', 'options' => ['jugador' => 'Jugadores', 'organizador' => 'Organizadores', 'espectador' => 'Espectadores', 'otro' => 'Otros']],
    ['title' => 'Quién entra al top', 'field' => 'eligibility', 'options' => ['nacionalidad-local' => 'Nacionalidad y juego local', 'nacionalidad' => 'Nacionalidad, aunque juegue solo fuera', 'otra' => 'Otra propuesta']],
    ['title' => 'Mínimo de actividad', 'field' => 'minimum', 'options' => ['2-eventos-4-sets' => '2 torneos y 4 sets', '3-eventos-6-sets' => '3 torneos y 6 sets', 'otro' => 'Otro mínimo']],
    ['title' => 'Torneos del extranjero', 'field' => 'international', 'options' => ['todos-validos' => 'Todos los válidos', 'solo-grandes' => 'Solo los más grandes', 'ninguno' => 'Solo Guatemala']],
];
?>
<!doctype html>
<html lang="es-GT">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex,nofollow,noarchive">
  <meta name="theme-color" content="#0c101c">
  <title>Opiniones privadas — Smash GT</title>
  <link rel="stylesheet" href="./style.css"><link rel="stylesheet" href="./arena.css"><link rel="stylesheet" href="./opiniones.css">
</head>
<body>
  <a class="skip-link" href="#contenido">Saltar al contenido</a>
  <header class="site-header wrap"><a class="brand" href="./" aria-label="Smash GT, inicio"><span class="brand-mark" aria-hidden="true">S<span>↗</span></span><span>SMASH<span class="brand-gt">GT</span><small>POR INGPORRAS</small></span></a><nav aria-label="Principal"><a href="./">Ranking público</a><a href="./encuesta.php">Cuestionario</a></nav><span class="country">ACCESO PRIVADO</span></header>
  <main id="contenido" class="wrap opinions-page">
    <?php if (!$authenticated): ?>
      <section class="login-panel"><p class="eyebrow"><span class="tiny-line"></span> SOLO PARA EL ORGANIZADOR</p><h1>OPINIONES<br><em>DE LA COMUNIDAD.</em></h1><p>Ingresa tu clave para consultar las respuestas del cuestionario 2026.</p>
        <?php if ($error !== ''): ?><p class="login-error" role="alert"><?= h($error) ?></p><?php endif; ?>
        <form method="post" action="./opiniones.php"><input type="hidden" name="action" value="login"><input type="hidden" name="nonce" value="<?= h($_SESSION['smash_admin_nonce']) ?>"><label for="password">Clave de acceso</label><input id="password" name="password" type="password" required autocomplete="current-password" autofocus><button type="submit">ENTRAR ↗</button></form>
      </section>
    <?php else: ?>
      <div class="dashboard-heading"><div><p class="eyebrow"><span class="tiny-line"></span> CONSULTA PRIVADA / 2026</p><h1>LA COMUNIDAD<br><em>TIENE LA PALABRA.</em></h1><p>Estas opiniones ayudan a revisar las reglas; los puestos del top se calculan con resultados.</p></div><form method="post" action="./opiniones.php"><input type="hidden" name="action" value="logout"><input type="hidden" name="nonce" value="<?= h($_SESSION['smash_admin_nonce']) ?>"><button class="logout" type="submit">Cerrar sesión</button></form></div>
      <?php if ($readError): ?><p class="login-error" role="alert">No se pudo leer el archivo de respuestas. Intenta de nuevo.</p><?php endif; ?>
      <div class="total-card"><strong><?= $total ?></strong><span>respuestas reales recibidas</span><small>La respuesta de prueba técnica no se cuenta.</small></div>
      <?php if ($total === 0): ?><div class="no-responses"><h2>Aún no hay respuestas de la comunidad.</h2><p>Comparte el cuestionario y vuelve a esta página para verlas.</p></div><?php endif; ?>
      <div class="rating-grid"><div><strong><?= h($ratingAverages['clarity']) ?> / 5</strong><span>Claridad de la explicación</span></div><div><strong><?= h($ratingAverages['confidence']) ?> / 5</strong><span>Confianza en el piloto</span></div></div>
      <div class="opinion-grid">
        <?php foreach ($groups as $group): $counts = option_counts($rows, $group['field'], $group['options']); ?>
          <section class="opinion-card"><h2><?= h($group['title']) ?></h2>
            <?php foreach ($group['options'] as $key => $label): ?><div class="choice-result"><div><span><?= h($label) ?></span><strong><?= $counts[$key] ?></strong></div><progress value="<?= $counts[$key] ?>" max="<?= max(1, $total) ?>"><?= $counts[$key] ?> de <?= $total ?></progress></div><?php endforeach; ?>
          </section>
        <?php endforeach; ?>
      </div>
      <section class="comments" aria-labelledby="comments-title"><div class="section-heading"><div><p class="eyebrow">TODAS LAS RESPUESTAS</p><h2 id="comments-title">LO QUE PROPONEN.</h2></div></div>
        <?php foreach ($rows as $row): $source = safe_source($row['source'] ?? null); $when = strtotime((string)$row['submittedAt']); ?>
          <article class="comment-card"><div class="comment-meta"><time><?= $when ? h(date('d/m/Y H:i', $when)) : 'Fecha no disponible' ?></time><span><?= h($groups[0]['options'][$row['role'] ?? ''] ?? 'Participante') ?></span></div>
            <dl class="response-choices"><div><dt>Elegibilidad</dt><dd><?= h($groups[1]['options'][$row['eligibility'] ?? ''] ?? 'Sin respuesta') ?></dd></div><div><dt>Actividad</dt><dd><?= h($groups[2]['options'][$row['minimum'] ?? ''] ?? 'Sin respuesta') ?></dd></div><div><dt>Extranjero</dt><dd><?= h($groups[3]['options'][$row['international'] ?? ''] ?? 'Sin respuesta') ?></dd></div><div><dt>Claridad / confianza</dt><dd><?= h((string)($row['clarity'] ?? '—')) ?> / 5 · <?= h((string)($row['confidence'] ?? '—')) ?> / 5</dd></div></dl>
            <?php if (trim((string)($row['comment'] ?? '')) !== ''): ?><p><?= nl2br(h((string)$row['comment'])) ?></p><?php endif; ?>
            <?php if ($source): ?><a href="<?= h($source) ?>" target="_blank" rel="noopener noreferrer">Ver referencia en start.gg ↗</a><?php endif; ?>
          </article>
        <?php endforeach; ?>
      </section>
    <?php endif; ?>
  </main>
  <footer class="wrap"><a href="https://ingporras.com/">INGPORRAS ↗</a><p>Panel privado de Smash GT.</p><span>SMASH GT</span></footer>
</body>
</html>
