# Prueba de carga controlada — Smash GT

Encargo del 8/oct/2026. **Producción no medida.** Esta entrega prepara un guion; ejecutarlo contra BanaHosting requiere la orden expresa del dueño, la captura de Uso de recursos y un horario elegido por él. No hay fusión ni despliegue.

## La respuesta que podemos dar

El caso principal **completó los seis escalones hasta 40 visitantes virtuales**: 1,482 peticiones, 0 errores, p95 a 40 = **42 ms**, 78 descargas iniciales y 468 respuestas 304 del JSON. Los perfiles estático/PHP anónimo y el análisis con sesión también completaron 40 sin errores. En análisis, p95 a 40 fue **563 ms**. La escritura quedó limitada a 2 visitantes y produjo **9 visitas falsas solo locales**. [Resumen por escalón](loadtest-local/summary-20261008.csv). [Resultado principal local](loadtest-local/visitor-20261008.json). No se sustituye una medición de BanaHosting por la de una Mac. «N visitantes» significa **N visitantes virtuales activos durante un escalón**, no el máximo de personas que pueden tener una pestaña abierta, ni un número prometido para premium.

En producción aún no sabemos **N** (aguanta sin degradarse), **M** (se pone lento) ni **K** (falla). También está pendiente qué recurso del plan se agota primero. Si la escalera llega a 40 sin degradarse, la conclusión será «al menos 40 bajo este recorrido y en ese horario», **no** «el máximo es 40». Nunca se sube el tope para buscar una caída.

## Laboratorio — mediciones comprobadas

Mac Apple M4 Pro, 12 CPU lógicas, 24 GiB RAM, macOS 26.6.2, PHP 8.5.3, MariaDB 13.0.2 y Python 3.9. Hosting real: versiones/límites diferentes; no extrapolar. Base independiente: 3,435 jugadores, 47 eventos, 8,985 sets, 4,787 games, 9,530 selecciones y 376 posiciones. JSON del repo igual al del paquete: **3,067,344 bytes**; gzip precalculado **189,182 bytes**. Sin TLS/red de internet, ni JS/imágenes/fuentes completos.

| Visitantes virtuales | Peticiones | p95 HTTP | Errores | JSON 200 / 304 |
| --- | --- | --- | --- | --- |
| 1 | 19 | 7.7 ms | 0 | 1 / 6 |
| 2 | 38 | 5.5 ms | 0 | 2 / 12 |
| 5 | 95 | 11.4 ms | 0 | 5 / 30 |
| 10 | 190 | 23.9 ms | 0 | 10 / 60 |
| 20 | 380 | 27.0 ms | 0 | 20 / 120 |
| 40 | 760 | 42.1 ms | 0 | 40 / 240 |

Todos esos escalones duraron 60 s y se completaron; máximo 12.7 peticiones/s a 40. RSS PHP agregado observado: 62,896 KiB (~61.4 MiB, suma de cinco procesos con posible doble conteo de páginas compartidas). `Threads_running` observado: 1 incluyendo el monitor; el muestreo de 1 s puede perder los picos de consultas rápidas. CPU del proceso cliente/frente/monitor en el escalón de 40: 1.429 s en 60 s; no sugiere saturación del generador en este caso. **No se agotó un recurso observado, no encontramos M ni K antes del tope.** No está demostrado que el hosting soporte 40; tampoco que el laboratorio falle a 41.

### Perfiles separados

Cada escalón duró 60 s. Los perfiles de lectura también completaron 1/2/5/10/20/40; la escritura se limitó a 1/2. Los JSON adjuntos guardan p50/p95/p99, bytes, códigos y recursos de cada escalón.

| Perfil | Mayor escalón completo | Peticiones totales | p95 en ese escalón | Errores | Visitas falsas locales |
| --- | --- | --- | --- | --- | --- |
| [Visitante](loadtest-local/visitor-20261008.json) | 40 | 1,482 | 42.1 ms | 0 | 0 |
| [Estático](loadtest-local/static-20261008.json) | 40 | 1,482 | 32.1 ms | 0 | 0 |
| [PHP sin SQL](loadtest-local/php-no-db-20261008.json) | 40 | 468 | 31.8 ms | 0 (401 esperado) | 0 |
| [PHP con lectura](loadtest-local/php-read-20261008.json) | 40 | 468 | 29.5 ms | 0 | 0 |
| [PHP con escritura](loadtest-local/php-write-20261008.json) | **2** | **9** | 7.1 ms | 0 | **9** |
| [Análisis autenticado local](loadtest-local/analysis-local-20261008.json) | 40 | 468 | 562.8 ms | 0 | 0 |

El contador aumentó exactamente **9** en SQL desechable: 3 + 6 POST, sin tocar el techo de 10. No permite concluir cómo se comporta con 40 escrituras simultáneas: ese caso está prohibido por el guion. **Producción: cero visitas falsas.** Las bases temporales se eliminan al acabar; no se borra ni corrige una fila del hosting.

Los seis perfiles sanos suman **4,377 peticiones**. Los cinco perfiles de lectura completaron hasta 40; no se alcanzó M (lentitud >3 s) ni K (errores >1 %) en el laboratorio bajo estos recorridos. El análisis fue el caso más lento, pero eso **no prueba** qué recurso se agotaría primero: no se alcanzó un límite. En su repetición se observaron 281,120 KiB de RSS PHP agregado (~274.5 MiB), 5 procesos PHP y `Threads_running` máximo 5 incluido el monitor. Son observaciones con muestreo de 1 s, no límites del hosting ni perfiles completos de CPU/E/S SQL.

**Incidente del laboratorio, separado del resultado de capacidad:** el primer intento autenticado recibió un único 401 y el freno terminó al instante, en el escalón de 1. Las sesiones se habían creado antes de los otros cinco perfiles; PHP local tiene `session.gc_maxlifetime=1440` (24 min) y la batería anterior tomó unos 30 min. Ese fixture no aseguraba una sesión viva al llegar al análisis. Ahora renueva las 40 sesiones independientes por CLI inmediatamente antes de ese perfil, sin cambiar los parámetros de sesión del servidor ni las cuentas de producción. La repetición completa con otra instancia MariaDB desechable creada por `local_run.py` terminó con 468 respuestas 200, cero errores y los seis escalones completos. Ese comando automático también limpió correctamente su servidor, base y sesiones locales. El 401 no demuestra «falla con un usuario» ni se mezcla con los errores de los perfiles sanos.

**Base medida y reproducibilidad:** los cinco primeros perfiles copiaron el sitio de `0a99525` (#59); el análisis corregido también inició antes de rebasar la rama. La rama de entrega se actualizó después sobre main `54d7d45` (#62), CI [37843876447](https://github.com/Bucaro-19/rankingsmashbros/actions/runs/37843876447) correcta: los cambios posteriores son SEO, imagen compartida y documentación; las APIs/PHP y `public.json` medidos permanecen iguales. Esos pequeños cambios de cabecera HTML no están medidos en los primeros perfiles. No prometer tiempos idénticos tras cualquier cambio de producto.

## Límites del plan — pendiente del dueño

Solicitada una captura de **cPanel → Uso de recursos**, con límites, uso actual y fallos. No deducirlos del nombre del proveedor ni usar valores típicos de otros planes. La cuenta comparte recursos con los demás sitios del dueño; medirlos mientras sus otros sitios trabajan es parte del contexto, no atribuir todo a Smash GT.

| Recurso | Límite del plan | Uso antes/durante/después | Fallos |
| --- | --- | --- | --- |
| CPU (%) | Pendiente | Pendiente | Pendiente |
| Memoria física (MiB) | Pendiente | Pendiente | Pendiente |
| Procesos de entrada (EP) | Pendiente | Pendiente | Pendiente |
| E/S (KiB/s) | Pendiente | Pendiente | Pendiente |
| Operaciones de E/S por segundo (IOPS) | Pendiente | Pendiente | Pendiente |
| Procesos totales (NPROC) | Pendiente | Pendiente | Pendiente |

Pedir también que confirme el tiempo máximo del worker cada cinco minutos. El guion deja **90 segundos tras cada frontera de cinco minutos y 90 antes de la siguiente**, incluyendo margen para terminar peticiones. Si el worker no cabe en esa franja o coincide otra tarea de publicación/mantenimiento, **no ejecutar**: acordar otra ventana o ampliar la exclusión en una revisión del guion. No detener ni cambiar el cron en esta entrega. No usar herramientas SEO/marketing, SSH o APIs de cPanel.

## Guion y alcance

- `scripts/loadtest/smash_load.py`: cliente **Python estándar** (Mac/Linux), sin navegador, crawlers, servicios externos, proxies de entorno ni dependencias del medidor. Por defecto solo imprime un plan, sin HTTP. `--execute` es explícito; en producción se exige además `--production`, `--owner-authorized`, la ventana y los límites comprobados. Un flag **no reemplaza la orden del dueño en el chat**.
- `local_run.py`: crea su propio MariaDB temporal en loopback, con `--no-defaults`, contraseña aleatoria en memoria, y lo elimina al acabar. No lee `~/.my.cnf`. Usa MariaDB/PHP ya instalados, sin descargar ni instalar software. PyMySQL es únicamente la dependencia ya usada por las pruebas/importadores SQL para preparar el laboratorio; el cliente de producción no la necesita.
- `local_site.py`: copia temporal del sitio, instala esquema/migraciones solo en una base nueva `smash_load_test_*` y aplica un paquete ya guardado. PHP CLI con `PHP_CLI_SERVER_WORKERS=4` (padre + cuatro hijos observados); frente local Python sirve estáticos con gzip precalculado/ETag/304 y reenvía solo endpoints permitidos a PHP. No es LiteSpeed/BanaHosting. Una cuenta y 40 sesiones de administrador **sintéticas locales**, creadas por CLI, permiten medir análisis sin serializar todo por un único archivo de sesión. No hay endpoint de login de prueba publicado ni llamadas OAuth.

**Topes escritos en el código, sin argumentos para aumentarlos:**

| Control | Valor |
| --- | --- |
| Visitantes por escalón | 1, 2, 5, 10, 20, 40; techo 40 |
| Duración activa | 60 s por escalón |
| Pausa entre escalones | 10 s; en producción además se espera la franja sin cron |
| Peticiones por escenario/ejecución | Máximo 2,000, compartido por todos los hilos y escalones |
| Escrituras del contador | Solo local; máximo 10 peticiones, máximo 2 visitantes |
| Lote local | Cada uno de los 6 escenarios una sola vez; techo 12,000 peticiones por lote |
| Timeout de E/S por petición | 4 s, sin reintentos |
| Admisión de escalones | Hasta 30 min, incluida espera de ventana/cron; se termina lo ya en vuelo |
| Respuesta recibida / JSON descomprimido | 8 MiB / 32 MiB |

Un bloqueo local impide dos ejecuciones del medidor a la vez en esta máquina. No repartir la prueba entre varias máquinas/IP para multiplicar esos topes. No ejecutar simultáneamente el cliente de producción y otras herramientas de carga.

**Freno:** tras cada respuesta, detiene nuevas peticiones y no sube de escalón si errores >1 % o p95 >3 s. También frena si el p95 de un endpoint supera 3 s: muchos estáticos rápidos no pueden ocultar un PHP lento. Se termina lo que ya estaba en vuelo (máximo 40, timeout 4 s), se guarda lo medido y se termina la escalera. El lote local también se detiene; no sigue con otros escenarios tras un freno. Timeout, 5xx/508, 429, redirecciones y respuestas inesperadas cuentan como errores. TLS/DNS/conexión/JSON inválido se distinguen con códigos sin imprimir el texto de la excepción: un freno por configuración no demuestra falta de capacidad del hosting. El timeout es de E/S del socket; no es una garantía de reloj absoluto para DNS ni para un cuerpo que llega por fragmentos. Un 401 esperado del caso PHP sin SQL no cuenta como error. El freno se evalúa desde la primera respuesta, por prudencia; un fallo temprano puede detener un escalón aunque su porcentaje final baje cuando terminen las peticiones ya en vuelo. `Ctrl+C` guarda el informe parcial. El cliente y el laboratorio terminan con código 3 si no completan la escalera.

Solo se permite `https://rankingsmashbros.com` en producción y `http://127.0.0.1:PUERTO` en local. Sin URLs con credenciales, rutas arbitrarias o query libre, sin redirects ni desactivar TLS. `User-Agent: SmashGT-LoadTest`. No encuesta, creación de cuentas reales, pagos, premium API, OAuth, start.gg, Recurrente, webhook ni ranking-sync/worker. No se descargan fonts de Google, GitHub o imágenes externas.

## Qué significa el recorrido

**Visitante principal:** cada visitante virtual navega la portada, obtiene public.json y consulta account-api.php anónimo. Su primera navegación obtiene el JSON 200 y **comprueba inmediatamente una revalidación condicional** con ETag/Last-Modified; las navegaciones posteriores usan ese validador. Reutiliza su cookie anónima PHP. No usa cache-busting/no-store.

Repite el recorrido cada **10 segundos**, con un visitante por hilo y peticiones secuenciales dentro de su recorrido: es una simulación conservadora de visitantes **que vuelven a cargar la página**, más intensa que una pestaña quieta que revalida cada 60 s. La comprobación 304 inmediata sirve para probar ese camino dentro de un escalón de 60 s; **no reproduce el reloj exacto del app.js**. Si cambia el corte, un 200 condicional es válido y se actualiza el validador. No hay porcentajes de «usuarios reales» derivados de peticiones/s. El p95 mide respuesta HTTP hasta descargar el cuerpo, no pintura/LCP en un teléfono.

`visita.php` queda **excluido de ese recorrido y de todas las pruebas de producción**: el resultado principal no incluye su coste. Se mide por separado solo en local, 1 y 2 visitantes durante 60 s, una petición cada 20 s (9 peticiones previstas, techo 10). No se borran ni ajustan filas de producción.

Casos separados:

| Caso | Peticiones | Qué cubre / limitación |
| --- | --- | --- |
| `static` | Portada + JSON 200/304 + arena.css | Transferencia/validadores; sin ejecutar JS ni cargar todo el arte/fonts. |
| `php-no-db` | analisis-api.php anónimo (401 esperado) | PHP, sesión de archivos y rechazo previo a SQL; no análisis premium. |
| `php-read` | account-api.php anónimo | Consulta `tournament_catalog`; actualmente sí abre SQL aunque el visitante no esté vinculado. En este paquete V2 el catálogo está vacío: no mide un catálogo futuro grande. |
| `php-write` | POST visita.php | Transacción real del contador, solo en SQL desechable. 204 no garantiza escritura: verificar incremento de `SUM(views)` antes/después. |
| `analysis-local` | analisis-api.php, yo/rival del corte, sesiones locales independientes | Lectura completa de JSON/SQL, matrices y acceso admin local; jamás se habilita por argumento para producción. |

account-api.php puede ocultar un fallo del catálogo y visita.php oculta fallos de escritura: el HTTP por sí solo no certifica salud de la base. El clon SQL sano y los conteos permiten verificar el laboratorio; en producción harían falta los recursos/fallos observados por el dueño. No prestar una sesión real para esta entrega: el guion la rechaza en producción.

Por escalón se guarda peticiones/s, p50/p95/p99, errores/códigos/tipo, bytes del cuerpo transferido, duración y completitud. Hay también desgloses por endpoint. **No** guarda bodies, cookies, CSRF, secretos, usuarios, IP de visitantes o comentarios. `driverProcessCpuSeconds` es CPU del proceso del medidor; en el laboratorio este proceso también hospeda el frente estático/proxy/monitor, por lo que no es CPU de BanaHosting ni de PHP. El monitor SQL muestrea una vez por segundo; sus máximos observados pueden omitir picos breves. RSS de PHP suma procesos y puede contar páginas compartidas varias veces. No confundir RSS agregado con `memory_limit=512M` por proceso.

## Repetir en local

Desde la raíz del repositorio, con PHP y MariaDB ya disponibles, usando el Python de pruebas que ya tiene PyMySQL:

```sh
/tmp/smash-db-runtime/bin/python scripts/loadtest/local_run.py \
  --package "$HOME/.smash-gt-context-oct4-20261007/ranking-v2.json" \
  --output-dir /tmp/smash-load-oct4
```

Ese paquete es una **copia local ya guardada**, no una descarga ni una lectura de SQL de producción; no publicarlo en Git. Si no se conserva, omitir `--package` usa el fixture sintético pequeño de los tests: sirve para probar el circuito, **no** para comparar capacidad con el corte completo. `--scenarios visitor` permite repetir solo un caso; no permite elevar concurrencia/duración/topes ni repetir el mismo caso dentro del lote. Si el Python indicado no existe, usar un entorno local con la dependencia de SQL ya utilizada (`PyMySQL==1.1.2`); no son credenciales ni un servicio de pago.

Los resultados quedan en el directorio elegido, uno por caso y un resumen. El servidor, esquema y sesiones temporales se limpian; las mediciones se conservan. Las calibraciones interrumpidas para ajustar el cliente no forman parte del resultado definitivo. No bajar duraciones o umbrales para producir un informe de capacidad. Los seis casos definitivos conservaron sus 60 s por escalón; el freno solo apareció en pruebas sintéticas y en el intento con sesión inválida. Los escenarios autenticados renuevan primero sus sesiones locales para que la espera de los demás perfiles no invalide el fixture.

Pruebas rápidas de seguridad (los tests usan fixtures/tiempos simulados, no son la medición):

```sh
python3 -m unittest discover -s scripts/loadtest -v
```

17 pruebas de topes/frenos/contratos, incluida compresión PHP y renovación de sesiones; 62 regresiones del pipeline también correctas. CI propia `smash-load-test.yml`: únicamente esas pruebas contra loopback, sin secreto ni ejecución de carga en producción. Los scripts no están en FILES del FTP ni se publican en el servidor.

## Producción: comando preparado, aún no ejecutar

1. Dueño: adjuntar captura de Uso de recursos y completar la tabla de límites/uso/fallos. Confirmar duración del worker, ausencia de publicación u otros mantenimientos y margen para los visitantes reales. Acordar una madrugada **lunes–viernes** (se bloquean sábado y domingo enteros, conservadoramente). Vigilar cPanel durante la prueba y cancelar con Ctrl+C si ve fallos nuevos, CPU/memoria/EP saturados o lentitud real; no esperar un 508 para intervenir.
2. Guardar fuera de Git `~/smash-load-private/limits.json`, **solo** estos campos con los límites reales. Sustituir null; el guion rechaza valores sin completar. `workerWindowConfirmed` se pone true únicamente al verificar que el worker termina dentro de los primeros 90 s.

```json
{"cpuPercent":null,"memoryMiB":null,"entryProcesses":null,"ioKiBps":null,"iops":null,"processes":null,"workerWindowConfirmed":false}
```

3. Guardar la captura como `~/smash-load-private/uso-recursos.png`. Es evidencia privada; no subirla con datos de la cuenta al repo. Dejar libres al menos 29 minutos (los 6 escalones ocupan franjas de cron diferentes); como máximo 30 min por ejecución. Si la ventana no alcanza, el guion guarda lo logrado y termina, sin extrapolar.
4. **Solo cuando el dueño dé la orden y sus horas**, introducir sus fechas ISO con zona Guatemala. Estos parámetros de horario son los únicos que requieren completar; no hay contraseña ni sesión real:

```sh
SMASH_LOAD_START='FECHA_Y_HORA_ELEGIDA_POR_EL_DUENO-06:00'
SMASH_LOAD_END='FIN_DE_LA_VENTANA_ELEGIDA_POR_EL_DUENO-06:00'
python3 scripts/loadtest/smash_load.py \
  --origin https://rankingsmashbros.com --production --scenario visitor \
  --output "$HOME/smash-load-private/produccion-visitante.json" \
  --resource-snapshot "$HOME/smash-load-private/uso-recursos.png" \
  --limits-file "$HOME/smash-load-private/limits.json" \
  --window-start "$SMASH_LOAD_START" --window-end "$SMASH_LOAD_END" \
  --owner-authorized --execute
```

Formato de fecha: `AAAA-MM-DDTHH:MM:SS-06:00`. No se asigna una fecha concreta sin su elección. Para ver el plan con **cero HTTP**, quitar `--execute`; ese es el modo seguro por defecto. No copiar `--execute` mientras se estén rellenando los archivos. Otros casos anónimos usan el mismo comando cambiando solo `--scenario` por `static`, `php-no-db` o `php-read`, **en ventanas distintas autorizadas**. `php-write` y `analysis-local` están prohibidos en producción en este guion.

Después: comparar recursos/fallos antes/durante/después y resultados; añadir al informe N/M/K observados o «no alcanzado dentro del tope», primer recurso afectado y otras tareas activas. Las visitas falsas de **producción son cero** por diseño. No borrar ni «descontar» filas: si otro encargo autorizase escrituras, tendría que medir su incremento y declararlo expresamente. Para atribuir CPU/RAM/EP hace falta cPanel; los tiempos HTTP solos no identifican la causa.

## Recomendaciones por impacto (no implementadas)

1. **Conservar la revalidación 304 y comprobar compresión/caché real.** Ya se cambió a no-cache. Una actualización semanal no requiere descargar el corte entero cada minuto. Si no hay 304, arreglar eso primero. No desactivar cache ni añadir cache-busting para «refrescar».
2. **Reducir trabajo PHP repetido por corte, especialmente análisis.** Perfil/matrices de escena que no dependen del visitante pueden prepararse/cachearse por corte con invalidación clara; mantener permisos premium en servidor. Optimizar después de perfilar, sin inventar un nuevo índice por intuición ni alterar resultados. Revisar también la consulta de catálogo por visita anónima.
3. **Separar el coste del contador.** No confundir la lectura del ranking estático con las escrituras y locks del contador. Evaluar agregación/cola o menor frecuencia si el caso de escritura/cPanel muestra presión; requiere otro encargo y conservar privacidad/conteos.
4. **Peso y frecuencia.** Estudiar separar el listado inicial de historiales completos y revalidar menos seguido mientras el ranking solo cambia semanalmente. Pasar de 60 a 300 s reduciría **80 % de las consultas periódicas de pestañas quietas**, estimación aritmética, no aumento de capacidad medido; afecta frescura y debe decidirse como producto. No cambia las recargas manuales ni las llamadas PHP.
5. **Plan del hosting, solo con evidencia.** Si EP/CPU/RAM/IO llega a su límite con pocos visitantes tras las medidas anteriores, hablar con BanaHosting sobre el recurso concreto. No prometer que «más RAM» soluciona un límite de procesos ni recomendar comprar antes de medir. No se contrata ningún servicio extra.
