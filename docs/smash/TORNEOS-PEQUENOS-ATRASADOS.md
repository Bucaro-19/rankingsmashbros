# Carga única de contexto histórico pequeño

Decisión vigente del dueño, 9/oct/2026: **los torneos pequeños no cuentan para el ranking**. No se cambia ninguna regla ni se decide un mínimo nuevo para el top del organizador. El uso de esta carga es explicar al jugador, en su historial privado, por qué un evento que jugó no contó. Sustituye las propuestas de admisión del documento anterior de organizadores.

[PR #84](https://github.com/Bucaro-19/rankingsmashbros/pull/84), sin fusionar. Herramienta: `scripts/database/small_events_backfill.py`. CLI desde la Mac, sin endpoint nuevo, migración, cron, FTP, publicación o consultas por visita. No se incorpora al workflow semanal. Su carga **simula por defecto**; únicamente `load --apply` puede escribir y en producción necesita una orden expresa del dueño. En esta entrega no se ejecutó con `--apply` en producción.

## Circuito y garantías

1. **inventory** lee en una transacción SQL `READ ONLY` un corte publicado de la temporada y las marcas/IDs vivos. Guarda un inventario privado; no descarga personas, comentarios, credenciales ni la instantánea del corte.
2. **capture** usa `Client`, el catálogo y `fetch_event` existentes. Excluye todo ID marcado y todo evento vivo protegido del inventario; toma los pendientes **más antiguos primero** (fecha, ID). La selección de la tanda permanece fija aunque el capturador ordene sus eventos internamente. No modifica una captura nacional ni usa `--include-small`. No descarga games, personajes, dueños ni países extranjeros.
3. **load**, sin `--apply`, valida paquete, ancla, esquema, relaciones y colisiones en SQL `READ ONLY`. No hace INSERT/UPDATE/DELETE ni una prueba de escritura con rollback. Informa `validated_no_writes` o `already_imported`.
4. **load --apply**, solo tras autorización, toma el mismo bloqueo del importador semanal, usa transacción serializable, relee las marcas y agrega únicamente eventos todavía ausentes. Usa el importador de contexto existente y su paridad por tabla. Error/colisión/paridad fallida: rollback completo de esta tanda, sin marca de éxito parcial.

La repetición no compara ni refresca un evento ya marcado: **lo omite sin escribirlo**, incluso si su paquete trae una corrección. Una tanda parcialmente marcada carga solo su subconjunto pendiente; también al hacerlo coincidir con marcas de otra tanda del mismo corte. Un inventario obsoleto puede gastar consultas de captura redundantes, pero la comprobación SQL final evita sobrescrituras. Renovar el inventario después de cada carga autorizada. Repetir la simulación del paquete ya preparado no consulta start.gg.

Protección adicional: cualquier evento vivo sin marca se considera protegido, **aunque nunca haya entrado en cut_events**. Tampoco se reutilizan IDs de sets/entrants vivos. Las identidades globales ya existentes de players/tournaments se conservan completas; solo se insertan las nuevas. El complemento escribe las siete tablas de contexto y `organizer_event_context`, nunca `cuts`, `cut_events`, `cut_set_results`, `rankings`, `player_characters`, games, cuentas, encuesta o `public.json`.

La marca mantiene sus columnas/semántica actuales. `cut_id` referencia un corte ya publicado como procedencia; no significa membresía nacional ni modifica ese corte. `captured_at` es la observación actual, no se falsea a la fecha del corte antiguo. `active_players`, sets competitivos, ganador y relaciones permanecen compatibles con **`smash_account_small_events()`**; la función sigue excluyendo cualquier evento en cut_events y devolviendo `counts=false`. No se alteró accounts.php ni la pantalla.

## Captura, presupuesto y sets pendientes

Tanda por defecto **6 eventos**, argumento entre 1 y 10; techo inamovible **30 intentos HTTP**, incluyendo catálogo y reintentos. Se reservan tres intentos antes de cada consulta, por lo que una tanda puede detenerse antes de gastar 30. Presupuesto **120 segundos** para la captura, sin iniciar otra consulta al agotarse y descartando el resultado si excede al terminar. Igual que el recolector vigente, no es un timeout duro del proceso: la última consulta ya iniciada puede excederlo por timeout/reintentos. El tiempo SQL se mide aparte y no consume API. Ante fallo no se crea el paquete final ni se sustituyen archivos existentes. Si una tanda supera presupuesto, reducir `--limit`; nunca aumentar los techos.

Solo Guatemala, Ultimate, singles presenciales, evento terminado, 1–19 inscritos conocidos dentro del año. Se conservan las limitaciones conservadoras del catálogo actual: indicadores online desconocidos/torneos mixtos marcados online quedan fuera. No se promete cubrir registros ausentes en start.gg.

Un evento terminado puede conservar sets sin jugar en su bracket. El backfill **omite los sets en estado 1/2 sin ganador**, lo registra en `ignoredUnfinishedSets` y normaliza únicamente los terminados. No inventa una derrota, bye o marcador. Si un set sin terminar tiene ganador o estado desconocido, rechaza la tanda. DQ terminados se conservan con el tipo de resultado existente y no suman al conteo competitivo. El evento debe cumplir el requisito técnico existente de 006 (dos activos y al menos un set válido); si no hay actividad verificable, se detiene sin fabricar una marca. Esto no introduce una regla de elegibilidad. La captura/validación semanal conservan su comportamiento actual; el manejo anterior es exclusivo del backfill.

Paquete privado independiente `backfillVersion: 1`, `kind: small_events_backfill`: ancla de un corte existente, temporada, contexto schema 1 y auditoría agregada. SHA-256 canónico, IDs reales, 32 MiB JSON / 4 MiB gzip. **No es un paquete de ranking V4** y no se envía al receptor semanal. Fecha/ancla/auditoría/relaciones se validan también al cargarlo. Se comparten la normalización de identidades y validación de relaciones mediante funciones extraídas del exportador existente; pruebas fijan los mismos hashes V1–V3 y verifican V4/paridad Python–PHP. No se calcula ni se exporta un ranking para preparar el backfill.

## Simulación real comprobada, 9/oct (solo agregados)

Desde main `bbb08bb`, CI main [37894795531](https://github.com/Bucaro-19/rankingsmashbros/actions/runs/37894795531) y despliegue [37894818993](https://github.com/Bucaro-19/rankingsmashbros/actions/runs/37894818993) correctos. Se confirmó 006 por lectura y cero marcas; no se aplicó ninguna migración ni se cambió `SMASH_ORGANIZER_SMALL_ENABLED=true`.

[Captura 37958722496](https://github.com/Bucaro-19/rankingsmashbros/actions/runs/37958722496), alrededor de las **10:23 Guatemala**:

| Medida de la primera tanda | Resultado |
| --- | ---: |
| Candidatos y pendientes al consultar | 19 |
| Eventos seleccionados, más antiguos | 6 |
| Pendientes fuera de esta tanda | 13 |
| Consultas catálogo / contexto / total | 2 / 19 / **21** |
| Tiempo de captura | **20,624 s** |
| Sets terminados conservados | 178 |
| Sets pendientes omitidos | 15 |
| Tamaño JSON / gzip del paquete | 138.953 / 18.945 bytes |
| Simulación SQL optimizada desde la Mac | **2,231 s**, `validated_no_writes` |

No son medidas del año completo ni de una escritura. Los otros 13 eventos no se capturaron en la ejecución válida y **ninguno de los seis se cargó**: después de simular se comprobaron 0 marcas, 1 corte y 47 eventos en producción. La simulación anterior hizo comprobaciones SQL por identidad (25,616 s); se reemplazaron por lecturas agrupadas y se repitió sin escritura para medir los 2,231 s.

Se registran también los intentos previos: [37957904699](https://github.com/Bucaro-19/rankingsmashbros/actions/runs/37957904699) se detuvo al validar sets pendientes (23,15 s; aún no reportaba el conteo de consultas fallidas); [37958241714](https://github.com/Bucaro-19/rankingsmashbros/actions/runs/37958241714) permitió diagnosticar esa misma causa (21 consultas, 22,55 s, sin paquete cargable). Se usó su captura cifrada para comprobar la corrección **sin red**; luego la ejecución válida anterior verificó el circuito. No presentar las 21 consultas exitosas como costo total del diagnóstico: hay esas dos ejecuciones previas, una con conteo desconocido. Ahora los fallos informan fase, tiempo y consultas sin exponer respuestas del proveedor/driver.

El token siguió en GitHub Secrets. Un runner temporal en esta rama, bajo el grupo de concurrencia de publicación y sin secretos SQL/FTP, emitió solo conteos; su artefacto contenía exclusivamente datos **cifrados para la llave privada de la Mac**, retención un día. El workflow original fue restaurado y no forma parte del diff final. No hay datos reales en pruebas, Git o este informe: solo agregados. El paquete ya validado se conserva fuera de Git, permisos 600, en `~/smash-small-backfill-private/2026-10-09-batch-1.json`.

## Comandos para el dueño / Claude Code

Usar la rama/PR revisada y el entorno Python existente con PyMySQL 1.1.2. `~/.my.cnf` ya está configurado; no abrirlo ni copiarlo, ni pasar contraseñas por argumentos. Sin SSH ni instalación de migraciones. Los ejemplos siguientes son **preparación/simulación**, no autorización para escribir.

Primera tanda ya preparada, sin necesitar el token ni recapturar:

```sh
python3 scripts/database/small_events_backfill.py load \
  "$HOME/smash-small-backfill-private/2026-10-09-batch-1.json" \
  --database ivcjgjlk_smash
```

Si ese Python no tiene PyMySQL, usar el entorno de la Mac que sí lo tenga (la simulación de esta entrega usó `/tmp/smash-db-runtime/bin/python`). Si el entorno temporal desaparece, crear uno privado y fijar la misma dependencia que CI antes de continuar. Una IP no autorizada en Remote MySQL detiene el comando; no abrir `%`.

**Solo cuando el dueño ordene la escritura de esta tanda**, el comando exacto es el anterior con `--apply`:

```sh
python3 scripts/database/small_events_backfill.py load \
  "$HOME/smash-small-backfill-private/2026-10-09-batch-1.json" \
  --database ivcjgjlk_smash --apply
```

Repetirlo no vuelve a escribir eventos marcados. Una simulación no reserva la tanda: la aplicación vuelve a comprobar ancla/marcas/colisiones y puede omitir eventos que haya cargado el semanal mientras tanto. Ejecutar la futura carga en una ventana acordada, evitando la publicación del domingo; no se agenda nada en esta entrega.

Después de una carga autorizada, preparar una tanda nueva con archivos nuevos (el CLI nunca sobrescribe):

```sh
python3 scripts/database/small_events_backfill.py inventory \
  --database ivcjgjlk_smash --year 2026 \
  --output "$HOME/smash-small-backfill-private/inventory-2.json"
# Token únicamente en el entorno local, con entrada oculta (zsh); jamás por chat.
read -r -s 'STARTGG_TOKEN?Token start.gg (entrada oculta): '
export STARTGG_TOKEN
python3 scripts/database/small_events_backfill.py capture \
  --inventory "$HOME/smash-small-backfill-private/inventory-2.json" \
  --output "$HOME/smash-small-backfill-private/batch-2.json" \
  --start 2026-01-01 --end 2026-10-10 --limit 6
unset STARTGG_TOKEN
python3 scripts/database/small_events_backfill.py load \
  "$HOME/smash-small-backfill-private/batch-2.json" --database ivcjgjlk_smash
```

Ajustar `--end` al día siguiente de la captura, como fin exclusivo en Guatemala, dentro de 2026; nunca recapturar el año con `--include-small`. `--catalog` permite reutilizar el catálogo privado compatible si ya existe para esa misma ventana (entonces no gasta consultas de catálogo). `nothing_missing` no genera paquete: no intentar cargar un archivo anterior. El inventario es una lista de IDs vivos, no una copia pública de la base; guardar todo en carpeta privada.

## Por qué no se cambia la selección semanal

El colector semanal tiene start.gg y el catálogo, pero **no las marcas SQL**: Actions no está autorizado en Remote MySQL. Preferir después de los recientes a los sin marca exigiría publicar un inventario seguro o añadir un protocolo/endpoint a la carga semanal, con autenticación y reconciliación. No se añade ese alcance al flujo activo antes del primer domingo. Se conserva `--limit 6` y se drena el pasado con inventarios privados actualizados y tandas explícitas. Si el ritmo futuro supera seis eventos pequeños entre cortes, se necesitará revisar ese protocolo/cobertura con una medición nueva; no prometer que seis recientes cubren el año entero.

## Pruebas y pendientes

Ocho pruebas nuevas, con datos inventados: selección vieja sin duplicar, presupuesto conjunto/reintentos/tiempo, archivos privados/no sobrescritura, rechazo de relaciones/hash/auditoría/fecha inválidos, sets pendientes sin inventar resultados, simulación SQL `READ ONLY` (error 1792 al intentar escribir), múltiples tandas/repetición parcial, protección de todo contexto nacional, rollback por fallo SQL, bloqueo compartido, transacción ajena intacta y **salida real de smash_account_small_events() en PHP** (`counts=false`, G–P y motivo). Además, 90 pruebas del pipeline y regresión del paquete/contexto semanal con hashes V1–V3 intactos. Base MariaDB 13.0.2 local desechable, sin config privada (`--no-defaults`), eliminada al terminar.

Código `eec653b`: [CI 37958722598](https://github.com/Bucaro-19/rankingsmashbros/actions/runs/37958722598) correcto en **MySQL 8.0 y MariaDB 10.11**, incluyendo las nuevas pruebas. Revisar los checks finales de la PR tras la optimización de lecturas/documentación y restauración del runner.

Pendiente: revisión/orden de fusión; autorización separada de escritura para la primera tanda; después nuevos inventarios/capturas/simulaciones para el resto. No se fusionó, desplegó, migró, activó automatización ni escribió producción. La operación de carga futura agrega contexto vivo; no reconstruye un ranking histórico ni demuestra elegibilidad nacional.
