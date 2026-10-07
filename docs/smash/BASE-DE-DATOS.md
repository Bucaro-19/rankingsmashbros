# Base de datos — cuentas, historial y competición

Versión inicial `001_accounts_competition`, preparada el 7 de octubre de 2026. **El dueño confirmó que importó `install.sql` en BanaHosting y todo terminó correctamente.** Base seleccionada: `ivcjgjlk_smash`, según la captura de phpMyAdmin. La confirmación es del dueño; el agente todavía no se ha conectado a MySQL ni consultado conteos/versiones en producción. Tener estas tablas no activa por sí solo cuentas, reportes ni notificaciones: faltan conexión PHP, importadores y módulos.

## Estado instalado

- PR #1 fusionada en `main`, commit `cb89570`; SQL instalado reportado por el dueño. No reinstalar ni recrear tablas como siguiente paso.
- Esquema esperado: 31 tablas, 87 selecciones y versión `001_accounts_competition`. Verificar estos valores al configurar la conexión; no presentarlos como conteos ya consultados en el servidor.
- Dueño creó usuario y archivo privado. Ruta observada /home/ivcjgjlk/private-smash/config.local.php sin abrir contenido. Conector y diagnóstico administrativos preparados; asociación/permisos y versión por verificar en el hosting (ver EN-CURSO.md). Credenciales no compartidas ni solicitadas en chat.
- Web y encuesta siguen funcionando con JSON/archivo; todavía no se importaron cortes ni respuestas a la base.
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

1. Instalación confirmada por el dueño. Verificar estructura/versiones con la conexión privada, sin repetir importación por rutina.
2. Configurar conexión PHP privada y preparar el paquete/importador transaccional. El JSON público no incluye tournamentId/entrantIds: completar la exportación con relaciones reales de la captura antes de cargar. Ver SIGUIENTE-FASE.md. Mantener la web leyendo JSON hasta verificar paridad.
3. Migrar encuesta desde `feedback-data/respuestas-2026.php`, saltando guarda PHP y usando sha256 de cada línea como import_hash. Mantener respaldo y verificar conteos/pruebas internas antes de cambiar lectura/escritura.
4. OAuth, perfil con historial/mains, prueba de torneo activo, reportes y avisos por etapas. La base ya se instaló según el dueño; los módulos todavía no están conectados. No se han movido respuestas ni modificado ranking/despliegue.

Las respuestas anteriores ya se comprobaron en el dominio nuevo. La carpeta feedback-data permanece protegida. El acceso SSH/MySQL de un agente aún no está configurado; no abrir acceso remoto universal para instalar esto.
