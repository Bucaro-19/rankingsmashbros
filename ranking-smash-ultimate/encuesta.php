<?php
declare(strict_types=1);

// The page now talks to the private database: never print PHP or driver errors to visitors.
ini_set('display_errors', '0');
require_once __DIR__ . '/database.php';
require_once __DIR__ . '/survey.php';

ini_set('session.use_strict_mode', '1');
ini_set('session.cookie_httponly', '1');
ini_set('session.cookie_secure', !empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off' ? '1' : '0');
ini_set('session.cookie_samesite', 'Lax');
session_start();
header('Cache-Control: no-store');
header('X-Content-Type-Options: nosniff');

function h(string $value): string { return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'); }
function choice(string $field, array $allowed): ?string {
    $value = $_POST[$field] ?? null;
    return is_string($value) && in_array($value, $allowed, true) ? $value : null;
}

$error = '';
$saved = false;
if (!isset($_SESSION['smash_survey_nonce'])) {
    $_SESSION['smash_survey_nonce'] = bin2hex(random_bytes(24));
}
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $tooLarge = (int)($_SERVER['CONTENT_LENGTH'] ?? 0) > 12000;
    $nonce = $_POST['nonce'] ?? '';
    $role = choice('role', ['jugador', 'organizador', 'espectador', 'otro']);
    $eligibility = choice('eligibility', ['nacionalidad-local', 'nacionalidad', 'otra']);
    $minimum = choice('minimum', ['2-eventos-4-sets', '3-eventos-6-sets', 'otro']);
    $international = choice('international', ['todos-validos', 'solo-grandes', 'ninguno']);
    $clarity = choice('clarity', ['1', '2', '3', '4', '5']);
    $confidence = choice('confidence', ['1', '2', '3', '4', '5']);
    $comment = $_POST['comment'] ?? '';
    $source = $_POST['source'] ?? '';
    $honeypot = $_POST['website'] ?? '';
    if ($tooLarge || !is_string($nonce) || !hash_equals($_SESSION['smash_survey_nonce'], $nonce)
        || !is_string($honeypot) || $honeypot !== '' || !$role || !$eligibility || !$minimum
        || !$international || !$clarity || !$confidence || !is_string($comment) || !is_string($source)) {
        $error = 'Revisa las respuestas e intenta de nuevo.';
    } else {
        $comment = trim($comment);
        $source = trim($source);
        $sourceHost = $source === '' ? null : parse_url($source, PHP_URL_HOST);
        if (strlen($comment) > 2000 || strlen($source) > 250 || ($source !== '' &&
            (!filter_var($source, FILTER_VALIDATE_URL) || !in_array(strtolower((string)$sourceHost), ['start.gg', 'www.start.gg'], true)
             || parse_url($source, PHP_URL_SCHEME) !== 'https'))) {
            $error = 'El comentario o el enlace es demasiado largo, o el enlace no es de start.gg.';
        } elseif (time() - (int)($_SESSION['smash_survey_last'] ?? 0) < 300) {
            $error = 'Ya recibimos una respuesta reciente de esta sesión. Gracias.';
        } else {
            // Single storage: the private database. A failure is reported to the visitor and can be
            // retried with the same form; nothing is written anywhere else and no success is claimed.
            try {
                $outcome = smash_survey_store(smash_survey_connect(__DIR__), [
                    'role' => $role, 'eligibility' => $eligibility, 'minimum' => $minimum,
                    'international' => $international, 'clarity' => (int)$clarity,
                    'confidence' => (int)$confidence, 'source' => $source, 'comment' => $comment,
                ], smash_survey_submission_key($_SESSION['smash_survey_nonce']), time());
                // 'already_saved': an earlier attempt of this same form was stored and its answer
                // to the browser was lost. The form token stores one answer at most.
                $saved = $outcome === 'inserted' || $outcome === 'already_saved';
            } catch (Throwable $failure) {
                $saved = false;
            }
            if ($saved) {
                $_SESSION['smash_survey_last'] = time();
                $_SESSION['smash_survey_nonce'] = bin2hex(random_bytes(24));
            } else {
                $error = 'No pudimos guardar la respuesta. Intenta de nuevo más tarde.';
            }
        }
    }
}
?>
<!doctype html>
<html lang="es-GT">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#0c101c">
  <meta name="description" content="Opina sobre las reglas del ranking de Super Smash Bros. Ultimate de Guatemala, sin crear una cuenta.">
  <meta name="smash-survey-storage" content="sql">
  <title>Cuestionario de la comunidad — Smash GT</title>
  <link rel="stylesheet" href="./style.css">
  <link rel="stylesheet" href="./arena.css">
  <link rel="stylesheet" href="./encuesta.css?v=20260929-2">
</head>
<body>
  <a class="skip-link" href="#contenido">Saltar al contenido</a>
  <header class="site-header wrap"><a class="brand" href="./" aria-label="Smash GT, inicio"><span class="brand-mark" aria-hidden="true">S<span>↗</span></span><span>SMASH<span class="brand-gt">GT</span><small>POR INGPORRAS</small></span></a><nav aria-label="Principal"><a href="./#clasificacion">Ranking</a><a href="./metodologia.html">Método y torneos</a></nav><span class="country"><span class="flag" aria-hidden="true"></span> Guatemala</span></header>
  <main id="contenido" class="wrap survey-page">
    <p class="eyebrow"><span class="tiny-line"></span> PILOTO 2026 / TU OPINIÓN CUENTA</p>
    <h1>HAGAMOS UN<br><em>RANKING MEJOR.</em></h1>
    <p class="survey-lead">Queremos acordar reglas claras con la comunidad de Smash Ultimate de Guatemala. Contestar toma unos 3 minutos y no requiere cuenta. Esta consulta orienta la revisión; los puestos se calculan con resultados, no por votación.</p>
    <?php if ($saved): ?>
      <div class="survey-message success" role="status"><h2>¡Respuesta recibida!</h2><p>Gracias por ayudarnos a pulir el ranking 2026.</p><a href="./metodologia.html">Ver reglas y torneos ↗</a></div>
    <?php else: ?>
      <?php if ($error !== ''): ?><p class="survey-message error" role="alert"><?= h($error) ?></p><?php endif; ?>
      <form method="post" action="./encuesta.php" class="survey-form">
        <input type="hidden" name="nonce" value="<?= h($_SESSION['smash_survey_nonce']) ?>">
        <div class="trap" aria-hidden="true"><label for="website">Sitio web</label><input id="website" name="website" type="text" tabindex="-1" autocomplete="off"></div>
        <fieldset><legend>01 / ¿Desde dónde participas en la escena?</legend><div class="choices"><label><input type="radio" name="role" value="jugador" required> Jugador/a</label><label><input type="radio" name="role" value="organizador"> Organizador/a</label><label><input type="radio" name="role" value="espectador"> Espectador/a</label><label><input type="radio" name="role" value="otro"> Otra forma</label></div></fieldset>
        <fieldset><legend>02 / ¿Quién debería poder aparecer en el ranking nacional?</legend><div class="choices"><label><input type="radio" name="eligibility" value="nacionalidad-local" required> Guatemaltecos con participación presencial en Guatemala en 2026</label><label><input type="radio" name="eligibility" value="nacionalidad"> Guatemaltecos, aunque compitan solo en el extranjero</label><label><input type="radio" name="eligibility" value="otra"> Propongo otra regla en el comentario</label></div></fieldset>
        <fieldset class="activity-question">
          <legend>03 / ¿Cuánto debe jugar una persona para aparecer en el top?</legend>
          <p class="activity-intro">Hablemos de la actividad de <strong>cada jugador</strong>. Primero, el torneo debe estar admitido en el ranking; después contamos los sets que jugó esa persona.</p>
          <div class="activity-guide">
            <div class="activity-definition"><span class="activity-number" aria-hidden="true">01</span><h3>¿Qué torneo cuenta?</h3><p>Uno presencial de Smash Ultimate individual, terminado y admitido en el ranking. Debes haber jugado allí al menos un set válido: inscribirte no basta. Si el torneo quedó fuera, sus sets tampoco suman.</p></div>
            <div class="activity-definition"><span class="activity-number" aria-hidden="true">02</span><h3>¿Qué set cuenta?</h3><p>Un enfrentamiento terminado contra otra persona, con ganador y marcador en start.gg. <strong>Ganar y perder cuentan.</strong> Un 3–2 son cinco partidas, pero <strong>un solo set</strong>. DQ, pase automático (bye), W/O y resultados sin marcador no cuentan.</p></div>
          </div>
          <div class="activity-example">
            <h3>Con peras y manzanas</h3>
            <div class="activity-scenarios">
              <p class="activity-scenario yes"><span class="scenario-icon" aria-hidden="true">✓</span><span><strong>Sí cumple:</strong> 2 sets en el torneo A + 2 en el B = <strong>2 torneos y 4 sets en total.</strong></span></p>
              <p class="activity-scenario no"><span class="scenario-icon" aria-hidden="true">×</span><span><strong>No cumple:</strong> 4 sets solo en el torneo A. Falta otro torneo. Tampoco alcanzan 2 torneos con solo 1 set en cada uno.</span></p>
            </div>
          </div>
          <div class="activity-notes">
            <p><strong>¿Y la opción de 3 torneos y 6 sets?</strong> Son seis sets <strong>sumados entre los tres torneos</strong>, no seis en cada uno. En este piloto, al menos un torneo debe ser en Guatemala; otro puede ser en el extranjero si cumple las reglas.</p>
            <p>El mínimo de participantes de <em>cada torneo</em> es otra regla: en Guatemala se necesitan <strong>20 personas que hayan jugado al menos un set válido</strong>; no basta con estar inscritas. <a href="./analisis-torneos.html">Ver el estudio histórico de torneos pequeños ↗</a></p>
          </div>
          <h3 class="activity-choice-title">¿Qué mínimo te parece justo?</h3>
          <div class="choices"><label><input type="radio" name="minimum" value="2-eventos-4-sets" required> Al menos 2 torneos que cuenten y 4 sets válidos en total (regla actual)</label><label><input type="radio" name="minimum" value="3-eventos-6-sets"> Al menos 3 torneos que cuenten y 6 sets válidos en total</label><label><input type="radio" name="minimum" value="otro"> Otro mínimo; lo explico abajo</label></div>
        </fieldset>
        <fieldset><legend>04 / ¿Cómo tratar los torneos en el extranjero?</legend><div class="choices"><label><input type="radio" name="international" value="todos-validos" required> Contar todos los presenciales que cumplan las reglas</label><label><input type="radio" name="international" value="solo-grandes"> Contar solo los más grandes</label><label><input type="radio" name="international" value="ninguno"> Contar solo torneos de Guatemala</label></div></fieldset>
        <div class="survey-pair"><fieldset><legend>05 / ¿Qué tan clara es la <a href="./metodologia.html">explicación del cálculo</a>?</legend><select name="clarity" required><option value="">Selecciona de 1 a 5</option><option value="1">1 · Nada clara</option><option value="2">2</option><option value="3">3</option><option value="4">4</option><option value="5">5 · Muy clara</option></select></fieldset><fieldset><legend>06 / ¿Qué tanta confianza te da el piloto actual?</legend><select name="confidence" required><option value="">Selecciona de 1 a 5</option><option value="1">1 · Ninguna</option><option value="2">2</option><option value="3">3</option><option value="4">4</option><option value="5">5 · Mucha</option></select></fieldset></div>
        <div class="survey-text"><label for="source">Enlace de start.gg que debamos revisar (opcional)</label><input id="source" name="source" type="url" maxlength="250" placeholder="https://www.start.gg/..."></div>
        <div class="survey-text"><label for="comment">¿Qué mejorarías? Puedes mencionar jugadores, torneos o reglas.</label><textarea id="comment" name="comment" rows="5" maxlength="2000" placeholder="Cuéntanos qué cambiarías y por qué…"></textarea></div>
        <p class="privacy-note">No pedimos nombre, correo ni cuenta, y no guardamos tu IP en las respuestas. Evita incluir datos personales en el comentario. Las respuestas se guardan de forma privada en rankingsmashbros.com para revisar las reglas; publicaremos las decisiones y su justificación, no respuestas individuales.</p>
        <button class="survey-submit" type="submit">ENVIAR OPINIÓN <span aria-hidden="true">↗</span></button>
      </form>
    <?php endif; ?>
  </main>
  <footer class="wrap"><a href="https://ingporras.com/">INGPORRAS <span aria-hidden="true">↗</span></a><p>Hecho para la comunidad de Guatemala.<br>Proyecto independiente, sin afiliación con start.gg, UltRank o Nintendo.</p><span>SMASH GT</span></footer>
</body>
</html>
