# Top por organizador

Estado al 9 de octubre de 2026: módulo construido; auditoría y mejoras en la rama `feat/organizer-readiness`, pendiente de revisión y orden de fusión/despliegue. **Según confirmación del dueño**, la migración 005 ya está aplicada y el catálogo se llenará en el primer corte automático. En esta auditoría no se consultó ni escribió producción. La pestaña y la disponibilidad en Premium dependen de que el catálogo tenga filas.

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
| Qué torneos cuentan | Los del organizador que **también entran al ranking nacional** (presencial, singles, 20 jugadores activos o más) | Los pequeños capturados como contexto siguen fuera: tener sets en SQL no significa estar admitido en el corte nacional. |
| Quién aparece | Jugadores con al menos **2 sets válidos** en esos torneos, de cualquier país | Mínimo bajo a propósito; es la constante `SMASH_ORG_MIN_SETS`. |
| Cálculo | Bradley–Terry regularizado como el nacional: prior 0.5, peso `min(2, √(activos/32))`, pareja repetida ÷ √repeticiones, escala 1500 + 400/ln 10 | Mismo criterio, sin tabla TTS. Se calcula al consultar, desde SQL. |
| Premium | **Cada cuenta paga el suyo** (decisión del dueño, 7/oct): el coorganizador necesita su propio premium para ver la pestaña; la página pública depende del premium del organizador | Unirse como coorganizador es gratis y su nombre aparece («Coorganizan: …») en la pestaña y en la página pública aunque no pague. |
| Coorganizadores | Por **invitación de un solo uso** (vence en 7 días, crear otra anula la anterior). Máximo 10. Solo miran (con su premium): no cambian el enlace ni el tamaño | No hay forma de buscar una cuenta por alias sin exponer cuentas. |
| Torneo de otra cuenta | «Pedir revisión» con el enlace; lo aprueba o rechaza el dueño desde «Mis torneos». Acredita la organización; solo cuenta si está admitido en el corte nacional | start.gg no expone administradores. |
| Dirección pública | `/top/{slug}`, estable, generada del nombre de la cuenta; apagada por defecto | El organizador decide si comparte. |

## Piezas

- `docs/smash/migrations/005_organizer_tops.sql`: `tournament_catalog`, `organizer_profiles`, `organizer_members`, `organizer_invites`, `organizer_claims`.
- `scripts/smash/discover.py`: `tournamentCatalog` en la captura (creador y ciudad de cada torneo). Consulta opcional: si falla, la captura sigue.
- `ranking-smash-ultimate/organizador.php` (biblioteca, bloqueada en `.htaccess`), `organizador-api.php`, `organizador.js`, `organizador.css`.
- `top.php` + `top.css`: página pública, sin sesión ni cookies, `noindex`. `.htaccess` reescribe `/top/{slug}`.
- `account-api.php` añade `organizerReady: true` solo cuando `tournament_catalog` tiene filas; `cuenta.js` muestra la pestaña «Mis torneos» únicamente entonces.

## API (`organizador-api.php`)

`GET` (opcional `?organizador={id}` y `?invita={código}`): `state` es `login`, `interest`, `premium`, `expired` o `data`. Orden de acceso: sesión → interés «Organizador» (no se exige a un coorganizador) → premium de la cuenta que mira → datos. En `premium` y `expired` solo se envía el adelanto gratis descrito abajo, además de los metadatos de acceso. Nunca se envían datos de pago, ni para difuminarlos. El `id` pedido solo se acepta si la cuenta es ese organizador o uno de sus coorganizadores; un contexto ajeno o mal formado responde 403, sin sustituirlo por el propio.

Con `state: data`: `data` (`organizer`, `coorganizers`, `events`, `top`, `rest`, `summary`, `sizes`, `minRule`), `members` (solo el organizador), `publicUrl`, `contexts`, `role`. La cuenta con rol `admin` recibe además `pendingReviews`.

`POST` JSON con `X-CSRF-Token`: `settings` (`publicEnabled`, `topSize`), `invite`, `removeMember`, `review` (`url`), `join` (`token`), `leave`, y `resolve` (`claim`, `approve`, `message`; solo `admin`).

Motivos de «no cuenta»: `doubles`, `format`, `no_sets`, `out_of_season`, `small`, `unfinished`, `excluded`.

## Pruebas

- `php scripts/database/test_organizador.php`: cálculo, motivos, resumen, perfil y dirección, vista pública, invitaciones, revisiones.
- `python scripts/database/test_organizador_http.py`: accesos por rol, orden interés/premium, coorganizador, página pública y estados cerrados, revisiones, contratos de método y cuerpo.
- `scripts/smash/test_discover.py`: catálogo con creador, fallo de la consulta y torneo sin creador visible.
- Navegador con datos inventados (base desechable): pestaña a 375 px y escritorio, detalle de jugador, cambio de tamaño, interruptor público, invitación, revisión; página pública a 375 px. Sin desbordes ni errores de consola.

## Adelanto gratis: contrato para Claude Code

Solo cuentas con sesión e interés Organizador, coorganizadores invitados y admin. `state: premium` o `expired` añade:

```json
{
  "teaser": {
    "headline": {
      "kind": "latest_counted_tournament",
      "name": "Torneo inventado",
      "date": "2026-09-27",
      "url": "https://www.start.gg/tournament/torneo-inventado/event/singles"
    },
    "locked": {
      "tournaments": 5,
      "countedTournaments": 2,
      "rankedPlayers": 3,
      "validSets": 7
    }
  }
}
```

Ejemplo inventado de forma, no datos productivos. `headline: null` significa que no hay un torneo admitido que mostrar; conteos cero son reales, no relleno. `teaser: null` indica fallo de lectura, con mensaje explícito en pantalla. `tournaments` cuenta las filas de la lista de torneos/revisiones del contexto; `countedTournaments` cuenta torneos distintos admitidos. `rankedPlayers` cuenta quienes alcanzan la regla vigente de 2 sets; no ajusta el modelo ni expone sus identidades. `validSets` cuenta los resultados admitidos del corte. Un dato principal (torneo más reciente) y tarjetas con conteos: no se envían `data`, `members`, `publicUrl`, filas, puntos, puestos, récords, personajes, rivales ni resultados de revisiones. `contexts` mantiene únicamente la información necesaria del equipo al que pertenece la cuenta.

El adelanto no reserva slug ni modifica tablas. No consulta start.gg, no lee games/personajes ni calcula un top de pago. Usa el mismo corte que el top completo. La cuenta gratis puede unirse y salir; su nombre aparece como coorganizador aunque no pague. El premium del dueño del top no desbloquea la cuenta del invitado.

`premium.js` recibe `organizerReady` de `account-api.php` por `SmashPremium.setContext`. «Top por organizador» aparece disponible con enlace a `cuenta.html#torneos` solo cuando ese indicador es estrictamente `true`; al faltar catálogo o migración sigue «Próximamente». No se infiere la disponibilidad del premium ni de ejemplos locales.

## Resolver «Pedir revisión» sin SQL manual

Ya existían API y controles; se completaron sus casos de error, no se añadió pantalla.

1. Entrar con la cuenta con rol `admin` a **Mi cuenta → Mis torneos** (requiere catálogo disponible para mostrar la pestaña).
2. Al final aparece «Revisiones por resolver»: organizador, quién envió, enlace, fecha y si el torneo llegó al catálogo. El admin no necesita pagar premium.
3. Comprobar por medios propios quién organizó el torneo. «Aprobar» pide confirmación y exige que exista en el catálogo; si aún no llegó, esperar el corte. Una petición enviada antes de la captura ahora se habilita al llegar el torneo, sin SQL manual.
4. «Rechazar» exige motivo no vacío de hasta 255 caracteres. El solicitante lo ve y puede reenviar la misma petición; se conserva el límite de 10 pendientes, también al reabrir.
5. El servidor guarda decisión, admin y fecha. Resolver dos veces devuelve `invalid_review`, sin sobrescribir. Un no-admin recibe 403. Aprobar **no** hace contar pequeños, dobles, online o eventos fuera del corte.

## Auditoría del 9/oct: fallos corregidos y evidencia

- El top tomaba resultados vivos de `sets`: una corrección posterior podía alterar el top etiquetado con un corte antiguo. Ahora resultados y pertenencia salen de `cut_set_results`/`cut_events`, ámbito combinado y 20+ activos. Fórmula y reglas vigentes intactas. Prueba: corregir un set vivo y añadir otro no admitido deja toda la respuesta idéntica; agregar contexto 006 tampoco lo altera.
- Configuración mixta inválida podía activar el enlace antes de rechazar el tamaño. Se valida todo primero y se actualiza en una sola operación; un rechazo no reserva slug ni cambia campos.
- Crear invitaciones simultáneas podía dejar dos códigos vigentes. Crear y consumir se serializa con bloqueo de la fila del organizador; dos consumidores solo producen un miembro. Miembro existente/cupo lleno no consume la invitación; no se confirma ni revierte una transacción ajena.
- Cuenta gratis coorganizadora carecía de «Salir del equipo»; se añade con el componente existente y su nombre correcto.
- Revisiones previas al catálogo seguían deshabilitadas y reabrir una rechazada esquivaba el límite. Catálogo resuelto por slug y límite aplicado al reabrir. La lista del dueño identifica también al remitente.
- Copiar sin API del portapapeles causaba error; ahora da instrucciones de copia manual. Top público usa `Cache-Control: no-store, private` para no retener un top apagado/vencido.

Pruebas locales: MariaDB 13.0.2 desechable y PHP 8.5.3; contratos PHP de organizador y **13 HTTP**, incluyendo concurrencia real con procesos PHP, campo de 21 jugadores, tamaños 5/10/15 con mismos puntos/orden, enlaces apagados/vencidos, revisión aprobada/rechazada, acceso por cuenta y exclusión de pequeños. **6 pruebas Node** nuevas de presentación/adelanto/disponibilidad/portapapeles. Regresión: cuentas (9 HTTP), premium (2 HTTP, proveedor simulado), 90 pruebas Python del pipeline y 42 Node existentes correctas. CI requerida: MySQL 8.0 y MariaDB 10.11 (ver EN-CURSO para enlace final).

Navegador local con cuentas y torneos inventados: escritorio 1280 px y móvil 375 px, adelanto libre/vencido, contexto de coorganizador y nombre, invitación aceptada, detalle del jugador, selector, enlace público y pausa, solicitud/rechazo administrativo, vacío premium y disponibilidad en Premium. Sin desbordes de documento. El servidor PHP local usa un router de pruebas equivalente a `/top/{slug}`; no se probó Apache productivo. El diálogo nativo de confirmación de salida no se pudo confirmar con el navegador integrado; la salida y aprobación se verificaron con contratos HTTP y pruebas JS/servidor, sin cambiar los diálogos. Sin pagos ni OAuth reales.

## Pendiente

1. Revisar este PR y autorizar fusión/despliegue. No exige migraciones nuevas.
2. **Dueño/Claude Code:** después del corte automático comprobar catálogo y visibilidad con una sesión real; esta auditoría no demuestra datos ni pagos reales en producción.
3. **Claude Design:** [adenda](BRIEF-CLAUDE-DESIGN-TOP15-ADENDA.md) y adelanto gratis; controles existentes reutilizados, pendientes de diseño final. Detalle en PENDIENTES-DUENO.
4. Los pequeños **siguen fuera** de este top. La captura de contexto sirve al historial y no cambia ninguna regla.
