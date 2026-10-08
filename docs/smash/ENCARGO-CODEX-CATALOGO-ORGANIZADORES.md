# Encargo para Codex — llevar el catálogo de torneos (con su creador) a SQL

Fecha: 7 de octubre de 2026, noche. Una sola tarea. Claude Code está con el top por organizador: `organizador.php`, `organizador-api.php`, la pestaña «Mis torneos» de `cuenta.*` y la página pública. No toques esos archivos.

## Contexto

- El dueño aprobó el top por organizador: un ranking aparte calculado solo con los sets de los torneos de cada organizador. start.gg expone quién creó cada torneo (`Tournament.owner`), comprobado con una consulta real.
- **Ya está en main (#48):** `scripts/smash/discover.py` añade a la captura nacional la llave `tournamentCatalog`. Es una lista con todos los torneos de Ultimate del catálogo de Guatemala, también los que el ranking excluye:
  `{id, name, slug, startAt, city, ownerId, events: [{id, name, type, numEntrants, startAt, reason}]}`. `reason` es el motivo de exclusión de la captura (`not_singles`, `online_or_unknown`, `unfinished_event`, `under_20_entrants`, `outside_window`) o `null` si el evento se capturó. `ownerId` y `city` pueden ser `null`.
- La consulta de dueños es opcional: si start.gg la rechaza, **`tournamentCatalog` llega en `null`** y la captura sigue igual. `combine.py` conserva la llave tal cual.
- **Ya está en main:** la migración `docs/smash/migrations/005_organizer_tops.sql` con la tabla `tournament_catalog` (una fila por torneo y evento; llave `(tournament_id, event_id)`; sin llaves foráneas a `tournaments`/`events`, porque esas tablas solo tienen lo capturado). **Todavía no está aplicada en producción**: el dueño no tiene acceso a cPanel ni a su red estos días.

## Tarea

Que la carga semanal deje `tournament_catalog` al día en SQL, por el mismo circuito que ya construiste (paquete → receptor → cola → importador PHP), sin poner en riesgo la primera carga automática del domingo 11/oct.

- Reemplazo completo del catálogo en cada corte (es una foto de la temporada, no un historial): lo que ya no esté en la captura se borra, dentro de la misma transacción del importador.
- Columnas: `tournament_id`, `event_id`, `owner_startgg_user_id`, `tournament_name`, `slug`, `starts_at` (inicio del torneo, UTC), `city`, `event_name`, `entrants`, `reason`, `captured_at`. Valida identificadores y longitudes como el resto del paquete; un `slug` que no sea `tournament/...` va en `NULL`.
- **Tolerante en tres frentes**, y con prueba de cada uno:
  1. captura con `tournamentCatalog: null` o sin la llave → el paquete no toca la tabla (no la vacía);
  2. base **sin** la migración 005 → el importador carga el corte normal y omite el catálogo, sin fallar ni dejar el trabajo en error;
  3. paquetes anteriores (versiones 1 y 2) siguen importándose y reproduciendo sus hashes.
- Decide tú si es `packageVersion` 3 o una sección aparte; lo que importa es que el hash y la idempotencia del corte (`already_imported`) sigan valiendo y que reenviar el mismo paquete no duplique nada.
- Paridad entre el importador Python y el PHP, como hoy.
- El identificador del creador es dato público de start.gg, pero trátalo como el resto del paquete privado: nada de imprimirlo en registros de Actions.

## Fuera de alcance

- No cambies `discover.py`, el cálculo, la elegibilidad ni `public.json`.
- No captures eventos de menos de 20 inscritos: el top del organizador usa, por ahora, los mismos torneos que entran al ranking nacional.
- No apliques la migración ni escribas en producción. Deja el comando exacto para cuando el dueño tenga acceso.

## Entrega

Una PR en rama propia desde `main`, pruebas en base desechable (MySQL 8.0 y MariaDB 10.11 en CI), `CARGA-SEMANAL-SQL.md`/`IMPORTACION-RANKING.md` y `EN-CURSO.md` actualizados. Di en la PR si es seguro fusionarla y desplegarla **antes** del domingo con la migración sin aplicar. No fusiones ni despliegues sin la orden del dueño.
