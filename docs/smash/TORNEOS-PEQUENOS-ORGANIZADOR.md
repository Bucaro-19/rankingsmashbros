# Torneos pequeños: contexto SQL separado del ranking nacional

Estado: implementación en `feat/organizer-small-events`, desde main `224d413` (8/oct/2026). Sin fusionar, desplegar, aplicar 006 ni escribir en producción. No se modifica la pantalla/API del organizador. La ampliación semanal está **apagada por defecto**; necesita una decisión del dueño sobre cobertura y costo. No se cambió ninguna variable del repositorio.

## Captura y costo comprobado

No se usa `discover.py --include-small`: es una herramienta de estudios que mezcla los eventos con el grafo evaluado por el ranking. La carga semanal añade, solo al habilitar la ampliación, `--organizer-candidates`: una lista privada obtenida de la misma consulta de catálogo, sin consultas adicionales, sin añadir jugadores, eventos ni sets al grafo nacional. Si falla esa selección opcional, deja `organizerCandidates: null` y conserva la captura nacional.

`scripts/smash/organizer_small.py` descarga el complemento aparte usando `Client` y `fetch_event`: entrants, standings y sets. No descarga games, personajes ni países extranjeros; tampoco agrega jugadores pequeños a las semillas de la búsqueda internacional. La captura nacional se conserva byte por byte. Se requieren eventos completados, Ultimate, singles, Guatemala, inscritos conocidos entre 1 y 19, dentro de la temporada y ambos indicadores online explícitamente falsos. **Limitación conservadora:** un evento presencial en un torneo mixto cuyo indicador general sea online queda fuera; los indicadores desconocidos también. No se promete cobertura completa de todos los torneos del país.

Medición real de solo lectura del **8/oct a las 20:25 de Guatemala**, ventana 1/ene–9/oct (fin exclusivo): [Actions 37874502707](https://github.com/Bucaro-19/rankingsmashbros/actions/runs/37874502707). Se utilizó temporalmente el runner de comprobación de dueños, en esta rama y con el grupo de concurrencia de publicación; su archivo original fue restaurado y no cambia en la PR. Solo se usó el secreto de start.gg; sin FTP, SQL, publicación ni artefacto público de personas.

| Medición | Resultado |
| --- | ---: |
| Candidatos pequeños descubiertos | 19 eventos |
| Eventos capturados en la muestra, más recientes | 2 |
| Eventos omitidos deliberadamente | 17 |
| Consultas del catálogo para medir | 2 |
| Consultas adicionales de contexto | 7 |
| Total de consultas de la medición | 9 |
| Sets descargados | 104 |
| Tiempo total, incluido catálogo | 9,225 s |

En la carga semanal las dos consultas del catálogo ya forman parte de `discover.py`; **el incremento medido de la muestra es 7 consultas**. El tiempo medido incluye catálogo; no se midió por separado el tiempo incremental. Para los 19 eventos, el mínimo estimado es **57 consultas adicionales** (tres por evento); puede ser mayor por paginación de sets, reintentos y nuevos torneos. No se ejecutó la captura completa del año ni un corte semanal nuevo: no presentar esta estimación como un tiempo/costo semanal medido. No se atribuye un precio monetario por petición.

Propuesta pendiente del dueño: comenzar por una muestra de los **dos eventos más recientes**, observar su costo en una ejecución semanal y decidir después cobertura completa, captura con caché incremental o solo organizadores verificados. La herramienta admite `--limit 2`; el workflow preparado usa su techo por defecto de 10, **pero sigue apagado**. Antes de activarlo, ajustar ese argumento a la cobertura aprobada. Limitarlo a dos o diez no significa que se cubra todo el año: hay que comunicarlo en la futura pantalla.

Techos de seguridad que no se pueden ampliar por argumento: **10 eventos**, **30 intentos HTTP** adicionales contando los reintentos de `Client`, y no iniciar otra consulta después de **120 s**. Se reservan tres intentos antes de cada consulta; por eso puede detenerse antes de gastar 30. Los 120 s son un presupuesto de planificación, **no un timeout estricto del proceso**: una consulta ya iniciada puede tardar más por su timeout/reintentos; si el tiempo final excede el presupuesto, se descarta todo el complemento. Si un evento falla o se agota el presupuesto, no se publica un grafo parcial. Una selección limitada completa puede omitir otros candidatos y registra sus IDs privadamente. No hay caché incremental nueva: al habilitarlo recaptura la selección, incluso al reanudar. Si la ampliación se apaga, se elimina el complemento descargado de un artefacto anterior.

## Paquete y circuito de importación

El paquete normal sigue siendo V1, V2 o V3. Sin complemento válido, **sus bytes canónicos y su hash son exactamente los mismos**. Con complemento válido, se construye un transporte V4:

```text
content.packageVersion = 4
content.nationalPackageVersion = versión original (1, 2 o 3)
content.nationalSha256 = hash original del contenido nacional
content.organizerContext = {schemaVersion: 1, capturedAt, entities, eligibility}
sha256 = hash del contenido completo de transporte V4
```

`organizerContext.entities` contiene únicamente `players`, `tournaments`, `events`, `entrants`, `entrant_players`, `sets`, `set_slots`. `eligibility` conserva evidencia de presencial, terminado y singles por evento. IDs reales de start.gg. No se transforma el cálculo ni se vuelve a exportar `public.json`. La validación Python/PHP proyecta el paquete nacional restaurando su versión y retirando los tres campos nuevos; verifica que su hash coincida con `nationalSha256`. No basta con confiar en el hash exterior. Se valida el grafo completo y su coherencia con los datos nacionales; colisiones de eventos/sets/entrants y duplicados se rechazan. Players/tournaments compartidos deben coincidir con la identidad nacional del paquete.

La fecha nacional de captura y la temporada deben coincidir con las del complemento privado; la observación del complemento no puede ser posterior al combinado. `capturedAt` SQL se normaliza a la fecha del corte. Un JSON opcional inválido, ausente, vacío, obsoleto o demasiado grande deja el paquete nacional normal. Límites intactos: **4 MiB gzip y 32 MiB descomprimidos**; se comprueban antes de aceptar V4. Los errores del paquete nacional siguen deteniendo la publicación, como antes.

No se añade otro endpoint ni canal: `publish_sql.py` → receptor `ranking-sync.php` (HMAC/hash V4) → cola por hash V4 → worker → `ranking-import.php`. El worker compara el `public` nacional original con el archivo vigente; el complemento nunca aparece en `public.json`. Python `import_ranking.py` implementa el mismo contrato. `cuts.source_hash`, snapshots y hashes de filas nacionales guardan **el hash original**, no el hash de transporte V4.

## SQL y contrato para Claude Code

Migración propuesta: [006_organizer_event_context.sql](migrations/006_organizer_event_context.sql). No aplicada a producción. Añade una tabla InnoDB, sin alterar las existentes:

| Campo | Significado |
| --- | --- |
| `event_id` (PK, FK events) | Evento pequeño con grafo completo disponible |
| `cut_id` (FK cuts) | Corte cuyo circuito transportó el contexto, **no admisión al ranking** |
| `captured_at` | Fecha normalizada del corte transportador |
| `active_players` | Personas distintas con al menos un set competitivo válido |
| `valid_sets` | Sets competitivos válidos; no DQ/bye/walkover |
| `context_hash` | SHA-256 del complemento normalizado completo |

Los sets pequeños quedan en las tablas normales de lectura `sets`, `set_slots`, `entrant_players`, `entrants`, `events`, `players`, `tournaments`. Se conservan los tipos de resultado del importador existente. **Nunca** se agregan a `cut_events`, `cut_set_results`, `rankings` ni `player_characters`; tampoco se modifica `cuts`, su snapshot/hash o `public.json` por el complemento. La asociación `cut_id` de la marca únicamente indica procedencia.

Para el futuro top del organizador, Claude debe construir el conjunto de eventos como una unión deduplicada de:

1. Los eventos nacionales del corte vigente que ya obtiene con `cut_events`, según temporada/Guatemala y permisos del organizador actuales.
2. Los eventos de `organizer_event_context`, unidos a `events`, `tournaments` y al catálogo/reclamos de organizador ya verificados. Filtrar **la fecha del evento** al año solicitado, su juego y el creador/reclamo verificado; no usar solo el año del corte transportador. No inferir propiedad por nombre o jugador.

Mantener el control de organizador y la regla de actividad del jugador del top actual. Si un evento pequeño pasa después al ranking nacional, priorizar la membresía nacional y no contar sus sets dos veces. La marca de contexto **no convierte el evento en torneo nacional**. No todos los eventos del catálogo tienen sets disponibles: una ausencia de marca no equivale a cero resultados.

La marca es el contexto **más reciente por evento**, no una instantánea por corte. Eventos omitidos por el límite conservan su última marca/datos; mostrar la fecha/cobertura o decidir explícitamente si se exige `cut_id` vigente para una vista totalmente recapturada. No borrar ni declarar actualizado todo el año al capturar solo los más recientes. Una corrección histórica fuera de la selección necesita un futuro encargo de recaptura/backfill, no una escritura oportunista al visitar la pantalla.

**Propuesta de mínimo para que cuente en el top del organizador:** cuatro jugadores activos distintos y tres sets válidos. Ofrece una muestra menor que el nacional sin considerar un único enfrentamiento como torneo suficiente. El dueño decide. **No está aplicado como regla de clasificación**: el marcador técnico solo exige dos activos y un set válido, para poder guardar contexto verificable. El ranking nacional mantiene veinte activos y sus reglas actuales.

## Transacción, errores, correcciones y repetición

El corte nacional se importa/parifica primero. Dentro de su transacción se abre un savepoint para el complemento:

- Sin registro de 006: `organizer.status = migration_missing`; importar el corte nacional normalmente.
- Registro de 006 pero marcador ausente/incompleto/no InnoDB: `schema_unavailable`; mismo resultado nacional.
- Complemento correcto: `imported`; paridad columna por columna de las siete tablas y la marca, idéntica Python/PHP. Players/tournaments globales mantienen los datos ya observados, como el importador normal; se comprueban contra sus filas previas o la entrada nueva.
- Fallo SQL o de paridad: rollback al savepoint, `skipped_context_error`, publicar/commit del corte nacional. No se registran mensajes del driver ni datos personales.
- Repetición de un corte: `already_imported`, complemento `not_reapplied`; **cero escrituras**, aun si se instaló 006 después, cambió el contexto o se envió el núcleo V3 original. No usar la repetición como carga inicial.

Un corte nuevo puede refrescar correcciones de los eventos pequeños seleccionados (winner, score, entrants y slots): reemplaza únicamente su grafo marcado y actualiza la marca. Se rechaza cualquier evento usado alguna vez en `cut_events`, cambios de padre por ID, datos vivos sin marca y eventos con games previos. FKs que protegen referencias de otras funciones no se desactivan: si impiden refrescar, se omite el complemento entero con rollback. Las instantáneas de cortes anteriores siguen intactas. Cargar contexto de un corte ya importado requiere una herramienta y orden independiente; esta PR no modifica ni rellena el corte del 4/oct.

## Pruebas y mediciones del worker

Pruebas automáticas con datos inventados: cálculo/exportación nacional idénticos antes/después de capturar; flag de candidatos sin consultas adicionales; fallback ante fallos; hashes V1–V3 fijados; validación PHP/Python de V4 y 16 variantes inválidas; recepción HTTP real y deduplicación; worker con el `public` vigente; paridad tabla por tabla; repetición sin cambios; corrección en corte nuevo; 006 ausente/rota; fallos SQL/paridad incluso en identidades globales. No datos ni comentarios de producción.

Laboratorio MariaDB **13.0.2 local desechable**, sin configuración personal (`--no-defaults`), eliminado al terminar. 90 pruebas del pipeline, 9 de esquema y 8 nuevas del contrato/circuito (además de regresión de visitas/estadísticas). La matriz CI comprueba específicamente MySQL 8.0 y MariaDB 10.11; consultar los checks finales de la PR.

| Fixture local a través del worker real | JSON | Gzip | Pico memoria PHP | Tiempo |
| --- | ---: | ---: | ---: | ---: |
| Corte pequeño V4, con 006 | 15.409 B | 2.689 B | 2 MiB | 0,077 s |
| Mismo V4, sin 006 | 15.409 B | 2.689 B | 2 MiB | 0,065 s |
| V4 sintético con 5.000 games nacionales | 1.339.067 B | 59.236 B | 54 MiB | 0,988 s |

Son medidas locales con fixtures, **no** memoria/tiempo del paquete semanal completo ni rendimiento del hosting. Se midió `memory_get_peak_usage(true)` del worker bajo su límite 512M. Los tres paquetes quedan bajo los límites. No extrapolar a un JSON de 32 MiB: al habilitar y seleccionar cobertura, revisar tamaño y memoria del paquete real antes de depender del complemento. Sin acceso/consulta/escritura SQL de producción en esta tarea.

## Fusión, despliegue y siguiente paso del dueño

Con CI correcta, **es seguro fusionar/desplegar el código antes del domingo 11/oct manteniendo la ampliación apagada y 006 sin aplicar**: la ruta normal V1–V3 queda igual y no incorpora datos pequeños. Recomendación: dejar la activación y la migración para **el lunes**, después del primer corte semanal, por orden del dueño y con cobertura acordada. Esta PR no fusiona ni despliega.

Secuencia futura, solo con autorización: revisar PR/CI; decidir mínimo y cobertura; aplicar 006 en una ventana acordada; ajustar `--limit` del workflow (propuesto 2 para la primera prueba); habilitar `SMASH_ORGANIZER_SMALL_ENABLED=true`; validar en simulación el paquete real/tamaño/memoria antes de la siguiente carga; Claude conecta el conjunto de eventos disponible a su top. Deshabilitar la variable detiene nuevas capturas complementarias sin borrar datos SQL ya guardados. No requiere servicios nuevos ni consultas a start.gg por visita.
