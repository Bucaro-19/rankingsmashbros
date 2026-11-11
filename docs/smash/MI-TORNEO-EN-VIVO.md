# Mi torneo por inscripción y próximo set

## Primer cambio

Legends 7 pasa al desplegable «Torneos finalizados». Solo se ofrece si el jugador vinculado aparece en el último snapshot privado. La vista inicial devuelve la ficha mínima del torneo archivado. El bracket se pide al seleccionarlo con `eventId=1687524`, previa comprobación de sesión e inscripción. Se muestra la fecha guardada y se retiran el aviso y las predicciones de próximo set del archivo. Una captura anterior al cierre puede omitir resultados finales.

La política de captura actual autoriza únicamente Legends 7 y ya venció. El archivo conserva su formato. Esta entrega prepara la selección histórica dentro de la pantalla existente.

## Validación del proveedor — 6/nov/2026 GT

- Una sonda acotada sobre un inscrito público de Legends 7 confirmó el mismo entrant y player en `event.userEntrant` y en la lista del evento. El filtro de sets devolvió 4 sets propios en una página, los 4 con ganador y hora de cierre. La sonda usó 3 consultas en 2,88 s. [Ejecución](https://github.com/Bucaro-19/rankingsmashbros/actions/runs/42304352416)
- `User.events` acepta filtros de juego, tipo, búsqueda, lugar y cantidad de inscritos. El esquema consultado carece de un filtro `upcoming`. Para ese mismo participante la conexión devolvió un solo evento y omitió Legends 7, pese a que el evento confirmó la inscripción. Para el piloto se eligen eventos de la agenda o internacionales y se configuran sus IDs. La ventana configurada mantiene el evento disponible mientras se juega, aunque la agenda deje de listarlo al comenzar. [Ejecución](https://github.com/Bucaro-19/rankingsmashbros/actions/runs/42304490030)
- El lector PHP pasó también con los datos reales del mismo evento. En 3 consultas, incluida la búsqueda del inscrito de prueba, encontró el último resultado y cero sets pendientes. Las sondas hicieron 8 solicitudes en total y solo registraron agregados. [Ejecución](https://github.com/Bucaro-19/rankingsmashbros/actions/runs/42304953539)
- La prueba corresponde a un torneo finalizado con lista pública. La visibilidad de listas ocultas y la latencia de resultados en un torneo activo se medirán aparte.

## Piloto integrado — 11/nov/2026 GT

En Tu cuenta → Mi torneo, «Buscar mis torneos» comprueba la inscripción en los eventos configurados. El selector agrupa los confirmados por horario en «En curso» y «Próximos». «Actualizar mi set» consulta start.gg durante la ventana del evento y muestra el último resultado reportado y el nuevo rival asignado, cuando existe. Los enlaces usan el ID de ese rival. Si la lista está oculta, la paginación no se puede completar o no hay una asignación inequívoca, la pantalla indica el estado y ofrece el enlace al bracket oficial. Si la consulta falla, conserva la última lectura con su hora. El archivo de Legends 7 sigue en «Torneos finalizados» y usa su última captura guardada.

`mi-torneo-api.php` conserva el GET de la captura privada. Las dos operaciones nuevas son POST con sesión, CSRF y vínculo vigente en SQL. `discover` comprueba una inscripción por evento. `refresh` vuelve a verificar el evento de Ultimate Singles, el usuario y el jugador vinculados antes de leer hasta dos páginas de 12 sets de su entrant. El lector comprueba que cada set devuelto le pertenezca. `event.state = COMPLETED` cierra la lectura aunque el horario configurado todavía no haya vencido. La ausencia de una asignación se muestra como pendiente. El organizador define cuándo registra el resultado. [Esquema de Event](https://developer.start.gg/reference/event.doc.html) · [Límites de start.gg](https://developer.start.gg/docs/rate-limits/)

El piloto consulta bajo demanda. El hosting reutiliza descubrimientos durante 120 s y lecturas de sets durante 30 s por cuenta, vínculo y evento. Usa un bloqueo privado compartido y un máximo de 12 intentos por 60 s, espaciados al menos un segundo. El archivo `mi-torneo-live-state.json` contiene resúmenes recientes y conteos de intentos, con permisos 600. Ante saturación responde 429 y el usuario puede volver a intentar. El GET de cuenta, el archivo y la agenda usan sus fuentes existentes.

## Preparar el primer torneo

1. Después de publicar el cambio, elige un evento real de Ultimate Singles con inscritos visibles. Anota el **ID del evento**, el enlace del evento en start.gg y el horario aproximado de inicio y cierre. Usa los datos de la agenda o el enlace del organizador.
2. En cPanel, crea `/home/ivcjgjlk/private-smash/mi-torneo-live.local.php` con permisos 600. Configura una llave de lectura de start.gg para este piloto. Guárdala directamente en el archivo privado.
3. Completa los datos del ejemplo y cambia `enabled` a `true` cuando vayas a probar. Se aceptan hasta tres eventos, con inicio hasta 14 días adelante y ventana de hasta siete días. Cada evento sale del selector cuando pasa su hora de cierre.

```php
<?php
return [
    'enabled' => false,
    'token' => '',
    'events' => [
        // Completa un evento real con esta estructura:
        // ['id' => 'ID_NUMERICO_DEL_EVENTO', 'name' => 'Nombre del torneo',
        //  'url' => 'https://www.start.gg/tournament/slug/event/ultimate-singles',
        //  'startAt' => strtotime('AAAA-MM-DD HH:MM:SS -06:00'),
        //  'endAt' => strtotime('AAAA-MM-DD HH:MM:SS -06:00')],
    ],
];
```

4. Desde una cuenta inscrita, abre «Mi torneo», busca la inscripción y actualiza el set al comenzar. Verifica que el primer enlace corresponda al rival asignado. Cuando el organizador reporte un resultado, mide cuánto tarda en aparecer el nuevo cruce y confirma el enlace. La caché del botón dura 30 s. Prueba también una cuenta sin inscripción.
5. Para cerrar el piloto anticipadamente, pon `enabled` en `false`. El archivo histórico sigue disponible.

Las pruebas con datos inventados cubren sesión, CSRF, eventos ajenos y fuera de horario, caché, límite global y cambio del enlace después de reportar una victoria. Queda pendiente medir el primer torneo activo, incluidos los casos de inscripción oculta y la demora de publicación de un set.

## Brief para Claude Design

Actualizá la pestaña gratuita «Mi torneo» de Tu cuenta usando el handoff actual. Diseñá un selector con **En curso**, **Próximos** y **Torneos finalizados**, con estos últimos cerrados al entrar. Mostrá título, evento de Ultimate, fecha, estado de inscripción y hora de última actualización. Usá el torneo activo como opción inicial cuando haya uno comprobado. Si no hay ninguno, mostrar un vacío breve y el archivo disponible.

Con el torneo en curso, hacé visible **«Actualizar ahora»** al lado de **«Última actualización»**. Diseñá cómo se ve el último resultado publicado, el próximo set, el rival confirmado y los botones para analizar a ese rival o preparar el set. Incluí ganador reportado con rival pendiente, paso a losers, eliminado, evento finalizado, lista o pools ocultos, rival sin historial y fallo temporal que conserva la última captura. Un rival probable lleva etiqueta propia.

Entregá móvil de 375 px y escritorio. Conservá la vista de bracket y la lista accesible, con foco visible y controles que se puedan usar con teclado. El archivo lleva «Torneo finalizado» y la fecha de la captura. No muestra una pelea pendiente como si fuera actual. Los botones de análisis conservan el acceso Premium existente.
