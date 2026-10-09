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
                ], $_SESSION['smash_survey_nonce'], time());
                // 'already_saved': this same answer of this same form was stored by an earlier
                // attempt whose confirmation never reached the browser.
                $saved = $outcome === 'inserted' || $outcome === 'already_saved';
            } catch (Throwable $failure) {
                $saved = false;
                // Only a reason code reaches the server log: no answer text, no visitor data.
                error_log('Smash GT encuesta: respuesta no guardada (' . smash_survey_failure_code($failure) . ')');
                $failure = null;
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

// Presentation only. Validation, nonce, rate limit and SQL storage above are unchanged.
$surveyQuestions = [
    [
        'id' => 'q1', 'name' => 'role',
        'legend' => '¿Desde dónde participas en la escena?',
        'options' => [
            ['jugador', 'Jugador/a'],
            ['organizador', 'Organizador/a'],
            ['espectador', 'Espectador/a'],
            ['otro', 'Otra forma'],
        ],
    ],
    [
        'id' => 'q2', 'name' => 'eligibility',
        'legend' => '¿Quién debería poder aparecer en el ranking nacional?',
        'options' => [
            ['nacionalidad-local', 'Guatemaltecos con participación presencial en Guatemala en 2026'],
            ['nacionalidad', 'Guatemaltecos, aunque compitan solo en el extranjero'],
            ['otra', 'Propongo otra regla en el comentario'],
        ],
    ],
    [
        'id' => 'q3', 'name' => 'minimum',
        'legend' => '¿Cuánto debe jugar una persona para aparecer en el top?',
        'options' => [
            ['2-eventos-4-sets', 'Al menos 2 torneos que cuenten y 4 sets válidos en total (regla actual)'],
            ['3-eventos-6-sets', 'Al menos 3 torneos que cuenten y 6 sets válidos en total'],
            ['otro', 'Otro mínimo; lo explico abajo'],
        ],
    ],
    [
        'id' => 'q4', 'name' => 'international',
        'legend' => '¿Cómo tratar los torneos en el extranjero?',
        'options' => [
            ['todos-validos', 'Contar todos los presenciales que cumplan las reglas'],
            ['solo-grandes', 'Contar solo los más grandes'],
            ['ninguno', 'Contar solo torneos de Guatemala'],
        ],
    ],
    [
        'id' => 'q5', 'name' => 'clarity',
        'legend' => '¿Qué tan clara es la <a href="./metodologia.html">explicación del cálculo</a>?',
        'options' => [
            ['1', '1 · Nada clara'],
            ['2', '2'],
            ['3', '3'],
            ['4', '4'],
            ['5', '5 · Muy clara'],
        ],
    ],
    [
        'id' => 'q6', 'name' => 'confidence',
        'legend' => '¿Qué tanta confianza te da el piloto actual?',
        'options' => [
            ['1', '1 · Ninguna'],
            ['2', '2'],
            ['3', '3'],
            ['4', '4'],
            ['5', '5 · Mucha'],
        ],
    ],
];
$surveyAnswers = [];
$surveyMissing = [];
foreach ($surveyQuestions as $question) {
    $name = $question['name'];
    $surveyAnswers[$name] = choice($name, array_column($question['options'], 0));
    if ($error !== '' && $surveyAnswers[$name] === null) $surveyMissing[] = $question;
}
$surveyAnswered = count(array_filter($surveyAnswers, static function ($value) { return $value !== null; }));
$surveyRecent = $error === 'Ya recibimos una respuesta reciente de esta sesión. Gracias.';
$surveyTextError = $error === 'El comentario o el enlace es demasiado largo, o el enlace no es de start.gg.';
$surveySourceError = $surveyTextError && (strlen($source) > 250 || ($source !== '' &&
    (!filter_var($source, FILTER_VALIDATE_URL) || !in_array(strtolower((string)$sourceHost), ['start.gg', 'www.start.gg'], true)
     || parse_url($source, PHP_URL_SCHEME) !== 'https')));
$surveyCommentError = $surveyTextError && strlen($comment) > 2000;
function survey_text(string $name): string {
    $value = $_POST[$name] ?? '';
    return is_string($value) ? $value : '';
}
?>
<!doctype html>
<html lang="es-GT">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#0B0F1A">
  <meta name="description" content="Opina sobre las reglas del ranking de Super Smash Bros. Ultimate de Guatemala, sin crear una cuenta.">
  <meta name="smash-survey-storage" content="sql">
  <title>Cuestionario de la comunidad — Ranking Smash Bros</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@500;700;800;900&family=Archivo:wght@400;500;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="./arena.css?v=20261009-2">
  <link rel="stylesheet" href="./paginas.css?v=20261008-1">
  <link rel="stylesheet" href="./encuesta.css?v=20261009-1">
  <script src="./cabecera.js?v=20261009-1" defer></script>
  <script src="./encuesta.js?v=20261008-1" defer></script>
</head>
<body class="smash-redesign page-read">
  <a class="skip-link" href="#contenido">Saltar al contenido</a>
  <header class="gt-header">
    <a class="gt-brand" href="./" aria-label="Ranking Smash Bros, inicio"><span class="gt-mark">GT</span><span>RANKING SMASH BROS<small>por ingporras</small></span></a>
    <nav aria-label="Principal"><a href="./#ranking">Ranking</a><a href="./torneos.html">Torneos</a><a href="./metodologia.html">Método</a><a href="./encuesta.php" aria-current="page">Tu opinión</a><a id="panel-link" href="./panel.php" hidden>Panel</a><a id="account-link" class="account-link" href="./cuenta.html">Iniciar sesión</a></nav>
  </header>
  <main id="contenido" class="survey-page">
    <div class="survey-hero">
      <p class="kicker"><span class="survey-dot" aria-hidden="true"></span> PILOTO 2026 / TU OPINIÓN CUENTA</p>
      <h1>HAGAMOS UN<br><em>RANKING MEJOR.</em></h1>
      <p class="survey-lead">Queremos acordar reglas claras con la comunidad de Smash Ultimate de Guatemala. Contestar toma unos 3 minutos y no requiere cuenta. Esta consulta orienta la revisión; los puestos se calculan con resultados, no por votación.</p>
    </div>
    <?php if ($saved): ?>
      <section class="survey-message success" role="status"><span class="message-mark" aria-hidden="true">✓</span><h2>¡Respuesta recibida!</h2><p>Gracias por ayudarnos a pulir el ranking 2026.</p><a class="outline" href="./metodologia.html">Ver reglas y torneos ↗</a></section>
    <?php elseif ($surveyRecent): ?>
      <section class="survey-message recent" role="status"><span class="message-mark" aria-hidden="true">i</span><h2>Ya respondiste desde este navegador</h2><p><?= h($error) ?></p><div class="link-row"><a class="outline" href="./metodologia.html">Ver reglas y torneos ↗</a><a class="outline" href="./#ranking">Volver al ranking</a></div></section>
    <?php else: ?>
      <form method="post" action="./encuesta.php" class="survey-form">
        <input type="hidden" name="nonce" value="<?= h($_SESSION['smash_survey_nonce']) ?>">
        <div class="trap" aria-hidden="true"><label for="website">Sitio web</label><input id="website" name="website" type="text" tabindex="-1" autocomplete="off"></div>
        <nav class="survey-progress" aria-label="Avance del cuestionario">
          <p id="survey-progress-text" role="status">Respondiste <?= $surveyAnswered ?> de 6</p>
          <div class="progress-segments">
            <?php foreach ($surveyQuestions as $question): $answered = $surveyAnswers[$question['name']] !== null; ?>
              <a href="#<?= $question['id'] ?>" data-question="<?= $question['name'] ?>" class="<?= $answered ? 'answered' : ($error !== '' ? 'missing' : '') ?>" aria-label="Pregunta <?= substr($question['id'], 1) ?>: <?= $answered ? 'respondida' : 'sin responder' ?>"><span aria-hidden="true"></span></a>
            <?php endforeach; ?>
          </div>
        </nav>
        <?php if ($error !== ''): ?>
          <div class="survey-message error" id="survey-error" role="alert" tabindex="-1">
            <span class="message-mark" aria-hidden="true">!</span>
            <?php if ($surveyMissing): ?><h2>Faltan <?= count($surveyMissing) ?> respuestas</h2><?php endif; ?>
            <p><?= h($error) ?></p>
            <p>Tus respuestas siguen marcadas abajo; no tienes que contestar otra vez.</p>
            <?php if ($surveyMissing): ?><div class="link-row"><?php foreach ($surveyMissing as $missing): ?><a href="#<?= $missing['id'] ?>">Pregunta <?= substr($missing['id'], 1) ?> ↗</a><?php endforeach; ?></div><?php endif; ?>
          </div>
        <?php endif; ?>
        <?php foreach ($surveyQuestions as $index => $question):
            $name = $question['name'];
            $scale = $index >= 4;
            $missing = $error !== '' && $surveyAnswers[$name] === null;
        ?>
          <fieldset id="<?= $question['id'] ?>" class="survey-question<?= $missing ? ' question-error' : '' ?>"<?= $missing ? ' aria-describedby="'.$question['id'].'-error"' : '' ?>>
            <legend><span class="question-number">0<?= $index + 1 ?> / 06</span><span><?= $question['legend'] ?></span></legend>
            <div class="question-body">
              <?php if ($name === 'minimum'): ?>
                <p class="activity-intro">Hablemos de la actividad de <strong>cada jugador</strong>. Primero, el torneo debe estar admitido en el ranking; después contamos los sets que jugó esa persona.</p>
<div class="activity-guide"><details class="fold"><summary><span class="activity-number" aria-hidden="true">01</span>¿Qué torneo cuenta?</summary><div><p>Uno presencial de Smash Ultimate individual, terminado y admitido en el ranking. Debes haber jugado allí al menos un set válido: inscribirte no basta. Si el torneo quedó fuera, sus sets tampoco suman.</p></div></details>
<details class="fold"><summary><span class="activity-number" aria-hidden="true">02</span>¿Qué set cuenta?</summary><div><p>Un enfrentamiento terminado contra otra persona, con ganador y marcador en start.gg. <strong>Ganar y perder cuentan.</strong> Un 3–2 son cinco partidas, pero <strong>un solo set</strong>. DQ, pase automático (bye), W/O y resultados sin marcador no cuentan.</p></div></details>
<details class="fold"><summary><span class="activity-number yellow" aria-hidden="true">✦</span>Con peras y manzanas</summary><div class="activity-scenarios">
              <p class="activity-scenario yes"><span class="scenario-icon" aria-hidden="true">✓</span><span><strong>Sí cumple:</strong> 2 sets en el torneo A + 2 en el B = <strong>2 torneos y 4 sets en total.</strong></span></p>
              <p class="activity-scenario no"><span class="scenario-icon" aria-hidden="true">×</span><span><strong>No cumple:</strong> 4 sets solo en el torneo A. Falta otro torneo. Tampoco alcanzan 2 torneos con solo 1 set en cada uno.</span></p></div></details>
<details class="fold"><summary><span class="activity-number" aria-hidden="true">?</span>¿Y la opción de 3 torneos y 6 sets?</summary><div class="activity-notes">
            <p>Son seis sets <strong>sumados entre los tres torneos</strong>, no seis en cada uno. En este piloto, al menos un torneo debe ser en Guatemala; otro puede ser en el extranjero si cumple las reglas.</p>
            <p>El mínimo de participantes de <em>cada torneo</em> es otra regla: en Guatemala se necesitan <strong>20 personas que hayan jugado al menos un set válido</strong>; no basta con estar inscritas. <a href="./analisis-torneos.html">Ver el estudio histórico de torneos pequeños ↗</a></p></div></details>
</div>
<h3 class="activity-choice-title">¿Qué mínimo te parece justo?</h3>
              <?php endif; ?>
              <div class="choices<?= $scale ? ' scale-choices' : '' ?>">
                <?php foreach ($question['options'] as $optionIndex => $option): ?>
                  <label><input type="radio" name="<?= $name ?>" value="<?= h($option[0]) ?>"<?= $optionIndex === 0 ? ' required' : '' ?><?= $surveyAnswers[$name] === $option[0] ? ' checked' : '' ?><?= $missing ? ' aria-invalid="true" aria-describedby="'.$question['id'].'-error"' : '' ?><?= $scale ? ' aria-label="'.h($option[1]).'"' : '' ?>><span><?= h($scale ? $option[0] : $option[1]) ?></span></label>
                <?php endforeach; ?>
              </div>
              <?php if ($scale): ?><div class="scale-labels" aria-hidden="true"><span><?= h($question['options'][0][1]) ?></span><span><?= h($question['options'][4][1]) ?></span></div><?php endif; ?>
              <?php if ($missing): ?><p class="question-error-text" id="<?= $question['id'] ?>-error"><span aria-hidden="true">!</span><?= $scale ? 'Elige un número del 1 al 5.' : 'Elige una opción para continuar.' ?></p><?php endif; ?>
            </div>
          </fieldset>
        <?php endforeach; ?>
        <div class="survey-optional">
          <p class="kicker">Opcional</p>
          <div class="survey-text"><label for="source">Enlace de start.gg que debamos revisar (opcional)</label><input id="source" name="source" type="url" maxlength="250" placeholder="https://www.start.gg/..." value="<?= h(survey_text('source')) ?>"<?= $surveySourceError ? ' aria-invalid="true" aria-describedby="source-error"' : '' ?>><?php if ($surveySourceError): ?><p class="question-error-text" id="source-error"><?= h($error) ?></p><?php endif; ?></div>
          <div class="survey-text"><label for="comment">¿Qué mejorarías? Puedes mencionar jugadores, torneos o reglas.</label><textarea id="comment" name="comment" rows="5" maxlength="2000" placeholder="Cuéntanos qué cambiarías y por qué…" aria-describedby="comment-count<?= $surveyCommentError ? ' survey-error' : '' ?>"<?= $surveyCommentError ? ' aria-invalid="true"' : '' ?>><?= h(survey_text('comment')) ?></textarea><span id="comment-count"><?= function_exists('mb_strlen') ? mb_strlen(survey_text('comment'), 'UTF-8') : strlen(survey_text('comment')) ?> / 2,000</span></div>
        </div>
        <div class="privacy-note"><span class="privacy-mark" aria-hidden="true">i</span><p>No pedimos nombre, correo ni cuenta, y no guardamos tu IP en las respuestas. Evita incluir datos personales en el comentario. Las respuestas se guardan de forma privada en rankingsmashbros.com para revisar las reglas; publicaremos las decisiones y su justificación, no respuestas individuales.</p></div>
        <button class="survey-submit cta blue" type="submit"><span>ENVIAR OPINIÓN <b aria-hidden="true">↗</b></span></button>
      </form>
    <?php endif; ?>
  </main>
  <footer class="gt-footer"><span>Hecho para la comunidad de Guatemala. <a href="https://ingporras.com/">INGPORRAS ↗</a></span><span>Datos: start.gg · <span id="footer-method">BT-PILOTO-3</span><br>Arte: Nintendo y titulares respectivos · Recursos: <a href="https://github.com/marcrd/smash-ultimate-assets" target="_blank" rel="noopener noreferrer">marcrd</a> / <a href="https://github.com/jonborg/ThumbnailGenerator" target="_blank" rel="noopener noreferrer">ThumbnailGenerator</a></span><p>Proyecto independiente, sin afiliación con Nintendo, start.gg ni UltRank. Ranking experimental.</p></footer>
</body>
</html>
