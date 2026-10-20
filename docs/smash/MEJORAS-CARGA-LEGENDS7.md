# Progreso y propuestas de carga de Legends 7 — 19/oct/2026

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
