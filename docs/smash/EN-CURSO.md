# Cuentas, ranking e historial — 7 de octubre de 2026, Guatemala

## Sesión persistente — publicada el 7 de octubre (Claude Code)

Primer punto de la hoja de ruta, aprobado por el dueño («lo normal, como Facebook»). **Estado: PR #27 fusionada (`fcd2985`), desplegada y con la migración 002 aplicada en producción.** Falta que el dueño vuelva a entrar con start.gg una vez para recibir la cookie y confirme que ya no se le pide. Detalle en CUENTAS-OAUTH.md, «Mantener la sesión iniciada».

- CI de main `fcd2985` correcta; despliegue `37688777954`, `assets_only=true`, correcto. `public.json` idéntico (SHA-256 `1e681141bf4d043319593effc3153f44a7ec38531deef8a427f76c2573a24df1`).
- Migración 002 aplicada desde la Mac del dueño por su orden explícita («aplica la migración 002»): de 31 a 34 tablas, `schema_migrations` con ambas versiones, las tres tablas nuevas InnoDB utf8mb4 y vacías. Sin cambios en lo existente: cuts=1, users=1, survey_responses=16, rankings=376.
- Producción comprobada por HTTP: API anónima `ok`, `authenticated=false`, `oauthReady=true`; una cookie `smash_recordar` inventada devuelve 200 sin sesión y el servidor la borra (`Secure; HttpOnly; SameSite=Lax`), lo que confirma código nuevo y lectura de `user_sessions`. Bibliotecas 403; encuesta, opiniones y cuenta 200.
- No comprobado todavía: emisión y uso de la cookie con la cuenta real (requiere una autorización del dueño en start.gg).
- **Encabezado de la página principal** (pedido del dueño el mismo día, en PR aparte): el enlace «Tu cuenta · Beta» muestra el alias cuando hay sesión. `cuenta.js` guarda el alias como pista visual en `localStorage` (`smashgt.cuenta`) y `app.js` la confirma con `account-api.php`; quien nunca inició sesión no genera ninguna petición de cuenta. La pista no autentica nada. Probado en navegador contra copia local con base desechable: sin sesión, con sesión y después de cerrar sesión.
- **Decisión del dueño para el contador de visitas:** autorizó usar también la IP («si jalemos la ip no hay problema»). Diseño previsto: guardar una huella con clave privada, no la IP en claro; documentar el cambio de la regla de privacidad en esa entrega.

- Cookie propia `smash_recordar` de 90 días que se renueva con el uso; en SQL solo su SHA-256 (`user_sessions`). Sin tokens de start.gg, IP ni navegador. Cerrar sesión termina ese navegador; desvincular termina todos.
- Cambio deliberado respecto a la entrega de cuentas: iniciar sesión en un segundo dispositivo **ya no cierra** el primero. La versión de la conexión solo cambia al volver a vincular después de desvincular.
- Migración nueva `docs/smash/migrations/002_sessions_visits.sql` (3 tablas: `user_sessions`, `site_visit_days`, `site_visitor_days`). Las dos de visitas quedan creadas para la siguiente entrega; ningún código las usa todavía.
- Orden seguro: el código se puede publicar antes de la migración. Sin la tabla, el ingreso funciona como hoy (sesión de navegador de ocho horas) y simplemente no emite la cookie.
- El diagnóstico del panel ahora informa `migrations`; tras aplicar la 002 debe listar ambas versiones y `tableCount` 34.
- Pruebas locales en MariaDB desechable (13.0.2): `test_schema.py` 9, `test_accounts.php`, `test_accounts_http.py` 8, diagnóstico, importadores, encuesta y sincronización; 48 de Python del ranking y Node sin cambios. Nada probado aún en producción ni con el proveedor real.

**Brief listo para el dueño:** [BRIEF-CLAUDE-DESIGN-PANEL-ESTADISTICAS.md](BRIEF-CLAUDE-DESIGN-PANEL-ESTADISTICAS.md), para pedir a Claude Design el panel de estadísticas. Define los únicos datos que existirán; el contador de visitas del servidor es la siguiente entrega y no necesita esperar el diseño.

## Pedidos nuevos del dueño — 7 de octubre

Panel administrativo de estadísticas, sesión persistente, historial/rivales gratis, análisis de contrincante y top 15 por organizador como premium, y ranking por país a futuro. Registro y estado técnico en [HOJA-DE-RUTA-DUENO-2026-10-07.md](HOJA-DE-RUTA-DUENO-2026-10-07.md). Nada implementado; el orden propuesto espera confirmación del dueño.

## Carga automática a SQL — activada el 7 de octubre (Claude Code)

**Estado: `SMASH_SQL_SYNC_ENABLED=true` desde el 7/oct 20:32 UTC, activada por orden explícita del dueño después de la prueba del circuito real.** Falta por ocurrir la primera carga de un corte nuevo (domingo 11/oct).

- Pasos del dueño en cPanel, según la salida que pegó: `/usr/local/bin/php` es PHP 8.1.34 CLI con mbstring, pdo_mysql y zlib; `private-smash/sync.local.php` con permisos 600 (122 bytes); worker manual `{"ok":true,"status":"idle"}`; un solo cron `*/5 * * * *` con el comando documentado (captura de pantalla de Cron Jobs).
- Verificado directamente desde la Mac del dueño: `publish_sql.py diagnostic` devolvió `ok:true`, `phpVersion` 8.1, `memoryLimit` 2048M, `maxExecutionTime` 30 e `inboxWritable:true`. La clave se leyó del archivo local solo hacia el entorno del subproceso; no se imprimió.
- `publish_sql.py check` validó el paquete original (`/tmp/smash-ranking-package.json`, hash `ecb1d4a5cd44f87250537a85d0d166fa6f9824ff3408f0b55c98ac6102fd9e45`); `send` devolvió `sql_synchronized`, `jobId` 1, transporte `dce58f65d9d8abecc775fb6d3058b3fb7242848d477875fbff6851c98f7ed1e0`.
- Lo procesó el cron real, no una ejecución manual: `sync_jobs` id 1, `ranking_import`, `succeeded`, inicio 20:30:02 UTC (tick de cinco minutos), fin 20:30:04, sin `error_code`. Línea del registro del worker pegada por el dueño: `already_imported`, `cutId` 1, pico de memoria 141082624 bytes (~134.5 MiB, con límite de 512M).
- Sin duplicados: antes y después 1 corte publicado (cutId 1), 188 posiciones por vista, 8985 sets, 3435 jugadores, 81 `cut_events`, 5272 `cut_set_results`. Un segundo `send` del mismo paquete devolvió el mismo `jobId` 1; `sync_jobs` sigue con una fila.
- `public.json` sin cambios: SHA-256 `1e681141bf4d043319593effc3153f44a7ec38531deef8a427f76c2573a24df1`.
- La publicación programada ya dispara en este repositorio: run `37670973001` (7/oct 18:58 UTC, evento `schedule`, omitido por no ser domingo). Queda resuelta la duda anotada más abajo.
- **Pendiente de comprobar el domingo 11/oct o el lunes 12:** que `smash-publish.yml` publique el corte nuevo y que su paso de SQL termine `sql_synchronized` con un `cutId` 2. Si la web se publica y SQL falla, la ejecución queda en rojo: reenviar el paquete de ese corte (artefacto `smash-gt-paquete-sql`) con `publish_sql.py send`, o usar el respaldo `weekly_ranking_load.py`; no borrar cortes.
- Observación: la CI de `main` `37667860684` seguía con el job de MariaDB 10.11 en curso más de hora y media después de iniciar (los otros dos jobs correctos); parece el atasco de entorno ya descrito, no un fallo de pruebas.

## Relevo vigente a Claude Code

El dueño pidió detener a Codex y documentar la continuidad. Leer primero **[RELEVO-CLAUDE-CONTINUACION.md](RELEVO-CLAUDE-CONTINUACION.md)**: prompt listo, estado comprobado, configuración de BanaHosting (ya completada, ver bloque anterior) y opciones para avanzar remotamente. Recomendación: historial disponible desde SQL/estadísticas de rivales; el dueño no seleccionó todavía ese módulo ni agenda/estudio TrueSkill. Esta entrega solo documenta; no cambia código, datos ni producción.

## Encargo vigente — dueño remoto y transparencia del método

- El dueño está trabajando remotamente y pidió dejar por escrito los pasos que requieren su computadora/cPanel. Guía: [PENDIENTES-DUENO-BANAHOSTING.md](PENDIENTES-DUENO-BANAHOSTING.md). No pedir claves por chat; el archivo local ya existe. El agente puede continuar diagnóstico/envío/lecturas/activación después de recibir evidencia de la configuración del servidor.
- Revisión directa antes de esta entrega: `SMASH_SQL_SYNC_ENABLED=false`, receptor POST 503 `sync_not_configured`, public.json SHA-256 `1e681141bf4d043319593effc3153f44a7ec38531deef8a427f76c2573a24df1`. No se ha confirmado subida del archivo ni cron; no activar SQL todavía.
- Se preparó la explicación pública en la página existente `metodologia.html#trueskill`: Bradley–Terry regularizado frente a TrueSkill clásico, incertidumbre, actualización, pesos, repeticiones y actividad. Rankup 2024 declara separar puntos de invitacionales del ranking TrueSkill; sus parámetros exactos no están detallados en la página revisada. Fuentes enlazadas de Microsoft y de la liga.
- El dueño autorizó publicar esta información. No se modifica cálculo, contrato/validación ni `public.json`; no se implementó una simulación TrueSkill ni se cambió el orden de jugadores. Se reutiliza la pantalla de metodología, sin pantalla nueva que necesite handoff.
- Validación local: 48 pruebas del ranking/exportación/despliegue correctas, `git diff --check` correcto, HTML con IDs únicos y fragmentos válidos. Revisión visual en navegador: tabla de escritorio y filas apiladas en iframe de 390 px legibles. JavaScript de metodología sigue cargando torneos/datos. No se modificaron scripts del modelo ni datos.
- CI de la PR detectó una prueba de paridad intermitente: comparaba `players.updated_at` generado por SQL en importaciones ejecutadas en segundos distintos. Solo esa comparación entre importadores omite ese metadato de reloj; conserva fechas del paquete/fuente y todas las columnas de resultados. Snapshots de rollback/conflicto mantienen el timestamp. Corrección limitada a pruebas, sin tocar importadores de producción.
- **Publicado y verificado:** PR #23 fusionada en `82858eb`; evidencia de cierre abajo. Siguen pendientes los pasos de configuración privada/cron y la prueba real de SQL del dueño; no confundir publicación de información con activación de la automatización.

### Cierre — guía del dueño y comparación pública

- CI del último commit de PR #23: `37665496993` y `37665508275`, completas/correctas (check y MySQL 8.0/MariaDB 10.11). Dos jobs detenidos instalando dependencias se cancelaron y se reintentaron; ambos terminaron correctamente. No se ignoró el fallo inicial de la prueba de timestamps: quedó corregido solo en el test.
- Despliegue `37666259662` desde main `82858eb`, `assets_only=true`, correcto. URL para compartir: **https://rankingsmashbros.com/metodologia.html#trueskill**. Página y CSS servidos coinciden byte por byte con main; vista en navegador con cinco filas de comparación y catálogo cargado (42 eventos/7,526 sets en la vista combinada).
- `public.json` idéntico antes/después, SHA-256 `1e681141bf4d043319593effc3153f44a7ec38531deef8a427f76c2573a24df1`. No recálculo, cambios de posiciones, contrato ni esquema.
- API anónima: ok=true, authenticated=false, oauthReady=true; encuesta/opiniones 200; worker y bibliotecas de sincronización/importación 403. No se enviaron paquetes ni se escribió en SQL durante esta entrega.
- Archivo privado local conservado, ignorado y con permisos 600. `SMASH_SQL_SYNC_ENABLED=false` comprobado tras publicar. El dueño todavía debe subir el archivo privado, comprobar PHP/worker y crear el cron; guía práctica PENDIENTES-DUENO-BANAHOSTING.md. Diagnóstico autenticado, prueba con cron real y activación siguen pendientes.
- Los documentos de operación/continuidad enlazan la guía. La evaluación empírica de TrueSkill con los mismos sets no se ejecutó ni se encargó; no sustituir el modelo actual basándose solo en la comparación conceptual.

## Cuentas — nueva entrega de Codex

- Revisadas entregas de Claude Code: encuesta en SQL y cierre de migración, cargador semanal operado desde la Mac, sin reinstalar tablas. Base de trabajo `main` en `99d65c3`.
- Handoff de Claude Design leído e implementado: ingreso, elección de intereses, perfil y editor de mains. Backend OAuth/sesiones y preferencias sobre las tablas existentes; sin cambios al cálculo ni JSON. Detalles/activación: [CUENTAS-OAUTH.md](CUENTAS-OAUTH.md).
- El dueño ya registró **OAuth Application** y configuró el archivo privado. API real con `oauthReady=true`; vinculación real del propietario comprobada en Chrome. Tokens descartados después de verificar identidad; reportes/agenda y sincronización personal quedan para otra fase.
- Pruebas locales con base desechable: vinculación por IDs, roles sin permisos administrativos, guardado/rollback, revocación y paridad de ambas vistas. No se creó ningún usuario real ni se usaron tokens de producción. CI y publicación cerradas; pendiente la prueba real de OAuth tras el registro de la aplicación.

## Cierre de cuentas — publicado y comprobado

- PR #18 fusionada el 7/oct: `4229d26`. CI `37654934247` (push) y `37654969407` (PR), correctas en los tres jobs; incluyen MySQL 8.0, MariaDB 10.11 y lint PHP 7.4/8.1.
- Despliegue `37655240917`, correcto, `assets_only=true`, desde `main`. Sitio: https://rankingsmashbros.com/cuenta.html. Ingreso desactivado: API real devuelve `ok=true`, `authenticated=false`, `oauthReady=false` y `no-store, private`.
- Verificado directamente por HTTP y navegador: pantalla de ingreso 200, biblioteca `accounts.php` 403, escritura sin CSRF 403, encuesta y opiniones 200. JSON íntegro conservado, SHA-256 `1e681141bf4d043319593effc3153f44a7ec38531deef8a427f76c2573a24df1`.
- Lectura SQL real de conteos (sin escritura): `users=0`, `survey_responses=16`. No se crearon cuentas sintéticas en producción. Perfil/editor/guardado, filtros y sets revisados en base local desechable; también versión móvil a 390 px sin desbordamiento.
- Configuración registrada por el dueño: **OAuth Application**, retorno exacto `https://rankingsmashbros.com/oauth.php`, alcance `user.identity`, credenciales en `private-smash/oauth.local.php`. Pasos completos y ejemplo seguro: CUENTAS-OAUTH.md. No pedir secrets por chat ni configurar tokens de usuarios desde mensajes antiguos.
- Próxima acción técnica, después de configurar: probar autorización/cancelación reales, vinculación del jugador, guardado, cierre y desvinculación. No afirmar que el proveedor fue probado por pasar tests simulados.

## Activación OAuth y protección local — actualización del dueño

El dueño confirmó que registró la aplicación, subió `oauth.local.php` al archivo privado del servidor y puso `enabled=true`. Codex comprobó directamente que `account-api.php` devuelve `ok=true`, `authenticated=false` y **`oauthReady=true`**. La configuración pasó la validación del backend y posteriormente se completó la autorización real en Chrome.

El dueño había colocado su client secret en el ejemplo local versionado. Se preservó el contenido en `docs/smash/config/oauth.local.php` (permisos 600, ignorado por Git) y se restauró `oauth.local.php.example` con placeholders. No se imprimió el secreto. La comparación de su valor contra el índice, archivos versionados y objetos del historial local disponible no encontró coincidencias; no se declara una auditoría de clones o fuentes externas.

El cierre documental anterior estaba en `docs/accounts-activation`, commit `5cd9afe`, sin PR por errores de GitHub. Esta entrega incorpora ese cierre y la protección de credenciales a una rama nueva; no duplicar la entrega de código ni desplegar otra vez por cambios de documentación/.gitignore. La vinculación real del propietario fue comprobada; ver evidencia siguiente.

## Vinculación real comprobada — Bucaro19

- En Chrome, el proveedor reconoció la aplicación registrada por el dueño, `rankingsmashbross`, con enlace a `https://rankingsmashbros.com/` y permiso exclusivo de información básica. Se completó Approve y el callback regresó a la cuenta autenticada.
- Perfil real observado: Bucaro19 y enlace `https://www.start.gg/user/7a6063d8`, coincidente con el perfil que el dueño compartió al iniciar el proyecto. Foto, país GT de perfil, intereses jugador/organizador, ranking combinado #177 (1276 puntos), cuatro eventos disponibles y mains detectados Lucas/Hero/Incineroar. El puesto pertenece al corte Oct4; no es una recalculación nueva ni nacionalidad verificada.
- Lectura directa posterior confirmó un usuario y una vinculación activa con **ambas columnas de tokens NULL**. No se imprimieron credenciales, códigos, state ni tokens. Cuenta real del propietario; no se agregó una cuenta sintética de pruebas.
- La consulta GraphQL de identidad y el intercambio de código funcionan con el proveedor real. Guardado, cancelación, revocación y rollback tienen pruebas desechables previas; no se hicieron cambios arbitrarios a mains ni cierre/desvinculación de la sesión real del dueño.
- Pestaña del perfil conservada en Chrome para el dueño. Continúan pendientes agenda/torneo en curso, verificación de organizadores, reportes y notificaciones; nuevas pantallas requieren handoff de Claude Design.

## Redespliegue solicitado por el dueño — 7/oct

- La entrega de protección y cierre OAuth ya estaba fusionada: PR #19, `main` en `0328693`. No quedaron PR abiertas de Claude ni cambios locales pendientes; CI de main `37657991274` correcta.
- A petición explícita del dueño se volvió a publicar desde `main` con `assets_only=true`: [run 37658175611](https://github.com/Bucaro-19/rankingsmashbros/actions/runs/37658175611), terminado correctamente. No se recalculó el ranking ni se reemplazó el corte.
- Verificación HTTP posterior: index/cuenta, JS y estilos servidos coinciden byte por byte con main; encuesta/opiniones 200; accounts.php, database.php y feedback-data/ 403. API anónima 200, `oauthReady=true`, `authenticated=false`, `Cache-Control: no-store, private`. La autorización real de Bucaro19 fue comprobada antes de este redespliegue, según la sección anterior.
- `data/public.json` idéntico antes/después: SHA-256 `1e681141bf4d043319593effc3153f44a7ec38531deef8a427f76c2573a24df1`, corte 2026-10-04T11:43:18.348499+00:00, 188 jugadores por vista.
- Archivo OAuth local conservado e ignorado, ejemplo sin credenciales. Protección adicional en `.git/info/exclude` para conservar la exclusión local al cambiar de rama; no es un archivo para publicar. El despliegue no incluye los archivos de configuración privados.
- Continúan los pendientes de operación semanal/SQL y módulos posteriores descritos arriba. Este cierre solo registra el redespliegue verificado y no requiere volver a publicar documentos.

## Automatización SQL en BanaHosting — nueva entrega

El dueño eligió BanaHosting para funcionar con la Mac apagada. Implementado receptor HTTPS autenticado + cola privada + importador PHP/worker CLI + paso Actions; sin migración ni cambio de cálculo. Detalles, límites y activación: CARGA-SEMANAL-SQL.md, bloque vigente. Paridad Python/PHP tabla por tabla, 11 casos locales y paquete real Oct4 verificados en base desechable. Preparado; configuración/cron y prueba del circuito de producción aún pendientes. No afirmar que ya está programado ni activar variable antes de validar servidor.

## Cierre de entrega SQL en hosting — publicado, activación pendiente

- PR #21 fusionada en `5963fbe`. CI `37661548814` y `37661557318` completas/correctas: contrato/JS/lint PHP y ambos motores MySQL 8.0/MariaDB 10.11; incluyen las 11 pruebas nuevas. Sin cambios de esquema.
- Despliegue `37661808161`, desde main y `assets_only=true`, correcto. HTTP real posterior: receptor GET 405, bibliotecas/worker 403; cuenta API con `oauthReady=true`; encuesta/opiniones 200. JSON íntegro sin cambios, SHA-256 `1e681141bf4d043319593effc3153f44a7ec38531deef8a427f76c2573a24df1`.
- Recepción POST en producción devuelve 503 `sync_not_configured`, coherente con archivo privado todavía ausente. Lectura SQL directa: cuts=1, users=1, ranking_import_jobs=0. No se cargó un corte ni se crearon trabajos de prueba en producción.
- Generada clave aleatoria en `docs/smash/config/sync.local.php`, ignorado/permisos 600; preservada fuera del índice. Se guardó el mismo valor por stdin como secreto GitHub `SMASH_SQL_SYNC_KEY`, sin mostrarlo. Variable `SMASH_SQL_SYNC_ENABLED=false`, comprobación/activación pendientes. No imprimir archivo ni secreto.
- **Siguiente acción del dueño:** copiar archivo privado a `/home/ivcjgjlk/private-smash/sync.local.php`, comprobar PHP CLI/worker y crear cron cada cinco minutos según CARGA-SEMANAL-SQL.md. La cuenta FTP del despliegue solo ve el sitio, no la carpeta privada ni crontab; no se supone que esto ya está hecho.
- Después Codex puede ejecutar diagnóstico autenticado, reenvío idempotente del paquete original Oct4, lectura de paridad/job y activar la variable si el circuito funciona. Primer nuevo corte/disparo semanal del 11/oct sigue pendiente de ocurrir; no crear recaptura con hash diferente ni dar por verificado el cron.

## Estado vigente

- El dueño compartió el resultado real del diagnóstico privado: connection=connected, MariaDB 11.4.13, schemaVersion=001_accounts_competition, tableCount=31, missingTables=[], engineCompatible=true y schemaReady=true. Base de la instalación: `ivcjgjlk_smash`. Evidencia recibida del dueño el 6/oct/2026 (Guatemala), no lectura directa del agente mediante navegador.
- PR #1 del repo nuevo fusionada en `main`, commit `cb89570`. Preparó v1 `001_accounts_competition`: 31 tablas/87 selecciones esperadas. CI correcto: 46 Python + 12 Node y 8 pruebas por motor (MySQL 8.0/MariaDB 10.11), run `37574948355`.
- No reinstalar tablas. Archivo observado sin abrir contenido: /home/ivcjgjlk/private-smash/config.local.php. Conector y diagnóstico publicados: PR #4 `a29355e`, PR #5 `e8e7d55`, PR #6 `8d509c2`; último despliegue `37578387425`, correcto. Conexión y esquema confirmados por el diagnóstico compartido; no pedir contraseñas por chat.
- Conteos iniciales del diagnóstico (antes de importar): characters=87 y demás tablas consultadas=0. Primera carga real completada por Codex el 7/oct/2026: cutId=1, status=published, 188 rankings combined + 188 guatemala, 3435 jugadores de contexto, 43 torneos, 47 eventos, 4498 entrants, 8985 sets y 17970 slots. Usuarios siguen en cero. Posteriormente el dueño ejecutó el importador de Claude: 13 respuestas SQL, incluida 1 prueba interna; conteos/hashes únicos verificados directamente por Codex.
- La web pública sigue leyendo JSON. Desde el 7/oct la encuesta y el panel usan SQL (ver «Encuesta y panel en SQL» abajo); `feedback-data/respuestas-2026.php` quedó congelado como archivo histórico. El corte/historial ya están en SQL.
- Dominios/repos: sitio activo https://rankingsmashbros.com/, repo Bucaro-19/rankingsmashbros. Graduación es legado.

## Instrucción nueva del dueño

Toda pantalla nueva debe solicitarse primero a **Claude Design** y seguir su handoff. Documentar funciones/estados en un brief y entregarlo al dueño; no inventar la pantalla en código. Backend/importadores pueden avanzar sin pantallas. Regla guardada en AGENTS.md y CLAUDE.md.

## Conexión PHP — publicada y confirmada por el diagnóstico del dueño

- database.php carga únicamente el archivo privado hermano del sitio, valida formato y conecta mediante PDO con utf8mb4, UTC y prepared statements nativos. No imprime secretos/excepciones.
- opiniones.php?diagnostico=base ofrece cuerpo JSON de conteos/versiones solo a sesión administrativa válida. Navegaciones que aceptan text/html reciben text/plain; clientes API application/json. Anónimo 401; POST 405. El panel existente incluye el enlace «Comprobar conexión a la base de datos» únicamente tras autenticarse. No pantalla nueva ni cambios a respuestas.
- El dueño renovó la sesión en Chrome; el panel mostró 12 respuestas antes y después de publicar. La herramienta de Chrome devolvió ERR_BLOCKED_BY_CLIENT al abrir el diagnóstico, tanto por navegación directa como por clic en su enlace. Cambiar el formato no resolvió ese bloqueo, pero el dueño lo abrió manualmente y compartió la respuesta exitosa. La limitación de la herramienta no bloquea la siguiente fase ni requiere más cambios a ciegas. Nunca extraer cookies ni contraseñas.
- Pruebas locales: configuración privada, supresión de salida y sesiones; 6 contratos HTTP; 46 Python + 12 Node. Última CI `37578278589`/`37578275593`: todos los checks correctos, incluida conexión PDO real sobre MySQL 8.0/MariaDB 10.11. Esas bases son desechables, no el hosting.
- Último despliegue assets_only=true: `37578387425`, correcto. Verificación HTTP real: diagnóstico anónimo 401/login_required en ambos formatos y cache no-store/private; acceso directo a database.php 403; inicio, encuesta y opiniones 200. public.json idéntico tras despliegues y carga SQL (SHA-256 `1e681141bf4d043319593effc3153f44a7ec38531deef8a427f76c2573a24df1`). El importador CLI no requiere un nuevo despliegue del sitio.
- Conexión y primera carga cerradas: lectura y escritura transaccional verificadas directamente desde la Mac. Solo se crearon datos de contexto y un corte; el frontend y la encuesta conservan su almacenamiento actual.

## Próximo trabajo

### Encuesta y panel en SQL — publicado el 7 de octubre (Claude Code)

- **Producción escribe y lee la encuesta en `survey_responses`.** PR #13 fusionada (`033bd6a`), despliegue `37647575579` correcto. Contratos, protocolo ejecutado y evidencia: MIGRACION-ENCUESTA.md, «Entrega 2» y «Transición en producción».
- Base al publicar: 14 filas (13 de comunidad + 1 prueba), todas importadas de los dos archivos y comparadas fila por fila. El archivo del sitio nuevo quedó congelado (440) con dos respaldos en `private-smash/`.
- Verificado después: una respuesta de prueba real entró por el formulario nuevo y quedó con `is_test=1` (15 filas: 13 de comunidad, 2 de prueba); el diagnóstico del panel, abierto por el dueño, dio `phpVersion=8.1`.
- **Migración cerrada el 7/oct:** dominio anterior redirigido (`rsvp-graduacion#26`), su archivo congelado e importado, y la prueba del dueño marcada `is_test=1`. Estado final: 16 filas, 13 de comunidad y 3 de prueba. Evidencia en MIGRACION-ENCUESTA.md, «Cierre».
- No revertir el PR ni desplegar ramas anteriores: `deploy.py` rechaza páginas de encuesta que no sean las de SQL y los despliegues solo corren desde `main`.
- Hallazgo para el dueño: el repositorio es público, así que los artefactos de Actions los puede descargar cualquier usuario con sesión en GitHub.
- Handoff de Claude Design para cuentas ya entregado por el dueño: carpeta local `SmashRankingGT/design_handoff_smash_gt_cuentas/` (fuera de este repo, sin versionar). Su README nombra el repo `rsvp-graduacion`; el correcto es este. Implementación en esta entrega; configuración habilitada y autorización real comprobada con el propietario.

### Carga semanal del ranking a SQL — preparada, sin activar (Claude Code)

- PR #14 fusionada (`0c727fc`): cargador de un comando operado desde la Mac del dueño (`scripts/database/weekly_ranking_load.py`) y artefacto propio del paquete SQL con 90 días. Documento: CARGA-SEMANAL-SQL.md. Nada programado.
- **Siguiente acción, lunes 12 de octubre:** comprobar que la publicación del domingo 11 terminó bien y dejó el artefacto `smash-gt-paquete-sql`; después, desde la Mac, `status`, `load` (simulación) y `load --apply`. Es la primera prueba real de la descarga y del segundo corte.
- **Vigilar antes del domingo:** al cierre de esta entrega (7/oct, 16:05 UTC) el workflow `smash-publish.yml` todavía no había generado ninguna ejecución programada en este repositorio, ni el tick diario de las 12:23 UTC que debe aparecer como omitido. En el repositorio anterior ese tick llegó con unas seis horas de retraso, así que puede ser demora de GitHub. Si el jueves sigue sin aparecer ninguno, la publicación del domingo podría no dispararse sola: lanzarla a mano con `workflow_dispatch` desde `main`. El primer tick también es la primera evaluación real de la condición `if` del trabajo, que ahora exige `main`.

### Ranking/historial — entrega completada por Codex

- PR #9 fusionada en main, commit e685fb2. Checkout separado /tmp/smash-ranking-db-import; el principal queda disponible para Claude. Reparto y prompt: TRABAJO-PARALELO-2026-10-07.md.
- ranking_package.py genera paquete determinista desde combined.json y public.json sin recalcular ni consultar API. import_ranking.py valida y escribe con transacción/bloqueo/paridad; modo predeterminado de simulación. Guía IMPORTACION-RANKING.md.
- Lectura directa desde la Mac confirmada mediante configuración privada ya provisionada: MariaDB 11.4.13 y cuts=0. No se imprimieron credenciales. La simulación real del corte Oct4 terminó validated_no_writes: 3435 jugadores de contexto, 43 torneos, 47 eventos, 4498 entrants, 8985 sets y 17970 slots; vistas de 188 jugadores cada una (42/39 eventos y 2648/2624 resultados). No confundir jugadores de contexto con clasificados guatemaltecos.
- Primera importación real: imported/cutId=1; repetición: already_imported/cutId=1. Consulta directa confirmó published, generated_at=2026-10-04 11:43:18.348499, 188 jugadores por vista, players=3435, sets=8985, users=0 y survey_responses=0. Hash del paquete: ecb1d4a5cd44f87250537a85d0d166fa6f9824ff3408f0b55c98ac6102fd9e45. El importador verificó paridad completa antes de publicar y nuevamente al repetir; no fabricó el corte anterior.
- CI 37581615922 y 37581612335 correcta: 46 pruebas Python del ranking, 12 Node, 4 contratos del paquete y 6 casos SQL reales por motor (MySQL 8.0/MariaDB 10.11), además de las pruebas de esquema/conector existentes.
- La encuesta queda asignada a Claude para preparar código/tests, sin activar escritura SQL todavía. SQL semanal automático aún pendiente: Actions prepara artefacto privado; no tiene acceso remoto a MySQL. No abrir ese acceso a las IP variables de Actions.

### Encuesta — revisión de PR #10

- Claude entregó importador CLI repetible, pruebas inventadas y MIGRACION-ENCUESTA.md. El dueño ya ejecutó una primera copia en cPanel; el archivo sigue siendo la fuente de encuesta/opiniones.
- Codex verificó directamente solo agregados de producción: 13 filas, 13 hashes distintos, 1 is_test. Sin leer comentarios ni ejecutar escrituras.
- PR #10 revisada y fusionada en main `972225d`: protección de la transacción del llamador y regresión; integración en CI MySQL 8.0/MariaDB 10.11 con extensiones SQLite/mbstring explícitas. Sintaxis y suite SQLite locales correctas. CI `37582761629` correcta sobre `b7d842a`; suite nueva confirmada en logs sobre MySQL 8.0.46 y MariaDB 10.11.19. Checks del commit final correctos: `37582899820` y `37582895363`.
- Pendientes: repetición real con versión revisada, hash/tamaño del respaldo y comparación de valores. Después, transición controlada del archivo a SQL con pausa de envíos y verificación final; no activar doble escritura ni asumir que el despliegue FTP es atómico.

Siguiente: completar la transición de encuesta y preparar transporte privado/autenticado para automatizar la carga SQL semanal. Mantener JSON público y método/calendario actuales. Después OAuth y perfil según handoff de Design. OAuth no garantiza cuota independiente por usuario; consultar datos compartidos desde base/caché.

El dueño encargó esa continuación a Claude Code. Relevo/prompt vigente en **RELEVO-CLAUDE-CODE-2026-10-07.md**; sustituye el encargo paralelo anterior, ya cumplido. Prompt de ingreso/perfil/mains para el dueño en **BRIEF-CLAUDE-DESIGN-CUENTAS.md**. Codex solo preparó el relevo y el brief; no inició la transición ni OAuth y no envió mensajes a otras sesiones.

Este relevo documenta instalación, conector y primera importación/repetición de ranking completadas. Encuesta y automatización SQL pendientes. Consultar Git/Actions antes de retomar.

---
## Archivo histórico del rediseño (trabajo completado)

Las listas de pendientes anteriores se conservan como historial; el estado vigente está arriba.


# Rediseño y mains automáticos — 6 de octubre de 2026

## Pedido actual
Recrear el handoff de Claude Design con alta fidelidad: Big Shoulders Display + Archivo, fondo #0B0F1A, celeste #49A6E9, cortes diagonales, ticker, hero #1, podio 2-1-3, barras, búsqueda y chips de mains, panel lateral para TODOS, adelanto visual de elegir main (sin cuentas reales). Conservar cálculos/validaciones y ambas vistas. Añadir extracción real de personajes por game, schema nuevo y DLC completos. Crear estos documentos para continuidad.

## Estado
- Rediseño publicado desde `main` (ver "Publicado" abajo).
- Diseño recreado y publicado. Carpeta del handoff y `.DS_Store` son archivos del usuario; no borrarlos ni agregarlos indiscriminadamente.
- Confirmado en docs oficiales: sets → games → selections → character. Falta prueba autenticada del vínculo `selection.entrant.id` usando token ya guardado en Actions.
- No hay STARTGG_TOKEN en entorno local. No solicitar que lo peguen al chat. Consultas mediante Actions.
- Plan: enriquecimiento de personajes independiente, en lotes pequeños y con caché; no recalcular el ranking para añadir datos. Primero habilitar pipeline/prueba de API, después rediseño y publicación validada.
- Solo contar selecciones registradas de games en sets competitivos admitidos. No deducir personajes de aliases. Orden por games, empate determinista; mostrar principal y hasta 2 secundarios. Informar cobertura y uso repartido.
- marcrd incluye Piranha Plant; DLC restantes necesitan fuente oficial/archivos locales. API de árbol: `/tmp/smash-asset-paths.txt`. Sora oficial: https://www.smashbros.com/assets_v2/img/fighter/sora/main.png; falta resolver stock icons DLC.

## Capturas reproducibles disponibles en esta máquina
- `/tmp/smash-scope-oct4/`: combined.json, pilot-ranking.json, previous-public.json (Oct2), nacional/extranjero.
- Tabla TTS fijada: `scripts/smash/data/ultrank_players.csv` (ignorada).
- `/tmp/smash-activity-before.json`: JSON previo a añadir activity. NO usar para desplegar.
- Artefactos de run semanal `37198767448` (Oct4), capturas privadas. Expiran: comprobar disponibilidad.
- Corte vivo debe verificarse siempre: https://ingporras.com/ranking-smash-ultimate/data/public.json

## Pendientes de esta entrega
1. Extracción/caché/tests de personajes; consultar games reales vía Actions, medir faltantes; extender schema sin debilitar validaciones.
2. Assets y catálogo de slugs, incluidos DLC, fallback `?`, atribuciones.
3. HTML/CSS nuevo aislado de encuesta/metodología (comparten estilos antiguos); adaptar render sin sustituir reglas.
4. Panel todos, rivales frecuentes con IDs, actividad/historial existentes, flechas y chips; elegir main solo demo.
5. Pruebas, comparación de campos de ranking antes/después, QA móvil/escritorio, CI, despliegue y verificación.
6. Actualizar este archivo con resultados, commits, ejecuciones y pasos exactos pendientes.

## Avance técnico
- PR #23 fusionado: `d850aa4`. Pipeline de personajes, caché y compatibilidad schema 2/3; cálculo y exportación previa intactos. `smash-characters.yml` solo produce artefactos, NO despliega.
- Consulta autenticada terminada: run `37540350390` (captura origen `37198767448`), 2648 sets consultados, 175 de 188 clasificados con personaje registrado. Artefacto `smash-mains` (caduca a los 14 días).
- Backend añade mains al JSON ya exportado mediante characters.py. El workflow semanal invoca este paso después de exportar ambas vistas. Mains se calculan por scope; selecciones duplicadas se deduplican por game/entrant/character, ambiguas se omiten y cuentan como tales, games sin ganador se omiten.

## Relevo Codex → Claude (6 de octubre, tarde)
Codex dejó el rediseño sin commit en la carpeta principal (rama local `feat/smash-design-ui`, sin commits propios). Claude copió ese estado a la rama `claude/smash-folder-review-f38d72` y continuó ahí. **Continuar desde esa rama (o desde `main` si su PR ya se fusionó), no desde los cambios sin commit de la carpeta principal: quedaron obsoletos.** No se borraron; el dueño decide cuándo descartarlos. La carpeta `design_handoff_smash_gt_ranking/` sigue sin versionar en la carpeta principal.

Hecho en esta rama:
- UI nueva completa en `index.html`, `app.js`, `arena.css` (bloque `.smash-redesign` al final; los estilos viejos de arriba siguen porque metodología/encuesta los comparten) y `characters.js` (86 personajes, IDs de start.gg).
- `data/public.json` del repo: mismo corte del 4 de octubre, schema 3 con `mains`, `mainCoverage` y `results[].playerTags`. Comparado contra producción: todos los demás campos de ambas vistas son idénticos (puestos, puntos, sets, eventos, actividad).
- Correcciones de Claude: alias `Simon Belmont` y `Duck Hunt` (start.gg los nombra distinto al catálogo y salían con `?`); retratos locales reducidos (ver ASSETS.md); en móvil el panel ya no hereda el padding viejo de `#player-dialog`, el marcador G–P no se parte y los chips de mains van en una fila con scroll horizontal.
- QA en navegador (1024 px y 375 px): hero, ticker, podio 2-1-3, filas, chips, búsqueda, cambio de alcance, panel con mains/torneos/rivales/calendario/sets, carta de demo y metodología con schema 3. Sin errores de consola ni scroll horizontal.
- Pruebas: 46 de Python, 12 de Node, `node --check` de `characters.js` y `app.js`, `git diff --check`.

## Publicado (6 de octubre, noche)
- PR #24 fusionado en `main` (`4e37fac`). `smash-deploy-snapshot.yml` con `assets_only=false`: run `37543142250`, correcto.
- Verificado en https://ingporras.com/ranking-smash-ultimate/: schema 3, corte 2026-10-04T11:43:18, 188 clasificados en ambas vistas, 175 con personaje, 25 archivos en `assets/characters/`, UI nueva cargando sin errores de consola ni imágenes rotas, panel de jugador con mains.
- La rama `claude/smash-folder-review-f38d72` ya no hace falta. Trabajar desde `main`. Los cambios sin commit de la carpeta principal (rama local `feat/smash-design-ui`) son una copia vieja de lo ya publicado: descartarlos antes de seguir, con permiso del dueño.

## Pendiente
0. Migración a repo y dominio propios: ver `MIGRACION.md` (sitio ya publicado en rankingsmashbros.com; falta confirmar el semanal del domingo y redirigir la URL vieja). Base de datos propuesta: `BASE-DE-DATOS.md`. Siguientes fases de producto: orden en `scripts/smash/ACUERDOS-2026-10-01.md` (toca el top 15 por organizador; después perfiles, agenda e inicio de sesión).
1. Domingo: comprobar que el semanal (`smash-publish.yml`) publica schema 3 con mains por sí solo y que las flechas de movimiento aparecen.
2. Decisiones abiertas para el dueño: (a) start.gg registra "Random Character" (id 1746); hoy se muestra tal cual con `?` y es el más usado de Zigma y keks; (b) no se probó a 1366 px o más, revisar hero y podio en pantalla grande; (c) el botón del header dice "Próximamente: tu cuenta" en vez de "Crear cuenta" del handoff, a propósito porque no hay cuentas.
3. Fuera de esta entrega: cuentas reales/OAuth, donaciones, agenda, top 15 por organizador, rotación del token de start.gg.
