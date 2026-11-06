# Mi torneo por inscripción y próximo set

## Primer cambio

Legends 7 pasa al desplegable «Torneos finalizados». Solo se ofrece si el jugador vinculado aparece en el último snapshot privado. La vista inicial devuelve la ficha mínima del torneo archivado. El bracket se pide al seleccionarlo con `eventId=1687524`, previa comprobación de sesión e inscripción. Se muestra la fecha guardada y se retiran el aviso y las predicciones de próximo set del archivo. Una captura anterior al cierre puede omitir resultados finales.

La política de captura actual autoriza únicamente Legends 7 y ya venció. El archivo conserva su formato. Esta entrega prepara la selección histórica dentro de la pantalla existente.

## Siguiente entrega

1. **Inscripciones y selector.** Mostrar en curso primero, luego próximos y finalizados en su propio desplegable. Para el primer piloto usar eventos de Ultimate Singles de la agenda y eventos internacionales configurados de forma explícita. Validar la inscripción por ID vinculado. El esquema de start.gg documenta `event.userEntrant(userId: …)`. Comprobar su visibilidad con la cuenta y el token de prueba antes de asumir que devuelve registros privados o listas ocultas. Inscripción no verificable, inscripción inexistente y pools sin publicar son estados distintos. [Referencia de Event](https://developer.start.gg/reference/event.doc.html)
2. **Estado en vivo.** Durante el torneo, «Actualizar ahora» llama al backend autenticado. Este consulta sets del evento filtrados por el entrant comprobado en el servidor. Pedir solo ID, estado, ganador, ronda, slots y sus prerequisitos, con paginación y topes. Mantener la captura completa para horarios, pools y grafo cuando esté disponible. Confirmar primero con una sonda acotada cómo responde el filtro a slots sin asignar, fase nueva, winners, losers y DQ. [Sets de un evento](https://developer.start.gg/docs/examples/queries/sets-in-event/) · [SetFilters](https://developer.start.gg/reference/setfilters.doc.html)
3. **Cuota y datos viejos.** Propuesta de caché privada de 30 segundos por evento e inscripción, con una sola consulta en curso por clave y presupuesto global para el token. El servidor puede reutilizar una respuesta reciente. Refrescar al volver a la pestaña y permitir actualización manual. Cualquier refresco periódico debe limitarse a la pantalla visible y al periodo activo. Si start.gg tarda o limita la consulta, mostrar la fecha de la última lectura exitosa y ofrecer el enlace al bracket oficial. Medir la carga antes de activar. El token va en configuración privada del servidor. [Límites de start.gg](https://developer.start.gg/docs/rate-limits/)
4. **Próximo rival.** Avanzar solo tras un ganador o slot confirmado en start.gg. Mostrar el último set reportado, la ronda y «Rival por confirmar» cuando falte el otro resultado. Distinguir fase pendiente, entrada a losers, eliminado y torneo finalizado con evidencia explícita. Si se conoce el rival, enlazar a su análisis con los controles existentes. Si no tiene historial suficiente, señalar ese estado y ofrecer el modo por personaje cuando esté disponible.

La velocidad real depende del reporte del resultado y de cuándo start.gg publique el cruce. Medir con un evento de prueba antes de fijar una expectativa.

## Brief para Claude Design

Actualizá la pestaña gratuita «Mi torneo» de Tu cuenta usando el handoff actual. Diseñá un selector con **En curso**, **Próximos** y **Torneos finalizados**, con estos últimos cerrados al entrar. Mostrá título, evento de Ultimate, fecha, estado de inscripción y hora de última actualización. Usá el torneo activo como opción inicial cuando haya uno comprobado. Si no hay ninguno, mostrar un vacío breve y el archivo disponible.

Con el torneo en curso, hacé visible **«Actualizar ahora»** al lado de **«Última actualización»**. Diseñá cómo se ve el último resultado publicado, el próximo set, el rival confirmado y los botones para analizar a ese rival o preparar el set. Incluí ganador reportado con rival pendiente, paso a losers, eliminado, evento finalizado, lista o pools ocultos, rival sin historial y fallo temporal que conserva la última captura. Un rival probable lleva etiqueta propia.

Entregá móvil de 375 px y escritorio. Conservá la vista de bracket y la lista accesible, con foco visible y controles que se puedan usar con teclado. El archivo lleva «Torneo finalizado» y la fecha de la captura. No muestra una pelea pendiente como si fuera actual. Los botones de análisis conservan el acceso Premium existente.
