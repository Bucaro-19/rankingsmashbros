# Encargo para Codex — medir cuántos visitantes aguanta el sitio

Fecha: 8 de octubre de 2026. El dueño quiere saber cuántos usuarios soporta rankingsmashbros.com antes de promocionarlo y vender premium. Es una **medición controlada del sitio propio**, no una prueba de fuerza: el objetivo es encontrar el punto donde empieza a degradarse, no tumbarlo.

## Contexto que condiciona la prueba

- Hosting **compartido** (BanaHosting, cPanel, sin SSH). Los límites del plan (procesos de entrada, CPU, memoria, E/S, procesos) cortan antes que el código, y un exceso puede provocar errores 508/503 para los visitantes reales o una suspensión de la cuenta. **Antes de medir**, pide al dueño una captura de cPanel → «Uso de recursos» (límites del plan y uso actual) y deja esos números en el informe.
- El ranking público es estático: `index.html` + `data/public.json` (3 MB; 180 KB con Brotli; desde el 8/oct con `Cache-Control: no-cache`, revalida con 304). Cada visitante lo consulta al entrar y cada 60 s.
- PHP con base de datos por visita: `visita.php` (contador, una escritura por página vista), `account-api.php`, `premium-api.php`, `organizador-api.php`, `analisis-api.php` (la más pesada; requiere sesión), `encuesta.php`, `top.php`.
- Cron cada 5 minutos (`ranking-worker.php`) y publicación semanal el domingo 00:00 Guatemala. No midas durante esas ventanas.

## Reglas de seguridad (no negociables)

1. **Local primero.** Todo el guion se prueba contra un sitio local con base desechable. Producción solo con la orden expresa del dueño, en el horario que él elija (madrugada de Guatemala, nunca sábado noche ni domingo).
2. **Escalones pequeños y freno automático.** Sube de a poco (por ejemplo 1, 2, 5, 10, 20, 40 visitantes simultáneos, 60 s por escalón) y **detente solo** en el primer escalón con más de 1 % de errores (5xx, 508, tiempos agotados) o con p95 por encima de 3 s. No sigas «para ver qué pasa».
3. **Tope duro** de visitantes simultáneos y de peticiones totales escrito en el guion, que no se pueda superar por argumento.
4. **Sin escrituras basura.** No envíes la encuesta, no crees cuentas, no inicies pagos ni llames a Recurrente, no dispares OAuth contra start.gg, no llames a `ranking-sync.php` ni al webhook. `visita.php` escribe en el contador del dueño: o se excluye, o se mide con un tope bajo y el informe dice cuántas visitas falsas quedaron para descontarlas (no borres filas de producción).
5. **Solo este dominio.** Nada contra start.gg, Recurrente, Google Fonts ni GitHub.
6. **Un solo origen identificable:** `User-Agent` propio (`SmashGT-LoadTest`) para que el dueño o el hosting puedan reconocerlo y bloquearlo.
7. Sin credenciales en el guion ni en registros. Los endpoints con sesión se miden en local; en producción solo anónimos, salvo que el dueño preste su sesión de administrador para `analisis-api.php` y lo ordene.

## Qué medir

- **Escenario «visitante»:** portada + `public.json` (primera carga y revalidación 304) + `visita.php` + `account-api.php` anónimo. Es el caso real y el que define la respuesta para el dueño.
- **Por separado:** estático puro, PHP sin base, PHP con lectura, PHP con escritura (`visita.php`), y en local `analisis-api.php` con sesión.
- Por escalón: peticiones/s, p50/p95/p99, errores por código, bytes. Y el uso de recursos de cPanel durante la prueba, si el dueño puede mirarlo.

## Entrega

- Guion reproducible en `scripts/` (Python estándar o `k6`/`hey` si justificas la dependencia), con pruebas del freno automático y del tope.
- Informe `docs/smash/PRUEBA-DE-CARGA.md` en lenguaje llano: «aguanta sin problema N visitantes a la vez, empieza a ir lento con M, falla con K», qué recurso se agota primero, y recomendaciones ordenadas por impacto (caché, peso de `public.json`, frecuencia de consulta, contador de visitas, plan de hosting), distinguiendo lo medido de lo estimado.
- Resultados locales en la PR. La medición en producción queda preparada con el comando exacto y espera la orden del dueño.
- `EN-CURSO.md` actualizado. No fusiones ni despliegues sin la orden del dueño.
