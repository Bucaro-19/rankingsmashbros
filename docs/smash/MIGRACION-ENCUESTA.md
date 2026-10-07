# Migración de la encuesta a `survey_responses` — entrega 1 (Claude Code, 7 de octubre de 2026)

Encargo: `TRABAJO-PARALELO-2026-10-07.md` (Codex). Rama `feat/survey-import`. La entrega era solo código y pruebas. **Actualización del mismo día: el dueño decidió copiar ya las respuestas y ejecutó el importador en producción; ver «Ejecutado en producción» al final.** La encuesta y el panel siguen leyendo y escribiendo su archivo.

## Qué se entrega
- `scripts/database/import_survey.php`: biblioteca y CLI.
- `scripts/database/test_import_survey.php`: pruebas con datos inventados.
- Este documento. No se tocó ningún otro archivo.

## Reglas del importador
- **Fuente:** `feedback-data/respuestas-2026.php`. La línea 1 debe ser exactamente la guarda `<?php http_response_code(404); exit; ?>`; cada línea siguiente es un objeto JSON compacto. Se lee completo bajo `flock(LOCK_SH)`, igual que `opiniones.php`. Límite 5 MB por archivo y 32 KB por línea; no sigue enlaces simbólicos.
- **Hash:** `import_hash = sha256` de los bytes exactos de la línea, **sin** su `\n` final. No se normaliza ni se reserializa el JSON.
- **Validación estricta, igual a lo que `encuesta.php` ha escrito en todas sus versiones** (el formato no cambió desde el PR #7 del repo viejo): las 10 claves en su orden (`submittedAt`, `seasonYear`, `role`, `eligibility`, `minimum`, `international`, `clarity`, `confidence`, `source`, `comment`), sin claves extra; `submittedAt` con forma `AAAA-MM-DDTHH:MM:SS+00:00` y fecha real; `seasonYear` entero 2026–2100; las cuatro opciones dentro de sus listas; `clarity`/`confidence` enteros 1–5; `source` vacío o `https://start.gg/...` de hasta 250 bytes; `comment` texto de hasta 2000 bytes.
- **Conversión:** `submittedAt` → `submitted_at` UTC con `.000000`; `minimum` → `minimum_activity`; `source` y `comment` vacíos → `NULL`; `is_test = 1` si el comentario empieza con `PRUEBA TÉCNICA INTERNA` (misma regla con la que el panel lo oculta).
- **Archivo inválido = nada se importa.** Línea vacía, con espacios o `\r`, JSON roto, UTF-8 inválido, campo fuera de regla, línea repetida o última línea sin salto (escritura truncada) rechazan el archivo entero antes de abrir la transacción. El error es `Línea N: motivo` (JSON `{"ok":false,"reason":...,"line":N}` en el CLI); nunca incluye comentarios, enlaces ni credenciales.
- **Una transacción por archivo.** Por cada línea busca su hash: si existe y los valores guardados coinciden, cuenta `alreadyPresent`; si existe y difieren, aborta con `hash_conflict` sin sobrescribir; si no existe, inserta. Verifica que el conteo de la tabla suba exactamente lo insertado. Cualquier fallo hace rollback y devuelve `database_write_failed` sin el texto de PDO.
- **Repetible:** una segunda corrida inserta 0. Si el archivo creció, inserta solo las líneas nuevas.

## Uso
```sh
php scripts/database/import_survey.php --file RUTA                          # solo valida el archivo
php scripts/database/import_survey.php --file RUTA --site-root SITIO        # simulación: conecta, calcula y hace rollback
php scripts/database/import_survey.php --file RUTA --site-root SITIO --apply # escribe
```
`--site-root` es la carpeta que contiene `database.php`; las credenciales salen de `../private-smash/config.local.php` por el conector existente, sin cambios. Sin `--apply` nunca queda nada escrito. Salida: resumen JSON de conteos (`fileRows`, `inserted`, `alreadyPresent`, `testRows`, `tableRowsBefore/After`). Códigos: 0 correcto, 1 rechazo, 2 uso incorrecto.

## Qué se verificó y cómo
- `php scripts/database/test_import_survey.php` sin variables: análisis, 38 casos de rechazo, privacidad de errores y la secuencia completa de importación sobre SQLite en memoria (sustituto del motor, mismo SQL).
- Con `SMASH_SCHEMA_TEST_DB=smash_schema_test SMASH_SCHEMA_TEST_PORT=33306 SMASH_SCHEMA_TEST_PASSWORD=...` repite la secuencia sobre el esquema real instalado con `install.sql`: simulación sin escritura, primera importación, valores guardados iguales al archivo, repetición sin cambios, línea añadida, archivo inválido, fallo a mitad de transacción con rollback y conflicto de hash no sobrescrito. Borra `survey_responses` antes y después, y se niega a correr si la base no se llama `smash_schema_test*`.
- Ejecutado por Claude Code en una MariaDB local desechable **13.0.2** (Homebrew) con `install.sql` (31 tablas, 87 personajes): pasó. También el CLI de punta a punta: validar, simular, aplicar, repetir, archivo dañado y uso incorrecto.
- MariaDB 11.4.13 de producción: verificado con la ejecución real descrita al final. **No verificado:** las pruebas nuevas en MariaDB 10.11 y MySQL 8.0 de CI (el workflow no se tocó, por encargo).

## Para integrar en CI (Codex)
En el paso que ya corre `php scripts/database/test_connection.php`, añadir:
```sh
php -l scripts/database/import_survey.php
php scripts/database/test_import_survey.php
```
Debe ir **después** de `python scripts/database/test_schema.py` o en un orden que tolere que este test deja `survey_responses` vacía. `test_connection.php` exige `players` y `cuts` en cero, no la encuesta, así que no chocan.

## Observaciones para revisar juntos
1. **Dónde ejecutarlo en producción.** No hay SSH y `scripts/` no se despliega. Dos opciones: (a) el dueño lo corre en la Terminal web de cPanel tras subir `import_survey.php` a la carpeta privada, con `--site-root ~/rankingsmashbros.com`; lee el archivo real en el servidor y nada privado sale de ahí; (b) desde la Mac del dueño por la conexión MySQL remota, lo que obliga a bajar el archivo de respuestas a la Mac y a crear un segundo archivo de credenciales con la forma de `config.local.php`. Recomendada: (a).
2. **PHP 8.5** marca como obsoleta `PDO::MYSQL_ATTR_MULTI_STATEMENTS` en `database.php` (línea 69). No afecta a PHP 8.x anteriores; no se tocó por encargo. Si el hosting muestra avisos en CLI, saldrían por stderr antes del resumen.
3. **Comentarios vacíos** se guardan como `NULL`. Al cambiar la lectura de `opiniones.php` hay que tratar `NULL` como "sin comentario".
4. **`source_url`** admite 512 caracteres en la tabla; la encuesta limita a 250 bytes y el importador respeta ese límite.
5. El charset por defecto de la base es latin1 (ver `VERIFICACION-BASE-2026-10-07.md`); `survey_responses` es utf8mb4 y la prueba guarda y compara acentos, ñ y emoji.

## Protocolo de la migración real (pasos 1–5 ejecutados el 7 de octubre; el 6 sigue pendiente)
1. **Respaldo:** copia del archivo dentro de la carpeta privada del servidor, con fecha; anotar su tamaño y `sha256sum`. No bajarlo a un repo ni exponerlo por URL.
2. **Validar:** `--file` solo. Debe dar `ok` y `fileRows` igual al número de líneas menos la guarda. Si rechaza una línea, no editar el archivo: revisar el motivo y decidir con el dueño.
3. **Simular:** con `--site-root`, sin `--apply`. Esperado en la primera vez: `inserted = fileRows`, `alreadyPresent = 0`.
4. **Aplicar** con `--apply` y **repetir** una vez: la repetición debe dar `inserted = 0`.
5. **Comparar:** `SELECT COUNT(*), SUM(is_test) FROM survey_responses` contra `fileRows` y `testRows`; el panel debe seguir mostrando el mismo total (hoy 12 visibles, que excluye el envío de prueba). Un agente en la Mac del dueño puede hacer esos SELECT por el acceso directo.
6. **Transición** (entrega posterior, no incluida): mientras `encuesta.php` siga escribiendo al archivo, repetir el paso 4 es seguro y trae las respuestas nuevas. Cambiar la escritura a SQL y la lectura del panel en un mismo despliegue, justo después de una última importación, conservando validaciones, CSRF y el límite de 5 minutos. No activar doble escritura. Conservar el archivo original y su respaldo.

## Ejecutado en producción — 7 de octubre de 2026

Por decisión del dueño, que corrió los comandos en la Terminal web de cPanel con el importador del commit `4008a85` descargado a `~/private-smash/import_survey.php`. Salidas pegadas por el dueño (solo conteos):

1. Respaldo: `~/private-smash/respuestas-2026.respaldo-2026-10-07.php`. No se anotó tamaño ni sha256.
2. Validar: `ok`, `fileRows=13`, `testRows=1`.
3. Simular: `inserted=13`, `alreadyPresent=0`, `applied=false`, tabla 0 → 0.
4. Aplicar: `inserted=13`, `applied=true`, tabla 0 → 13. No se corrió la repetición.

Verificación directa de Claude Code desde la Mac del dueño, solo agregados y sin leer comentarios: 13 filas, 13 hashes distintos, 1 `is_test`, temporada 2026, fechas de 2026-09-29 14:47:21 a 2026-10-01 21:11:23 UTC, 4 sin comentario, 0 con enlace; sin la prueba: 8 jugadores, 2 organizadores, 2 espectadores (12, igual que el panel).

Estado: `survey_responses` es una copia; `encuesta.php` sigue escribiendo al archivo y `opiniones.php` leyendo de él. Las respuestas nuevas no llegan a la base hasta repetir el paso 4 (seguro, no duplica) o hasta la transición del paso 6. Quedan en el servidor, fuera del sitio público y fuera de Git, el respaldo y `import_survey.php`; conservarlos hasta la transición.
