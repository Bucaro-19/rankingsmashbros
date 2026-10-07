# Relevo para Claude Code — importar datos a la base conectada

**Encargo vigente del dueño (7/oct):** Claude Code continúa la transición de encuesta y, después, la automatización SQL. Leer primero RELEVO-CLAUDE-CODE-2026-10-07.md. PR #10 ya fusionada en main 972225d; no rehacer ese importador ni seguir el encargo limitado de tres archivos. Las pantallas de cuentas esperan el handoff solicitado con BRIEF-CLAUDE-DESIGN-CUENTAS.md.

## Punto de partida confirmado

- Repo: Bucaro-19/rankingsmashbros. Sitio: https://rankingsmashbros.com/. No continuar sobre los cambios obsoletos de rsvp-graduacion.
- El dueño informó que importó `install.sql` exitosamente en BanaHosting. Captura: base `ivcjgjlk_smash`. Esquema preparado en PR #1/main `cb89570`, versión `001_accounts_competition`.
- Diagnóstico inicial del dueño: MariaDB 11.4.13, schema 001_accounts_competition, 31 tablas, characters=87, schemaReady=true. Después Codex comprobó lectura/escritura y completó primera importación real el 7/oct/2026: cutId=1 publicado, 188 rankings por vista, 3435 jugadores de contexto, 43 torneos, 47 eventos, 4498 entrants y 8985 sets. Repetición sin duplicación y paridad verificadas. Users sigue en cero. El dueño copió después la encuesta con el importador de Claude: 13 respuestas, incluida 1 prueba interna; Codex confirmó conteos/hashes distintos con SELECT. EN-CURSO.md conserva la evidencia y hashes.
- Conector/diagnóstico PDO publicados (PR #4–#6, despliegue `37578387425` correcto). Importador de ranking CLI en PR #9/main e685fb2, ya probado en producción. Encuesta/OAuth todavía pendientes. Archivo privado observado /home/ivcjgjlk/private-smash/config.local.php sin abrirlo; acceso MySQL privado desde la Mac confirmado. No volver a pedir instalación ni copiar credenciales.
- Verificación directa posterior (Claude Code, 7/oct/2026): mismos valores observados con una conexión MySQL desde la Mac del dueño, más 31 tablas InnoDB utf8mb4, charset por defecto de la base latin1 (declarar siempre `DEFAULT CHARSET=utf8mb4` en migraciones) y `ALL PRIVILEGES` del usuario sobre la base. Un agente en esa Mac ya puede consultar la base: ver «Acceso directo a la base» en BASE-DE-DATOS.md. No hay SSH.
- Web pública sigue leyendo `data/public.json`; encuesta/opiniones siguen usando archivo protegido. No activar funciones incompletas mediante botones nuevos.

## Regla de diseño obligatoria del dueño

**Toda pantalla nueva se pide primero a Claude Design.** Preparar un brief con funciones, estados de carga/error/vacío, datos realmente disponibles, permisos, accesibilidad y móvil. Entregarlo al dueño para solicitar el diseño; implementar cuando exista el handoff. No controlar ni enviar mensajes a otra sesión de Claude sin autorización explícita del dueño.

El diseño actual vive en index.html/arena.css/app.js. No portar support.js ni datos de ejemplo del handoff viejo. Conexión, importación y pruebas se pueden hacer sin pantalla nueva.

## Entrega 1 — conexión privada y diagnóstico (completada)

Implementación publicada en database.php y opiniones.php?diagnostico=base, con enlace en el panel ya existente. Solo resumen administrativo (cuerpo JSON; MIME text/plain al aceptar text/html), no nueva pantalla. CI correcto en ambos motores; acceso anónimo 401 y library 403 verificados en producción. El dueño ya compartió el diagnóstico exitoso descrito arriba. No intentar resolver el bloqueo de Chrome con más cambios a ciegas ni pedir la comprobación otra vez por rutina. La lista siguiente conserva el contrato implementado; avanzar a Entrega 2.

1. El dueño confirmó que creó el usuario MySQL; comprobar su vínculo a `ivcjgjlk_smash`, administrado por cPanel. Plantilla e instrucciones: CONFIGURACION-PRIVADA.md. No pedir su contraseña por chat. El dueño configura un archivo privado en el servidor, fuera del document root, con host/puerto, base, usuario y contraseña.
2. Preparar plantilla sin secretos e instrucciones. Nombre sugerido: `config.local.php`, ignorado por Git. Ruta fuera del sitio, por ejemplo `/home/<cuenta>/private-smash/config.local.php`, ajustada al hosting real. Evitar credenciales en .htaccess, URL, JS o logs. FTP publica solo archivos de la allowlist y no debe subir ese config.
3. Conector PDO (`pdo_mysql`), utf8mb4, UTC, excepciones y prepared statements nativos. La instalación SQL no prueba permisos de PHP. No exponer PDOException con datos de conexión al visitante.
4. Diagnóstico CLI/control administrativo protegido: SELECT VERSION(), versión del esquema, tablas y catálogo. Nunca una página pública que muestre credenciales o información de la base. Si no hay SSH/CLI, definir con el dueño el mecanismo protegido antes de publicarlo.
5. Criterio de entrega: conexión verificada en el hosting, solo resumen saneado de conteos/versión, web/encuesta actuales intactas. No afirmar conexión exitosa por el hecho de que phpMyAdmin importó el SQL.

## Entrega 2 — importación de cortes e historial (completada; automatización pendiente)

Codex completó paquete/importador y primera carga real en PR #9/main e685fb2. Leer IMPORTACION-RANKING.md y EN-CURSO.md antes de duplicar trabajo. El semanal prepara artefacto privado, pero aún no escribe SQL automáticamente; faltan transporte privado y autenticación para ese paso. Claude puede preparar Entrega 3 en otra rama/worktree y archivos propios según TRABAJO-PARALELO-2026-10-07.md, sin cambiar la encuesta productiva todavía. La lista de implementación siguiente conserva el contrato; no rehacerlo por rutina.

### Datos que faltan en el JSON público actual

Inspeccionado el corte del 4 de octubre, schema 3:
- events tiene id/nombre/eventName/fecha/country/activePlayers/url, pero **no tournamentId**.
- results tiene setId/eventId, playerIds en orden ganador/perdedor y playerTags, pero **no entrantIds, slots ni marcador numérico tipado**. Su url es del evento, no necesariamente del set.
- No contiene todas las inscripciones, standings finales por entrant ni todas las selecciones/gameIDs de la captura. No llenar `competitive_sets` con el total parcial de sets visibles.
- `bestPlacement` agregado del jugador no permite reconstruir su posición en cada evento. Fecha DATE tampoco permite inventar hora UTC.

El esquema usa IDs reales y relaciones. **No generar tournamentId/entrantId desde nombres o hashes, ni confundir playerId con entrantId.** Antes de importar, ampliar un paquete de exportación a partir de la captura privada completa o extender el exportador con datos reales validados. Si se extiende public.json, revisar contrato/validadores y decidir si esos campos deben ser públicos. No añadir consultas API por visita.

### Implementación

1. Revisar `discover.py`, `combine.py`, `rank.py`, `publish_ranking.py`, `characters.py`, `deploy.validate_public_data()` y capturas privadas. No cambiar cálculo/reglas. Raw combinado más games (si disponibles) aporta las relaciones que faltan. Artefactos viejos son del repo rsvp-graduacion y sus IDs no se transfieren al nuevo repo.
2. Diseñar paquete privado con JSON público validado, IDs y relaciones consistentes. No conservar datos personales innecesarios. Si faltan campos, conservar NULL donde permitido o detener la importación; no hacer sustituciones inventadas.
3. Importador en PHP/CLI o endpoint administrativo protegido que se defina al implementar; no confiar solo en un nombre de archivo secreto. No abrir MySQL a todas las IP de GitHub Actions. Subir paquete de forma privada, validar tamaño/formato/hash y publicar transacción.
4. Orden: catálogo/player oponentes → torneos/eventos → entrants/vínculos → sets/slots/games disponibles → cut y copia de eventos/resultados → rankings/mains de ambas vistas. No crear users para cada jugador sin OAuth.
5. Normalizar generatedAt a UTC conservando microsegundos; hash reproducible del snapshot íntegro. Misma identidad + mismo hash = ya importado, sin duplicación. Misma identidad + diferente hash = conflicto para auditar; no sobrescribir un corte publicado.
6. `cut_events`, `cut_set_results`, public_snapshot y rankings representan lo usado en ese corte. La sincronización en vivo modifica otra capa y no reescribe el corte. No completar games históricos con selecciones reportadas después sin fijar la fecha de captura.
7. previousRank/previousCutAt se conservan; previous_cut_id solo enlaza un corte importado real de la misma vista/jugador. No fabricar un corte anterior.
8. No inferir condición nacional de oponentes que no estén clasificados ni país desconocido como GT. Perfil incompleto muestra faltantes; registro en evento no garantiza participación.
9. Mantener frontend leyendo JSON hasta comparar exactamente corte, puestos, puntos, récord y mains de ambas vistas con la base. Verificar 188/175 solo si sigue siendo ese corte; comprobar el sitio primero.
10. Pruebas necesarias: primera importación, repetición, error/rollback, cambio de hash, integridad de relaciones, paridad por vista, conservación del corte anterior y protección del acceso. No dejar credenciales/capturas privadas en Git.

## Entrega 3 — encuesta

PR #10 entrega importador y pruebas, revisados por Codex con protección de transacciones previas e integración en CI. Primera copia ya ejecutada por el dueño; la web sigue usando archivo. Leer MIGRACION-ENCUESTA.md: pendientes de repetición real y respaldo verificado, después transición controlada con pausa de envíos y comparación final. No repetir la primera carga como si la tabla estuviera vacía ni cambiar ambas fuentes mediante FTP sin atender los envíos durante la transición.

- Respaldar `feedback-data/respuestas-2026.php`, no descargarlo ni publicarlo con un acceso público nuevo. La primera línea es guarda PHP; el resto son líneas JSON.
- Migrar cada línea válida con import_hash=sha256 de los bytes originales de la línea según una regla fija; repetir sin duplicar. Fechas UTC, campos actuales, comentario <=2000, sin IP/correo/cuenta.
- Revisar cómo opiniones.php omite el envío de prueba y conservar is_test. Si una línea es inválida, no declarar migración completa ni descartarla silenciosamente.
- Comparar conteos y valores con el archivo original; conservar respaldo. No publicar doble escritura sin protocolo para evitar pérdidas o duplicados durante la transición.
- Solo después cambiar escritura en encuesta.php y lectura en opiniones.php, conservando validaciones/CSRF/límite de 5 min y acceso privado. La encuesta y el panel existen: no necesitan pantalla nueva para esta sustitución de almacenamiento.

## Fases posteriores

1. Brief a Claude Design: ingreso con start.gg, primera vinculación, perfil/cuenta, edición de mains y ajustes. Respetar roles múltiples y no sugerir que autodeclararse organizador concede permiso externo.
2. OAuth user.identity, sesiones y vinculación por IDs reales. Reporter requiere scope y permiso real por torneo. Credenciales persistentes cifradas con llave externa; el esquema no cifra por sí solo.
3. Perfil con cortes/historial, top 15 por organizador con atribución y criterio definidos, agenda y torneo en curso. Diseño primero para vistas nuevas.
4. Propuestas de ambos jugadores, desacuerdos/revisión, lectura previa y reconciliación de reportes; después notificaciones con consentimiento y deduplicación. Un set pendiente no significa que ya llamaron al jugador.

## Operación y pruebas

- Variables existentes del repo nuevo: SMASH_PUBLIC_URL=https://rankingsmashbros.com, SMASH_FTP_DIR=., SMASH_SYNC_ENABLED=true, SMASH_RELEASE_MODE=weekly. Confirmarlas antes de cambios.
- Domingo 11/oct: primera actualización semanal del nuevo repo; lunes 12 comprobar éxito antes de apagar el viejo/activar redirección. No programar tareas automáticamente solo por leer este pendiente.
- OAuth no garantiza cuota independiente por usuario. Leer rank/historial de datos compartidos y cachear torneo activo. No repartir el recolector nacional entre tokens de jugadores ni presentar tarifa API inexistente como costo probado.
- Pruebas actuales: python3 -m unittest discover -s scripts/smash -q; node --test scripts/smash/test_app.cjs; node scripts/database/build_character_seed.cjs --check; git diff --check. Integración SQL en smash-check.yml: MySQL 8.0 y MariaDB 10.11.
- Flujo: rama/PR/checks/merge y despliegue solo si toca código servido. No desplegar docs/SQL a la carpeta pública. No borrar feedback-data ni config privado.
- Cerrar cada entrega actualizando EN-CURSO.md, BASE-DE-DATOS.md y este relevo con qué se verificó directamente, qué confirmó el dueño, commits/runs, limitaciones y siguiente acción. Sin secretos.

## Mensaje listo para iniciar Claude Code

> Lee AGENTS.md, CLAUDE.md y docs/smash/{CONTEXTO,EN-CURSO,BASE-DE-DATOS,SIGUIENTE-FASE,TRABAJO-PARALELO-2026-10-07}. La base ya funciona y Codex importó el corte Oct4 con paridad e idempotencia verificadas: 188 clasificados por vista, cutId=1, sin cambiar el cálculo ni la web. No rehagas conexión/importador ni reinstales tablas. Continúa con el encargo paralelo de encuesta en sus archivos asignados y otro worktree; entrega PR/tests sin activar producción todavía. Automatización SQL semanal sigue pendiente; Actions solo prepara el paquete privado. Toda pantalla nueva pasa primero por Claude Design; mantener el relevo y no imprimir credenciales.
