# Encargo para Codex — guardar en SQL los personajes de cada game

Fecha: 7 de octubre de 2026. Lo pidió el dueño para que el análisis premium de matchup (personaje contra personaje) tenga datos reales. Claude Code sigue con cobros y premium; **este encargo es solo de datos, sin pantallas.**

## Por qué

En producción `games` y `game_selections` tienen 0 filas. Solo existe el resumen por jugador (`player_characters`, 175 jugadores). Sin las selecciones por game no se puede calcular cómo le va a un personaje contra otro.

## Qué ya existe (no rehacer)

- **Tablas:** `games` y `game_selections` están en el esquema `001_accounts_competition`, con claves compuestas contra `sets` y `set_slots`. No hace falta migración salvo que se demuestre lo contrario; si la hay, va como archivo versionado en `docs/smash/migrations/` (hay 002 y 003) y la aplica un agente desde la Mac con orden del dueño.
- **Captura:** `scripts/smash/characters.py` ya pide a start.gg `games { id winnerId selections { entrant { id } character { id name } } }` por set admitido, con caché (`characters-cache.json`, restaurada en `smash-publish.yml`). Hoy ese detalle se reduce a `mains` y se descarta.
- **Transporte a SQL:** `scripts/database/ranking_package.py` arma el paquete; `import_ranking.py` (Python, respaldo desde la Mac) y `ranking-import.php` + `ranking-worker.php` (hosting, cron cada cinco minutos) lo importan con paridad probada. El paquete dice hoy, literalmente, «No individual games/selections imported».
- **Carga automática activa:** `SMASH_SQL_SYNC_ENABLED=true`. El domingo 11/oct a las 00:00 de Guatemala corre el primer corte nuevo.

## Qué hay que hacer

1. Llevar al paquete los games y las selecciones de los sets admitidos, con IDs reales de start.gg (game, set, entrant, character). Mismas reglas que `player_mains`: se omiten games sin ganador, selecciones ambiguas y duplicados por game/entrant/personaje; nada se infiere de alias.
2. Importarlos en ambos importadores, en la misma transacción del corte, con la paridad Python/PHP que ya se exige tabla por tabla. Repetir un paquete debe seguir dando `already_imported` sin duplicar.
3. Validar en el paquete, antes de publicar: que cada game pertenezca a un set del paquete, que el ganador y cada entrant sean slots de ese set, y que cada personaje exista en `characters` (incluido 1746, Random).
4. Decidir y documentar qué pasa cuando start.gg corrige un set ya guardado. `games` y `game_selections` son tablas de contexto, no instantáneas del corte: proponer reemplazo por set dentro de la transacción y dejarlo probado.
5. **Carga inicial de lo ya jugado:** el corte del 4/oct ya está importado y es inmutable. Proponer cómo cargar sus games sin tocar `cuts`, `rankings` ni las tablas de instantánea (por ejemplo, un paquete solo de contexto). No recapturar el corte ni cambiar su hash.
6. Medir tamaño y tiempo: cuántos games y selecciones por corte, cuánto crece el paquete (límite del transporte: 4 MiB comprimido, 32 MiB descomprimido) y la memoria del worker (límite 512M; el corte actual usa ~134 MiB).

## Límites

- No cambiar el cálculo, la elegibilidad, `public.json` ni su versión de esquema. Los mains publicados deben quedar idénticos.
- No aumentar las consultas a start.gg: los datos ya vienen en la captura semanal y su caché.
- No pantallas nuevas. No tocar cuentas, encuesta, contador ni panel.
- No imprimir ni versionar secretos; la base de producción solo se lee, y cualquier escritura fuera del circuito normal necesita la orden del dueño.
- Si el domingo 11 llega antes de terminar, no pasa nada: el corte se carga como hoy y los games se añaden después con la carga inicial.

## Entrega

Rama propia, pruebas en base desechable (MySQL 8.0 y MariaDB 10.11 en CI), PR, y actualizar `EN-CURSO.md`, `IMPORTACION-RANKING.md` y `CARGA-SEMANAL-SQL.md` con lo comprobado, lo medido y lo pendiente. Avisar si la primera carga real debe hacerse a mano.

## Para qué se usará después (no implementar ahora)

Claude Code leerá estas tablas para el análisis premium: récord de un personaje contra otro, por jugador y en general, siempre mostrando la muestra. Conviene que las consultas por `character_id` y por jugador sean baratas; proponer índices si hacen falta, sin crearlos por adelantado sin medir.
