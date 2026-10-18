# Mi torneo: bracket privado de Legends 7

## Alcance

Sección gratuita en Tu cuenta, provisional por autorización expresa del dueño (17/oct). No es la pestaña premium de tops «Mis torneos». Muestra fases/grupos propios, horarios GT/local, primer set pendiente y rival confirmado o probable, camino posible si ganas, rival con mejor puesto conocido en el ranking combinado o menor seed si nadie tiene puesto, y lista del pool. Sin puesto no equivale a débil. Los enlaces de análisis conservan los controles premium existentes.

Los botones junto a **Tu primer set pendiente** analizan a su oponente (con su nombre en cada botón). Los del rival de referencia permanecen en su sección, también con nombre y aclaración de que puede ser otra persona. Sin oponente o sin enlace no se sustituye por el rival de referencia ni se muestra un botón inventado.

## Captura y límites

`scripts/database/my_tournament_sync.py` reutiliza collect.Client/BudgetClient: una petición/s incluyendo reintentos, dos tandas como máximo de 30 intentos/120 s cada una. Máximo 1000 inscritos, 100 grupos, 5000 seeds/sets, 8 MiB JSON / 4 MiB gzip. Solo publica una captura completa y validada; falla en rojo y conserva la anterior si se exceden límites o cambia la paginación. Sin artefactos, caché pública ni MySQL en Actions. No extender límites a ciegas.

Esquema oficial inspeccionado en Actions 39076192675 (dos consultas): **Event.phaseGroups es una lista sin argumentos**; seeds y sets se paginan independientemente. Conexiones ya agotadas pueden devolver total cero: se ignora solo la ya acabada, no un cambio de total en una página activa. Tres grupos por consulta, 24 seeds/sets por página; nunca slots.stats.

Horarios nulos/0 quedan null. Pool: startAt, luego wave.startAt, luego firstRoundTime, con fuente explícita. Set.startAt ya puede incluir fallback de ronda del proveedor: etiqueta «Horario de set/ronda de start.gg». Si falta, se usa el horario del pool etiquetado; nunca el inicio del evento como si fuera un set. Sin fecha: «Horario aún no publicado». Zona ausente: hora local null, no estimada.

IDs opacos preview_* se conservan, no se inventan IDs SQL. Camino por slots.prereqType=set/prereqId/prereqPlacement=1, ganador real si existe y, en caso contrario, seed menor cuando ambos se conocen. No se inventa un bracket estándar ni se adivinan rivales sin seeds. Solo se salta un bye marcado isBye: un slot null no prueba un bye. opponentConfirmed distingue primer rival real de probable. Memoización, detección de ciclos y profundidad acotada.

## Archivo y seguridad

Receptor HMAC/nonce existente ranking-sync.php, tipo application/vnd.smash.bracket+gzip, **antes de abrir PDO**. bracket-store.php valida esquema cerrado/tipos/relaciones/tamaños y escribe private-smash/brackets/1687524.json, fuera del sitio, permisos 0600/directorio 0700, lock y temp+rename. Repetición idéntica: already_stored. Fecha vieja o contradictoria con igual fecha: rechazo sin reemplazar. Captura de máximo 30 minutos, no futura >60 s; entrega cerrada al terminar autorización. Sin cola SQL ni dependencia de 007. Bibliotecas negadas por .htaccess antes de desplegar.

GET mi-torneo-api.php sin parámetros. Sesión reanudada y **users.player_id vigente** mediante smash_account_current; 401 anónimo/revocado, 405 otros métodos, 400 si intentan elegir jugador/pool/evento. Gratis/admin obedecen la misma identidad. Solo salen los pools que contienen al jugador de la sesión; nunca roster completo, prerequisitos, IDs de seed, cuentas/correos/pagos o estadísticas premium. Player IDs de miembros propios únicamente sirven a los enlaces existentes de análisis. Cache-Control no-store, private; X-Robots-Tag noindex; sin CORS ni start.gg por visita. Logout limpia DOM y aborta; respuestas tardías se descartan.

Contrato v1: `{ok,status,capturedAt,event,upcoming,pools}`. Estados snapshot_unavailable, registrations_unavailable, not_registered, pools_unpublished, ready. event: name, url, start, endAt. Cada horario: timestamp/guatemala/local/timezone/source, nullable. Pool: phase, phaseOrder, group, start, members, strongest, strongestBasis, firstSet, probablePath. Miembro: playerId nullable, tag, seed, groupSeed, rank nullable, analysisUrl/prepareUrl nullable. firstSet: id opaco, round, opponent nullable, opponentConfirmed, time. probablePath: round, opponent nullable, time. Lista oculta no equivale a no inscrito. Si se retiran datos, el vacío se refleja en la captura siguiente.

## Programación y apagado

smash-my-tournament.yml usa smash-gt-publication, compartido con FTP/contexto. Cron UTC `19,49 * * * *`. Antes del torneo captura cada 3 horas en zona del torneo, minutos 19-48 para tolerar cola; durante sus fechas cada 30 minutos. Actions puede retrasarse. Manual salta cadencia, nunca expiración. Termina sin consultas desde **25/oct/2026 22:00 SV = 26/oct 04:00 UTC**, fin verificado, anterior al límite del contexto histórico. No ampliar si cambian las fechas sin nueva orden. ID configurable, pero solo 1687524 está autorizado en las políticas Python/PHP; otro evento exige política verificada.

Con CI verde, fusión y despliegue assets-only, activación autorizada por el dueño:

```sh
gh variable set SMASH_MY_TOURNAMENT_EVENT_ID --body 1687524
gh variable set SMASH_MY_TOURNAMENT_ENABLED --body true
gh workflow run smash-my-tournament.yml --ref main
```

Apagar nuevas ejecuciones: `gh variable set SMASH_MY_TOURNAMENT_ENABLED --body false`. Un run iniciado se cancela explícitamente si se necesita parada inmediata. No borra el resumen anterior; su fecha sigue visible.

## Verificación

- Captura 39076906817: 309 inscritos, 12 grupos, 617 sets; 17 consultas, 29,734 s, validación Python sin escribir.
- Sonda completa **39077207149**: mismos conteos, 17 consultas, **37,186 s**, validación PHP y proyección propia de 309 jugadores en el runner (309 ready). **309729 B JSON con espacios, 21969 B gzip y 12582912 B de pico PHP (12 MiB)**. Sin nombres/IDs/pools en logs ni entrega al hosting. Son mediciones de esa fecha, no garantía si crece el bracket.
- Pruebas inventadas: captura/oculto/paginación agotada, presupuesto/fecha, dos validadores, firma/replay real sin configuración MySQL, atomicidad/repetición/fecha antigua, identidad de sesión SQL/401/revocación/desvinculación, sin pool ajeno, privacidad, estados vacíos, horarios/fallback GT-local, rank/seed, byes/null/ciclos, rival confirmado/probable y camino. CI exige MySQL 8.0 y MariaDB 10.11.
- Navegador local con base exclusiva, escritorio y 375 px: sin desborde (scrollWidth 360, viewport 375), foco del aviso, no inscrito/lista oculta/pools no publicados/error y recuperación con Reintentar, horarios null/publicados y tag largo. Captura local /tmp/smash-mi-torneo-375.jpg; sin fixtures de producción.

Implementación fusionada en PR #107, squash 19ec520; CI 39077567317 verde en MySQL 8.0/MariaDB 10.11 y general. Despliegue assets-only 39077993177 correcto. Captura real 39078437363 **stored**: 310 inscritos / 12 grupos / 619 sets, 17 consultas / 34,738 s, 22033 B gzip / 310689 B JSON con espacios. Variables habilitada=true/evento=1687524 releídas. El intento anterior falló en fuente antes de guardar; la sonda de solo lectura posterior validó el mismo código antes de ejecutar esta prueba. Causa del rechazo anterior no reproducida. Evidencia y hash productivo intacto en EN-CURSO.md. No cambia cálculo, public.json, mains, elegibilidad, puntos o esquema. Prompt de diseño final en PENDIENTES-DUENO.md. Sin support.js ni datos de handoff.
