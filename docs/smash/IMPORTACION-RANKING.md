# Importador de ranking e historial — 7 de octubre de 2026

## Carga inicial de contexto — implementada, pendiente de producción (7/oct)

Entrega en `feat/initial-game-context`, desde main `8f2e53a`. `scripts/database/game_context.py` es una herramienta CLI, no un endpoint ni una migración. Construye un paquete **solo games/selecciones** con hash propio y exige aparte el paquete original como prueba; no reenvía V2 al importador semanal. Nunca modifica `cuts`, `rankings`, instantáneas ni el hash original. No realiza consultas a start.gg.

`build ORIGINAL CAPTURADO_V2 SALIDA --cut-id 1` comprueba entidades/public idénticos y las mismas reglas de cobertura, relaciones, catálogo y mains de V2. Rechaza archivos mayores de 32 MiB y salida gzip mayor de 4 MiB. Crea salida privada (600), sin sobrescribir archivos. `load CONTEXTO --original ORIGINAL --database BASE` simula por defecto con transacción SQL **READ ONLY**; solo `--apply` permite insertar las dos tablas, en una transacción serializable. Ambas variantes usan el bloqueo del importador semanal.

Protecciones: exactamente un corte publicado y coincidente con el anclaje; paridad original antes/después; comparación completa de los sets, slots y vínculos entrant/jugador cubiertos. Games/selecciones deben estar **ambos vacíos**, o coincidir completamente con el paquete (incluida fecha de captura), en cuyo caso devuelve `already_imported`. Datos parciales, corregidos, posteriores, catálogo faltante o fuentes distintas detienen todo; no se borran ni sobrescriben filas. Si ya existe otro corte, incluso con games vacíos, rechaza `later_or_other_cut`: no resucita capturas históricas que una corrección pudo retirar. El fallo intermedio revierte todas las inserciones. Una transacción ajena se rechaza sin revertirla.

### Fuente recuperada sin recaptura

Las copias temporales anteriores desaparecieron al reiniciar la Mac. Se recuperaron los artefactos privados existentes de `Bucaro-19/rsvp-graduacion`: `smash-gt-capturas`, run **37198767448**, y `smash-mains`, run **37540350390**. Solo se leyó el JSON público actual por HTTP; nunca respuestas de la encuesta. Desde `combined-mains.json` y ese public se reconstruyó V2; para la prueba V1 se retiraron games/cobertura y se restauraron literalmente las tres limitaciones del exportador de `e685fb2`. Ambos hashes coinciden con los documentados anteriormente:

- Original V1: `ecb1d4a5cd44f87250537a85d0d166fa6f9824ff3408f0b55c98ac6102fd9e45`.
- Captura V2: `a9e43b90421e56a4eaf5912ee294608b459ffbebd42e934de1f571c4bb068def`.
- Contexto: `853b8788e264ad8e302c8dc62657f4e4506503b8d98e2be9656048ebf466f109`.

Archivos privados en `/tmp/smash-initial-context/` (carpeta 700, paquetes 600). Son temporales; conservarlos fuera de Git antes de reiniciar o expirar los artefactos. No subir el paquete de prueba ni las capturas al sitio público. No sustituir public por `public-mains.json` antiguo: le faltan algunos playerTags.

### Medición comprobada SOLO en la base desechable de la Mac

MariaDB local 13.0.2, PyMySQL 1.1.2, Python 3.9. Fuente Oct4, personajes capturados Oct6. Contexto: **3,837 sets, 4,787 games, 9,530 selecciones**. JSON **1,471,290 bytes**, gzip determinista **92,604 bytes**: bajo 32/4 MiB.

| Operación local | Tiempo | Pico RSS del proceso |
|---|---:|---:|
| Construir y validar contexto | 1.218 s | 250,773,504 bytes |
| Simular lectura (tablas vacías) | 1.479 s | 244,531,200 bytes |
| Aplicar en base desechable | 1.941 s | 257,785,856 bytes |
| Repetir aplicación desechable | 1.606 s | 248,922,112 bytes |

El máximo (~246 MiB) está bajo 512 MiB; corresponde a este CLI Python, **no al worker PHP de BanaHosting**. No se cambió el worker. Las nueve pruebas del contexto verifican anclaje, relaciones/mains, rollback, repetición, inmutabilidad de doce tablas y protección de contexto posterior; se añadieron al CI MySQL 8.0/MariaDB 10.11. Estado de la CI en EN-CURSO.

### Pendiente: simulación de producción y orden de escritura

**No se escribió producción. Tampoco se pudo completar la simulación de producción:** el servidor rechazó la conexión desde el router actual. El dueño no puede acceder ahora a cPanel; no se cambió Remote MySQL ni se solicitó una contraseña. Cuando la Mac vuelva a una IP autorizada (o el dueño autorice la nueva IP específica), desde la rama de esta entrega:

```sh
# Construcción offline ya ejecutada; una nueva salida debe tener otro nombre si existe.
/tmp/smash-db-runtime/bin/python scripts/database/game_context.py build /tmp/smash-initial-context/ranking-original.json /tmp/smash-initial-context/ranking-v2.json /tmp/smash-initial-context/context-oct4.json --cut-id 1
# Primero SOLO lectura: usa el ~/.my.cnf privado del dueño, sin imprimirlo.
/tmp/smash-db-runtime/bin/python scripts/database/game_context.py load /tmp/smash-initial-context/context-oct4.json --original /tmp/smash-initial-context/ranking-original.json --database ivcjgjlk_smash
# NO ejecutar sin revisar la simulación y recibir orden expresa del dueño:
/tmp/smash-db-runtime/bin/python scripts/database/game_context.py load /tmp/smash-initial-context/context-oct4.json --original /tmp/smash-initial-context/ranking-original.json --database ivcjgjlk_smash --apply
```

La simulación pendiente imprimirá solo conteos, hashes, tiempo y memoria; no contenido privado ni errores del driver. Si ya corrió el corte del 11/oct, **no forzar esta carga**: el circuito semanal V2 ya trae games. Comparar contra la captura vigente y preparar un nuevo encargo para cualquier contexto histórico faltante. No renombrar hashes ni vaciar tablas para saltar la protección.


## Selecciones por game — entrega de Codex, 7/oct/2026

Rama `feat/game-selections-sql`, desde `main` `4e5bb2d`. **Sin fusionar, desplegar ni escribir producción.** La automatización actual sigue activa. No necesita migración: usa `games` y `game_selections` de 001. No cambia cálculo, elegibilidad, `public.json`, esquema público 3 ni mains; la única versión nueva es **`packageVersion=2` del paquete privado**. Ambos importadores siguen admitiendo v1 con su hash original.

### Captura, reglas y validación antes de publicar

El workflow añade `--output-snapshot scripts/smash/data/combined.json` a la misma ejecución de `characters.py`. Antes solo persistía el JSON público; los games enriquecidos quedaban en memoria. No cambia `FIELDS`, caché, caducidad ni cantidad de consultas a start.gg. El exportador solo lee archivos y llama a `player_mains` para comprobar, sin recalcular ranking, que mains y cobertura coincidan exactamente en ambas vistas.

- Games de sets competitivos de eventos admitidos donde participa al menos un clasificado de alguna vista; recoge las selecciones de **ambos entrants**, también del rival extranjero/no clasificado. No es todo start.gg ni todo el país.
- IDs reales de game/set/entrant/character. Primer game con ID y ganador válido por cada ID del set; sin ganador o sin ID se omite. Un ID compartido por dos sets se rechaza.
- Selección con nombre no vacío y entrant del set. Picks repetidos del mismo personaje se deduplican; dos personajes distintos para un entrant/game omiten **ese entrant**, conservando al rival si tiene un único pick. No deducir por alias ni sustituir un pick ausente por el main agregado.
- `game_number` es la posición (desde 1) en el array capturado; puede tener huecos por omisiones y **no certifica el orden oficial**, que la consulta actual no pide. `stage_id=NULL`. `synced_at` es la captura de personajes del conjunto; los games pueden venir de la caché vigente, no implica consulta individual ese día.
- V2 valida games→sets, ganador/selecciones→slots, ordinal único, máximo SMALLINT, selecciones no ambiguas ni duplicadas y personajes contra el catálogo versionado `characters.js` más Random 1746. En SQL vuelve a exigir existencia en `characters`. Un personaje nuevo requiere actualizar el catálogo primero, nunca inventar equivalencias.
- El paquete contiene `gameContextSetIds`: sets competitivos realmente cubiertos, **incluso si devolvieron `games=[]`**, y sets capturados que dejaron de ser competitivos. Estos últimos solo invalidan contexto; no generan games ni consultas. Cobertura exacta derivada y verificada por Python y PHP. Agregaciones por ID/uso deben reproducir los mains públicos; el exportador también compara nombres y `mainCoverage` contra la captura.

### Correcciones e idempotencia

En un **corte nuevo**, con el mismo bloqueo y dentro de la transacción de publicación, se eliminan selecciones y después games de los sets cubiertos, se insertan los nuevos y se comprueba paridad de todas sus columnas antes de commit. Una selección corregida, ganador de game corregido, game retirado, captura vacía o set convertido en DQ elimina el detalle anterior. Un set competitivo fuera de la cobertura conserva contexto; no se interpreta «no consultado» como «vacío».

Un game conocido trasladado a otro set o un cambio de los entrants de un set competitivo cubierto ya guardado provoca rollback y conciliación manual. Los slots, sets y otras entidades existentes mantienen la política previa de primera observación; una corrección del ganador del set aparece en el `cut_set_results` y snapshot del **nuevo** corte, y en los games actuales, sin sobrescribir la entidad set inicialmente observada. Para el futuro matchup, usar `games.winner_entrant_id` y las dos selecciones, no el ganador inicial de `sets`.

Repetir el mismo paquete devuelve `already_imported` y verifica las instantáneas. **No vuelve a aplicar ni compara el contexto mutable con una fotografía histórica**: repetir un corte antiguo después de uno nuevo no revierte los games ni exige que las correcciones actuales coincidan con el paquete antiguo. Distinto hash para la misma identidad sigue siendo conflicto. Python ahora también rechaza un corte nuevo fuera de orden o con un corte previo incompleto; el respaldo conserva su opción explícita `--allow-gap`.

No modifica `cuts`, `rankings`, `player_characters`, `cut_events` ni `cut_set_results` históricos. Fallo posterior al reemplazo (p. ej. al insertar rankings) revierte tanto games como el corte nuevo.

### Carga inicial del 4/oct: propuesta, no ejecutada

Lectura de producción comprobada por Codex el 7/oct con transacción **READ ONLY**: cutId 1 publicado, hash original `ecb1d4a5cd44f87250537a85d0d166fa6f9824ff3408f0b55c98ac6102fd9e45`; games=0, game_selections=0; catálogo igual al seed de 87 IDs. HTTP público sigue con SHA-256 `1e681141bf4d043319593effc3153f44a7ec38531deef8a427f76c2573a24df1` y contenido idéntico al paquete original.

Se puede generar offline el detalle desde `/tmp/smash-mains-oct4/combined-mains.json` usando el **public del paquete original**, sin recapturar ni editar JSON público. La copia antigua `public-mains.json` no tiene todos los `playerTags` actuales: no usarla como reemplazo. La reconstrucción con el public original pasó validación y mantiene idénticos los mains y la totalidad del public. El nuevo paquete v2 medido tiene hash `a9e43b90421e56a4eaf5912ee294608b459ffbebd42e934de1f571c4bb068def`; **no enviarlo al importador normal en producción**: chocaría correctamente con la identidad/hash inmutable de cutId 1.

Propuesta para una entrega posterior con orden expresa del dueño:

1. Herramienta **CLI de contexto**, sin endpoint nuevo, con simulación predeterminada y `--apply` explícito. Paquete separado anclado a cutId, fecha y **hash original v1**, con hash propio para el detalle; no reutilizarlo como paquete de un corte nuevo.
2. Validar offline contra public original y catálogo; bajo el bloqueo `smash-ranking-import-v1`, confirmar snapshot/paridad original, que cutId 1 siga siendo el último publicado y que ambas tablas de games sigan vacías. Si cambió alguna condición, detener sin escribir.
3. En una transacción escribir **solo games y game_selections** para sets/slots/jugadores que ya existen y coinciden. No insertar ni actualizar cuts, rankings, entidades de identidad ni ninguna instantánea. Comprobar filas, agregado de mains y hash original antes/después. Repetición exacta, sin duplicados; conflicto de contexto, rollback.
4. Registrar reporte y volver a comprobar hash del public y del corte. No recapturar ni «actualizar» el hash guardado.

**Esta herramienta de backfill no se implementó ni ejecutó en esta PR.** La primera carga del corte existente requiere un paso manual autorizado; el importador semanal no convierte `already_imported` en una escritura extraordinaria. Si ya existe un corte posterior (11/oct), no insertar a ciegas la captura vieja: preparar el contexto desde la captura/paquete del último corte, y una comparación específica para cualquier set histórico restante. Una tabla vacía no permite distinguir «nunca capturado» de «eliminado por corrección»; no sobrescribir ni resucitar datos sin esa comparación.

### Evidencia y recursos

Datos reales del corte Oct4, únicamente en SQL **local desechable**, MariaDB 13.0.2 / PHP 8.5.3 CLI, con `memory_limit=512M`:

| Medición | V1 original | V2 con games |
|---|---:|---:|
| JSON canónico | 8,958,166 bytes | 10,429,237 bytes (9.95 MiB) |
| gzip determinista | 1,064,392 bytes | 1,159,150 bytes (1.11 MiB) |
| games / selecciones | 0 / 0 | 4,787 / 9,530 |
| sets de contexto | — | 3,837 (2,648 competitivos + 1,189 invalidaciones) |

Crecimiento: 1,471,071 bytes de JSON (+16.4%) y 94,758 de gzip (+8.9%). Límites comprobados: 33,554,432 bytes JSON y 4,194,304 gzip. La captura trae 4,789 games: dos sin ganador válido se omiten. Pico validación PHP 148,848,640 bytes (142 MiB); worker real de prueba (gzip→validación→SQL→repetición) 150,945,792 bytes (144 MiB), 2.42 segundos. Construcción/validación/transporte ~1.4 s; solo validar/transporte ~0.81 s. Son mediciones de la Mac, **no del hosting**. El pico anterior en BanaHosting era ~134.5 MiB; queda pendiente medir V2 allí después de autorizar/publicar.

Paridad real Python/PHP: mismas filas/columnas en las **14 tablas** del circuito, incluidas games y game_selections. Solo se omiten los timestamps SQL de reloj documentados en la prueba; fechas de fuente/paquete sí se comparan. Los fixtures de CI prueban correcciones, invalidaciones, vacío, fuera de cobertura, repetición v1/v2, colisiones, cambios de slots, rollback y catálogo faltante. Hay además un worker con 5,000 games / 10,000 selecciones bajo los límites. CI MySQL 8.0 y MariaDB 10.11 comprobada: [run 37703150785](https://github.com/Bucaro-19/rankingsmashbros/actions/runs/37703150785), tres jobs correctos. PR [#36](https://github.com/Bucaro-19/rankingsmashbros/pull/36), actualizada sobre el main de premium de Claude; comprobar sus checks actuales al revisar.

Reproducir tamaño sin red ni SQL: `python scripts/database/measure_ranking_package.py PAQUETE_V2.json --baseline PAQUETE_V1.json`. Fixtures SQL: `test_import_ranking.py`, `test_weekly_ranking_load.py`, `test_hosting_sync.py` con `SMASH_SCHEMA_TEST_DB=smash_schema_test*` y localhost, nunca producción. No se versionan capturas ni paquetes reales.

Para Claude/premium: contar solo games con los dos picks válidos; mostrar tamaño de muestra. Random 1746 es el pick literal, no identifica al luchador finalmente sorteado. Los índices existentes permiten jugador→entrant→set_slots→game_selections por `(set_id, entrant_id)` y rival por game_id; carácter usa el índice de FK a `characters`. `EXPLAIN` local sobre la muestra real eligió esos índices (ningún escaneo completo), consulta de un jugador con mayor muestra: ~0.8 ms, 33 combinaciones. **No se propone migración de índices ahora**; medir con volumen y consultas reales antes de añadir índices. No se implementó el módulo premium.

## Antecedentes: importación inicial y respaldo (leer el estado vigente anterior)

## Contrato

`scripts/database/ranking_package.py` une la captura privada completa con el JSON público ya calculado. No consulta start.gg ni recalcula puestos/puntos. Valida el contrato existente de public.json, fecha de corte, IDs, cobertura de sets y correspondencia de resultados/eventos en ambas vistas. El paquete tiene JSON canónico y SHA-256 de contenido. Su archivo local se crea con permisos 600.

`scripts/database/import_ranking.py` carga ese paquete por CLI usando PyMySQL 1.1.2 y el archivo privado del cliente MySQL del dueño. Nunca imprime credenciales, conexiones ni errores crudos del driver. La simulación es el modo predeterminado; `--apply` escribe en una transacción InnoDB, con bloqueo exclusivo del importador y validación previa del catálogo. No hay endpoint HTTP nuevo ni acceso remoto desde Actions.

La clave del corte es generatedAt UTC con microsegundos + año + método. Mismo contenido = comprobación de paridad y `already_imported`. Misma identidad con hash distinto o estado incompleto = conflicto. El corte se publica al final, después de comparar snapshot, posiciones, puntuaciones, récords, cobertura, personajes, eventos y resultados. Un error revierte todo. El corte anterior solo se enlaza si existe su ranking en esa misma vista y coincide el puesto; de lo contrario conserva la fecha y deja previous_cut_id=NULL.

## Qué importa

- Jugadores de contexto, incluidos rivales extranjeros; no crea cuentas OAuth ni concede roles.
- Torneos/eventos con IDs reales; incluye eventos capturados que no puntúan para conservar historial. Solo cut_events y cut_set_results indican qué entró en cada clasificación.
- Entrants observados en slots, vínculos a jugadores y posiciones finales que pueden reconciliarse con el mismo evento. No constituye un padrón completo de inscripciones. competitive_sets se calcula sobre todos los sets de un evento cuya captura se comprobó completa.
- Sets/slots y marcador textual del origen. El recolector histórico no guardó score numérico por slot: queda NULL, incluso en las copias del corte. No parsear nombres para inventar marcadores.
- Ambos rankings y sus mains publicados, junto con la fecha específica de captura de personajes. No reconstruye games ni selecciones individuales desde agregados.

Las entidades/slots ya existentes se conservan como registro inicialmente observado; el importador no sobrescribe filas vivas de otros módulos. Un ID asociado a otro evento/torneo o un entrant vinculado a otro jugador provoca rollback. Cada corte mantiene copias propias de nombres/resultados y snapshot íntegro. El futuro sincronizador en vivo actualizará su capa con control de versiones y no reescribirá cortes.

## Operación desde la Mac

El dueño ya configuró `~/.my.cnf` con permisos 600 y autorizó únicamente la IP de su Mac en Remote MySQL. No abrir `%` ni copiar ese archivo al repo. Detalles en VERIFICACION-BASE-2026-10-07.md. Codex confirmó lectura directa de MariaDB 11.4.13 y cuts=0 antes de esta importación, sin leer/imprimir el archivo privado.

```sh
python3 -m venv /tmp/smash-db-runtime
/tmp/smash-db-runtime/bin/pip install PyMySQL==1.1.2
python3 scripts/database/ranking_package.py CAPTURA_PRIVADA.json PUBLICO_VALIDADO.json /tmp/smash-ranking-package.json
/tmp/smash-db-runtime/bin/python scripts/database/import_ranking.py /tmp/smash-ranking-package.json --database ivcjgjlk_smash
# Después de revisar el resumen y aprobar la escritura:
/tmp/smash-db-runtime/bin/python scripts/database/import_ranking.py /tmp/smash-ranking-package.json --database ivcjgjlk_smash --apply
```

El dueño autorizó continuar la fase de importación en este chat. Validar primero código/CI y simulación, luego importar el corte y comprobar repetición/paridad. No recrear tablas. Esta operación no cambia el frontend: sigue leyendo public.json.

El workflow semanal genera database-package.json dentro del artefacto existente de capturas privadas (7 días de retención). No se publica por FTP ni se agrega a Git. Si falla su preparación, el corte público conserva su flujo actual, y no hay paquete SQL nuevo que importar. **Esto aún no automatiza la escritura semanal en BanaHosting**: esa integración requiere un transporte privado/mecanismo autenticado adicional, sin abrir MySQL a las IP variables de Actions.

## Validación

`python scripts/database/test_import_ranking.py`: contratos sin SQL y, con SMASH_SCHEMA_TEST_DB apuntando a un servicio localhost desechable, importación/repetición, dos vistas con puestos diferentes, conflicto de hash, enlace/falta de corte previo, fallo SQL intermedio con rollback, conflicto de relación y conservación del corte ante correcciones vivas. Los tests rechazan bases que no sean smash_schema_test* en localhost. CI ejecuta MySQL 8.0 y MariaDB 10.11.

Primera importación real completada el 7/oct/2026 por Codex, después de fusionar PR #9/main e685fb2 y CI 37581615922/37581612335 correctas. Corte Oct4, cutId=1, status=published; la repetición devolvió already_imported. Paridad completa comprobada antes de commit y al repetir. Datos: 188 clasificados en combined y 188 en guatemala; 3435 jugadores de contexto, 43 torneos, 47 eventos, 4498 entrants, 8985 sets y 17970 slots. Las copias por vista contienen 42/39 eventos y 2648/2624 resultados. Users/survey_responses=0; no se modificó encuesta ni frontend.

Hash del paquete: ecb1d4a5cd44f87250537a85d0d166fa6f9824ff3408f0b55c98ac6102fd9e45. public.json permaneció idéntico después de importar (SHA-256 1e681141bf4d043319593effc3153f44a7ec38531deef8a427f76c2573a24df1); inicio/encuesta/opiniones respondieron 200. Estado posterior y pendientes: EN-CURSO.md.
