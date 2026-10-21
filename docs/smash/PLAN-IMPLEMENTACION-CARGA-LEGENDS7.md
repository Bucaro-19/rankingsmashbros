# Plan de implementación — historiales de Legends 7

19/oct/2026, Guatemala. Pedido del dueño: publicar la barra y preparar el plan; **este documento no activa una frecuencia nueva ni cambia el capturador**. Continuación de [MEJORAS-CARGA-LEGENDS7.md](MEJORAS-CARGA-LEGENDS7.md). El plazo de importación ya autorizado termina el **26/oct a las 00:00 GT**. No extenderlo para cumplir el plan.

**20/oct:** fase 1 fusionada y activada por orden posterior del dueño, PR #114 y corrección #115. Política definitiva 3:1, pruebas y mediciones en AUTOMATIZACION-ANALISIS.md y MEJORAS-CARGA-LEGENDS7.md. La frecuencia sigue en seis horas; fases 2–4 pendientes.

## Resultado que buscamos

Que más inscritos tengan datos utilizables pronto, que los historiales largos sigan avanzando y que el panel explique el avance confirmado. No prometer una fecha de finalización ni considerar «identidad conocida» como «historial completo». Sin servicios nuevos o cuota adicional contratada; más ejecuciones sí consumen más consultas y minutos de Actions.

## Base y límites que se conservan

- Evento 1687524, solo contexto de análisis, canal firmado → cola → worker existente. Sin acceso de Actions a MySQL.
- Dos tandas por ejecución; cada tanda conserva 30 intentos HTTP incluyendo reintentos, 120 segundos y una petición por segundo. Sin paralelizar recolectores; misma concurrencia smash-gt-publication.
- Misma autorización de entidades y 007, validación, hashes, recibos, CAS, checkpoint activo después del commit, recuperación de .pending y already_imported. No reiniciar cobertura ni repetir páginas confirmadas para probar rendimiento.
- Ranking, elegibilidad, puntos, mains, cortes y public.json fuera del alcance. Sin migraciones ni cPanel nuevo.
- El registro oficial de start.gg documenta 80 solicitudes por 60 segundos como promedio y 1000 objetos anidados por consulta: https://developer.start.gg/docs/rate-limits/ . No usar otros tokens para repartir cuota.

## Fase 0 — Barra y línea de base

Publicar PR #112 con CI general/MySQL 8.0/MariaDB 10.11 verde y assets_only=true. Verificar hash público antes/después, 401 anónimo del panel y nuevas versiones de panel.js/css. La barra lee exclusivamente el checkpoint confirmado; no consulta start.gg ni hace polling.

Registrar las siguientes ejecuciones normales: inscritos, objetivos, finalizados, parciales, sin iniciar, páginas, consultas y duración. El ejemplo observado 39344382294 tuvo 320 inscritos, 108 identidades conocidas al inventariar y 249 historiales pendientes; conocidos y pendientes se solapan. No usar 320−249 como prueba de temporadas completas.

## Fase 1 — Repartir las páginas (primera PR de código)

Archivos principales: scripts/smash/rival_history.py, scripts/database/rival_automation.py y sus pruebas. Sustituir el while que agota un jugador por selección de una página por turno. Orden inicial: menor nextPage, desempate por ID estable; volver a evaluar después de cada página. Así un ID bajo con 200 páginas no impide que otros reciban su primera página. El orden se deriva de cobertura, no del orden de claves JSON, que se canonicaliza.

Antes de fijar el algoritmo, simular también entradas nuevas entre tandas: si retrasan demasiado a parciales, reservar una de cada cuatro oportunidades para parciales existentes, con rotación verificable. No introducir un cursor persistido sin revisar el contrato estricto de checkpoint en Python/PHP. La regla final y su garantía deben quedar en la PR; no fingir equidad con un for que siempre empieza por el mismo ID.

Pruebas de aceptación con datos inventados:

1. Un historial enorme y muchos cortos: todos los objetivos reciben turno antes de profundizar repetidamente el enorme; se conserva cada nextPage confirmado.
2. Presupuesto agotado a mitad, reintentos y nueva ejecución: cero retrocesos, cero repetición de páginas confirmadas, cero envío de captura parcial tras error.
3. Nuevos inscritos entre tandas y parciales previos: ambos grupos avanzan según la regla documentada, sin reiniciar a conocidos que aún tienen coverage.
4. Sin inscritos, sin pendientes, expirado, receptor ocupado, job pendiente/fallido, caída antes/después del commit: contratos existentes intactos.
5. Paridad Python/PHP, acceso gratis/premium y no modificación del ranking en MySQL 8.0 y MariaDB 10.11.

Medir con la misma cantidad de intentos: jugadores distintos que avanzan y cuántos quedan sin primera página. Criterio para avanzar: distribución demostrablemente mejor, ninguna pérdida de contexto, todos los techos y pruebas conservados. Captura repetida no se hace en producción como benchmark: usar próximas tandas autorizadas y sus agregados tras desplegar con orden del dueño.

## Fase 2 — Métricas útiles y verificación (PR separada)

Añadir agregados seguros al resumen: jugadores con avance, páginas nuevas, sets de temporada aceptados, segundos de captura y segundos de espera de cola/worker. Ningún tag, ID de jugador, cuerpo GraphQL o credencial. Revisar si una página sin sets útiles está consumiendo el presupuesto. Antes de podar historial por fecha, comprobar en el esquema un orden/filtro contractual: la primera página actual no garantiza los sets más recientes.

Mantener finalizados/objetivos en la barra y páginas aparte. Si se muestra disponibilidad básica, contar objetivos con al menos una página confirmada y rotular «captura iniciada», no «historial completo» ni «rival listo»: una página puede no contener sets válidos de 2026. No inventar ETA a partir de identidades añadidas.

Observar al menos tres ejecuciones normales (aprox. 18 h con el cron actual, sujetas a retrasos de Actions). Si queda poco plazo antes de Legends 7, priorizar fase 1 y medir; no omitir validaciones para alcanzar las demás.

## Fase 3 — Frecuencia temporal de dos horas (solo tras evaluar fase 2)

Proponer cron 37 */2 * * *, con los mismos techos y expiración. Son como máximo doce disparos previstos y unas 672 páginas/día en lugar de 224; no son sets útiles garantizados. A 320 inscritos, el roster cuesta aproximadamente siete consultas por ejecución, más reintentos. GitHub puede retrasar o perder disparos programados; no prometer una revisión cada dos horas exactas.

Condiciones: sin jobs fallidos por revisar, sin crecimiento persistente de cola, sin 429 y sin conflicto con semanal/bracket/agenda. Conservar cancel-in-progress=false y no bajar el cron de cPanel. Actualizar el texto de seis horas en el panel, documentación y pruebas de cron en la misma PR. Desplegar bibliotecas antes de activar el nuevo flujo. Si hay 429, mayor cola o esperas hasta timeout, volver al cron previo; no aumentar intentos para compensar. La activación requiere orden de publicación para esta nueva PR.

## Fase 4 — Captura ligera y detalle (posterior; no requisito para Legends 7)

Investigar lista ligera de sets y posterior detalle de games/personajes con caché por set ID + updatedAt. Antes de implementarlo: confirmar campos/orden del esquema, comparar consultas y tamaño con la consulta actual, y demostrar cómo el checkpoint distingue ambos recorridos sin marcar completo el detalle pendiente. Si aumenta consultas o requiere un contrato/migración no autorizados, dejar estudio y no activar. Datos ausentes siguen ausentes; ningún personaje o resultado se estima.

## Publicación y reversión de cada fase

Una PR por cambio, documentación EN-CURSO y AUTOMATIZACION-ANALISIS actualizada, CI general y ambos motores verde. Sin escritura manual de producción. Pedir orden para fusionar/desplegar cambios posteriores a la barra; la autorización vigente de importación sigue limitada al evento y plazo originales. Verificar public.json idéntico tras cada assets-only.

Para detener futuras capturas: gh variable set SMASH_RIVAL_SYNC_ENABLED --body false. No cancela un run ni un job ya aceptado: revisar ambos antes de intervenir; nunca borrar recibos, cobertura o trabajos fallidos a ciegas. Volver al código anterior solo si puede leer el checkpoint conservado. Al vencer el plazo, el proceso debe salir sin consultar ni importar aunque la variable continúe encendida.

## Entregables para Claude Code

1. PR de rotación y simulaciones; documentar algoritmo definitivo y medición.
2. PR de métricas agregadas y comparación de tres tandas normales.
3. PR de cron temporal solo si los resultados justifican aumentarlo; la fecha límite no cambia.
4. Estudio de captura ligera/detalle, independiente, sin bloquear las anteriores.

No hay paquetes privados ni listas de inscritos en este documento o en artefactos públicos.
