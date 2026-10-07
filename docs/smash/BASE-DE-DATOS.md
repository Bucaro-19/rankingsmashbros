# Base de datos — cuentas, historial y competición

Versión inicial `001_accounts_competition`. **Conexión PHP e instalación confirmadas por el diagnóstico de BanaHosting compartido por el dueño el 6 de octubre de 2026 (Guatemala): MariaDB 11.4.13, 31 tablas y 87 selecciones, schemaReady=true.** Base seleccionada: `ivcjgjlk_smash`, según la captura de phpMyAdmin. El agente recibió el resultado del dueño; no lo leyó directamente en el navegador. Tener estas tablas no activa por sí solo cuentas, reportes ni notificaciones: faltan importadores y módulos.

## Estado instalado

- PR #1 fusionada en `main`, commit `cb89570`; SQL instalado reportado por el dueño. No reinstalar ni recrear tablas como siguiente paso.
- Diagnóstico compartido: 31 tablas, 87 selecciones y versión `001_accounts_competition`; missingTables=[], engineCompatible=true y schemaReady=true. MariaDB 11.4.13. Jugadores, torneos, eventos, sets, cortes, rankings, usuarios y respuestas SQL están en cero, como corresponde antes de importar.
- Dueño creó usuario y archivo privado. Ruta observada /home/ivcjgjlk/private-smash/config.local.php sin abrir contenido. Conector y diagnóstico administrativos publicados (PR #4–#6, último commit `8d509c2`, despliegue `37578387425` correcto). El diagnóstico confirma conexión y lectura desde PHP; permisos de escritura aún deben probarse al importar. La herramienta de Chrome bloqueó la visualización, pero el dueño compartió el resumen exitoso (ver EN-CURSO.md). Credenciales no compartidas ni solicitadas en chat.
- Primer corte/historial importado y comparado por Codex el 7/oct/2026 (PR #9): cutId=1 publicado, 188 rankings por vista, 3435 jugadores de contexto, 43 torneos, 47 eventos y 8985 sets. Repetición confirmó ausencia de duplicados. Web/encuesta siguen con JSON/archivo; usuarios permanecen en cero. El dueño ejecutó después la primera copia de encuesta preparada por Claude: Codex verificó directamente 13 filas con 13 hashes distintos, incluida 1 prueba interna. No se cambió el almacenamiento de las nuevas respuestas. Detalles en IMPORTACION-RANKING.md, MIGRACION-ENCUESTA.md y EN-CURSO.md.
- Siguiente entrega: `SIGUIENTE-FASE.md`. Toda pantalla nueva requiere handoff de Claude Design, por instrucción del dueño.

## Instalación inicial (referencia; ya ejecutada por el dueño)

1. En cPanel → MySQL Databases / Database Wizard, crear una base exclusiva para Smash y un usuario exclusivo. Asociarlo a esa base con permisos para instalar las tablas. No reutilizar la base de otro sitio. cPanel añade su propio prefijo: conservar los nombres completos.
2. Abrir phpMyAdmin y **seleccionar esa base vacía**. En SQL ejecutar `SELECT VERSION();`. El esquema requiere **MySQL 8.0.16+ o MariaDB 10.6+**; no usa collation exclusiva de MySQL. Si la versión es anterior, adaptar antes de importar.
3. En Importar, seleccionar **`docs/smash/install.sql`** y ejecutar. Incluye las 31 tablas y el catálogo de 87 selecciones (86 personajes del catálogo más Random Character). No contiene cuentas, jugadores de prueba ni credenciales.
4. Verificar en SQL:

```sql
SELECT COUNT(*) AS tablas
FROM information_schema.tables WHERE table_schema = DATABASE(); -- 31, en base exclusiva vacia
SELECT version FROM schema_migrations; -- 001_accounts_competition
SELECT COUNT(*) AS personajes FROM characters; -- 87
SELECT id, name FROM characters WHERE id IN (1319, 1766, 1897, 1746);
```

5. Conservar nombre completo de base y usuario. Configurar después PHP con credenciales **fuera de la carpeta pública**, no pegarlas en chat ni guardarlas en Git. Para continuar basta indicar que la importación terminó y el nombre de la base, sin contraseña.

`install.sql` se puede repetir en ESTA instalación sin borrar datos. `IF NOT EXISTS` **no adapta una tabla vieja** de estructura diferente. No se necesita `CREATE DATABASE`, `DROP TABLE`, desactivar claves foráneas ni crear usuarios desde SQL. No se ejecuta en el servidor por el despliegue FTP.

## Migraciones posteriores a la instalación

Carpeta `docs/smash/migrations/`, un archivo por versión, en orden. Solo crean o amplían; se pueden repetir sin cambios. `schema.sql` e `install.sql` siguen describiendo la versión 001; una base nueva se instala con `install.sql` y después con cada migración. Las pruebas (`test_schema.py`) aplican todo dos veces en MySQL 8.0 y MariaDB 10.11.

| Versión | Tablas | Estado en producción |
|---|---|---|
| `002_sessions_visits` | `user_sessions` (sesión persistente), `site_visit_days` y `site_visitor_days` (conteo de visitas, aún sin uso) | Pendiente de aplicar al escribir esto; comprobar con `SELECT version FROM schema_migrations` |

Aplicación: phpMyAdmin → base `ivcjgjlk_smash` → Importar el archivo, o un agente desde la Mac del dueño con su visto bueno explícito. Verificar después 34 tablas y ambas versiones en `schema_migrations`.

## Archivos

- `schema.sql`: fuente del esquema, sin catálogo.
- `seed-characters.sql`: catálogo generado desde `ranking-smash-ultimate/characters.js`, más el ID real 1746 de Random Character. Conserva el nombre desconocido en futuras importaciones en vez de inventar equivalencias por ID. Los assets locales se resuelven contra la URL del sitio.
- `install.sql`: archivo único generado con ambos. Regenerar tras cambiar el esquema o catálogo: `node scripts/database/build_character_seed.cjs`. Verificar: añadir `--check`.
- `scripts/database/test_schema.py`: pruebas reales sobre bases locales desechables en CI. MySQL 8.0 y MariaDB 10.11; instalación y catálogo dos veces, claves foráneas, sets pendientes, versiones/reportes, cortes y entregas de notificaciones. No usa ni acepta el servidor de producción. Validado: run `37574948355`, 8 pruebas por motor correctas; las 58 pruebas existentes del ranking/UI también pasan.

## Tablas y propósito

| Módulo | Tablas | Qué conservan |
|---|---|---|
| Instalación | `schema_migrations` | Versión instalada; futuras alteraciones requieren migraciones. |
| Identidades | `players`, `users` | Jugador estable de start.gg y cuenta OAuth verificada. Puede haber jugador sin cuenta y cuenta sin jugador. |
| Roles y mains elegidos | `user_roles`, `user_characters` | Una persona puede jugar y organizar; principal más dos secundarios elegidos. |
| Acceso OAuth | `oauth_connections` | Permisos concedidos, caducidad, revocación y tokens cifrados cuando se implemente persistencia. |
| Agenda e historial | `tournaments`, `events` | Torneo y sus categorías. Una misma entidad para futuros, activos y terminados. Reemplaza la propuesta `upcoming_tournaments`. |
| Organizadores | `tournament_staff` | Vínculo verificable por torneo, roles reporter/manager/organizer. No da permisos externos por autodeclaración. |
| Participación | `entrants`, `entrant_players` | Inscripción concreta, jugador(es), alias de inscripción y posición final. Participación competitiva separada de inscripción. |
| Enfrentamientos | `sets`, `set_slots` | Set y dos lados, rival pendiente, ronda, lado del bracket, estación si está disponible, estado y marcador numérico. |
| Partidas | `games`, `game_selections` | Personajes/escenarios reportados por game; admite selecciones ambiguas para auditarlas. |
| Cortes | `cuts`, `cut_events`, `cut_set_results` | Snapshot público íntegro y copias de eventos/resultados usados por vista, con hash. |
| Ranking | `rankings`, `player_characters` | Todos los puestos, puntos, récord y uso de personajes por corte/vista. |
| Reportes | `result_submissions`, `result_reviews`, `result_publish_attempts` | Versiones de propuestas, comparación/revisión y seguimiento del envío. |
| Auditoría | `audit_log` | Acciones relevantes sin credenciales ni IP. |
| Avisos | `notification_preferences`, `push_subscriptions`, `notifications`, `notification_deliveries` | Consentimiento, dispositivos, bandeja y entregas sin duplicación. |
| Sincronización | `sync_jobs` | Trabajo compartido, estado, consumo observado y reintentos. |
| Encuesta | `survey_responses` | Respuestas anónimas, pruebas internas y hash de importación. Sin relación a usuarios ni IP. |

## Reglas de implementación

- Todos los tiempos DATETIME se guardan en UTC con microsegundos; conservar también la zona horaria del torneo. PHP usa sesión SQL UTC. País desconocido se guarda NULL, no como GT por defecto.
- User, player y entrant tienen IDs distintos. OAuth vincula por la identidad confirmada, nunca por el nombre. En reportes start.gg pide IDs de **entrant**.
- Importar oponentes aunque sean extranjeros o no estén clasificados; la clave foránea de un resultado no debe excluirlos. Su perfil puede mostrar datos incompletos.
- Historial personal puede incluir torneos que no puntúan. Solo `cut_events`/`cut_set_results` determinan los eventos/sets de un corte; no puntuar todo lo almacenado. Ranking semanal y sincronización de un torneo activo son tareas distintas.
- La DB permite sets sin ganador y slots sin rival. No asumir que `pending` significa que ya llamaron al jugador: la próxima ronda puede depender de otro resultado. `called_at`/estación solo se rellenan con fuente confirmada; no prometer que la API siempre los da.
- La app valida que el ganador pertenece a los dos slots, que el marcador corresponde al ganador, que las propuestas vienen de participantes autorizados y que las revisa un organizador autorizado. Las FK comprueban relaciones, no autenticación. Los cambios de bracket se reconcilian transaccionalmente con sus slots/games/propuestas.
- Dos propuestas iguales se marcan coincidentes, no automáticamente publicadas. Releer estado, resultado y permisos reales antes de enviar; tras timeout reconciliar con start.gg antes de reintentar. La llave local de idempotencia no constituye garantía de idempotencia externa ni elimina carreras con otro administrador.
- `tournament_staff` sirve para atribuir torneos al futuro top 15; su cálculo/criterios específicos todavía deben definirse.
- Cortes publicados son inmutables por política del importador (no mediante triggers). Importar JSON validado en una transacción, guardar hash/snapshot y publicar estado al final. Si el mismo generatedAt/método llega con otro hash, detenerse y auditar; no sobrescribirlo silenciosamente.
- `rankings.previous_cut_at` preserva la comparación aunque no se haya importado el corte anterior. `previous_cut_id` se completa cuando existe su ranking de la misma vista/jugador; no inventar cortes vacíos. Verificar que timestamp y previous_rank coincidan con ese corte al enlazarlo.
- Agregados de mains no reemplazan las selecciones individuales; los elegidos no cambian los detectados ni aportan puntos. Random Character no se deduce como otro personaje.
- Permisos de administrador local se conceden en servidor. Organizador autoidentificado no equivale a permiso reporter externo. No guardar IP ni datos privados en auditoría o encuesta.

## OAuth y límites de start.gg

OAuth entrega un access token del usuario con scopes aprobados y permite renovarlo. Usar `user.identity` para cuentas; pedir `tournament.reporter` solo al habilitar reportes. No se necesita el correo para el perfil inicial.

La documentación publica un máximo medio de **80 solicitudes por 60 segundos** y **1,000 objetos por solicitud**; muestra el error `Rate limit exceeded - api-token`. Esto sugiere un control por token, pero **no garantiza cuota independiente por usuario, ausencia de límites compartidos por aplicación/IP ni aumento ilimitado al vincular cuentas**. No usar credenciales de usuarios para repartir el recolector nacional ni prometer que OAuth elimina consumo.

Diseño: rank e historial desde JSON/DB; consultas compartidas con caché para cada torneo; OAuth para identidad y operaciones autorizadas del usuario. Implementar espera/backoff ante rate limit, medir límites reales y confirmar con start.gg antes de depender de cuotas independientes. Acceso OAuth no publica una tarifa por consulta en estas páginas; no presentarla como costo comprobado.

Tokens persistentes solo cifrados con autenticación (p. ej., libsodium), llave fuera de DB/Git y rotación mediante encryption_key_id. La columna no cifra automáticamente: el módulo PHP debe hacerlo. Client_secret y tokens nunca se entregan al frontend ni aparecen en payloads/logs. Sesiones PHP requieren CSRF/state OAuth, cookies seguras, regeneración del ID y caducidad. No almacenamos contraseñas de start.gg.

Fuentes oficiales revisadas el 7 de octubre:
- https://developer.start.gg/docs/rate-limits/
- https://developer.start.gg/docs/oauth/oauth-overview/
- https://developer.start.gg/docs/oauth/scopes/

## Lo que sigue

1. Instalación y conexión confirmadas por el diagnóstico del dueño. No repetir instalación ni configuración por rutina.
2. Paquete/importador transaccional y escritura completados. Mantener la web leyendo JSON; preparar transporte privado/autenticado para importar semanalmente el paquete que emite Actions, sin abrir MySQL a las IP variables de Actions. Ver SIGUIENTE-FASE.md.
3. Migrar encuesta desde `feedback-data/respuestas-2026.php`, saltando guarda PHP y usando sha256 de cada línea como import_hash. Mantener respaldo y verificar conteos/pruebas internas antes de cambiar lectura/escritura.
4. OAuth, perfil con historial/mains, prueba de torneo activo, reportes y avisos por etapas. La base está instalada y conectada; los módulos todavía no están implementados. No se han movido respuestas ni modificado el cálculo/ranking con esta conexión.

Las respuestas anteriores ya se comprobaron en el dominio nuevo. La carpeta feedback-data permanece protegida. Acceso directo de un agente a la base: **configurado desde el 7 de octubre de 2026** por MySQL remoto desde la Mac del dueño (sin SSH); ver la sección «Acceso directo a la base» abajo. No abrir acceso remoto universal (`%`).

## `survey_responses.import_hash` desde la encuesta en SQL

La columna UNIQUE guarda la huella de origen de cada respuesta: sha256 de la línea para las importadas del archivo, y una clave de reintento para las recibidas por la web: `sha256("smashgt-encuesta-web-v1\n" + nonce + "\n" + sha256(respuesta))` (no identifica a la persona). No asumir que `import_hash IS NULL` significa «respuesta web». Para separar unas de otras, `import_survey.php --compare` contra el archivo. Contrato completo en MIGRACION-ENCUESTA.md.

## Acceso directo a la base (desde la Mac del dueño)

Configurado y verificado por Claude Code el 7 de octubre de 2026. Detalle de lo consultado: `VERIFICACION-BASE-2026-10-07.md`.

- **Cómo conectarse:** ejecutar `/opt/homebrew/opt/mysql-client/bin/mysql` sin argumentos de conexión (no está en el PATH). Lee `~/.my.cnf` del dueño: host `bh8932.banahosting.com`, puerto 3306, usuario `ivcjgjlk_admin`, base `ivcjgjlk_smash`, `utf8mb4`. Ejemplo: `/opt/homebrew/opt/mysql-client/bin/mysql -e "SELECT version FROM schema_migrations"`.
- **Quién puede usarlo:** cualquier agente que corra en esa Mac (Claude Code o Codex). No funciona desde GitHub Actions ni desde otra máquina: cPanel → Remote MySQL solo autoriza la IP de la casa del dueño (`190.14.141.191`), que es residencial y puede cambiar. Si aparece `Host ... is not allowed to connect`, el dueño debe agregar la IP nueva (`curl -4 -s https://ifconfig.me`).
- **Credenciales:** la contraseña la escribió el dueño en `~/.my.cnf` (permisos 600). No abrir, imprimir ni copiar ese archivo; no pasar la contraseña por línea de comandos, chat, repo ni logs. Es independiente de `config.local.php` del servidor, que usa PHP.
- **Permisos:** `ALL PRIVILEGES` sobre `ivcjgjlk_smash.*`. Es producción: usar para lectura, diagnóstico y verificación de importaciones. Cambios de esquema solo por migración versionada en el repo; escrituras de datos con visto bueno del dueño y dentro de transacción.
- **Sin SSH:** los puertos SSH no responden desde fuera y el dueño retiró su llave de cPanel el 7 de octubre. No hay forma de ejecutar comandos en el servidor salvo la Terminal web de cPanel (la usa el dueño). Los archivos del sitio se publican solo por Git y `smash-deploy-snapshot.yml`.
- **Qué desbloquea:** el diagnóstico ya no depende de que el dueño abra `opiniones.php?diagnostico=base`; un agente puede comprobar versión, tablas, conteos y, tras una importación, comparar filas contra `public.json`. El importador de producción sigue necesitando la vía definida en `SIGUIENTE-FASE.md` (no abrir MySQL a GitHub Actions), aunque esta conexión permite una primera carga manual supervisada desde la Mac si el dueño la aprueba.

Codex también confirmó lectura directa y ejecutó la simulación del importador sin escritura. El dueño autorizó continuar la fase de importación en el chat el 7/oct/2026; el código aplica paquetes validados en una transacción. Estado de la primera carga y pruebas: EN-CURSO.md e IMPORTACION-RANKING.md.

## Cuentas — 7/oct, nueva entrega

Se reutilizan `users`, `user_roles`, `user_characters`, `oauth_connections` y `players`, sin migración ni reinstalación. `oauth_connections.updated_at` invalida sesiones anteriores al revocar/reautorizar. Los tokens no se persisten en esta fase. La elección de organizador no toca `tournament_staff`. Consultar [CUENTAS-OAUTH.md](CUENTAS-OAUTH.md) para alcance, privacidad, pruebas y activación pendiente del registro de la aplicación por el dueño. Pruebas hechas únicamente con usuarios sintéticos en SQL local desechable.

Cierre verificado por Codex: PR #18 `4229d26`, despliegue `37655240917` correcto, sin migración. Lectura directa posterior: `users=0`, `survey_responses=16`; beta con OAuth desactivado (`oauthReady=false`). No se escribieron fixtures en producción. Activación/prueba real del proveedor aún pendiente.

Actualización posterior del dueño: app OAuth registrada y archivo privado habilitado; Codex comprobó `oauthReady=true`. La llave local se preservó en un archivo ignorado y el ejemplo se restauró a placeholders. No se escribieron usuarios ni datos de prueba al verificar la configuración; la vinculación real todavía debe probarse.

Vinculación real posterior comprobada en Chrome: Bucaro19, perfil esperado y datos de corte disponibles. Lectura directa: `users=1` y una conexión activa sin access/refresh tokens persistidos. No cuenta sintética. Intercambio de código y GraphQL real confirmados; no se modificaron preferencias del propietario como prueba.
