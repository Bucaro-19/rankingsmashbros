# Automatización del contexto de inscritos — Legends 7

Entrega del 14/oct/2026. Sin pantalla, migración nueva, credenciales nuevas ni servicio adicional. No fusionar, desplegar o activar sin orden. No se ejecutó captura real ni escritura/consulta SQL productiva en esta tarea.

## Alcance y bloqueo de autorización

Destino autorizado: Legends 7, torneo 942547, Ultimate Singles **1687524**, `tournament/legends7`, El Salvador. Temporada 2026; expiración **26/oct/2026 06:00 UTC**, justo después del 25/oct en GT/SV. El proceso no puede extender esa fecha por argumento. Otro evento requiere una nueva orden y actualizar la política fija en ambos extremos; el ID ya se recibe por variable para reutilizar el circuito.

El dueño autorizó `rival_context.py --apply` «solo en las tablas de la migración 007». Ese importador necesita además insertar las entidades ausentes en `players`, `tournaments`, `events`, `entrants`, `entrant_players`, `sets`, `set_slots`, `games` y `game_selections`; 007 tiene llaves foráneas hacia ellas. No sería posible registrar un jugador desconocido escribiendo exclusivamente las tres tablas de 007. **Pregunta pendiente en el chat:** autorizar esas inserciones necesarias, preservando todas las filas existentes, o mantener literalmente el alcance 007. Hasta respuesta expresa, `RC_ENTITY_INSERTS_AUTHORIZED=false` rechaza el inventario/importación automática. Las pruebas habilitan solo una copia temporal de la biblioteca, nunca la fuente productiva. No presentar esto como automatización activa.

La migración 007 se comprueba por versión **y por tablas InnoDB** antes de consultar historiales o crear trabajos. Sin ella: error `analysis_migration_required`, ejecución roja, sin escrituras SQL. No se aplica desde el workflow/receptor. Claude Code la aplica cuando lo ordene el dueño.

## Circuito

1. `.github/workflows/smash-rival-context.yml`: cron **02:37, 08:37, 14:37, 20:37 UTC** (20:37 del día anterior, 02:37, 08:37, 14:37 GT). Grupo `smash-gt-publication` compartido con el semanal/despliegue, sin cancelarlo. Solo repo original, main y `SMASH_RIVAL_SYNC_ENABLED=true`; apagado por defecto. Máximo 30 minutos.
2. `scripts/database/rival_automation.py` usa `collect.Client`. Una consulta combina identidad y primera página de inscritos. Vacío con total 0 significa **lista no disponible**, no cero personas; termina sin receptor, SQL, rutas alternativas, historiales ni sondeos de esquema. Si hay lista, verifica identidad y paginación completa (50 por página, 1000 personas como máximo).
3. Inventario privado firmado por el mismo canal HTTPS `ranking-sync.php`, HMAC existente, nonce, ventana temporal y sin redirecciones. Devuelve IDs ya conocidos en SQL, progreso privado y trabajo pendiente. No es endpoint público de análisis ni devuelve datos a visitantes.
4. `rival_history.capture_batch` y `rival_context.package` se reutilizan sin alterar su contrato/manual. Se capturan solo inscritos ausentes; un conocido ya tiene datos para análisis y no vuelve a consultar su historial. Un inscrito parcialmente cargado **sí se reanuda**, aunque ya exista su fila en players. No se recorren historiales de sus oponentes. La temporada se filtra por fecha del evento GT; el proveedor no garantiza filtro/orden por temporada, por lo que se completa la paginación.
5. Hasta **dos tandas** por ejecución; cada una ≤30 intentos HTTP incluidos reintentos, ≤120 s, una petición/s mediante Client. Habitualmente 28 páginas por tanda sin reintentos (se reservan tres intentos por consulta); cinco sets por página. No hay parámetro que suba estos límites. La lista tiene además su propio BudgetClient. Client limita a 60 inicios/minuto, bajo 80/min. Una consulta lenta que exceda el plazo hace descartar la tanda sin publicarla.
6. Paquete de análisis independiente, nunca paquete nacional. Transporte `application/vnd.smash.analysis+gzip`, límite existente 4 MiB comprimido/32 MiB JSON; este complemento se restringe además a **8 MiB descomprimidos, 150 sets, 1500 games y 3000 selecciones** por tanda. Solo raíces cuyo historial avanzó; se rechazan sets sin relación con ellas. `audit.seconds` se redondea al entero superior antes del hash canónico PHP/Python; el resumen conserva tiempo real fraccionario.
7. El receptor valida y pone `kind=player_history` en **sync_jobs existente**. No se añade tabla, migración o endpoint nuevo. El cron CLI ya instalado de `ranking-worker.php` consume el trabajo, con los mismos bloqueos del semanal. Actions solo tiene STARTGG_TOKEN y SMASH_SQL_SYNC_KEY; no MySQL, FTP, configuración de cPanel ni permisos para aplicar esquemas.
8. `rival-import.php` porta la semántica de `rival_context.load(..., apply=True)` a PHP porque el hosting no dispone del Python admitido por las herramientas. Simulación → transacción serializable InnoDB → paridad → recibo → repetición `already_imported`. Las pruebas comparan Python/PHP tabla por tabla. Inserta contexto ausente; conserva resultados, slots, games y selecciones preexistentes. Una corrección de identidad se rechaza. No escribe cuts, rankings, cut_events, cut_set_results, player_characters, elegibilidad, mains ni archivos públicos. También verifica vigencia antes del commit.
9. El runner espera hasta 600 s al cron por tanda. Si queda pendiente, falla rojo y la siguiente ejecución espera el mismo trabajo antes de capturar más. Hash de transporte deduplica entregas; hash de contenido de 007 deduplica importaciones. Capturas, listas y paquetes no se suben como artefactos, a caché de Actions, al repo ni por FTP.

## Reanudación, errores y privacidad

El estado compacto vive fuera de la web en `private-smash/analysis-context/1687524.json`, permisos 0600, directorio 0700, ≤2 MiB. Guarda lista verificable y cobertura (siguiente página, páginas totales, completo), no páginas históricas. Se comparan revisiones para impedir sobrescribir estado viejo o retroceder páginas. El avance solo se confirma después de importar todos los datos de esa tanda; las páginas ya importadas no se vuelven a pedir.

SQL y archivos no comparten transacción: antes de escribir SQL se deja un candidato privado atómico `.pending`. Después del commit, se renombra atómicamente a estado vigente. Si el worker muere tras el commit y antes del renombrado, el recibo permite completar el estado sin reconsultar start.gg ni perder los conteos originales. Trabajo `running` se recupera bajo bloqueo exclusivo del worker. Un error de importación revierte toda la tanda; anteriores tandas ya completas siguen válidas. Un fallo durante captura no envía un paquete parcial y conserva el checkpoint anterior: la siguiente ejecución puede repetir únicamente esa tanda no confirmada.

Se reintenta la **entrega idéntica** un máximo de tres veces ante pérdida de respuesta; errores permanentes de esquema/autorización no se reintentan. Un job fallido se detiene y exige revisión (`analysis_failed_job_requires_review`); no se borra/reinicia automáticamente. Busy/archivo privado transitorio conserva el reintento limitado del worker, sin afectar la política semanal. La expiración impide que un trabajo en cola se aplique fuera del plazo. El cron después del plazo termina sin consultas ni importaciones; no se borra el YAML ni se amplía autorización.

Los logs y GITHUB_STEP_SUMMARY solo tienen agregados y errores de lista cerrada, sin tags, IDs de jugadores, capturas, SQL, tokens, cuerpos o cabeceras. No hay consultas a start.gg por visita ni cambios de cuentas/premium. La respuesta firmada de inventario es privada/no-store y su lectura está acotada.

## Resumen por ejecución

- **Inscritos:** total de personas verificadas en la lista completa; desconocido si oculta.
- **Conocidos:** inscritos que ya estaban en players al primer inventario (pueden tener una tanda previa todavía incompleta).
- **Agregados:** nuevas identidades de inscritos insertadas por tandas completadas en esta ejecución; no incluye oponentes. Un inscrito puede tener historial pendiente aun después de crear su identidad.
- **Pendientes:** inscritos ausentes cuya paginación no terminó; no un conteo inventado de sets. Cero implica que cada objetivo terminó su recorrido, no que start.gg tenga todos los personajes registrados.
- **Consultas:** intentos HTTP reales de start.gg, incluidos roster/reintentos. No incluye mensajes al receptor ni las esperas del cron.
- **Tiempo:** duración total con receptor y esperas. Una configuración inválida también emite resumen con cero consultas y cantidades desconocidas.

Segunda ejecución sin nuevos inscritos: una consulta de lista (más paginación si supera 50) e inventario; `already_imported`, sin captura/importación adicional. Un nuevo inscrito se captura en la siguiente vuelta. La lista puede cambiar mientras se pagina: duplicados o total incoherente detienen sin importar, en vez de adivinar. No se refresca después el historial completo de un inscrito terminado: este encargo incorpora ausentes, no es un sincronizador permanente de correcciones/sets nuevos de todo el roster.

## Activación futura: solo con orden

1. Aclarar el permiso de inserciones de entidades base descrito arriba. Si se aprueba, cambiar la constante y su prueba/documentación antes de integrar. Si se mantiene 007 solamente, no activar este circuito y rediseñar su almacenamiento en otro encargo.
2. Claude Code aplica 007 con orden del dueño por el procedimiento habitual; no desde Actions. Confirmar CI y revisar PR. Fusionar/desplegar bibliotecas/receptor antes de activar cron, siempre con nueva orden.
3. Reutilizar los Secrets existentes, nunca pegarlos en comandos/chat. Configurar `SMASH_RIVAL_EVENT_ID=1687524`; habilitar `SMASH_RIVAL_SYNC_ENABLED=true` únicamente después de los puntos anteriores. El primer inventario comprueba la migración, no se confía solo en su confirmación verbal.
4. Para apagar futuras ejecuciones: `SMASH_RIVAL_SYNC_ENABLED=false`. Esto no cancela un run ya iniciado ni un trabajo ya aceptado; cancelar ese run explícitamente si se necesita una parada inmediata y revisar su estado antes de nueva orden.
5. Revisar resumen de Actions y fallo rojo si aparece. No publicar capturas ni imprimir config privada para diagnosticar. No reintentar jobs fallidos a ciegas. Tras 25/oct no se importará más, aunque la variable siga true.

No se cambiaron variables del repo, permisos de red, cron de cPanel o secretos en esta entrega. No se comprobó el estado productivo actual de 007 ni de la lista; los datos del 13/oct en LEGENDS7-ANALISIS.md siguen siendo observaciones históricas.

## Pruebas y medición

Datos enteramente inventados, base local aislada MariaDB **13.0.2**, PHP **8.5.3**, límite PHP **512M**. CI exige **MySQL 8.0 y MariaDB 10.11**, además de lint PHP 7.4/8.1. `test_rival_automation.py` tiene **21 pruebas**: lista oculta de una consulta, expiración sin consultas, evento no autorizado, configuración inválida, lista publicada una vez/repetición/nuevo inscrito, conocido sin captura, 60 páginas reanudadas 28+28+4, falta de 007 antes de crear trabajo, fallo de fuente sin paquete parcial, expiración en servidor, CAS/retroceso, interrupción tras commit, transacción revertida por error tardío y paridad tabla por tabla con Python. Las pruebas heredadas comprueban uso desde análisis, premium/gratis y mains/ranking intactos.

Tanda sintética densa: **140 sets, 1400 games, 2800 selecciones**, **28 consultas simuladas**; sobre completo **551042 bytes JSON**, aproximadamente **30 KB gzip**, worker **16777216 bytes (16 MiB) de pico**. Captura simulada + normalización + transporte/receptor + importación en local: **0,83–0,98 s**, sin espera ni latencia real de start.gg. No es una promesa de rendimiento productivo: las 28 consultas reales tienen como mínimo unos 28 s y el cron puede tardar varios minutos. Los techos comprobados siguen muy por debajo de 4 MiB/32 MiB y 512M.

Regresión local: 100 pruebas del pipeline; receptor semanal 18, herramienta manual 7, paquetes 14, carga semanal 13, catálogo 11, contexto de organizador 8 y contexto de games 9 correctas. Se actualizaron las copias temporales de bibliotecas en fixtures HTTP al añadir las dos dependencias privadas; no se relajaron sus aserciones. SHA-256 versionado de public.json intacto: `1e681141bf4d043319593effc3153f44a7ec38531deef8a427f76c2573a24df1`. CI y PR final: ver EN-CURSO.md.
