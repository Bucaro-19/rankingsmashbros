# Mi torneo: bracket privado de Legends 7

## Alcance

Sección gratuita en Tu cuenta. El diseño provisional del 17/oct se reemplaza en la entrega del 18/oct por el handoff final `design_handoff_rsb_mi_torneo/`. No es la pestaña premium de tops «Mis torneos». Muestra fases/grupos propios, horarios GT/local, primer set pendiente y rival confirmado o probable, camino posible si ganas, rival con mejor puesto conocido en el ranking combinado o menor seed si nadie tiene puesto, y lista del pool. Sin puesto no equivale a débil. Los enlaces de análisis conservan los controles premium existentes.

Los botones junto a **Tu primer set pendiente** analizan a su oponente (con su nombre en cada botón). Los del rival de referencia permanecen en su sección, también con nombre y aclaración de que puede ser otra persona. Sin oponente o sin enlace no se sustituye por el rival de referencia ni se muestra un botón inventado.

## Captura y límites

`scripts/database/my_tournament_sync.py` reutiliza collect.Client/BudgetClient: una petición/s incluyendo reintentos, dos tandas como máximo de 30 intentos/120 s cada una. Máximo 1000 inscritos, 100 grupos, 5000 seeds/sets, 8 MiB JSON / 4 MiB gzip. Solo publica una captura completa y validada; falla en rojo y conserva la anterior si se exceden límites o cambia la paginación. Sin artefactos, caché pública ni MySQL en Actions. No extender límites a ciegas.

Esquema oficial inspeccionado en Actions 39076192675 (dos consultas): **Event.phaseGroups es una lista sin argumentos**; seeds y sets se paginan independientemente. Conexiones ya agotadas pueden devolver total cero: se ignora solo la ya acabada, no un cambio de total en una página activa. Tres grupos por consulta, 24 seeds/sets por página; nunca slots.stats.

Horarios nulos/0 quedan null. Pool: startAt, luego wave.startAt, luego firstRoundTime, con fuente explícita. Set.startAt ya puede incluir fallback de ronda del proveedor: etiqueta «Horario de set/ronda de start.gg». Si falta, se usa el horario del pool etiquetado; nunca el inicio del evento como si fuera un set. Sin fecha: «Horario aún no publicado». Zona ausente: hora local null, no estimada.

IDs opacos preview_* se conservan, no se inventan IDs SQL. Camino por slots.prereqType=set/prereqId/prereqPlacement=1, ganador real si existe y, en caso contrario, seed menor cuando ambos se conocen. No se inventa un bracket estándar ni se adivinan rivales sin seeds. Solo se salta un bye marcado isBye: un slot null no prueba un bye. opponentConfirmed distingue primer rival real de probable. Memoización, detección de ciclos y profundidad acotada.

## Archivo y seguridad

Receptor HMAC/nonce existente ranking-sync.php, tipo application/vnd.smash.bracket+gzip, **antes de abrir PDO**. bracket-store.php valida esquema cerrado/tipos/relaciones/tamaños y escribe private-smash/brackets/1687524.json, fuera del sitio, permisos 0600/directorio 0700, lock y temp+rename. Repetición idéntica: already_stored. Fecha vieja o contradictoria con igual fecha: rechazo sin reemplazar. Captura de máximo 30 minutos, no futura >60 s; entrega cerrada al terminar autorización. Sin cola SQL ni dependencia de 007. Bibliotecas negadas por .htaccess antes de desplegar.

GET mi-torneo-api.php sin parámetros. Sesión reanudada y **users.player_id vigente** mediante smash_account_current; 401 anónimo/revocado, 405 otros métodos, 400 si intentan elegir jugador/pool/evento. Gratis/admin obedecen la misma identidad. Solo salen los pools que contienen al jugador de la sesión; nunca roster completo del evento, prerequisitos internos, IDs de seed, cuentas/correos/pagos o estadísticas premium. El grafo ampliado expone solo referencias entre sets del propio pool, con nombres de campos de presentación. Player IDs de miembros propios únicamente sirven a los enlaces existentes de análisis. Cache-Control no-store, private; X-Robots-Tag noindex; sin CORS ni start.gg por visita. Logout limpia DOM y aborta; respuestas tardías se descartan.

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


## Diseño final y contrato ampliado — 18/oct

La pestaña gratuita **Mi torneo** aparece después de Mis torneos (esta última sigue condicionada al catálogo). El aviso de siete días abre esa pestaña y lleva el foco al contenido; se oculta mientras ya estás dentro de ella. No se cambia la pestaña premium de organizadores. Navegación de pestañas de cuenta y de bracket separadas, con flechas, Home/End y foco visible.

Se conserva el contrato existente y se amplía sin cambiar el archivo privado/captura ni su versión:

- `event.discipline`, `event.country`, `event.timezone`: metadatos ya presentes en la captura. No se inventa ciudad.
- Cada miembro (también dentro de firstSet/strongest/bracket): `isMe` identifica al jugador de la sesión; `characters` es null o `{source: "profile" | "detected", mains: [{characterId, games}]}` (máximo tres). `games` es null para preferencias de perfil. No se convierte en sets, proporciones ni selección futura.
- Los detectados proceden exclusivamente de los mains del ranking ya público. Si hay elecciones, se prefieren: una consulta SQL de solo lectura, limitada por los player IDs de los pools ya autorizados, lee únicamente IDs de personajes ordenados de perfiles activos y vinculados. No consulta historiales premium, otras cuentas ni start.gg. No salen IDs internos de cuenta o datos de la conexión. Sin datos se muestran iniciales/«Sin personaje registrado».
- `pool.bracket`: null si no hay sets disponibles; en caso contrario `{sets: [...]}`. Cada set tiene `id` opaco de fuente, `round`, `label`, `side` W/L/null, `state`, `finished`, `isMine`, `time` (solo horario propio del set/ronda; sin fallback) y `slots`.
- Cada slot: `index`, `member` confirmado o null, `possibleMember` según seeds o null, `from: {setId, outcome: "winner" | "loser"}` o null, `isBye`, `isWinner`, `score: null`. Solo se exponen enlaces a sets del mismo grupo. No se entregan entrantId/seedId/prereqId internos. Marcadores no capturados permanecen null incluso si hay un ganador.
- La resolución confirmada sigue resultados/bye explícito. El rival probable permanece marcado; nunca avanza al jugador solo por su seed. Ciclos, huecos y falta de seeds conservan los vacíos.

El versus usa assets locales de `assets/characters`, resueltos por characterId contra el catálogo existente. No se descarga un retrato de la sección hasta mostrarla; solo se insertan el main de cada lado y hasta dos íconos secundarios. No se precargan los 147 assets ni los de otros miembros. Error de imagen conserva iniciales y avisa «retrato no disponible». Guardar personajes refresca el resumen de la sección, sin start.gg.

Horarios: si firstSet.time.source no es set_or_round, el número grande se etiqueta «Inicio del pool · no es la hora de tu set» y la fila del set queda «Sin programar». Si existe horario de proveedor, se etiqueta «horario de set/ronda de start.gg»: no se promete una precisión que el proveedor no garantiza. GT/local coincidentes se unifican; distintos permanecen ambos, con fecha. Sin hora no hay reloj inventado ni cuenta regresiva.

Bracket: Mi camino por defecto a menos de 760 px; Bracket en escritorio. Winners/Losers se dibujan por rondas reales, tarjetas legibles con scroll horizontal propio, conexiones reales en codo, próximo set destacado. Las conexiones entre lados se identifican por «Ganador/Perdedor de W…/L…» en cada casilla. Lista conserva nombres completos/seed/ganador/horarios y es la alternativa accesible. Sin grafo solo existe Mi camino, con aviso de información parcial. No se dibuja un cuadro estándar por seeds. No se anticipan fases no asignadas ni reglas de avance.

Pruebas y revisión: ver bloque de entrega del 18/oct en EN-CURSO.md. No se fusiona/despliega como parte de la implementación sin completar revisión y CI. No hay escrituras productivas, migraciones, cambios del cálculo/elegibilidad/public.json ni nuevas consultas de captura.
