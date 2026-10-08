# Agenda pública de próximos torneos — contrato y operación

Entrega de Codex, 8/oct/2026. **Solo datos y automatización preparada; sin pantalla, fusión ni despliegue.** Claude Code conecta el archivo con el handoff de Claude Design. No hay tabla SQL, geocodificación, consulta API por visita ni cambios del ranking.

## Comprobación real y cuota

Captura autenticada **solo lectura**, [Actions 37850971108](https://github.com/Bucaro-19/rankingsmashbros/actions/runs/37850971108): `generatedAt=2026-10-08T22:03:19.017932+00:00` (16:03 Guatemala). **1 torneo próximo, 1 consulta, 1 página, archivo 1,598 bytes**:

- [GAMELAND 2](https://www.start.gg/tournament/gameland-2), domingo 11/oct/2026 a las 10:00 Guatemala; San Pedro Sacatepéquez, San Marcos; Ultimate Singles, presencial, 10 entrants informados. La agenda lo conserva aunque aún no tenga 20 jugadores: la actividad real se conoce después del torneo.

El token no existe en el entorno local; se usó el secreto existente de Actions. Para comprobar el esquema y obtener el archivo se adaptó **temporalmente, solo en esta rama**, el workflow existente de consulta de dueños. Esa ejecución no pidió dueños/personas, no tenía secretos FTP/SQL y no publicó. El workflow original quedó restaurado y el helper temporal eliminado del diff de entrega. No se relanzó una captura semanal ni se reutilizó el token del chat.

Antes de fijar QUERY se verificó el esquema vivo con introspección autenticada: [Tournament/Event/Query](https://github.com/Bucaro-19/rankingsmashbros/actions/runs/37850420246) y [TournamentPageFilter/TeamRosterSize](https://github.com/Bucaro-19/rankingsmashbros/actions/runs/37850546000), **2 consultas correctas**. Hubo **2 consultas previas rechazadas** por nombres de tipos inexistentes (`TournamentFilter`, `TournamentQueryFilter`, `EventType`); no se asumieron esos tipos. Una prueba sin autenticación fue rechazada. Las comprobaciones de esquema son coste de desarrollo separado; **la captura normal no repite introspección**.

La captura usa `collect.Client`: espera de 1 s y hasta 3 intentos ante 429/5xx. `requests` cuenta los intentos de esta captura, no introspección, HTTP del público ni consultas SQL. Con cinco torneos por página cuesta normalmente `max(1, ceil(torneos/5))` consultas; límite de 40 páginas/200 torneos y hasta 120 intentos. Sin recortes silenciosos. Con el estado medido y frecuencia diaria sería aproximadamente **una consulta/día**, no una cuota prometida para siempre.

Fuentes oficiales: [torneos por videojuego y futuros](https://developer.start.gg/docs/examples/queries/tournaments-by-videogame/), [por país](https://developer.start.gg/docs/examples/queries/tournaments-by-location/), [eventos por videojuego](https://developer.start.gg/docs/examples/queries/events-by-tournament/), [límites API](https://developer.start.gg/docs/rate-limits/). La documentación limita la media a 80 solicitudes/60 s y 1,000 objetos por consulta; por eso la página pequeña y la reutilización de Client. No se afirma una tarifa por consulta.

## Cobertura y faltantes

- `TournamentQuery.filter` es realmente **TournamentPageFilter**. Se fija `countryCode:"GT"`, `videogameIds:[1386]`, `upcoming:true`, `afterDate` al inicio de captura, `published:true` y `publiclySearchable:true`; orden `startAt asc`. Se verifica otra vez el país y el juego en la respuesta.
- Incluye online cuando el **torneo declara GT**. El esquema no ofrece el país de quien lo organiza como filtro público independiente: `ownerId` requiere una persona concreta y no se usa. **No cubre** online con país desconocido aunque su organizador sea guatemalteco; tampoco se recorre todo el mundo ni se deduce país por nombre/horario/ubicación de una cuenta.
- Solo eventos publicados de Ultimate, `events(limit:50,filter:{videogameId:[1386],published:true})`. Si se llega a 50 se rechaza el resultado por no poder comprobar cobertura; no se publican los primeros 50 como si fueran todos. No se excluyen dobles, equipos, online ni eventos pequeños por admisión del ranking.
- Sin fechas de inicio no es posible comprobar futuro: se detiene la captura. Torneos que comenzaron mientras se leían páginas se eliminan antes de cerrar la captura. El publicador comprueba de nuevo antes de STOR y antes de RNTO.
- **Null significa que no está informado.** Conteos reales de cero sí se conservan. Timestamp 0 es fecha no informada, no 1/ene/1970. Coordenadas `(0,0)` se pasan a null porque no corresponden a un lugar de Guatemala; no se corrigen otras coordenadas ni se geocodifica.
- Sin zona IANA informada, fechas desde el epoch conocido se expresan en **UTC +00:00**, y `timezone` permanece null. No se inventa `America/Guatemala`. Una zona inválida o fin anterior al inicio detiene la captura.

## Contrato de agenda.json (schemaVersion 1)

Raíz exacta; no añadir campos personales:

| Campo | Tipo / significado |
| --- | --- |
| `schemaVersion` | Entero 1; independiente de public.json. |
| `generatedAt` | ISO 8601 con zona UTC; cierre de captura completa. |
| `requests` | Intentos API de esta captura. |
| `coverage` | `{countryCode:"GT", videogameId:"1386", complete:true, pagesFetched, rawTournaments}`. Raw incluye algún torneo que pudo empezar mientras se capturaba. |
| `tournaments` | Array; orden por instante de inicio, luego ID (string). Vacío puede ser una respuesta válida comprobada. |

Cada torneo:

| Campo | Tipo / origen |
| --- | --- |
| `id` | ID **de torneo** real, string de dígitos. No es ID de usuario. |
| `name`, `slug`, `url` | String o null; URL HTTPS de start.gg, ligada al slug. Si falta URL pero existe slug válido se construye su enlace canónico. |
| `countryCode` | `"GT"` informado y comprobado. |
| `startAt` | ISO 8601 con offset, obligatorio y futuro al publicar. |
| `endAt`, `registrationClosesAt`, `eventRegistrationClosesAt` | ISO 8601 con offset o null. Los dos cierres son distintos: inscripción del torneo frente a inscripción en eventos; no sustituir uno por otro. |
| `timezone` | Zona IANA de start.gg o null. |
| `city`, `department` | String o null; department copia `addrState`, no se normaliza a una lista oficial. |
| `venueName`, `venueAddress` | String o null; lugar/dirección publicados, sin contactos aparte. |
| `latitude`, `longitude` | Número válido o null. Sin uno de los dos no hay distancia. |
| `isOnline` | Boolean o null **tal como Tournament lo define**: al menos un evento online de cualquier videojuego. No significa que todo Ultimate sea online. |
| `attendanceType` | `offline`, `online`, `mixed` o null, derivado solo de eventos de Ultimate; si faltan banderas y no se comprueba mezcla, null. |
| `isRegistrationOpen` | Boolean o null informado en el corte; no se calcula a partir de un cierre ni garantiza que siga abierto hoy. |
| `numAttendees` | Número o null: inscritos totales **incluyendo espectadores y otros juegos**. No es un total único de jugadores Ultimate. |
| `isOfflineSingles` | True si hay un evento conocido de singles presencial; false si se sabe que no; null cuando no se puede determinar. **Candidato**, no admisión al ranking ni confirmación de 20 activos. |
| `events` | Array completo de eventos publicados de Ultimate, orden por ID. |

Cada evento tiene exactamente: `id`, `name`, `slug`, `url`, `videogameId:"1386"`, `startAt`, `type`, `competitionType`, `isOnline`, `numEntrants`, `teamRosterSize`, `isOfflineSingles`.

- IDs reales **de evento**, no de personas. `startAt` puede ser null; cuando existe lleva offset en la zona del torneo o UTC si falta la zona.
- `type`: entero nullable de la API. `competitionType`: `singles` cuando type=1 (mismo valor usado por el pipeline existente), `doubles` para roster fijo de 2, `teams` para roster fijo mayor de 2; si no se sabe, null. **No** se infiere por el nombre. `teamRosterSize` es null o `{minPlayers, maxPlayers}`, cada valor nullable, sin IDs de integrantes.
- `numEntrants`: inscritos del evento, nullable. En dobles/equipos cuenta entrants/equipos, no personas; no sumar los eventos para obtener jugadores únicos.
- `isOfflineSingles` describe solo ese evento, con la misma regla nullable anterior.

La allowlist es estricta en todos los niveles; campos extra se rechazan. Nunca se piden/publican dueños, cuentas, correo, teléfono, contactos ni listas/IDs de participantes.

## Relevo de pantalla para Claude Code

Leer primero [brief para Claude Design](BRIEF-CLAUDE-DESIGN-TORNEOS.md), esperar su handoff y usar este contrato. Esta entrega no implementa HTML/CSS/JS.

1. Leer **solo** `data/agenda.json` estático, por ejemplo con `fetch(...,{cache:'no-cache'})`; no start.gg por visitante. El JSON versionado es una captura inicial, no se actualiza en Git en cada ejecución: la copia viva está en FTP.
2. **Filtrar `startAt <= Date.now()` al renderizar**: un archivo estático diario inevitablemente conserva un anuncio cuando empieza, o si el último refresh falla. El publicador evita entregar algo empezado en ese instante, pero no puede retirar un torneo futuro de un archivo ya servido cuando avanza el reloj. No mostrar esos registros como próximos, incluso si la captura lleva menos de 48 h.
3. Mostrar «no informado» para null, no cero, no inscrito, no abierto/cerrado supuesto. Renderizar texto con `textContent`; nombres/direcciones son texto del organizador, no HTML confiable.
4. Para presencial/online de Ultimate usar `attendanceType` o eventos, **no** solo `Tournament.isOnline`. El filtro del ranking se presenta como «candidato: singles presencial; falta confirmar actividad», nunca «ya cuenta».
5. Si falta latitud/longitud mostrar «sin distancia». «Cerca de mí» se calcula localmente con permiso; no envía ni guarda la posición.
6. Fechas visibles en Guatemala, manteniendo el instante ISO. `isRegistrationOpen` es del momento de captura: enlazar a start.gg para confirmar e inscribirse. Aplicar estado desactualizado después de 48 h y error de lectura por separado.

## Publicación y fallos

`scripts/smash/agenda.py` usa Python estándar. `capture` solo lee la API y escribe localmente por archivo temporal/replace; no abre FTP. `validate` no toca red. `publish` sin `--apply` solo valida: cero FTP/API/SQL.

Publicación autorizada: valida versión, futura/frescura (máximo 48 h), campos/IDs únicos, URLs HTTPS start.gg ligadas a su torneo/evento, offsets, coordenadas/rangos, conteos, orden y **512 KiB máximo**. CWD solo a la carpeta FTP configurada y `data/`; STOR a `agenda.json.<UUID>.tmp`, y RNTO a `agenda.json` después de validar otra vez. No borra el destino para poder reemplazarlo. Fallo previo a RNTO limpia únicamente su temporal y mantiene el archivo anterior; un acuse perdido de RNTO puede dejar **el nuevo archivo completo**, no medio JSON: revisar el run/archivo antes de repetir.

Una captura vacía con totales/páginas ausentes, error GraphQL o conteo incoherente **no** llega a publicarse. Vacío completo verdadero (total=0, lista=[], página 0/1) sí existe: antes de subir se lee acotadamente la agenda anterior. Si aún contiene un anuncio futuro, se detiene para revisión; si estaba vacía/no existe/solo tiene torneos pasados, puede renovarse vacía. Un 550 ambiguo/permisos en esa lectura no se interpreta como «no hay archivo». **Matiz conservador:** una cancelación legítima de todos los torneos futuros también frena; requiere revisión del dueño, no un flag para eludir el guard. No borrar manualmente filas/archivos por rutina.

El workflow **smash-agenda.yml**, propuesto diario **07:17 Guatemala / 13:17 UTC**, comparte `group: smash-gt-publication`, `cancel-in-progress:false` con publicación semanal, assets y mains. También serializa capturas que usan el token. Secretos FTP solo en el paso de publicación. Nada de discover/rank/deploy genérico/SQL. Una captura/validación fallida termina el job antes del FTP; no usa la semilla de Git como fallback.

**agenda.json NO se añade a FILES de deploy.py**: un assets-only o corte semanal no debe restaurar una captura vieja de Git. Solo el nuevo flujo lo reemplaza. No se modifican los otros workflows.

## Comandos y activación — solo tras la orden del dueño

Pruebas locales sin credenciales:

```sh
python3 -m unittest discover -s scripts/smash -p test_agenda.py -v
python3 -m unittest discover -s scripts/smash -q
```

Captura manual con el token ya configurado en entorno privado, **sin pegarlo al chat/CLI**:

```sh
python3 scripts/smash/agenda.py capture
python3 scripts/smash/agenda.py validate ranking-smash-ultimate/data/agenda.json
python3 scripts/smash/agenda.py publish ranking-smash-ultimate/data/agenda.json
```

La última línea NO sube nada. Una semilla histórica puede fallar validate al quedar pasada: es correcto, capturar de nuevo. Los tests de la semilla validan estructura a su generatedAt y no prometen que siga siendo futura para siempre.

Después de aprobar/fusionar esta PR, primero una ejecución **solo lectura** del nuevo flujo:

```sh
gh workflow run smash-agenda.yml --repo Bucaro-19/rankingsmashbros --ref main -f publish=false
```

**Solo con orden de publicar**, primer envío fresco (no subir la semilla guardada):

```sh
gh workflow run smash-agenda.yml --repo Bucaro-19/rankingsmashbros --ref main -f publish=true
```

Comprobar que solo `https://rankingsmashbros.com/data/agenda.json` cambió y responde como JSON completo. Para activar el diario **con su aprobación**: variable de Actions `SMASH_AGENDA_ENABLED=true`; para pausar, false. Ya se reutilizan STARTGG_TOKEN, FTP_SERVER/USERNAME/PASSWORD y SMASH_FTP_DIR; no hay secreto nuevo ni servicio de coste. Una rama puede capturar por workflow_dispatch, pero el paso FTP está bloqueado fuera de main. Un push/PR no captura ni despliega. Hasta esa autorización la variable queda sin configurar, el scheduler no se activa y no se envía nada.

## Comprobado y pendiente

19 pruebas nuevas: cliente paginado, vacíos y errores, preservación local, null/0, formatos/candidatos, validación/privacidad/relaciones, límites, STOR/RNTO parcial/acuses perdidos, fechas que pasan durante STOR, vacíos protegidos, traversal, modo sin FTP y contrato del workflow. **81 pruebas Python del pipeline** correctas. CI estándar mantiene pruebas en MySQL 8.0/MariaDB 10.11; esta tarea no necesita escribir ninguna base para probar captura/FTP.

Pendiente: revisión PR/orden de fusión y primer envío/activación diaria; pantalla y estados de Claude Design/Claude Code. La captura real, esquema y archivo sí están comprobados; la publicación en BanaHosting solo se probó con FTP simulado, **no** con el FTP de producción.
