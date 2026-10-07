# Encargo para Codex — datos del análisis de rival (premium)

Fecha: 7 de octubre de 2026, noche. Lo pidió el dueño al terminar tu entrega de personajes por game (PR #36). **Es solo servidor: ninguna pantalla.** Claude Code hace la pantalla del análisis, la pestaña Premium y el rediseño de Método y Tu opinión; no toques `cuenta.*`, `panel.*`, `metodologia.*`, `encuesta.*`, `paginas.css` ni `cabecera.js`.

## Qué construir

Un punto de consulta `analisis-api.php` (más su biblioteca, denegada en `.htaccess` y añadida a la lista de `deploy.py` antes de quien la usa) que entregue en JSON los datos que consume el diseño de Claude Design. El contrato está en la carpeta local del dueño `design_handoff_smash_gt_analisis/README.md`, secciones «Datos que consume», «Reglas de muestra» y «Qué se oculta si falta». Léelo completo antes de empezar; no portes `support.js` ni sus datos de ejemplo.

Entrada: `GET analisis-api.php?rival=<playerId>` y `GET analisis-api.php?buscar=<texto>` para el buscador. Solo con sesión de cuenta (usa `smash_account_resume` y `smash_account_current` de `accounts.php`, como hace `panel-api.php`). El jugador «yo» sale siempre de la sesión, nunca de un parámetro.

## Qué es gratis y qué es premium

- **Gratis para toda cuenta con sesión:** los dos jugadores (alias, puesto y puntos por vista) y el récord de sets entre ambos. Es lo que el diseño muestra en el estado «bloqueado».
- **Premium:** todo lo demás. La condición sale de `smash_premium_status()` en `premium.php` (lee PREMIUM.md). Si la cuenta no es premium, **el servidor no envía** los datos premium: no basta con que la pantalla los oculte. Devuelve además `premium: {active, expiredAt}` para que la pantalla distinga «bloqueado» de «vencido».
- La cuenta con rol `admin` (el dueño) puede ver el análisis completo aunque no sea premium, para poder probar. Usa `smash_stats_is_owner()`.

## Datos, con su fuente

1. `me` / `rival`: del corte publicado (`public.json` y `localRanking`), como hace `smash_account_profile()`. Personajes elegidos del usuario desde `user_characters`; detectados desde el corte, con porcentaje; cobertura «personaje registrado en r de t sets».
2. `h2h[]`: sets entre ambos del corte, con marcador y, si existe, el personaje de cada uno en ese set (desde `games` / `game_selections`). Para el marcador reutiliza la regla ya probada en `account-model.js` (`setScore`): si el texto no trae números, no se inventa.
3. `rivalForm[]`: últimos torneos del rival con sets ganados y perdidos. **`placement` y `entrants` del rival no están en el corte ni en SQL**: envíalos como `null` y documenta qué haría falta para tenerlos; no los estimes.
4. `rivalTiers[vista]`: récord del rival contra jugadores por tramo de puesto (top 10, 11–50, 51–100, sin puesto) en la vista pedida.
5. `meVsChar`, `himVsChar`, `gameMatrix`: desde `games` y `game_selections`. `scene` es toda la escena del corte. Entrega siempre conteos G–P, nunca porcentajes: el porcentaje lo decide la pantalla según la regla de 10 o más.
6. `recommendations[]`: aplica exactamente la regla de confianza del README (alta, media, baja o ninguna). Si no se cumple ninguna, lista vacía: la pantalla mostrará «Sin datos suficientes».
7. Probabilidad: entrega los puntos de ambos por vista y calcula `p` con la fórmula del README **solo si coincide con la metodología**; el modelo publica `puntos = 1500 + 400/ln(10) × fuerza`, así que revisa qué constante corresponde (400 u 800) y documenta la decisión. Si no puedes justificarla, entrega los puntos y deja `p` para decidir con el dueño.

## Estado de los datos hoy

`games` y `game_selections` tienen 0 filas en producción hasta que se fusione y publique tu PR #36 y se haga la carga inicial del corte del 4/oct. La API debe funcionar igual con las tablas vacías: cruces sin games, sin recomendaciones y con la cobertura real. Si el dueño ordena la carga inicial, es parte de este encargo: herramienta de contexto anclada al hash original, simulación primero, y escritura solo con su orden expresa.

## Reglas

- Solo lectura sobre el corte y las tablas; no cambia cálculo, elegibilidad, `public.json` ni su versión.
- Sin consultas a start.gg por visita.
- Un rival «sin puesto» nunca se presenta como débil: es `null`, no cero.
- Respuestas `no-store`, sin datos de otras cuentas, sin IDs internos de usuarios. Límites de tamaño y de frecuencia razonables para el buscador (mínimo de caracteres, máximo de resultados).
- Consultas con parámetros ligados; índices nuevos solo si mides que hacen falta, y por migración versionada (`docs/smash/migrations/`, van 004) aplicada con orden del dueño.

## Entrega

Rama propia desde `main`, pruebas en base desechable con datos inventados (incluye: cuenta sin premium que no recibe nada premium, cuenta premium, dueño, rival sin puesto, rival sin personajes, sin sets entre ambos, tablas de games vacías) en MySQL 8.0 y MariaDB 10.11, PR, y documentación en `EN-CURSO.md` y un `ANALISIS-RIVAL.md` con el contrato final de la respuesta, para que Claude Code conecte la pantalla. No fusiones ni despliegues sin la orden del dueño.
