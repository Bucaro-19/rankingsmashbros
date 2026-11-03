# Fase 4: listado ligero y detalle con caché — estudio, 2/nov/2026 GT

Pedido del dueño: avanzar mientras llegan las tres observaciones de la fase 2. **No hay que esperar tres semanas:** el corte nacional es semanal; esta carga de historiales tiene disparos nominales cada seis horas. Tres cargas son del orden de 18 horas, sujetas a retrasos/concurrencia de Actions. No son una fecha prometida ni tres capturas manuales para rellenar la muestra.

Este estudio puede adelantarse independientemente de la fase 3. **No implementa ni activa otro capturador**, no modifica el cron, checkpoint, receptor, SQL, mains o ranking. Base revisada: main **1119acc** (#130), con cinco sets por página y games en la misma consulta. #131 prepara la evaluación de frecuencia, sin fusionar ni cambiarla.

## Esquema comprobado, no deducido

Una consulta de introspección de solo lectura [41573539060](https://github.com/Bucaro-19/rankingsmashbros/actions/runs/41573539060), a 1 petición/s mediante Client, sin personas, historiales, SQL, FTP, paquetes ni artefactos. Imprime solo tipos, campos y descripciones del esquema. La sonda de workflow era temporal en rama y se restaura antes del PR; **su modificación no entra en el diff final ni en main**.

- `Player.sets` admite `page`, `perPage`, `opponentId` y `filters`. **No admite sortType**: que exista el enum SetSortType con RECENT en otras conexiones no lo vuelve válido aquí. La descripción de opponentId se refiere al recorrido cabeza a cabeza, con restricciones propias; no autoriza ordenar el historial completo.
- `SetFilters` ofrece IDs de eventos/torneos/fases, estado, tamaño de entrant y `updatedAfter`, entre otros. **No tiene un filtro de temporada ni de fecha de inicio de evento.** updatedAfter se refiere a creación/actualización del set; no demuestra que la participación pertenezca a 2026.
- `Query.set` permite el ID real; la captura de personajes existente ya agrupa cinco consultas por alias. Reutilizar ese patrón exige comprobar los objetos del payload ampliado con marcadores por game: no asumir que el tamaño actual de characters.py admite cualquier detalle.
- `perPage` es Int. Esto confirma el argumento, **no que una consulta concreta con 50 nodos pase los límites del proveedor**. No se hizo una captura real de datos con ese tamaño ni se certifica un máximo.

La fuente oficial mantiene 80 solicitudes por 60 s en promedio y 1000 objetos anidados por consulta: [límites de start.gg](https://developer.start.gg/docs/rate-limits/). No resolver este problema con paralelismo ni tokens adicionales. Una página antigua o vacía no permite terminar el recorrido anticipadamente sin un orden contractual suficiente.

## Modelo reproducible sin red

Desde la raíz: `python3 scripts/smash/study_history_cost.py`. Es un modelo con cargas **inventadas**, no una captura, benchmark de Legends 7 ni estimación de su terminación. No requiere token, cuenta, base o caché y no escribe archivos. Cuatro pruebas en `test_study_history_cost.py` cubren el contraejemplo donde separar etapas gasta más, redondeo por jugador, identidades corregidas y datos inválidos.

Hipótesis: página pesada actual de 5; manifiesto propuesto de 50; detalle agrupado de 5. Ambos tamaños propuestos deben validarse con la API antes de implementar. El coste de listado se redondea **por jugador**, no sobre un total agregado; el detalle se deduplica por versión entre jugadores cuando su vínculo real esté probado. Los aciertos de caché son una entrada hipotética **ya validada**, nunca deducidos de que exista una fila SQL.

| Carga inventada | Consultas actuales | Lista ligera | Detalle faltante | Lista + detalle |
|---|---:|---:|---:|---:|
| Un historial de 1000 sets, 50 de la temporada, caché fría | 200 | 20 | 10 | 30 |
| Los 1000 de la temporada, todos nuevos | 200 | 20 | 200 | **220** |
| Primer caso, manteniendo páginas ligeras de 5 | 200 | 200 | 10 | **210** |
| Cuatro historiales de 250, 500 sets únicos de temporada, 400 versiones en caché validada | 200 | 20 | 20 | 40 |
| Cien historiales de 5, todos de temporada y nuevos | 100 | 100 | 100 | **200** |

La separación **no es una mejora universal**. Su valor depende de poder listar más por llamada, descartar temporadas que no se necesitan y reutilizar detalle válido. No afirmar que nuestros 165 pendientes tienen la distribución del primer ejemplo. El modelo excluye roster, inventarios/cache del hosting, reintentos, límites reales de objetos, cambios de paginación y esperas de importación. No multiplicar estas cifras para anunciar sets por día o ETA.

Payload ilustrativo: cinco nodos pesados con diez games inventados cada uno, **16384 B JSON / 672 B gzip / 484 diccionarios JSON**. Cincuenta manifiestos de identidad, **16261 B JSON / 443 B gzip / 554 diccionarios**. Los nombres y valores repetidos hacen que la compresión sea artificialmente favorable; no son tamaños de respuestas reales. **Diccionarios JSON no equivalen al coste de complejidad de start.gg**, por lo que estar por debajo de 1000 en este conteo no certifica ninguna consulta.

## Caché: condiciones antes de contar un acierto

El capturador de personajes nacional tiene caché por fingerprint y vigencia de siete días; el capturador automático de análisis hoy **no comparte esa caché**. Su checkpoint compacto no guarda las páginas ya confirmadas. No importar la política nacional de selección de mains ni trasladar su caché directamente al análisis.

Una propuesta de clave incorpora ID del set, updatedAt, fingerprint de metadatos/identidades y versión del formato de detalle. Los campos que permiten detectar cambios incluyen evento, estado, ganador, marcador y los IDs reales de entrants/jugadores; los nombres no sustituyen a los IDs. El manifiesto del modelo conserva identidades para hacer visible su corrección, sin traer perfiles completos ni personajes.

Antes de reutilizar detalle: entrada íntegra y vigente, versión conocida, metadatos coincidentes y fuente procesada/validada. Un timestamp ausente o campos cambiados impiden dar por válido el acierto. No se ha demostrado que start.gg cambie updatedAt ante toda corrección de personajes: hace falta vigencia/revalidación, con política acordada y coste medido. `games: []` observado y detalle no consultado/ausente son estados distintos; no convertir desconocido en cero ni cachear un fallo como vacío.

Encontrar un set en SQL no prueba que todo su detalle esté capturado ni que corresponda a la versión listada. Los importadores actuales conservan resultados/games previos y la prioridad nacional; una caché no debe permitir sobrescribirlos o resolver identidades automáticamente. Para un set compartido entre raíces, el detalle validado debe acreditar a cada jugador por los slots: no se elimina la protección contra sets sin vínculo que añadió #115.

Persistencia propuesta: privada en hosting, limitada y por el canal firmado existente, sin caché compartida pública ni dataset de personas en Actions/Git. Inventariar versiones y entregar detalle añade tráfico al receptor, que **no está incluido** en el modelo API y debe medirse. No se ha creado ningún directorio, operación del receptor ni entrada de caché en producción.

## Checkpoint: la migración de protocolo es el punto delicado

El estado vigente es `stateVersion=1`, con nextPage/totalPages/complete por jugador; el servidor valida estrictamente sus campos y exige avance real de página en cada importación. **No cambiar perPage de 5 a 50 conservando esos nextPage**: la misma página representa otro intervalo y podría saltarse datos. Tampoco dividir el cursor por diez y confiar en que la lista permaneció estable.

Una captura en dos etapas necesita distinguir, al menos:

| Listado | Detalles pendientes | Importación confirmada | ¿Historial completo? |
|---|---|---|---|
| Parcial | Cualquiera | Solo lo confirmado | No |
| Terminado | Sí | Parte o ninguno | No |
| Terminado | Ninguno | No / respuesta incierta | No |
| Terminado | Ninguno | Sí, recibo y checkpoint coherentes | Solo el recorrido planificado; no promete que la fuente tenga todos los personajes |

No introducir esos campos en V1: `rc_validate_envelope`/`rc_progress` los rechazarían. Un futuro V2 debe convivir con V1 en receptor/worker antes de cambiar Actions; requiere paridad Python/PHP, límites, CAS, recibos, recuperación tras commit y tests de regresión. **No se requiere una migración SQL por el solo concepto**, pero no se confirma que pueda implementarse sin ninguna hasta diseñar almacenamiento y auditoría.

Reanudación segura propuesta para implementar después: mantener las raíces V1 en su camino actual hasta terminarlas; habilitar otro recorrido versionado solo para raíces nuevas bajo política explícita. Alternativa: migración simulada/validada de cada checkpoint y recibo, nunca una transformación aritmética de páginas. No resetear ni volver a recorrer todo Legends 7 para medir una optimización. El diseño debe permitir confirmar detalles sin fingir avance de un listado que ya terminó, lo que exige revisar el contrato actual del receptor.

## Siguiente paso, independiente de la espera

1. Reunir las tres observaciones reales de #130 y usar el evaluador de #131 para conocer rendimiento útil/esperas. No aumentar frecuencia para esconder páginas que no aportan datos.
2. Si las observaciones justifican la hipótesis, validar en una **sonda de datos pequeña de solo lectura** los tamaños/consistencia del manifiesto y detalle por alias, usando versiones coincidentes y sin imprimir personas. La introspección de este estudio no reemplaza esa medición. No publicar capturas ni usarlas para cambiar el corte.
3. Diseñar V2/caché con compatibilidad y simulación, y comparar contra V1 sobre el mismo material. Pruebas: correcciones, updatedAt nulo, detalle ausente, errores, raíces compartidas, conservación de prioridad nacional y checkpoint antiguo, interrupciones y paridad de ambos motores.
4. Abrir la implementación como PR separada; receptor antes de capturador, sin migración o escritura extraordinaria sin orden. Mantener V1 y límites actuales hasta comprobar beneficio y autorizar el cambio. No presentar este estudio como una fase 4 ya activada.
