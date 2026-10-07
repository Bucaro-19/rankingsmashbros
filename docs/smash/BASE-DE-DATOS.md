# Base de datos — propuesta del 6 de octubre de 2026

El dueño quiere cuentas, consulta de torneos y que mains y puestos queden guardados en MySQL (BanaHosting, phpMyAdmin) en vez de recalcularse o leerse solo del JSON. El esquema está en `schema.sql`. El dueño dijo que crearía las tablas a mano en phpMyAdmin; **confirmar con él si ya existen y con qué nombre de base antes de asumir nada.**

## Tablas
- `players`, `events`, `sets`: jugadores, torneos jugados admitidos y sets válidos. Los id son los de start.gg.
- `cuts`: cada corte semanal publicado. `rankings`: puesto, puntos y récord por corte, vista (`combined`/`guatemala`) y jugador; es el historial de rank.
- `characters`: catálogo (mismos id que `ranking-smash-ultimate/characters.js`). `player_characters`: partidas registradas por personaje, por corte y vista; el main detectado es el de más partidas.
- `users`: cuentas ligadas a start.gg, con `chosen_main_id` (main elegido por la persona) y rol.
- `upcoming_tournaments`: agenda.
- `survey_responses`: respuestas de la encuesta (añadida el 6 de octubre por pedido del dueño).

## Decisiones tomadas
- Sin contraseñas ni tokens guardados: el inicio de sesión será OAuth de start.gg (ver `scripts/smash/ACUERDOS-2026-10-01.md`, sección 6). `users` solo guarda la identidad confirmada.
- El main elegido (`users.chosen_main_id`) no sobrescribe el detectado (`player_characters`). Mostrar el elegido si existe; si no, el detectado.
- La base no reemplaza el cálculo: `rank.py` sigue en Actions. La base es una copia consultable de cada corte.
- La encuesta sigue hoy en `feedback-data/respuestas-2026.php` (una línea JSON por respuesta tras una línea de guarda PHP). El dueño quiere pasarla a `survey_responses`. Hacerlo en el mismo paso en que se configure la conexión de PHP a la base, no antes. Las opciones van como VARCHAR, no ENUM, porque la encuesta puede cambiar.
- `schema.sql` usa `CREATE TABLE IF NOT EXISTS`: se puede ejecutar entero aunque algunas tablas ya existan.

## Lo que NO existe todavía
1. Carga de cortes a la base. BanaHosting normalmente no acepta MySQL remoto sin habilitar "Remote MySQL" por IP, y las IP de GitHub Actions cambian. Opción sugerida: un `import.php` en el servidor, protegido con un secreto, que lea el `public.json` recién publicado y haga los INSERT dentro de una transacción. Alternativa: que `deploy.py` suba un `.sql` y un script PHP lo ejecute.
2. Credenciales de la base para PHP: archivo de configuración fuera de la carpeta pública o protegido por `.htaccess`, nunca en Git. Añadir su nombre a `.gitignore`.
3. Login con start.gg (registrar la app OAuth con `https://rankingsmashbros.com` como redirect), sesiones PHP, pantalla real de "Elige tu main".
4. Decidir si la página lee de la base o sigue leyendo `public.json` (hoy lee el JSON y funciona sin base; no romper eso).
5. Migración de la encuesta: (a) script único que lea `respuestas-2026.php`, salte la línea de guarda e inserte cada línea con `import_hash = sha256(línea)` para poder repetirlo sin duplicar; (b) cambiar `encuesta.php` para insertar en la base y `opiniones.php` para leer de ella, conservando validaciones, límite de 5 minutos por sesión y el compromiso de no guardar IP; (c) ver cómo `opiniones.php` identifica hoy el envío de prueba interna y marcarlo con `is_test`; (d) conservar el archivo como respaldo hasta verificar conteos iguales.
6. Datos faltantes en el JSON para llenar todas las columnas: `events.city`, `events.active_players` y `sets.url` hay que comprobarlos contra `publish_ranking.py`; las columnas admiten NULL.

## Estado de acceso (6 de octubre)
- El dueño confirmó que las respuestas anteriores aparecen en `https://rankingsmashbros.com/opiniones.php` (la carpeta `feedback-data/` se copió bien). Se le recomendó descargar `respuestas-2026.php` como respaldo.
- `opiniones.php`: la cookie de sesión estaba fija a `/ranking-smash-ultimate/` y en la raíz del dominio todo login daba "Solicitud inválida"; corregido para usar la ruta donde se sirva el sitio.
- El dueño escribió la clave del panel en un chat: debe cambiarla (hash nuevo en `SMASH_FEEDBACK_ADMIN_HASH` y un despliegue con `assets_only=true`).
- Acceso de un agente a la base: aún sin configurar. Opciones dadas al dueño: túnel SSH si el plan lo incluye (preferida) o "Remote MySQL" con su IP; credenciales en `~/.my.cnf` escrito por él. No abrir `%`.
