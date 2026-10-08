# Top por organizador

Estado al 7 de octubre de 2026 (noche): **programado y probado en base desechable; todavía no funciona en producción.** Falta aplicar la migración 005 y que el catálogo de torneos llegue a SQL (encargo de Codex). Hasta entonces la pestaña no se muestra a nadie.

## Qué es

Un ranking aparte por organizador, calculado **solo con los sets de sus torneos**. No cambia el ranking nacional ni lo reemplaza. Es parte de premium. Pagar no da puntos ni cambia puestos, tampoco aquí.

Diseño: handoff local `design_handoff_smash_gt_top_organizador/` (pestaña «Mis torneos» y página pública).

## Decisiones del dueño (7/oct)

- Los puntos de cada top salen únicamente de los sets jugados en los torneos de ese organizador.
- start.gg solo dice quién **creó** el torneo. Por eso el organizador puede **agregar coorganizadores** (varios).
- No todos tendrán una muestra grande: el organizador elige **top 5, 10 o 15**, y el aviso de muestra pequeña se muestra con 1 o 2 torneos.
- Guardar en la base quién creó cada torneo.

## Decisiones técnicas tomadas al programar (revisables)

| Tema | Decisión | Por qué |
| --- | --- | --- |
| Qué torneos cuentan | Los del organizador que **también entran al ranking nacional** (presencial, singles, 20 jugadores activos o más) | Son los únicos con sets capturados. Incluir torneos más chicos exige ampliar la captura semanal. |
| Quién aparece | Jugadores con al menos **2 sets válidos** en esos torneos, de cualquier país | Mínimo bajo a propósito; es la constante `SMASH_ORG_MIN_SETS`. |
| Cálculo | Bradley–Terry regularizado como el nacional: prior 0.5, peso `min(2, √(activos/32))`, pareja repetida ÷ √repeticiones, escala 1500 + 400/ln 10 | Mismo criterio, sin tabla TTS. Se calcula al consultar, desde SQL. |
| Premium | El premium **del organizador** cubre a sus coorganizadores y a la página pública | Un solo pago por equipo. |
| Coorganizadores | Por **invitación de un solo uso** (vence en 7 días, crear otra anula la anterior). Máximo 10. Solo miran: no cambian el enlace ni el tamaño | No hay forma de buscar una cuenta por alias sin exponer cuentas. |
| Torneo de otra cuenta | «Pedir revisión» con el enlace; lo aprueba o rechaza el dueño del sitio a mano. Aprobado, cuenta para ese organizador | start.gg no expone administradores. |
| Dirección pública | `/top/{slug}`, estable, generada del nombre de la cuenta; apagada por defecto | El organizador decide si comparte. |

## Piezas

- `docs/smash/migrations/005_organizer_tops.sql`: `tournament_catalog`, `organizer_profiles`, `organizer_members`, `organizer_invites`, `organizer_claims`.
- `scripts/smash/discover.py`: `tournamentCatalog` en la captura (creador y ciudad de cada torneo). Consulta opcional: si falla, la captura sigue.
- `ranking-smash-ultimate/organizador.php` (biblioteca, bloqueada en `.htaccess`), `organizador-api.php`, `organizador.js`, `organizador.css`.
- `top.php` + `top.css`: página pública, sin sesión ni cookies, `noindex`. `.htaccess` reescribe `/top/{slug}`.
- `account-api.php` añade `organizerReady: true` solo cuando `tournament_catalog` tiene filas; `cuenta.js` muestra la pestaña «Mis torneos» únicamente entonces.

## API (`organizador-api.php`)

`GET` (opcional `?organizador={id}` y `?invita={código}`): `state` es `login`, `interest`, `premium`, `expired` o `data`. Orden de acceso: sesión → interés «Organizador» (no se exige a un coorganizador) → premium del organizador → datos. Nunca se envían cifras en un estado bloqueado. El `id` pedido solo se acepta si la cuenta es ese organizador o uno de sus coorganizadores.

Con `state: data`: `data` (`organizer`, `events`, `top`, `rest`, `summary`, `sizes`, `minRule`), `members` (solo el organizador), `publicUrl`, `contexts`, `role`. La cuenta con rol `admin` recibe además `pendingReviews`.

`POST` JSON con `X-CSRF-Token`: `settings` (`publicEnabled`, `topSize`), `invite`, `removeMember`, `review` (`url`), `join` (`token`), `leave`, y `resolve` (`claim`, `approve`, `message`; solo `admin`).

Motivos de «no cuenta»: `doubles`, `format`, `no_sets`, `out_of_season`, `small`, `unfinished`, `excluded`.

## Pruebas

- `php scripts/database/test_organizador.php`: cálculo, motivos, resumen, perfil y dirección, vista pública, invitaciones, revisiones.
- `python scripts/database/test_organizador_http.py`: accesos por rol, orden interés/premium, coorganizador, página pública y estados cerrados, revisiones, contratos de método y cuerpo.
- `scripts/smash/test_discover.py`: catálogo con creador, fallo de la consulta y torneo sin creador visible.
- Navegador con datos inventados (base desechable): pestaña a 375 px y escritorio, detalle de jugador, cambio de tamaño, interruptor público, invitación, revisión; página pública a 375 px. Sin desbordes ni errores de consola.

## Pendiente

1. **Codex:** llevar `tournamentCatalog` a SQL ([encargo](ENCARGO-CODEX-CATALOGO-ORGANIZADORES.md)).
2. **Dueño:** aplicar la migración 005 en producción cuando tenga acceso.
3. **Claude Design:** [adenda](BRIEF-CLAUDE-DESIGN-TOP15-ADENDA.md) para coorganizadores, selector 5/10/15, invitación recibida, revisiones del dueño y selector de organizador. Hoy usan los componentes existentes, sin diseño propio.
4. Marcar «Top por organizador» como disponible en la pestaña Premium (`premium.js`) cuando funcione en producción.
5. Decidir si los torneos de menos de 20 activos deben contar en estos tops.
