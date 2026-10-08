# Encargo para Codex — carga inicial de games y rediseño de «Tu opinión»

Fecha: 7 de octubre de 2026, noche. Dos tareas independientes, en este orden. Claude Code está con la pantalla del análisis de rival (`analisis.html`, `analisis.css`, `analisis.js`, `analisis-model.js`) y ya publicó Método y la pestaña Premium; no toques esos archivos ni `cuenta.*`, `premium.js`, `panel.*`, `metodologia.*`.

## 1. Carga inicial de los games del corte del 4/oct

Tu PR #36 dejó propuesta en IMPORTACION-RANKING.md una carga solo de contexto anclada al hash original del corte. La API del análisis (#40) ya está publicada y hoy responde `gameDataStatus: "empty"` porque `games` y `game_selections` tienen 0 filas.

- Implementa la herramienta: paquete solo de contexto (games y selecciones) del corte ya importado, sin tocar `cuts`, `rankings`, tablas de instantánea ni el hash del corte; protección contra contexto posterior; simulación por defecto y `--apply` explícito; repetible.
- Fuente: la captura y la caché ya existentes. Sin recapturar el corte ni consultar de más a start.gg.
- Ejecuta la **simulación** contra producción (solo lectura) y documenta conteos esperados, tiempo y memoria.
- **No escribas en producción.** La escritura necesita la orden expresa del dueño; deja el comando exacto listo y dilo en la PR.
- Si el corte del domingo 11/oct llega antes, ajusta: ese corte ya trae games por el circuito normal.

## 2. Rediseño de «Tu opinión» (`encuesta.php`)

Handoff de Claude Design en la carpeta local del dueño `design_handoff_smash_gt_metodo_opinion/` (README, sección «Página 2 · Tu opinión», y `Encuesta.dc.html`). Es la segunda mitad del paquete; la primera (Método) ya está publicada y dejó la base que debes reutilizar:

- `paginas.css`: tokens, encabezado con `aria-current`, pie, tarjetas, avisos, botones (`.cta`, `.outline`), `.fold`. Cuerpo con `class="smash-redesign page-read"` y `arena.css` cargado antes.
- `cabecera.js`: aviso de sesión del encabezado. Copia el encabezado y el pie de `metodologia.html` tal cual (con `aria-current="page"` en «Tu opinión»).
- Mira `metodologia.html` y `metodologia.css` como ejemplo de la línea gráfica ya aprobada por el dueño.

Reglas que no se negocian:

- **No cambian preguntas, opciones, textos de ayuda, `name`/`value` de los campos, `nonce`, honeypot `website`, límites ni la lógica del servidor.** Es un rediseño visual y de lectura.
- La encuesta sigue en SQL (`survey.php`, `survey_responses`): sin doble escritura, sin volver al archivo, sin guardar ni registrar IP, correo, cuenta, navegador o identificador de sesión. Nunca leas ni imprimas los comentarios de producción.
- El marcador `<meta name="smash-survey-storage" content="sql">` y el `require_once __DIR__ . '/survey.php';` deben seguir: `deploy.py` rechaza la página sin ellos.
- **Funciona sin JavaScript**: formulario HTML normal. El servidor repinta los `checked` y los textos tras un error; las mejoras con JS (avance en vivo, contador, foco en el resumen de errores) son opcionales.
- Las escalas 5 y 6 pasan de `<select>` a radios reales con los mismos `name` y valores 1–5.
- No añadas `visita.js` a esta página: la encuesta no se cuenta en las estadísticas.
- `opiniones.php` (panel privado de respuestas) queda fuera; no lo rediseñes.

`scripts/database/test_survey_http.py` (más de 500 líneas) fija el comportamiento actual, incluidos textos y marcado que pueden cambiar con el rediseño: actualiza solo las aserciones de presentación y conserva intactas las de seguridad, almacenamiento, reintento y privacidad. Una de sus pruebas (`test_answers_are_never_exposed…`) compara el contador global de conexiones del servidor SQL y falla a veces en CI cuando el chequeo de salud del contenedor abre una conexión en medio: si puedes, hazla robusta sin debilitar lo que comprueba.

## Entrega

Una PR por tarea, cada una en su rama desde `main`, con pruebas en base desechable (MySQL 8.0 y MariaDB 10.11 en CI), revisión en navegador de «Tu opinión» en escritorio y a 375 px (estados: inicial, validación, guardado, error al guardar, ya respondiste, sin JS), y `EN-CURSO.md` actualizado. No fusiones ni despliegues sin la orden del dueño.
