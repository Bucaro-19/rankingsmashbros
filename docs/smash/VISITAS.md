# Contador de visitas — estadísticas privadas del dueño

Pedido del dueño el 7 de octubre de 2026: saber cuánta gente entra y cuánta se registra. Los datos se ven en el panel privado: [PANEL-DUENO.md](PANEL-DUENO.md). Requiere las migraciones 002 y 003.

## Qué se cuenta

- Una vista por cada carga de `index.html`, `metodologia.html`, `cuenta.html`, `analisis-top20.html` y `analisis-torneos.html`. **No se cuentan** la encuesta (anónima) ni el panel de opiniones.
- Día: el del calendario de Guatemala (UTC−6).
- `site_visit_days`: vistas por día y página.
- `site_visitor_days`: una fila por visitante y día, con sus vistas y si tenía la sesión recordada.
- `site_network_days`: una fila por red y día, con sus vistas y cuántos identificadores nuevos recibió.

Consultas base para el panel: visitantes de un día `COUNT(*)` en `site_visitor_days`; de un periodo `COUNT(DISTINCT visitor_hash)`; redes distintas igual sobre `site_network_days`. Registros: `users.created_at` y `oauth_connections.revoked_at`.

## Cómo se identifica a un visitante

1. `visita.js` (incluido en cada página contada) envía un POST a `visita.php` con la clave de la página. Sin JavaScript no se cuenta, lo que deja fuera a casi todos los robots; además se omiten agentes automáticos conocidos.
2. El servidor entrega la cookie propia **`smash_visita`** (HttpOnly, Secure, SameSite=Lax, 400 días): un identificador aleatorio más su firma HMAC. Solo se aceptan identificadores firmados por el servidor; uno inventado se descarta.
3. En SQL se guarda el SHA-256 del valor de la cookie, nunca el valor.
4. Si el navegador no admite cookies, el visitante es la red: un HMAC de la IP.

**Decisión del dueño (7/oct):** prefirió conteo exacto y autorizó usar la IP. Esto cambia, solo para el contador, la regla anterior de no guardar identificadores de visitantes. Límites honestos: es exacto por navegador, no por persona (dos dispositivos son dos visitantes; borrar cookies crea uno nuevo), y la IP no distingue a quienes comparten red (los operadores móviles ponen a muchas personas detrás de una misma IP), por eso es el respaldo y una segunda medida, no la principal.

## Privacidad

- **Nunca se guardan ni se registran:** la IP, el valor de la cookie, el navegador, la página de origen ni la cuenta. El contador no escribe en ningún log.
- La clave del HMAC se crea sola la primera vez en `private-smash/visits.key` (permisos 600, fuera del sitio). Si se pierde o se cambia, todos los visitantes cuentan como nuevos una vez; si queda dañada, el contador se detiene en silencio en vez de reemplazarla.
- Las respuestas de la encuesta siguen sin IP ni identificador y no se cruzan con el contador.
- `signed_in` solo indica que ese navegador tenía una sesión recordada vigente; no guarda de quién.

## Protección contra inflado

- Solo cuenta peticiones del propio sitio (`Sec-Fetch-Site` u `Origin` igual al host) con `application/json`.
- Un navegador deja de sumar después de 300 vistas en un día.
- Una red recibe como máximo 50 identificadores nuevos por día; pasado ese número sus visitas se atribuyen a la red.
- No es un sistema antifraude: alguien con muchas redes distintas podría inflar las cifras. Son estadísticas de orientación para el dueño.

## Comportamiento ante fallos

`visita.php` responde siempre vacío (204, o 400/403/405 a peticiones mal formadas) y nunca interrumpe la página. Sin la migración 003, sin clave o sin base, simplemente no cuenta.

## Pruebas

`php scripts/database/test_visits.php` (día de Guatemala, páginas, origen, robots, clave, firma, conteo, límites, privacidad, rollback) y `python scripts/database/test_visits_http.py` (cookie, cookies falsas, rechazos, fallo silencioso), en CI con MySQL 8.0 y MariaDB 10.11. Verificado en navegador contra una copia local con base desechable: tres páginas, un visitante, sin errores de consola.
