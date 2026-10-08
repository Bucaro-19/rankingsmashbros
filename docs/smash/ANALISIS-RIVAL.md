# API de análisis de rival — contrato para Claude Code

7 de octubre de 2026. Backend en `feat/rival-analysis-api`, [PR #40](https://github.com/Bucaro-19/rankingsmashbros/pull/40); espera revisión y orden del dueño para fusionar y publicar. No incluye pantalla ni carga inicial de games. El handoff local `design_handoff_smash_gt_analisis/README.md` es la referencia visual; no se porta `support.js` ni su información ficticia.

## Consulta y permisos

- `GET ./analisis-api.php?rival=<playerId>&scope=intl` o `scope=gt`.
- `GET ./analisis-api.php?buscar=<alias>&scope=intl`. `buscar=` vacío devuelve sugerencias con enfrentamientos previos. Siempre mandar uno de `rival` o `buscar`, nunca ambos.
- `scope` por defecto `intl`; también admite `combined` y `guatemala`. La respuesta normaliza a `intl` / `gt`.
- «Yo» siempre procede de `smash_account_resume()` y `smash_account_current()`. Cualquier parámetro adicional, incluido `me`, `userId`, `active` o `limit`, se rechaza. `rival` es el ID público de **jugador** de start.gg, distinto del ID de cuenta y del UUID del perfil.
- Gratis con sesión: identidad pública, puesto y puntos de ambos por vista y récord entre ambos. **Sin personajes, cobertura, historial, forma, tramos, recomendaciones ni probabilidad.**
- Premium: `smash_premium_status()` en el ambiente de la configuración privada; solo SELECT, sin refrescar Recurrente. Premium de otra cuenta o del otro ambiente no habilita acceso. El vencimiento se comprueba en cada petición. `admin` obtiene acceso por `smash_stats_is_owner()` aunque no pague.
- Para decidir la pantalla usar **`access.full`**, no solo `premium.active`: el dueño puede tener `active: false` y `full: true`. `premium.expiredAt` es ISO UTC cuando el último periodo conocido ya venció; en otro caso `null`.
- Cabeceras JSON, `Cache-Control: no-store, private`, `nosniff`, `no-referrer`, `noindex, nofollow`. No guardar estas respuestas en service worker ni caché pública.

No hay consultas a start.gg ni Recurrente por visita. El análisis se ejecuta en una transacción SQL **READ ONLY / REPEATABLE READ** y se termina con rollback. La reanudación de la sesión recordada conserva el mantenimiento de `user_sessions` que ya hacía `accounts.php`; esa autenticación ocurre antes de la transacción de análisis. No se escriben datos de torneos, cortes, cuentas, personajes elegidos o pagos desde esta API.

## Respuesta común y versión gratis

```json
{
  "ok": true,
  "scope": "intl",
  "generatedAt": "<fecha del corte publicado>",
  "seasonYear": 2026,
  "state": "bloqueado",
  "premium": {"active": false, "expiredAt": null},
  "access": {"full": false, "reason": "free"},
  "me": {
    "playerId": "1", "tag": "Yo", "avatarUrl": null, "country": "GT", "url": null,
    "rank": {"gt": 1, "intl": 2}, "points": {"gt": 1600, "intl": 1500}
  },
  "rival": {
    "playerId": "2", "tag": "Rival", "avatarUrl": null, "country": "MX", "url": null,
    "rank": {"gt": 2, "intl": 1}, "points": {"gt": 1500, "intl": 1600}
  },
  "record": {"wins": 2, "losses": 3, "sets": 5},
  "records": {
    "gt": {"wins": 2, "losses": 2, "sets": 4},
    "intl": {"wins": 2, "losses": 3, "sets": 5}
  }
}
```

Ejemplo ficticio de contrato. Puestos/puntos/alias vienen de `public.json` y `localRanking`; el récord usa sus `results` (ganador primero). Un jugador sin puesto conserva `rank` / `points` **null**, incluso si existe en SQL. No es puesto cero ni rival débil. País y URL se completan con `players`; país declarado no demuestra nacionalidad. El avatar propio puede venir de la sesión si pasa la lista de dominios de cuentas; el rival no tiene foto disponible y usa `null`.

`state`: `listo` con acceso completo; `bloqueado` sin premium; `vencido` con periodo vencido. `access.reason`: `admin`, `premium` o `free`. Si no hay jugador vinculado: `state: "sinJugador"`, `me`, `rival`, `record` en null y sin análisis adicional. `sinElegidos` es un estado visual derivado de `access.full && me.chosen.length === 0`; la API sigue respondiendo `listo`.

En una respuesta gratuita, **los campos premium no existen**: no vienen vacíos, difuminados ni con cifras inventadas. Esto también aplica a los campos anidados de ambos jugadores.

## Búsqueda

Respuesta: cabecera común, `state: "elegir"`, `results: [...]`, `truncated: boolean`. Cada resultado contiene los campos de perfil gratis y `record` de la vista pedida. No lleva personajes ni otras cuentas. Máximo 20; alias parcial, sin distinguir mayúsculas y acentos, mínimo 2 y máximo 80 caracteres UTF-8; la cadena vacía es la excepción de sugerencias. No se busca al propio jugador.

El índice comprende jugadores clasificados de ambas vistas **y sus rivales del ledger**, incluidos extranjeros y personas sin puesto. Un ID conocido en SQL pero sin datos en el corte puede consultarse directamente con `rival`; no se añade a la búsqueda por alias del corte. Las sugerencias vacías consideran que hubo enfrentamiento en cualquiera de las dos vistas, muestran el récord de la vista pedida y se ordenan por ese total, puesto, alias e ID. El buscador no cambia la cuenta ni su jugador.

## Campos adicionales premium/admin

Todos los récords son **conteos G–P**, no porcentajes. `setDataScope: "published_ledger"` indica que los sets proceden únicamente del ledger público: no son el historial completo de start.gg. Para rivales no clasificados, especialmente extranjeros, ese ledger puede omitir sus sets contra otras personas no clasificadas; rotular la forma y los récords como datos conocidos **en este corte**, sin prometer actividad completa. Los pares `[w,l]` se interpretan desde la persona o personaje indicado. No hay `share` en los detectados: se entrega `games` y `totalGames` para respetar la instrucción de conteos; Claude debe adaptar el diseño a estos nombres.

| Campo | Contrato y origen |
|---|---|
| `me.chosen` | Hasta tres slugs, en orden de `user_characters` de la propia cuenta. Nunca se leen preferencias de otra cuenta. Random no sirve como personaje para cruces. |
| `me.detected`, `rival.detected` | Lista del corte combinado: `{characterId: string, slug: string\|null, name, games: int, totalGames: int, usableForMatchups: bool}`. Orden publicado intacto. `totalGames` suma todos los usos publicados; no implica captura completa. El catálogo SQL resuelve slug; Random/ID desconocido no sirven para cruces. |
| `coverage` de ambos | `{registered: int\|null, total: int, source: "published"\|"unavailable"}`. Mains y cobertura publicados **idénticos**; no se recalculan con SQL. Para quien no está clasificado, `registered: null`, total de sets en el ledger combinado y `source: unavailable`. No afirmar que start.gg nunca registró su personaje. |
| `h2h` | Máximo 200 sets de la vista: `{setId, eventId, event, date, countryCode: string\|null, intl: bool\|null, myGames: int\|null, theirGames: int\|null, won: bool, myChar: slug\|null, theirChar: slug\|null, url: string\|null}`. Fechas/nombres/país/URL del corte. Orden por fecha del evento descendente, terminación SQL y desempate estable por ID; este desempate no demuestra cronología. `h2hTruncated` informa el límite; `record` cuenta todos. |
| `streak` | `{won: bool, sets: int}` o null. Solo con al menos 2 enfrentamientos, todos con hora de terminación conocida y distinta; se calcula por esa hora, no por el ID ni por un orden adivinado. Empates de hora o registros ausentes producen null. |
| `rivalForm` | Hasta cinco **eventos** recientes de la vista: `{eventId, event, date, countryCode, intl, placement: null, entrants: null, setsWon, setsLost, url}`. `rivalFormTotal` indica cuántos eventos tenía el ledger. No se agrupan dos eventos diferentes de un mismo torneo. |
| `rivalTiers` | `{gt: {...}, intl: {...}}`. Cada vista tiene `top10`, `t11_50`, `t51_100`, `unranked` y **`outsideTop100`**, todos `[w,l]`. Se compara con el puesto del contrincante **en este corte/vista**, no su puesto histórico. El quinto tramo evita clasificar como «sin puesto» a quien tiene puesto 101 o superior; Claude debe mostrarlo o explicarlo, nunca mezclarlo con `unranked`. |
| `meVsChar`, `himVsChar` | Objetos `{opponentSlug: [w,l]}` de **sets**, contra cualquier rival del ledger combinado cuyo personaje para todo el set pueda verificarse. `{}` si ninguno. No se infiere personaje con el main general del jugador. |
| `gameMatrix` | Objeto `"mySlug\|hisSlug": {me:[w,l], him:[w,l], scene:[w,l], sceneGames:int, mirror:bool}`. `me`: tú con A contra B, cualquier rival. `him`: él con B contra A, cualquier rival. `scene`: A contra B en los games disponibles de los eventos del corte combinado, aunque ninguno sea uno de ustedes. |
| `gameDataStatus` | `available`, `empty` (ningún game devuelto por la consulta) o `cut_not_synced` (SQL no tiene la misma instantánea pública publicada). No confundir el último con prueba de que nunca se registraron personajes. |
| `recommendations` | Máximo 2: `{type:"good"\|"avoid",slug,confidence:"alta"\|"media"\|"baja",ownSets,sceneGames,reasonData:{own:[w,l],scene:[w,l],opponentSlug,basis:"own_sets"\|"scene_games"}}`. Sin confianza o sin dirección demostrada, `[]`. |
| `probability` | `{p: float\|null, scale:400, methodVersion}`. `p` es probabilidad del modelo como fracción de 0 a 1, **no un porcentaje de victorias históricas**. Sin puntos de cualquiera, o método desconocido, null. |

### Qué es un personaje verificable por set/game

Para atribuir un personaje al **set completo**: ambos participantes deben coincidir con el resultado publicado, cada entrant tiene un solo jugador, todas las partidas de ese jugador tienen una sola selección conocida, ninguna Random, el personaje es el mismo en todas y el total de games coincide con la suma del marcador numérico publicado y su numeración va de 1 a ese total sin huecos. Si cambia de personaje, faltan selecciones/games, el marcador no es legible o la relación de jugadores cambió, se deja null para esa atribución. No usar el main como sustituto. El otro participante puede tener un personaje verificable aunque el primero cambie o no tenga selección.

Para contar un **game** en la matriz: dos entrants con un jugador distinto cada uno, un personaje conocido y no Random por lado y ganador que pertenece al set. Selecciones múltiples/ambiguas, desconocidas, Random y ganadores ausentes no se cuentan. Un game sigue contando aunque el set completo no pueda atribuirse a un solo personaje.

En un espejo A contra A, cada game da una victoria y una derrota a la escena (`scene: [n,n]`); **`sceneGames: n` cuenta games distintos**, no `2n`. La confianza usa `sceneGames`. Los récords propios/rival se mantienen en su perspectiva. No sacar un consejo direccional de una escena empatada.

### Recomendación y probabilidad

`own` = sets entre ustedes con el personaje elegido propio verificable, sin exigir que él siempre haya usado el mismo personaje. `scene` = games distintos del cruce entre ese personaje y su **primer detectado utilizable**. No constituye una tier list del juego. Si el récord propio no está empatado se usa su dirección; en otro caso se usa la escena. Si ambos empatan no hay consejo. Orden: confianza, muestra propia, escena e ID del slug; hasta dos.

Se aplica **en este orden**, sin sumar sets a games:

| Confianza | Condición |
|---|---|
| Alta | own ≥ 8, o own ≥ 4 y scene ≥ 200 |
| Media | own ≥ 4, o own ≥ 2 y scene ≥ 80 |
| Baja | own ≥ 2, o scene ≥ 150 |
| Ninguna | Todas las anteriores falsas |

El texto del README que permite «80 games» **sin sets propios** contradice su tabla. La implementación sigue la tabla: **150** en ese caso. Claude debe corregir ese aviso: «Para recomendar necesitamos al menos 2 sets tuyos con personaje o 150 games de la escena en el cruce». Sin personajes elegidos, no hay recomendaciones; la matriz usa hasta tres detectados propios. Sin detectados del rival, no hay matriz ni recomendaciones.

La constante correcta es **400**, no 800: `rank.py` publica `puntos = 1500 + 400 / ln(10) × fuerza` y el ajuste Bradley–Terry usa `sigmoid(fuerzaYo - fuerzaRival)`. Sustituyendo, `p = 1 / (1 + 10^((puntosRival - puntosYo)/400))`. A igual fuerza da 0.5; 400 puntos de ventaja dan odds 10:1, `p ≈ 0.90909`. Se reconoce solo `BT-PILOTO-3`. Es una aproximación desde puntos redondeados. El servidor no recorta a 10/90 ni calibra otra fórmula; esas etiquetas corresponden al diseño. No cambia el cálculo del ranking.

Cambiar vista modifica puestos, puntos, probabilidad, récord, historial, forma y tramos. **Elegidos, detectados, cobertura, récords por personaje, matriz y recomendaciones permanecen en el corte combinado**, según el diseño. La pantalla debe restablecer los chips del cruce a la primera opción al cambiar vista.

## Datos ausentes, alcance y errores

`placement` y `entrants` del rival por torneo se dejan siempre **null**. SQL tiene campos fuente como `events.registered_entrants` y `event_players.placement`, pero no constituyen ese contrato público e inmutable por jugador/corte ni equivalen a participantes activos. Para habilitarlos haría falta acordar su significado y guardar/verificar una instantánea por corte de la participación/puesto, sin confundir inscritos con activos. No se usa posición del ranking como puesto final de un torneo.

Para games se exige que identidad y `public_snapshot` de SQL coincidan con el `public.json` servido. Solo se leen eventos del corte combinado, sets competitivos y games con `synced_at <= characterCapturedAt`; un game corregido después no se introduce retroactivamente en un corte anterior. No hay instantáneas históricas de games: una corrección puede hacer que el corte viejo tenga **menos** games disponibles; la API no reconstruye su versión anterior ni afirma que sea una captura completa. `available` significa que hay filas disponibles, no cobertura total.

La «escena» son los **games registrados disponibles** de esos eventos, no todos los games disputados: la captura de mains es parcial y se hizo para los clasificados. No se consulta la API del proveedor para completarla al visitar la página. Con las tablas vacías: conserva el récord, historial, forma, tramos y cobertura real; objetos de récords por personaje vacíos, pares de matriz 0–0 y recomendaciones vacías. Con SQL aún sin ese corte: mismo fallback y `cut_not_synced`.

Errores: `{ok:false,reason}`. No contienen datos del análisis, SQL, credenciales ni IDs internos.

| HTTP | `reason` |
|---|---|
| 401 | `login_required` (sesión inexistente, vencida o conexión revocada) |
| 405 | `method_not_allowed`, `Allow: GET` |
| 400 | `invalid_parameters`, `invalid_scope`, `invalid_rival`, `invalid_search`, `search_too_short` |
| 404 | `rival_not_found` |
| 429 | `rate_limited`, `Retry-After: 60` |
| 503 | `analysis_unavailable` o `game_limit_exceeded` |

Límites: 30 peticiones de análisis/búsqueda por sesión en ventana móvil de 60 segundos; 20 resultados; 80 caracteres de búsqueda; 200 filas de historial. Consulta de escena limitada a **50,000 filas** del join (no games): se pide una extra para detectar exceso y se rechaza **toda** la respuesta, sin publicar conteos parciales. No es una cuota global por cuenta ni sustituto de controles del hosting. La sesión recordada recuperada empieza otra ventana de sesión. Mantener debounce/cancelación de búsqueda en la pantalla.

## Pruebas y medidas

- `php scripts/database/test_analisis.php`: 49 combinaciones de umbrales, probabilidad, frecuencia, acentos, perspectiva de games, espejo, Random/ambigüedad, personaje mezclado/parcial y abstención de consejos. No toca SQL.
- `python scripts/database/test_analisis_http.py`: 2 contratos estáticos (protección/publicación y marcador igual al modelo JS real) y **11 casos HTTP** en base local desechable. Anónima, gratis, premium, vencida/ambiente ajeno, otra cuenta, admin/revocación, sesión recordada, no vinculado, sin puesto/mains/elegidos/enfrentamientos, scope, huecos de games, corte desincronizado, racha, búsqueda/límites, consulta solo lectura y rechazo de escena sobredimensionada (25,001 games, 50,002 observaciones). El servidor de pruebas se ejecuta con `memory_limit=512M`.
- Local: PHP 8.5.3 / MariaDB 13.0.2. CI ejecuta estos contratos en **MySQL 8.0 y MariaDB 10.11** junto a las pruebas del repositorio; [run 37706831774](https://github.com/Bucaro-19/rankingsmashbros/actions/runs/37706831774) correcto en los tres jobs sobre `a030e9b`; comprobar también los checks de la revisión final de la PR antes de fusionar; la sintaxis se comprueba también en PHP 7.4/8.1. El límite y los resultados locales no prueban el rendimiento de BanaHosting.
- Medición aparte, sin red/proveedores: paquete privado original del 4/oct restaurado **solo en la base desechable**, más los games normalizados de la caché ya capturada para PR #36; 8,985 sets, 4,787 games y 9,530 selecciones. Cinco procesos PHP independientes con límite 512M; caso de los dos primeros clasificados y hasta tres personajes propios. Análisis: **47.46–51.55 ms**, pico **46,137,344 bytes (44 MiB)**, JSON **11,126 bytes**. Sugerencias vacías: **54.01–55.69 ms**, pico **16,793,600 bytes (~16.02 MiB)**, JSON **4,567 bytes**. Incluye construir/codificar la respuesta, no latencia HTTP, autenticación ni transporte de red. Medición final con el límite de 50,001 filas.
- `EXPLAIN` de esa consulta local: `ce.PRIMARY → s.idx_sets_event_status → g.uq_game_number → ss.uq_set_entrant → ep.PRIMARY → gs.PRIMARY`, accesos `ref`, sin barrido completo. **Sin índices ni migración nuevos**. Para repetir: instalar esquema y migraciones en una base `smash_schema_test_*` local, restaurar el paquete mediante el importador, insertar sus games en esa base únicamente y ejecutar `EXPLAIN` de `smash_analisis_games`; medir `hrtime`/`microtime` y `memory_get_peak_usage(true)` alrededor de `smash_analisis_response`. Las copias privadas de esa medición están en `/tmp`, no Git, y se eliminaron sus filas al terminar.

## Integración y pendientes

Claude Code puede conectar la pantalla consumiendo este contrato. Inicialmente pedir `buscar=`; por rival pedir `rival` y vista. Renderizar gratis con iniciales si falta retrato; no intentar deducir personajes desde otro endpoint para simular contenido premium. Para todos los campos opcionales usar null/listas vacías y `gameDataStatus`; no reutilizar ejemplos del prototipo. No prometer un porcentaje de detección porque no se envía `share`.

La biblioteca queda denegada en `.htaccess` y `deploy.py` la coloca después de sus dependencias y antes del endpoint. No cambia cálculo, elegibilidad, `public.json`, su esquema, ni cuentas/encuesta/panel/premium. **Nada fusionado ni desplegado por esta entrega.**

Pendientes del dueño: autorizar revisión/fusión/publicación de esta PR; PR #36 fue fusionada por el otro flujo en `656b7af` mientras se preparaba esta API; por separado, comprobar su publicación y ordenar la simulación/carga inicial de games del 4/oct si la desea. No se ejecutó carga inicial en producción ni se creó una migración. El primer corte nuevo del domingo 11/oct conserva el circuito normal. La pantalla y el pago de prueba siguen a cargo de Claude Code/dueño.

## «Prepara el set» (`deep`), 8/oct

Pantalla `preparar.html?rival={id}&scope={gt|intl}` (handoff `design_handoff_smash_gt_analisis_ampliado`). Usa la misma API; el campo `deep` solo existe con acceso completo, igual que el resto de campos de pago. Todo sale de sets y games del corte; nada se escribe a mano.

| Campo | Contenido |
| --- | --- |
| `rival` | `main` (primer personaje detectado utilizable o `null`), `mainShare` (parte de sus games con personaje registrado jugados con el main), `coveredSets` (sets suyos con el personaje del oponente registrado en algún game), `totalSets`. |
| `vsChars` | `hard` y `good`: hasta 5 `{slug, won, lost}` con sus games contra cada personaje. `hard` son récords negativos, peor primero; `good`, positivos. Los empates no aparecen. |
| `counters`, `avoid` | Hasta 5 cada una: `{slug, mine, mySets:[w,l]\|null, hisGames:[w,l], sceneGames:[w,l], confidence, guide}`. `mySets`: mis sets con ese personaje contra su main. `hisGames`: su main contra ese personaje, desde su lado. `sceneGames`: ese personaje contra su main en todos los games del corte, desde el lado del personaje. La dirección la decide la primera fuente que no esté empatada, en ese orden. `guide` es `null` hasta que exista una guía revisada. |
| `confidence` | `alta`: 4+ sets míos o 10+ games suyos. `media`: 2+ sets míos, 5+ games suyos o 20+ de la escena. `baja`: el resto. El diseño proponía 100–150 games de escena; en el corte real solo 7 cruces pasan de 30, así que ese umbral nunca se cumpliría. |
| `setPattern` | `null` sin sets con marcador. `setsScored` (sets con marcador legible), `setsWithScores` (los que además tienen todos sus games), `game1`, `decider` (sets que llegaron al último game), `close21`, `close32`, y `afterLoss` `{total, kept, switched:[{slug,n}]}` (games perdidos con personaje registrado en ese y en el siguiente). |
| `common`, `commonTotal` | Hasta 12 `{alias, me:[w,l], him:[w,l]}` en sets del corte combinado, sin identificadores. |
| `byTier` | `{top10, t11_30, rest}` en sets, según el puesto del oponente en la vista elegida; `null` sin sets contra clasificados. Los oponentes sin puesto no entran. |
| `toolkit`, `punishable` | `null`: los datos de frames esperan una fuente con permiso de uso. La pantalla muestra el estado «sin ficha». |

Pruebas: `scripts/database/test_analisis.php` (bloque «Prepara el set») y `test_analisis_http.py`.

