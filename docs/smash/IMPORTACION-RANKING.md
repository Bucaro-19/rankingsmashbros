# Importador de ranking e historial — 7 de octubre de 2026

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
