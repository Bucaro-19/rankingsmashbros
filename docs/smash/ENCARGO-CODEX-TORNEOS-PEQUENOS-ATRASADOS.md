# Encargo para Codex: carga única de los torneos pequeños atrasados

**Decisión del dueño (9/oct/2026):** los torneos pequeños **no cuentan** para el ranking ni cambian ninguna regla. Solo se guardan para explicarle a cada jugador, en su historial, que jugó un torneo que no contó y por qué. La migración 006 está aplicada en producción y `SMASH_ORGANIZER_SMALL_ENABLED=true`.

## El problema

`organizer_small.py` toma siempre los eventos pequeños **más recientes** (`--limit 6` en la carga semanal; el presupuesto de 30 intentos no alcanza para 10). Este año hay unos 19 candidatos: los más viejos nunca entrarían, y un jugador de The Oven 7 (23/ago, 13 jugadores) seguiría sin explicación.

## Qué se pide

1. Una herramienta de **carga única** («backfill») que capture el contexto de los eventos pequeños que todavía no tienen marca en `organizer_event_context`, por tandas que respeten los techos actuales (eventos, intentos y tiempo) y sin tocar el grafo nacional, `cut_events`, `rankings`, `cuts` ni `public.json`.
2. Que se pueda repetir sin duplicar: una tanda ya cargada no se vuelve a escribir.
3. Que la selección semanal prefiera, después de los recientes, los eventos sin marca, o documentar por qué no conviene.
4. Simulación primero (sin escribir) con el conteo de eventos, consultas y tiempo; la escritura en producción la ordena el dueño.
5. Pruebas con datos inventados y CI en MySQL 8.0 y MariaDB 10.11.

## Contrato que ya usa el sitio (no romper)

`smash_account_small_events()` en `accounts.php` lee `organizer_event_context` unido a `events`, `tournaments`, `entrants`, `entrant_players`, `sets` y `set_slots`: fecha del evento, `active_players` de la marca y sets `competitive` con `winner_entrant_id`. Excluye cualquier evento presente en `cut_events`.

## Límites

No aplicar migraciones ni escribir en producción sin orden del dueño. No fusionar ni desplegar: abrir PR y anotar la entrega en `EN-CURSO.md`. Sin datos reales en pruebas ni en documentos.
