# Carga semanal del ranking a SQL — preparación (Claude Code, 7 de octubre de 2026)

Encargo: `RELEVO-CLAUDE-CODE-2026-10-07.md`, «preparación del transporte privado para cargar semanalmente el ranking en SQL». **Nada de esto está activado como tarea automática.** Lo entregado es un cargador de un solo comando, probado, que el dueño o un agente ejecuta desde la Mac del dueño, más el diseño del transporte desatendido en el servidor para una entrega posterior.

## Hechos que deciden el diseño (verificados el 7 de octubre)
- Servidor (Terminal de cPanel, salida pegada por el dueño): PHP 8.1.34, **Python 3.6.8**, `crontab` disponible. El importador revisado (`import_ranking.py` + `ranking_package.py`) necesita Python 3.9+ (`zoneinfo`, `:=`) y PyMySQL 1.1.2 exige 3.8+: **no puede ejecutarse en el servidor**.
- No hay SSH. La cuenta FTP de Actions está enraizada en el document root y viaja sin cifrar; no puede escribir en `private-smash/`. MySQL remoto solo acepta la IP de la Mac del dueño y debe seguir así.
- El paquete del corte del 4 de octubre pesa unos 9 MB; cada corte añade unos 3 MB a la base (instantánea de 2 MB más unas 6,800 filas).
- El repositorio es **público**: los logs de Actions son legibles por cualquiera y los artefactos los puede descargar cualquier usuario con sesión en GitHub. Las «capturas privadas» no lo son en ese sentido. Su contenido son resultados de torneos obtenidos de start.gg y el ranking ya publicado; no contienen credenciales. Decisión pendiente del dueño: aceptar esa exposición o volver privado el repositorio.
- La primera ejecución semanal de este repositorio es el domingo 11 de octubre de 2026 a las 00:00 de Guatemala.

## Decisión
1. **Ahora: carga operada desde la Mac** con `scripts/database/weekly_ranking_load.py`. Reutiliza sin cambios el importador ya revisado y probado en producción, no añade ninguna superficie nueva en el servidor y usa el único acceso a la base que existe.
2. **Después, si el dueño quiere independencia de la Mac: transporte desatendido en el servidor** (sección final). Exige portar el importador a PHP y un punto de recepción autenticado; es una entrega propia, con riesgo propio, y no se construyó a medias.

Se descartó ejecutar el importador Python en el servidor (versión insuficiente) y abrir MySQL a las IP de Actions (prohibido por el dueño).

## Qué hace el cargador
`python weekly_ranking_load.py status|load --database ivcjgjlk_smash [--apply] [--run-id N] [--allow-gap] [--notify]`

Pasos de `load`, en orden; cualquiera que falle detiene todo con un motivo y sin escribir:
1. Lee `https://rankingsmashbros.com/data/public.json` (destino fijo en el código, sin redirecciones, máximo 32 MiB).
2. Abre la conexión con el archivo privado del cliente (`~/.my.cnf`, permisos 600 obligatorios). Nunca imprime errores del driver.
3. Busca en `Bucaro-19/rankingsmashbros` la ejecución más reciente de `smash-publish.yml` en `main` que terminó con éxito (los ticks diarios con el trabajo omitido no cuentan) o la indicada con `--run-id`.
4. Descarga con `gh` el artefacto `smash-gt-paquete-sql` a una carpeta temporal 700 que siempre se borra.
5. Valida el paquete con el contrato existente (`validate_package`: hash, versión, relaciones, ambas vistas).
6. **Solo el corte publicado:** el `public` del paquete debe ser idéntico, en forma canónica, al `public.json` que el sitio sirve. Detiene paquetes viejos, cortes que no llegaron a publicarse y variantes con mains recapturados.
7. **Cronología:** no carga si hay un corte sin terminar en SQL, si el corte es más antiguo que el último guardado, o si su corte anterior no está en SQL (los enlaces al corte anterior no se rellenan después). `--allow-gap` acepta explícitamente ese último caso.
8. Llama a `import_package` en simulación. Con `--apply` escribe en una transacción y vuelve a llamar para exigir `already_imported` con el mismo `cutId` (segunda comprobación de paridad).

Salida: una sola línea JSON con motivo o estado, hash, fecha del corte, conteos por vista y `cutId`. Nunca credenciales, datos de conexión, contenido del paquete ni mensajes del driver.

| Código | Motivos | Qué significa |
|---|---|---|
| 0 | — | `validated_no_writes`, `imported` o `already_imported` |
| 2 | `usage` | Argumentos inválidos |
| 3 | `github_unavailable`, `run_not_found`, `artifact_unavailable`, `package_missing` | Sin sesión de `gh`, sin ejecución exitosa, artefacto vencido o la publicación no produjo paquete |
| 4 | `public_unavailable`, `package_invalid`, `not_the_published_cut` | El sitio no respondió, el paquete no cumple el contrato o no es el corte que el sitio muestra |
| 5 | `unfinished_cut_present`, `older_than_stored_cut`, `previous_cut_missing` | Requiere decisión humana; no «reparar» borrando o sobrescribiendo |
| 6 | `database_unavailable`, `import_rejected`, `parity_not_confirmed`, `unexpected_failure` | Conexión, conflicto de identidad/hash, colisión de relaciones o paridad no confirmada |

`status` solo lee: fecha del corte en vivo, cortes guardados y `sqlHasLiveCut`. Sirve para saber si la carga de la semana está pendiente.

## Cambios en la publicación semanal
- `smash-publish.yml` sube, **después** del paso de despliegue y solo si este tuvo éxito, el artefacto `smash-gt-paquete-sql` con `database-package.json`, retención de 90 días. Así una semana omitida se puede cargar más tarde, en orden. El artefacto de capturas sigue igual (7 días).
- Antes de generar el paquete se borra cualquier `database-package.json` previo: una ejecución reanudada trae el del corte anterior y no debe quedar como si fuera el nuevo.
- La preparación del paquete sigue con `continue-on-error`: un fallo ahí nunca bloquea la publicación del sitio.

## Operación
Preparación única en la Mac (el entorno de `/tmp` de la primera importación no sobrevive a un reinicio):
```sh
python3 -m venv ~/.smash-db-runtime
~/.smash-db-runtime/bin/pip install PyMySQL==1.1.2
gh auth status   # debe haber sesión con acceso al repositorio
```
Cada semana, desde la carpeta del repositorio en `main` actualizado:
```sh
cd scripts/database
~/.smash-db-runtime/bin/python weekly_ranking_load.py status --database ivcjgjlk_smash
~/.smash-db-runtime/bin/python weekly_ranking_load.py load --database ivcjgjlk_smash           # simulación
~/.smash-db-runtime/bin/python weekly_ranking_load.py load --database ivcjgjlk_smash --apply   # escribe
```
Si la IP de la casa cambió, `database_unavailable`: agregar la nueva en cPanel → Remote MySQL (nunca `%`).

### Programarlo (opcional, no instalado)
Solo después de al menos una carga manual correcta. Un `launchd` de usuario que ejecute `load --apply --notify` los domingos a las 02:00 y repita a las 08:00, 14:00 y 20:00 es seguro porque la carga es idempotente: si ya entró, responde `already_imported`. Requisitos: Mac encendida, sesión de `gh`, IP autorizada. Lista de activación:
1. Dos semanas seguidas de carga manual con `imported` y `status` al día.
2. El dueño aprueba que la Mac escriba en producción sin supervisión.
3. Instalar el `plist`, comprobar el primer disparo en `~/Library/Logs/` y dejar anotado en EN-CURSO.md.

## Pruebas
`python scripts/database/test_weekly_ranking_load.py`: selección de ejecución, validación del paquete (ausente, corrupto, manipulado, enlace simbólico, tamaño), corte publicado frente a variantes, reglas de cronología, una línea saneada por comando con limpieza de la descarga, rechazo de archivo de credenciales compartido y errores del driver ocultos. Con base desechable (`SMASH_SCHEMA_TEST_*`): simulación, aplicación, repetición, `status`, secuencia semanal con enlace al corte anterior, desorden, hueco con y sin `--allow-gap`, corte sin terminar, conflicto de identidad y fallo a mitad de importación sin tocar la historia. En CI corre en ambos trabajos (sin base y con MySQL 8.0/MariaDB 10.11).

Verificado directamente por Claude Code el 7 de octubre desde la Mac del dueño, solo lectura: `status` contra producción devolvió `storedCuts=1`, `sqlHasLiveCut=true` para el corte 2026-10-04T11:43:18.348499Z. `load` en simulación devolvió `run_not_found`, correcto: todavía no existe una publicación semanal exitosa en este repositorio. **No verificado hasta el domingo:** descarga real del artefacto y carga del segundo corte.

## Límites conocidos
- Depende de la Mac, de su IP y de `gh`. Si falla, el sitio sigue publicándose desde JSON y SQL se atrasa; `status` lo muestra. Nada avisa por sí solo salvo `--notify` cuando se ejecuta.
- El importador conserva las filas de contexto tal como se observaron por primera vez; las correcciones posteriores en start.gg solo llegan a las copias de cada corte. Refrescar el contexto es trabajo del futuro sincronizador en vivo, que no debe reescribir cortes.
- Cargar ejecuciones manuales o reanudadas crea más de un corte por semana; cada una tiene su propia fecha. El cargador toma la última exitosa: usar `--run-id` para elegir otra.
- Mains recapturados para un corte ya importado tienen otro hash: el importador lo trata como conflicto y se detiene. Falta decidir qué versión es la canónica en SQL.

## Diseño del transporte desatendido en el servidor (no implementado)
Para cuando se quiera prescindir de la Mac. Requisitos del relevo: privado y autenticado, tamaño y hash validados, sin repetición, idempotente, el último corte sobrevive a cualquier fallo, sin destinos arbitrarios, sin secretos en la URL, paquete nunca accesible públicamente.

- **Envío:** un trabajo de Actions posterior a la publicación hace `POST` HTTPS del paquete (comprimido) a un único punto PHP nuevo. Cabeceras: marca de tiempo, identificador de envío aleatorio y `HMAC-SHA256(clave, método + ruta + marca + identificador + sha256(cuerpo))`. La clave vive en un secreto de GitHub y en `private-smash/` (la coloca el dueño a mano una vez; Actions no puede escribir ahí).
- **Recepción:** el punto solo acepta `POST`, tamaño máximo fijo, marca de tiempo dentro de ±5 minutos, HMAC en tiempo constante, y registra el identificador en `sync_jobs` (`kind='ranking_import'`, `deduplication_key` = sha256 del paquete; la clave única impide repetir). Guarda el paquete en `private-smash/entrada/` con permisos 600 y responde sin importar nada. No devuelve datos.
- **Importación:** una tarea `cron` de cPanel ejecuta por CLI un importador PHP sobre la bandeja de entrada, con el mismo bloqueo `smash-ranking-import-v1`, una transacción por corte y las mismas reglas (identidad, hash, solo-insertar contexto, paridad antes de publicar). Compara además el paquete con el `data/public.json` local del sitio antes de importar. Actualiza `sync_jobs` a `succeeded` o `failed` con un código; el diagnóstico administrativo existente puede mostrar ese estado.
- **Paridad entre implementaciones:** el importador PHP debe pasar en CI una prueba cruzada: mismo paquete importado con Python y con PHP en bases desechables, volcado idéntico tabla por tabla. El hash se calcula sobre los bytes canónicos recibidos, no reserializando en PHP.
- **Antes de construirlo hay que medir** en el servidor: `memory_limit`, `post_max_size`, `max_execution_time` del PHP web y del CLI, y el tiempo real de una importación. Decodificar 9 MB de JSON puede necesitar más de 100 MB de memoria.
- **Riesgos que justifican no hacerlo a medias:** dos implementaciones de un contrato de unas 480 líneas que hay que mantener iguales, y un punto web nuevo capaz de escribir unas 40 mil filas con los privilegios completos del sitio.
