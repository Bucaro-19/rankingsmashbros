# Revisión del esquema para cuentas y torneos en curso

Revisión del 7 de octubre de 2026. **Modelo incorporado después de aprobación del dueño en `schema.sql`/`install.sql`; la instalación y módulos PHP siguen pendientes. Ver `BASE-DE-DATOS.md` como estado vigente.** El esquema actual es una propuesta para copiar el ranking publicado a MySQL; todavía no cubre toda la experiencia de cuentas y competición en vivo. Este documento recomienda cambios: no modifica las tablas ni presupone que se hayan creado.

## Lo que sirve de base

- `users` separa la cuenta de `players`: puede haber jugadores sin cuenta y cuentas sin jugador vinculado. Vincular solo mediante identidad OAuth verificada, nunca mediante el alias.
- `cuts` + `rankings` conserva puestos por fecha y vista, adecuado para evolución del ranking.
- `characters` + `player_characters` conserva el uso detectado por corte y vista. El personaje elegido por la persona debe seguir separado.
- `events` + `sets` sirve para resultados terminados admitidos. `survey_responses` es independiente de competición y debe conservar el compromiso de anonimato.

## Cambios necesarios antes del módulo de competición

1. **Torneo y evento:** añadir `tournaments` y `events.tournament_id`. Un torneo puede contener Ultimate Singles, doubles y otras competiciones. Usar esta única entidad para agenda, eventos pasados y torneos en curso; evitar dos fuentes independientes entre `upcoming_tournaments` y los torneos históricos. Conservar fechas/hora UTC, zona horaria, estado y fecha de sincronización.
2. **Participación:** añadir `entrants` (ID start.gg, event_id, nombre y clasificación) y `entrant_players` (entrant_id, player_id). Aunque inicialmente sea singles, estos vínculos distinguen al jugador permanente de su inscripción concreta. Registro, check-in si la API lo permite y participación competitiva son estados distintos; no deducir asistencia únicamente de la inscripción. La posición final del torneo no es el puesto nacional.
3. **Enfrentamientos pendientes:** el `sets` actual exige ganador y perdedor, por lo que no admite un set que todavía no se jugó. Añadir estado, ronda, fase/grupo, horarios disponibles, estación si existe y `source_updated_at`/`synced_at`; resultado ganador/perdedor nullable hasta terminar. Añadir `set_slots` para los dos lados y sus entrant_id/score nullable: el rival puede no estar definido todavía. Conservar los IDs de entrant necesarios para las mutaciones de start.gg, distintos de player_id.
4. **Resultado estructurado:** guardar marcador numérico por lado y banderas/estado de DQ, bye y W/O según la fuente. `displayScore` sirve de presentación, no como única estructura para todas las consultas. Los sets en curso y excluidos nunca puntúan por estar almacenados.
5. **Organización y permisos:** sustituir el único `users.role` por roles múltiples si se mantiene esa clasificación, y añadir membresías/roles verificables por torneo. Una persona puede jugar y organizar. Autoidentificarse como organizador no otorga permisos de reporte. La asociación con torneos también permite seleccionar eventos para el top 15, pero no define todavía su fórmula ni su política de atribución.
6. **Cobertura de perfiles:** importar los oponentes que aparezcan en los sets, incluidos extranjeros y jugadores sin ranking nacional, para satisfacer las claves foráneas. Mostrar «sin datos suficientes» cuando falte su historial. Separar las competiciones consultables de las competiciones admitidas por un corte: un torneo de menos de 20 activos puede aparecer en la cuenta sin contar para el ranking.
7. **Cortes reproducibles:** añadir vínculos de cada corte con los eventos y versiones de resultados utilizados (o una captura inmutable identificada por hash). Consultar `sets` mutable no debe cambiar retrospectivamente la explicación de un ranking ya publicado. Las estadísticas del rival deben indicar temporada, vista, fecha de corte y alcance del historial.

## Módulos posteriores previstos

- **Reportes de resultados:** `result_submissions` para cada propuesta de jugador y su revisión; conservar ambos envíos y sus versiones, no sobrescribirlos. Coincidencia significa «ambos coinciden», no que el resultado ya fue validado en start.gg. Antes del envío, releer el set, verificar permisos reales y registrar la respuesta; después reconciliar. La lectura previa por sí sola no elimina una carrera con otro administrador. Usar registro de auditoría/estado de envío y evitar reintentos a ciegas.
- **Notificaciones:** preferencias, suscripciones Web Push/dispositivos si se implementan y entregas con deduplicación por usuario, set y transición. Alertar «ya te toca» solo con una señal que lo respalde; un set pendiente con rival asignado no garantiza que el organizador lo haya llamado.
- **Games y selecciones:** el agregado actual de mains sirve para mostrar personajes más usados. Añadir `games` y selecciones por entrant si se quiere historial por partida, enfrentamientos por personaje o etapas. No se puede reconstruir ese detalle a partir del agregado.
- **Mains elegidos:** `users.chosen_main_id` cubre uno. Si se permitirán secundarios elegidos, usar una relación ordenada usuario/personaje. Mantener cantidades y cobertura de selecciones automáticas aparte.
- **OAuth:** identidad básica con `user.identity`; reportar requiere `tournament.reporter` y acceso real de ese usuario al torneo. Si se necesita conservar acceso entre sesiones, resolver credenciales OAuth cifradas en servidor, caducidad, revocación y renovación. La nota actual «sin tokens guardados» requiere revisar esa decisión antes de reportes persistentes. No guardar tokens en claro ni en el navegador.

## Frecuencia de datos

El ranking sigue con corte semanal. «Mi próximo rival» necesita una sincronización aparte durante el torneo, con caché compartida, paginación, límites de API y marca visible de última consulta. Al principio, consultar bajo demanda o actualizar periódicamente mientras la pantalla esté activa; fijar el intervalo después de medir cobertura y consumo. Ninguna tabla por sí sola garantiza tiempo real ni notificaciones con la web cerrada.

## Orden recomendado

1. Confirmar qué tablas existen realmente antes de alterar `schema.sql`; `CREATE TABLE IF NOT EXISTS` no migra columnas de tablas ya creadas.
2. Ajustar el modelo de torneo/evento, participación, sets pendientes y permisos. Mantener el importador del ranking independiente.
3. Implementar cuentas y perfil/historial con importación transaccional e idempotente, conservando la lectura pública por JSON durante la transición.
4. Probar lectura autenticada de un torneo real en curso y casos de rival aún sin asignar. Después activar vista del próximo rival.
5. Reportes y notificaciones como módulos posteriores, con pruebas de permisos, conflictos y duplicación.

## Referencias oficiales comprobadas

- Entidades: https://developer.start.gg/docs/glossary/
- Historial: https://developer.start.gg/docs/examples/queries/sets-by-player/
- Entrants de un set: https://developer.start.gg/docs/examples/queries/set-entrants/
- Estado y marcador en curso: https://developer.start.gg/docs/examples/queries/set-score/
- Posición en evento: https://developer.start.gg/docs/examples/queries/event-standings/
- OAuth y renovación: https://developer.start.gg/docs/oauth/oauth-overview/
- Permisos: https://developer.start.gg/docs/oauth/scopes/
- Reporte: https://developer.start.gg/docs/examples/mutations/report-set/

Las consultas para determinar «próximo set», llamada a estación y permisos de un torneo concreto requieren pruebas autenticadas antes de prometer disponibilidad completa.
