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
- **Una transacción por archivo.** Por cada línea busca su hash: si existe y los valores guardados coinciden, cuenta `alreadyPresent`; si existe y difieren, aborta con `hash_conflict` sin sobrescribir; si no existe, inserta. Verifica que el conteo de la tabla suba exactamente lo insertado. Cualquier fallo hace rollback y devuelve `database_write_failed` sin el texto de PDO. Como biblioteca, rechaza una transacción ya abierta con `transaction_already_active` sin revertir las escrituras del llamador.
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
- MariaDB 11.4.13 de producción: primera copia descrita al final. Suite nueva integrada y verificada por Codex en CI `37582761629`: MySQL **8.0.46** y MariaDB **10.11.19**, además de SQLite; todos los checks correctos en el commit de revisión `b7d842a`.

## Integración en CI (Codex)
Integrada en `smash-check.yml`, después de las pruebas de esquema, conexión e importador de ranking. Se instalan explícitamente `php-mysql`, `php-sqlite3` y `php-mbstring` y se ejecutan:
```sh
php -l scripts/database/import_survey.php
php -l scripts/database/test_import_survey.php
php scripts/database/test_import_survey.php
```
Debe ir **después** de `python scripts/database/test_schema.py` o en un orden que tolere que este test deja `survey_responses` vacía. `test_connection.php` exige `players` y `cuts` en cero, no la encuesta, así que no chocan.

## Observaciones para revisar juntos
1. **Dónde ejecutarlo en producción.** No hay SSH y `scripts/` no se despliega. Dos opciones: (a) el dueño lo corre en la Terminal web de cPanel tras subir `import_survey.php` a la carpeta privada, con `--site-root ~/rankingsmashbros.com`; lee el archivo real en el servidor y nada privado sale de ahí; (b) desde la Mac del dueño por la conexión MySQL remota, lo que obliga a bajar el archivo de respuestas a la Mac y a crear un segundo archivo de credenciales con la forma de `config.local.php`. Recomendada: (a).
2. **PHP 8.5** marca como obsoleta `PDO::MYSQL_ATTR_MULTI_STATEMENTS` en `database.php` (línea 69). No afecta a PHP 8.x anteriores; no se tocó por encargo. Si el hosting muestra avisos en CLI, saldrían por stderr antes del resumen.
3. **Comentarios vacíos** se guardan como `NULL`. Al cambiar la lectura de `opiniones.php` hay que tratar `NULL` como "sin comentario".
4. **`source_url`** admite 512 caracteres en la tabla; la encuesta limita a 250 bytes y el importador respeta ese límite.
5. El charset por defecto de la base es latin1 (ver `VERIFICACION-BASE-2026-10-07.md`); `survey_responses` es utf8mb4 y la prueba guarda y compara acentos, ñ y emoji.

## Protocolo de la migración real (primera copia ejecutada el 7 de octubre; ver pendientes al final)
1. **Respaldo:** copia del archivo dentro de la carpeta privada del servidor, con fecha; anotar su tamaño y `sha256sum`. No bajarlo a un repo ni exponerlo por URL.
2. **Validar:** `--file` solo. Debe dar `ok` y `fileRows` igual al número de líneas menos la guarda. Si rechaza una línea, no editar el archivo: revisar el motivo y decidir con el dueño.
3. **Simular:** con `--site-root`, sin `--apply`. Esperado en la primera vez: `inserted = fileRows`, `alreadyPresent = 0`.
4. **Aplicar** con `--apply` y **repetir** una vez: la repetición debe dar `inserted = 0`.
5. **Comparar:** `SELECT COUNT(*), SUM(is_test) FROM survey_responses` contra `fileRows` y `testRows`; el panel debe seguir mostrando el mismo total (hoy 12 visibles, que excluye el envío de prueba). Un agente en la Mac del dueño puede hacer esos SELECT por el acceso directo.
6. **Transición** (entrega posterior, no incluida): mientras `encuesta.php` siga escribiendo al archivo, repetir el paso 4 es seguro y trae las respuestas nuevas. Preparar una pausa controlada de envíos durante la importación final y el cambio de escritura a SQL/lectura del panel; un despliegue FTP de dos archivos no es atómico. Comparar de nuevo conteos y valores antes de reabrir los envíos, conservando validaciones, CSRF y el límite de 5 minutos. No activar doble escritura. Conservar el archivo original y su respaldo.

## Ejecutado en producción — 7 de octubre de 2026

Por decisión del dueño, que corrió los comandos en la Terminal web de cPanel con el importador del commit `4008a85` descargado a `~/private-smash/import_survey.php`. Salidas pegadas por el dueño (solo conteos):

1. Respaldo: `~/private-smash/respuestas-2026.respaldo-2026-10-07.php`. No se anotó tamaño ni sha256.
2. Validar: `ok`, `fileRows=13`, `testRows=1`.
3. Simular: `inserted=13`, `alreadyPresent=0`, `applied=false`, tabla 0 → 0.
4. Aplicar: `inserted=13`, `applied=true`, tabla 0 → 13. No se corrió la repetición.

Verificación directa de Claude Code desde la Mac del dueño, solo agregados y sin leer comentarios: 13 filas, 13 hashes distintos, 1 `is_test`, temporada 2026, fechas de 2026-09-29 14:47:21 a 2026-10-01 21:11:23 UTC, 4 sin comentario, 0 con enlace; sin la prueba: 8 jugadores, 2 organizadores, 2 espectadores (12, igual que el panel).

Estado: `survey_responses` es una copia; `encuesta.php` sigue escribiendo al archivo y `opiniones.php` leyendo de él. Las respuestas nuevas no llegan a la base hasta repetir el paso 4 (seguro, no duplica) o hasta la transición del paso 6. Quedan en el servidor, fuera del sitio público y fuera de Git, el respaldo y `import_survey.php`; conservarlos hasta la transición.

## Revisión de Codex — 7 de octubre de 2026

- Lectura directa de producción, solo agregados: **13 filas, 13 hashes distintos y 1 prueba interna**. No se descargaron respuestas ni se consultaron comentarios. Coincide con lo documentado por Claude; no sustituye la comparación campo por campo con el archivo.
- Corregido el caso de biblioteca con transacción previa: ya no revierte datos ajenos. Regresión comprobada con una escritura pendiente del llamador.
- Sintaxis PHP y suite local SQLite correctas. CI `37582761629` correcta: se comprobó en los logs la ejecución efectiva de la suite de encuesta en ambos motores, además de las pruebas de ranking/UI, esquema y conector.
- Pendientes de producción: registrar tamaño/hash del respaldo existente, repetir la importación con la versión revisada y verificar valores contra el archivo. No se ejecutó ningún importador en producción durante esta revisión.

---

# Entrega 2 — encuesta y panel leen y escriben en SQL (Claude Code, 7 de octubre de 2026)

Rama `feat/survey-sql-storage`. Encargo: `RELEVO-CLAUDE-CODE-2026-10-07.md`. Estado de ejecución y evidencia de producción: sección «Transición en producción» al final; hasta que esa sección diga lo contrario, producción sigue en la era del archivo.

## Qué cambia
- `ranking-smash-ultimate/survey.php` (nuevo, biblioteca denegada por `.htaccess`): conexión con modo estricto de sesión, fila a partir de una respuesta validada, escritura con contrato de reintento y lectura en la forma que el panel ya renderiza.
- `encuesta.php`: mismas validaciones, mensajes, honeypot, nonce, cookies y límite de cinco minutos. La escritura va a `survey_responses`; ya no abre el archivo. `display_errors=0`. Solo abre conexión después de pasar las tres barreras de validación. Texto de privacidad: «ingporras.com» → «rankingsmashbros.com» (corrección de dominio; avisada al dueño).
- `opiniones.php`: misma autenticación y plantilla. Lee de SQL únicamente con sesión administrativa válida. Un fallo de lectura muestra un aviso y **oculta** total, promedios, tarjetas y comentarios; nunca parece «0 respuestas». Sigue respondiendo 200.
- Ambas páginas llevan `<meta name="smash-survey-storage" content="sql">` para comprobar desde fuera qué versión quedó publicada.
- `scripts/database/import_survey.php`: modo `--compare [--no-extra]`, solo lectura, que informa conteos fila por fila.
- `deploy.py`: `survey.php` en la lista, después de `database.php` y antes de sus dos páginas. `.htaccess`: `survey.php` denegado.

## Contratos
- **Sin doble escritura ni respaldo silencioso.** Si SQL falla, el visitante ve «No pudimos guardar la respuesta. Intenta de nuevo más tarde.», no se marca la sesión, no rota el nonce (puede reintentar con el mismo formulario) y no se escribe en ningún otro lugar.
- **Reintentos sin duplicar y sin datos del visitante.** Cada formulario lleva el nonce de sesión (48 hex, rota solo tras guardar). La respuesta web se guarda con `import_hash = sha256("smashgt-encuesta-web-v1\n" + nonce)`, reutilizando la columna UNIQUE existente: no hay cambio de esquema. Si el INSERT choca con esa clave **y la fila existe**, se trata como ya guardada: se muestra el agradecimiento, se marca la sesión y rota el nonce. Consecuencias:
  - Respuesta del servidor perdida o PHP detenido tras el INSERT → el reintento no duplica.
  - Un formulario guarda como máximo una respuesta: la primera confirmada. Si el visitante cambió el texto antes de reintentar, queda la primera.
  - Doble clic o recarga tras el éxito → el nonce ya rotó: «Revisa las respuestas e intenta de nuevo.» (igual que antes).
  - Dos personas con respuestas idénticas → formularios distintos, dos filas.
  - Una violación de CHECK u otro error de integridad sin fila bajo esa clave **no** es éxito.
- **`import_hash` pasa a ser «huella de origen»:** sha256 de la línea para las filas importadas del archivo; sha256 con prefijo de dominio del nonce para las recibidas por la web. Ya no vale «`import_hash IS NULL` = respuesta web». Para separar unas de otras se usa `--compare` contra el archivo (`databaseRowsNotInFile`).
- **Valores guardados iguales a la era del archivo:** reloj de PHP en UTC con segundos (`.000000`), temporada 2026, límites en bytes (2000/250), bytes UTF-8 inválidos sustituidos por U+FFFD como hacía `json_encode`, texto vacío → `NULL`, `is_test=1` si el comentario empieza con `PRUEBA TÉCNICA INTERNA` (sensible a mayúsculas).
- **Lectura:** `season_year = 2026 AND is_test = 0`, orden `submitted_at DESC, id ASC`, instante con `+00:00` explícito (la plantilla lo muestra en hora de Guatemala), puntajes como enteros, `NULL` como texto vacío. Los agregados se siguen calculando en PHP.
- **Modo estricto por sesión:** el `sql_mode` global de producción no es estricto (verificado: `ERROR_FOR_DIVISION_BY_ZERO,NO_AUTO_CREATE_USER,NO_ENGINE_SUBSTITUTION`); la biblioteca añade `STRICT_TRANS_TABLES` a su sesión.

## Verificación antes de producción
- `php scripts/database/test_survey_storage.php`: contrato de la fila, clave de envío, reintentos, lectura, filtro de temporada, modo estricto y errores saneados; SQLite y motor real.
- `python scripts/database/test_survey_http.py`: sitio PHP aislado contra una base desechable. Envío real y lectura real, anonimato (columnas de la tabla), CSRF con nonce de otra sesión, honeypot, validaciones, límite de cinco minutos, tres fallos de base sin éxito falso y reintento del mismo formulario, confirmación perdida sin duplicar, prefijo de prueba, panel (totales, promedios, conteos, orden, hora de Guatemala, escape HTML), panel vacío distinto de panel sin base, y nada visible sin sesión administrativa.
- `scripts/smash/test_publish.py`: toda página PHP está en la lista de despliegue, cada biblioteca sube antes que quien la requiere y está denegada.
- CI: lint de PHP 7.4 (código publicable) y 8.1 (todo), más las suites anteriores en MySQL 8.0 y MariaDB 10.11.
- Comparaciones únicas hechas en local por Claude Code con datos inventados y MariaDB 13.0.2 desechable (no están en CI porque necesitan las páginas antiguas):
  - **Panel:** 60 respuestas con empates, multilínea, HTML y prefijos de prueba; el panel antiguo leyendo el archivo y el nuevo leyendo SQL produjeron HTML idéntico (55 tarjetas).
  - **Escritor:** 14 envíos variados (espacios, bytes inválidos, NUL, límites, enlaces) al formulario antiguo y al nuevo: mismos resultados (12 guardados, 2 rechazados con el mismo mensaje) y mismos valores guardados.

## Protocolo de transición
Mecanismo de pausa: **congelar el archivo** (`chmod 440`). La página antigua, todavía publicada, no puede abrirlo para escribir y responde con su mensaje existente de error de guardado sin marcar la sesión; no hace falta desplegar nada para pausar y la pausa cubre todo el intervalo hasta que la página nueva queda publicada. La página nueva nunca escribe en el archivo, así que queda como archivo histórico de solo lectura.

Actores: **D** = dueño en la Terminal web de cPanel; **C** = agente (GitHub y Mac del dueño).

0. **C** PR, checks y fusión a `main`. Fusionar no publica nada; el siguiente despliegue sí (incluido el del domingo), por eso los pasos 1–3 se hacen el mismo día.
1. **D** Estado previo, solo lectura: tamaño, líneas y sha256 del archivo del sitio nuevo, del archivo del dominio anterior y del respaldo del 7 de octubre.
2. **D** Congelar el archivo, respaldo fechado con `cp -p`, tamaño y sha256 de ambos, descargar el importador del commit fusionado, validar, aplicar, repetir y `--compare --no-extra`. Esperado: `fileFullyStored=true`, `databaseRowsNotInFile=0`, segunda aplicación con `inserted=0`.
3. **C** Verificar agregados en SQL desde la Mac. Desplegar `main` con `smash-deploy-snapshot.yml`, `assets_only=true`. Comprobar por HTTP: marcador `sql` en `encuesta.php` y `opiniones.php`, 403 en `survey.php` y `database.php`, 401 del diagnóstico anónimo, `public.json` sin cambios.
4. **D** Entrar al panel y confirmar el mismo total y las mismas respuestas. Repetir sha256 del archivo y del respaldo: deben seguir iguales (prueba de que nada se escribió tras congelar).
5. Envío real de prueba, solo si el dueño lo aprueba: comentario que empiece con `PRUEBA TÉCNICA INTERNA`; queda con `is_test=1` y no cuenta en el panel. **C** lo verifica con agregados.

Si el archivo del dominio anterior tiene líneas que el del sitio nuevo no tiene: congelarlo también e importarlo con el mismo importador (solo añade las líneas nuevas) antes del paso 3.

## Recuperación
- **Fallo en el paso 2 (aún no hay página nueva):** devolver los permisos originales al archivo (los muestra el paso 1). La era del archivo continúa intacta; las filas ya copiadas a SQL son una copia inofensiva.
- **Despliegue interrumpido en el paso 3:** repetirlo. Los marcadores `<meta>` dicen qué página quedó en cada versión. Con `encuesta.php` nueva y `opiniones.php` antigua no se pierde nada: las respuestas entran a SQL y el panel antiguo muestra el archivo congelado hasta completar el despliegue.
- **Después de que SQL aceptó respuestas:** no volver a las páginas del archivo ni revertir este PR en `main` (el despliegue semanal las republicaría y las respuestas SQL desaparecerían del panel). Se corrige hacia adelante. Si la base falla, la encuesta informa el error sin aceptar y el panel muestra el aviso de lectura.
- El archivo congelado y sus respaldos se conservan. El importador se puede repetir en cualquier momento: no duplica.

## Pendiente fuera de esta entrega
- La encuesta del dominio anterior (`ingporras.com/ranking-smash-ultimate/encuesta.php`) sigue viva y escribe en **su** archivo. Hasta redirigirla al dominio nuevo, cualquier respuesta enviada allí queda fuera de SQL. Opciones: congelar también ese archivo o adelantar la redirección de `encuesta.php` y `opiniones.php` (cambio en el repo anterior, requiere visto bueno del dueño).
