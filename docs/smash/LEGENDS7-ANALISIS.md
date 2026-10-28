# Legends 7: contexto de análisis, no ranking

## Renovación del dueño — 27/oct/2026 GT

El dueño pidió continuar los historiales de Legends 7 para conservar el contexto de 2026 y consultarlo el próximo año. Se interpreta como renovación del mismo circuito de análisis y sus altas base ya autorizadas, **solo evento 1687524 / temporada 2026**, sin reiniciar checkpoint ni introducir otros eventos/temporadas. Nuevo tope fijo **2027-01-01T06:00:00Z = fin del 31/dic/2026 GT/SV**, sin argumento/variable que lo amplíe. Se mantiene cada seis horas, máximo dos tandas, 30 intentos/120 s por tanda y una petición/s. Receptor, worker, capturador y fecha mostrada en panel comparten ese plazo y sus pruebas comprueban la paridad. No cambia «Mi torneo»: pools/horarios de un torneo ya terminado no se reactivan.

El último run previo al vencimiento, **40241693908**, dejó **343 inscritos, 177 historiales pendientes**, 63 intentos y 558,503 s. Los runs posteriores siguen verdes pero responden **authorization_expired / 0 consultas** (confirmado 40605516240), no han estado capturando. SELECT de solo lectura 27/oct: **007 presente, 66 tandas / 270 marcas analysis_context_players de 2026, todos los 66 player_history succeeded, 4 cuts**. Las marcas no equivalen a historiales completos; la cobertura privada es quien determina pendientes.

La reanudación conserva nextPage, recibos, identidad, prioridad nacional y exclusión de mains/rankings. Los historiales terminados no se vuelven a consultar; «completo» significa paginación recorrida, no que start.gg registre todos los personajes o que un conocido ya tuviera historial completo. Tras terminar se obtiene already_imported y solo se revisa el roster/inventario mientras siga vigente la orden. No se amplían cuotas ni se reinicia a todos.

**Conservación:** el vencimiento detiene capturas, no borra SQL/checkpoints. Los datos quedan etiquetados con season_year/seasonYear **2026**, sin TTL de borrado en este circuito. En 2027 siguen como histórico: el lector actual selecciona la temporada del corte y no los mezcla automáticamente con un ranking 2027. Ofrecer historial multitemporada en la pantalla sería otra mejora; no se presenta este cambio de plazo como esa función ni como backup inmutable de toda la base. No capturar 2027 bajo esta autorización.

La variable estaba true. Despliegue seguro: pausar solo el interruptor antes de fusionar; comprobar que no haya jobs/capturas pendientes o ejecutándose, desplegar assets_only (aquí **sí hay cambio PHP**), volver a true y lanzar una ejecución normal. Nunca aplicar desde MySQL manualmente ni resetear la cola. Ver EN-CURSO.md para CI, publicación y primera tanda reanudada; no darlos por verificados hasta registrar resultados.


**Estado vigente 14/oct (orden posterior del dueño):** #102 fusionado/desplegado, altas de entidades aprobadas y constante en true; 007 aplicada según el dueño. El bloqueo de alcance mencionado abajo es histórico y queda resuelto. Corrección #103 fusionada y desplegada: cron habilitado y run 38606150069 verde con registrations_unavailable, una consulta y cero agregados. Evidencia completa en el primer bloque de EN-CURSO.md. No repetir migración ni pedir nuevamente autorización.

**Actualización 14/oct:** PR #100 fusionado y desplegado según el dueño. La sección siguiente describe la automatización nueva, todavía sin fusionar, activar ni desplegar. La comprobación de lista/esquema del 13/oct debajo es histórica; no se repitió contra producción en esta entrega.

## Automatización de inscritos (14/oct)

Implementación y operación en [AUTOMATIZACION-ANALISIS.md](AUTOMATIZACION-ANALISIS.md). Consulta cada seis horas, una sola petición si la lista sigue oculta, captura acotada de inscritos ausentes y reanudación privada en BanaHosting. Mismo receptor firmado/cola/cron; sin acceso MySQL desde Actions, capturas públicas ni cambios del ranking. Un inscrito nuevo se incorpora en la siguiente ejecución.

**La autorización del dueño dice «solo en las tablas de 007», pero `rival_context.py --apply` también inserta las identidades/resultados ausentes en nueve tablas base referenciadas por 007.** Se solicitó aclaración en este chat; no se recibió respuesta al documentar. El receptor queda cerrado con `RC_ENTITY_INSERTS_AUTHORIZED=false` hasta confirmación explícita. No convertir ese interruptor en true por interpretación ni activar el workflow mientras falte. La migración 007 la aplica Claude Code únicamente por orden del dueño; esta entrega no comprueba ni altera la base productiva.

La autorización original terminaba al finalizar el 25/oct/2026 GT; fue renovada el 27/oct hasta fin del 31/dic/2026 GT, como se detalla arriba; tanto el capturador como el receptor/worker la hacen cumplir. La orden actual permite entregar el PR, **no fusionarlo, desplegarlo ni activar el cron en main**.


## Comprobación real

Único candidato verificado por slug exacto: [LEGENDS7](https://www.start.gg/tournament/legends7/details), torneo **942547**, país **SV**, zona **America/El_Salvador**. Del **24/oct/2026 09:00** al **25/oct 22:00**, hora de El Salvador (UTC−6). Evento **ULTIMATE Singles**, **1687524**, `tournament/legends7/event/ultimate-singles`, inicia 24/oct 10:00 local; Ultimate 1386, singles, presencial.

La API devuelve `numEntrants: null`, entrants vacío y participants vacío también filtrando membresía del evento. **No significa cero inscritos**: inscritos, conocidos y faltantes son desconocidos. El dueño confirmó que tampoco puede ver la lista. No hay nombres verificables que capturar; no se inventó una carga real ni se consultaron historiales. **Cero jugadores añadidos a producción y cero escrituras**. SQL productivo se consultó solo para comprobar esquema e inventario agregado (3527 jugadores; 007 ausente).

Sondas oficiales de solo lectura, serializadas con el grupo de publicación, sin secretos FTP/SQL en el runner y con artefacto cifrado para la Mac:

- [38511287391](https://github.com/Bucaro-19/rankingsmashbros/actions/runs/38511287391): metadatos, entrants y esquema; **3 consultas, 2,144 s**.
- [38511501070](https://github.com/Bucaro-19/rankingsmashbros/actions/runs/38511501070): esquema de Participants/SetFilters; **1 consulta**, sin cronometraje registrado.
- [38511604583](https://github.com/Bucaro-19/rankingsmashbros/actions/runs/38511604583): participants/eventos; **1 consulta, 0,527 s**.

Total **5 consultas** de investigación; las duraciones anteriores no incluyen colas de Actions. El workflow temporal de sonda se restauró idéntico a main: no queda una ampliación de sus permisos en el diff final. No queda tarea automática ni token nuevo. El token se usó en GitHub Secrets, no se descargó a la Mac.

## Herramienta lista para una lista pública verificable

`scripts/database/rival_context.py`: roster → inventory → capture → load. Usa `collect.Client` y el normalizador relacional existente; es un paquete independiente del corte, sin `public`, cuts, rankings ni instantáneas. Guarda IDs reales de players, torneos, eventos, sets, games y selecciones; stocks por game en campos nullable separados (no son el marcador del set). DQ/byes no generan matchups. Selecciones desconocidas, ambiguas o sin ganador/orden real se omiten; no se infieren personajes.

- Solo se solicita historial de los inscritos que no existen todavía en players. Los rivales encontrados en esos sets se guardan como contexto necesario, sin volver a consultar sus historiales.
- Temporada por inicio del evento en calendario GT; singles Ultimate terminados, incluyendo fuera del país y online para análisis. Esto **no es admisión al ranking**.
- start.gg no ofrece filtro de temporada para Player.sets ni orden contractual por fecha: se recorren páginas y se filtra después. No se corta al encontrar un evento antiguo. PerPage 5 para no desbordar complejidad de games.
- Cada tanda: **30 intentos HTTP máximo incluyendo reintentos, 120 s, una petición/segundo**, techos fijos del proyecto. Con tres intentos reservados por consulta normalmente caben 28 páginas sin reintentos. Se reanuda desde páginas guardadas; una tanda fallida conserva el checkpoint anterior y se detiene (no reiniciar a ciegas).
- Archivos privados fuera del repositorio/publicación, JSON ≤32 MiB, paquete comprimido ≤4 MiB; atómicos, permisos 0600. La salida no sobrescribe un archivo existente salvo el estado privado explícito. No se publican las capturas.

Comandos futuros, **no ejecutados para historiales reales por falta de lista** (STARTGG_TOKEN ya configurado en entorno privado; no pegarlo en comandos/chat):

```sh
python3 scripts/database/rival_context.py roster --slug legends7 --output /ruta/privada/legends7/roster.json
python3 scripts/database/rival_context.py inventory /ruta/privada/legends7/roster.json --year 2026 --output /ruta/privada/legends7/state.json
python3 scripts/database/rival_context.py capture /ruta/privada/legends7/state.json --output /ruta/privada/legends7/batch-01.json
python3 scripts/database/rival_context.py load /ruta/privada/legends7/batch-01.json
```

Repetir capture con siguiente nombre de tanda hasta coverage completa; no borrar state. `inventory` y `load` usan la conexión privada normal, aceptan `--defaults-file` y `--database` sin imprimir credenciales. Sin 007 la simulación responde `migration_required_no_writes` con conteos; con 007 `validated_no_writes`. **Solo tras orden expresa del dueño y simulación correcta:** repetir load con `--apply`. Ningún comando aplica migraciones. Si roster responde `registrations_unavailable`, detenerse: un vacío no es lista válida.

## Migración propuesta, nunca aplicada en producción

[007_analysis_context.sql](migrations/007_analysis_context.sql), solo instalada en base desechable de pruebas:

- analysis_context_batches: hash de paquete/contexto, evento fuente y temporada; repetición `already_imported`.
- analysis_context_players: marca de los inscritos disponibles para búsqueda sin inventar clasificación.
- analysis_game_scores: stocks de ambos lados nullable. El esquema previo no tiene esos campos.

Necesaria para no confundir contexto con admisión y para conservar marcador por game. SQL apply transaccional InnoDB, mismo advisory lock del importador, verificación de relaciones y paridad de sets/games/selecciones/stocks. Inserta identidades ausentes; **no reemplaza resultados, slots ni games de sets existentes**, tampoco los de un corte. Una corrección posterior no se revierte al repetir el paquete. Un cambio de identidad/relación se rechaza. Refrescar sets existentes deliberadamente requeriría otro encargo y política de correcciones.

## Contrato de lectura para Claude Code

Biblioteca privada `analysis-context.php`, negada por .htaccess y publicada antes del endpoint. Sin 007 devuelve contexto vacío y la respuesta de hoy sigue funcionando. Sin start.gg por visita. Análisis admite búsquedas por los inscritos marcados; sus perfiles llevan `rank/points: {gt:null,intl:null}` cuando no están clasificados. No se añaden a arrays del ranking.

Gratis sigue limitado a perfiles y récord entre ambos; premium/admin obtiene métricas adicionales. `dataNotice` advierte que se incluye historial parcial de temporada sin cambiar ranking; ambas pantallas existentes lo muestran. `setDataScope=published_ledger_and_analysis_context` cuando se usa historial extra. `coverage.source=analysis_context` identifica mains detectados solo para jugadores sin ficha publicada. No se alteran mains publicados. El corte/su generatedAt siguen indicando la referencia nacional, no la fecha completa de todo el historial extra.

Resultados publicados tienen precedencia por ID: el contexto no cambia su ganador/metadata ni agrega games posteriores al corte a esos sets. El filtro GT toma solo eventos de país GT. Forma reciente carece de puesto final e inscritos por rival: siguen null, sin estimaciones. Tramos de puesto usan únicamente los puestos reales del corte; sin puesto no equivale a débil. Contexto máximo 1000 inscritos, 5000 sets por lectura y 50000 filas de games combinado; se rechaza exceso en lugar de devolver estadísticas parciales sin aviso. Las estadísticas de escena siguen sobre el grafo nacional, no sobre una muestra arbitraria de extranjeros: los games adicionales cuentan para el jugador y su rival, pero se excluyen explícitamente de scene/sceneGames y de la confianza de escena, con prueba SQL.

## Verificación y pendiente

Local: 7 pruebas nuevas (5 contratos y 2 SQL), 13 HTTP de análisis, 94 Python de pipeline, 5 Node y contratos PHP de análisis correctos; MariaDB 13.0.2/PHP 8.5.3 desechables. Incluye importación/repetición, migración ausente, conflicto de identidad, ranking/instantáneas inmutables, stocks, rival solo contexto, cuenta gratis y modo GT. CI del código 590d82c [38515107772](https://github.com/Bucaro-19/rankingsmashbros/actions/runs/38515107772) correcta en MySQL 8.0, MariaDB 10.11 y suite general. Fallback de imagen PHP ECR a Docker Official Images acotado a un intento alterno por throttling observado; no se omite ninguna comprobación. Consultar checks del head final en PR #100.

SHA-256 versionado public.json sin cambios: `1e681141bf4d043319593effc3153f44a7ec38531deef8a427f76c2573a24df1`. Pendientes reales: publicación de inscritos, autorización/aplicación de 007 por el dueño y medición de captura/importación reales cuando haya lista. No se fusiona ni despliega.
