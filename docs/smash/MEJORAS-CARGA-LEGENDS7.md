# Progreso y propuestas de carga de Legends 7 — 19/oct/2026

Plan solicitado después por el dueño: [PLAN-IMPLEMENTACION-CARGA-LEGENDS7.md](PLAN-IMPLEMENTACION-CARGA-LEGENDS7.md). La barra se publicó el 19/oct; el plan de captura sigue pendiente de implementación.

## Barra del panel privado

La tarjeta «Historiales de Legends 7» usa el archivo activo privado `private-smash/analysis-context/1687524.json`. Se lee con límite de 2 MiB, sin seguir enlaces simbólicos, sin crear directorios/archivos y sin incluir configuración o secretos. Ignora `.pending`: solo muestra el estado que el worker dejó activo después de importar. Una lectura inválida aísla esta tarjeta; no deja el resto del panel fuera de servicio.

Contrato aditivo de panel-api.php: **analysisProgress** (fuera de report, por lo que las cifras/listas de registros conservan su contrato). Mismo control smash_stats_is_owner, 401/403 y no-store/private; no endpoint nuevo. No expone nombres, IDs de jugadores/cuentas, páginas individuales, revisión/hash, lista de inscritos, rutas o mensajes de error internos. Solo el evento fijo Legends 7 y estos agregados:

- `registered`: inscritos del último roster confirmado.
- `preexisting`: inscritos fuera de coverage porque el sincronizador ya los encontró en SQL. **No equivale a temporada completa.**
- `targets`: cantidad de historiales programados en coverage.
- `completed`: objetivos con complete=true y nextPage>totalPages.
- `partial`: objetivos no terminados con al menos una página confirmada.
- `notStarted`: objetivos pendientes con nextPage=1.
- `pending`: partial+notStarted = targets-completed.
- `percentage`: completed/targets, redondeado a un decimal. No registered/known ni porcentaje de partidas descargadas. Con cero objetivos es 100 del plan, sin afirmar capturas nuevas.
- `pagesConfirmed`: suma de nextPage-1; explica avance aun cuando no termina ningún jugador. Una página vacía verificada también es una página procesada.
- `rosterCapturedAt`, `checkpointSavedAt`: consulta del roster y mtime del archivo leído, en Guatemala. El mtime pertenece al mismo descriptor que el contenido; no es la hora de finalización de Actions ni un cronómetro de importación.
- `authorizationEndsAt`: 26/oct/2026 00:00 Guatemala. No se amplía desde el panel.
- `status`: pending/complete/expired, o not_started/unavailable con conteos y porcentaje null. Unknown no se representa como 0%.
- `stale`: pendientes y más de 12 h sin guardar avance. Es advertencia de antigüedad, **no diagnóstico de fallo**.

La tarjeta tiene progressbar con aria-valuenow/valuetext y estado anunciado, conteos, fechas y «Actualizar progreso». Actualizar recarga el informe privado, recupera el foco en el botón y no hace consultas a start.gg. No hace polling ni lee Actions por visita. No se afirma que hay un job activo o que la variable está encendida. Se mantiene la frecuencia descriptiva actual de seis horas y la fecha límite; cambiar el cron exige actualizar ese texto.

El denominador puede crecer con nuevos inscritos y bajar el porcentaje sin perder páginas. 100% significa que el plan guardado no tiene objetivos incompletos, no que todos los torneos, marcadores o personajes existan en start.gg. El recorrido histórico de los jugadores preexistentes no se vuelve completo por este indicador.

## Cuello de botella comprobado en código

`scripts/smash/rival_history.py:capture_batch` recorre coverage en orden y mantiene un `while not complete` para un mismo jugador hasta agotar el presupuesto. `merge_state` vuelve a ordenar por ID; por eso un historial largo puede consumir repetidamente las tandas antes de dar turno al resto. No es un fallo de subida FTP: esta carga pasa por receptor firmado, cola y worker SQL.

Cada ejecución tiene dos tandas, cada una de máximo 30 intentos/120 s, una petición por segundo. Normalmente caben 28 páginas por tanda (reserva de reintentos), 56 por ejecución, 224 al día con cuatro ejecuciones. Cada página trae cinco sets antes de filtrar a 2026: **no son 1120 sets útiles garantizados**. El resumen real 39344382294 del 19/oct: 320 inscritos, 108 conocidos al inventariar, 249 historiales incompletos, 63 consultas y 368,872 s. Conocidos y pendientes se solapan; no deben sumarse. No se convierte 320-249 en un conteo demostrado de historiales de temporada completos.

start.gg documenta un promedio máximo de 80 solicitudes por 60 s y 1000 objetos anidados por petición: [fuente oficial](https://developer.start.gg/docs/rate-limits/), revisada el 19/oct. No aumentar paralelismo/perPage a ciegas, ni usar tokens de cuentas para repartir cuota.

## Cambios recomendados, todavía NO implementados

1. **Turnos justos por jugador.** Una página por objetivo en cada vuelta, priorizando nextPage más bajo y desempate estable. Al agotarse la tanda, el checkpoint ya permite reanudar; evita que uno monopolice. No necesita inventar avance o borrar checkpoints. Ensayar nuevos inscritos entre tandas, historiales enormes, reintentos, expiración y paridad Python/PHP. La prioridad de nuevos debe tener un límite para que nunca abandone a los ya parciales.
2. **Más vueltas pequeñas antes del torneo.** Proponer cada dos horas hasta la fecha ya autorizada, sin aumentar los techos por tanda ni la velocidad. Techo nominal: doce ejecuciones y 672 páginas/día, tres veces la frecuencia actual; a 320 inscritos se añaden unas siete consultas de roster por vuelta (más si crece/reintenta). No garantiza terminar el 25/oct. Medir cuota compartida, cola y tiempos antes de activar; seguir usando el mismo grupo de concurrencia con publicación/bracket. No se modifica la variable, el cron ni la autorización en esta entrega.
3. **Separar disponibilidad básica y detalle profundo.** Conseguir un primer avance por todos antes de profundizar games/personajes, mostrando historial parcial con claridad. NO asumir que la primera página contiene los sets más recientes: el código actual no pide un orden contractual ni filtro de fecha al servidor. Una versión de dos etapas (lista liviana de sets, detalle con caché por set/updatedAt) necesita comprobar el esquema y medir complejidad/consultas. Tampoco se deben crear identidades fingiendo que nextPage avanzó: el receptor exige progreso real.
4. **Medir rendimiento útil.** Jugadores que avanzaron, páginas y sets realmente de 2026 por tanda, tiempo de captura frente a espera del cron y fallos seguros. Añadir ETA solo cuando exista base suficiente y señalar incertidumbre. Revisar después si acortar el cron del worker (hoy cada cinco minutos) compensa en el plan compartido; no cambiar cPanel a ciegas.

Orden sugerido: rotación justa, medir varias tandas, luego probar dos horas; la captura en dos etapas queda como optimización posterior. En esta entrega no se cambia capturador, receptor/importador, cálculo, elegibilidad, public.json, migraciones ni producción.


## Fase 1 implementada en rama — 20/oct/2026

feat/fair-rival-history-batches, sin fusión/activación todavía. Reparto 3:1 explicado en AUTOMATIZACION-ANALISIS.md. La reserva se eligió al simular un checkpoint heredado con nextPage=201 y 27 nuevos: priorizar únicamente el menor nextPage dejaría quieto al parcial hasta que los demás alcanzaran su profundidad o terminaran. Se reservan turnos sin extender el estado ni cambiar los validadores.

Comparación **sin red ni SQL de producción**, ejecutando el capturador anterior del commit **0286a0e** y el nuevo contra el mismo cliente inventado, con el mismo presupuesto:

| Caso / política | Intentos | Jugadores con avance | Historiales terminados | Sin primera página | Páginas del historial largo |
|---|---:|---:|---:|---:|---:|
| Un largo nuevo + 27 de una página, anterior | 28 | 1 | 0 | 27 | 28 |
| Mismo caso, nuevo | 28 | 28 | 27 | 0 | 1 |
| Un largo parcial (201) + 27 nuevos de una página, anterior | 28 | 1 | 0 | 27 | 28 |
| Mismo caso, nuevo | 28 | 22 | 21 | 6 | 7 |

Es una comparación de distribución, **no una predicción** del roster real o su fecha de terminación. No aumenta consultas por tanda ni afirma que todos reciban datos útiles con una página. El historial largo avanza menos páginas en esa tanda porque reparte el presupuesto con otros, pero conserva todas las anteriores.

Tanda densa inventada por receptor/cola/worker SQL reales **locales**: 28 raíces, 28 consultas, **140 sets / 1400 games / 2800 selecciones**, **590778 B JSON**, aproximadamente **30790 B gzip** (el tamaño comprimido puede variar unos bytes con la fecha), **16 MiB de pico PHP**, aproximadamente **1,006 s** local sin latencia de start.gg ni espera del cron. Se conserva el techo específico de 8 MiB JSON del receptor de análisis (más estricto que el general de 32 MiB), 4 MiB comprimidos y 512M de PHP. Los límites de 150 sets/1500 games/3000 selecciones no cambian.

Regresiones añadidas: orden JSON canónico o invertido produce los mismos turnos; checkpoint antiguo/identidad ya conocida retoma cada nextPage; nuevos inscritos entre tandas sin repetir páginas; reserva rotativa y raíz que termina antes de su reserva; raíces completas/conocidas/vacías; reintentos agregados y 120 s compartidos entre raíces; error o consulta de más de 120 s conserva intacto el estado del llamador. HTTP firmado con 35 raíces deja defaults reales sin consultar y los conserva tras canonicalización; reanudación legado→nuevo, paridad de todas las tablas Python/PHP, simulación sin escrituras, repetición, recuperación tras commit y rollback. Se mantienen las pruebas de permisos gratis/premium, ranking/instantáneas/mains y public.json inventado intactos.

Local: MariaDB **13.0.2**, esquema propio desechable smash_schema_test_fair_history; no se presenta como MySQL 8.0 o MariaDB 10.11. La matriz requerida sigue en CI. El primer ensayo de la nueva prueba de paridad rechazó correctamente un roster recortado por alias de objetos en el fixture: se corrigió el fixture para copiar el roster como ya hace auto.run; no se relajó el receptor ni se cambió código productivo para aceptarlo.

Reproducción de contratos: `PYTHONPATH=scripts/database:scripts/smash python -m unittest test_rival_automation.FairHistory -v`. Integración completa: preparar una base **local desechable** como en CI, ejecutar test_schema.py y luego test_rival_automation.py con SMASH_SCHEMA_TEST_DB/PORT/PASSWORD exclusivamente de pruebas. La herramienta no necesita tokens ni acceso a start.gg. No se registra un ETA a partir de esta simulación.
