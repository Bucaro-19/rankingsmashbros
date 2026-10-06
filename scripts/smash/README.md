# Smash GT: importación y publicación

Página: `ranking-smash-ultimate/`. Destino previsto: `https://ingporras.com/ranking-smash-ultimate/`.
Esta es la implementación activa. El prototipo anterior de datos se conserva en `../SmashRankingGT`, fuera de este repositorio.

Próxima revisión: consultar los [acuerdos del 1 de octubre de 2026](ACUERDOS-2026-10-01.md) antes de modificar las reglas o ampliar el producto. Incluyen el mínimo nacional de 20 participantes, mantener 2 torneos/4 sets, constancia, cuadro de puntos, ranking completo y top 15 por organizador. La ampliación del listado y el mínimo de 20 activos están implementados; la ficha ya muestra actividad mensual y el estudio de constancia está publicado; los bonos y el top 15 por organizador siguen pendientes.

## Primera ampliación: consulta gratuita de todos los clasificados

- `rank.py` conserva `ranking` con el top 100 para auditorías y simulaciones, y añade `fullRanking` con todas las posiciones elegibles. No cambia la puntuación ni las reglas de admisión.
- `publish_ranking.py` exporta todo `fullRanking`, junto a sus sets válidos, y marca `rankingCoverage: all_eligible`. La publicación verifica el total de clasificados, IDs únicos, posiciones consecutivas y coincidencia con el top 100. Conserva compatibilidad con capturas antiguas.
- La web abre en Top 100, permite ver todos los clasificados y busca alias en todo el listado. El detalle permite recorrer todos los sets exportados de ese jugador de veinte en veinte; no promete su historial completo de start.gg. El puesto y el historial básico son gratuitos, sin cuenta.
- El flujo semanal existente calcula y publica el listado completo para todos. Conserva el último corte ante errores; la hora programada no garantiza que GitHub termine a esa hora. El artefacto de auditoría ahora incluye el JSON público del corte para recuperación y revisión.
- Se reutilizan BanaHosting para servir la web y GitHub Actions para el cálculo. Esta fase no requiere una suscripción nueva; el costo adicional depende del consumo de las cuotas existentes de la cuenta. El acceso con start.gg, la agenda, las funciones premium y los pagos quedan para fases posteriores.
- Desde BT-PILOTO-3, los torneos de Guatemala requieren 20 participantes activos (personas distintas con un set válido), en todo el país. Fuera de Guatemala se mantienen 64 activos. La bonificación por constancia sigue pendiente; los pesos de los sets no cambian.

## Estado

- Web estática sin dependencias de compilación: búsqueda, filtros nacionales/internacionales, detalle de jugador, estados vacíos/error y consulta del archivo público cada 60 segundos mientras la página está visible. La página `metodologia.html` explica el cálculo y lista los torneos incluidos y exclusiones documentadas usando el mismo JSON que el top.
- La vista local contiene un **top 100 piloto de 2026**, calculado con 23 eventos guatemaltecos y tres extranjeros y 6,739 sets competitivos del primer corte. El periodo comienza el 1 de enero de 2026 y termina en la fecha local visible de cada consulta. Se observaron 155 candidatos con al menos dos eventos y cuatro sets; la página muestra los primeros 100. Véase [METODOLOGIA.md](METODOLOGIA.md).
- Cada corte semanal muestra el cambio de puesto frente al corte público anterior de la misma temporada y versión del método. La primera comparación puede ser con el último corte de pruebas; la fecha exacta está en el JSON. La edición 2026 seguirá siendo provisional hasta la revisión comunitaria de nacionalidad y torneos. Al cerrar 2026 se debe guardar su corte final antes de configurar 2027.
- `encuesta.php` recibe opiniones anónimas sin GitHub ni otro servicio: no pide identidad ni registra IP en la respuesta. Guarda una línea JSON por respuesta en `ranking-smash-ultimate/feedback-data/respuestas-2026.php`, después de una primera línea PHP que bloquea acceso directo; además, la carpeta se protege con `.htaccess` y se conserva entre despliegues. Revisar respuestas desde el administrador de archivos del alojamiento, omitiendo la primera línea; no compartir el archivo públicamente. Antes de difundir la encuesta, verificar que `feedback-data/.htaccess` devuelve acceso denegado y que el formulario puede escribir.
- `analisis-torneos.html` conserva la comparación histórica del corte con mínimo 32 con la excepción TTS estimada de 200 puntos/dos jugadores valorados y con mínimos exploratorios de 24 y 16 activos. Se capturaron 37 eventos locales con menos de 32 inscritos; dos superan la excepción numérica tras descartar Squad Strike y formatos especiales. Ningún evento de The Oven la supera. Esta página es una simulación histórica fechada: la publicación semanal ahora aplica 20 activos (BT-PILOTO-3). Sus resultados extranjeros se mantienen fijos al corte anterior indicado en la página.
- El organizador consulta las respuestas en `https://ingporras.com/ranking-smash-ultimate/opiniones.php` con una clave privada. La página muestra conteos, promedios y respuestas individuales, omitiendo el envío de prueba interna. No enlazarla desde la web pública. La contraseña solo se guarda fuera del repositorio; el secreto de Actions `SMASH_FEEDBACK_ADMIN_HASH` contiene un hash bcrypt que se publica como archivo PHP protegido en `feedback-data/`. Cambiar ese secreto y publicar solo recursos rota la clave sin modificar respuestas ni el ranking.
- Diseño de arena en `arena.css`: fondo oscuro, tipografía de combate, acentos rojo/azul/amarillo y una ilustración vectorial propia de dos figuras sobre una plataforma.
- Importador nacional con paginación completa y deduplicación por set. País público como candidatura, no como nacionalidad verificada. El importador anterior de un perfil y sus rivales permanece para pruebas de cobertura.
- Exportación pública separada de las capturas crudas: solo alias, perfil público, resultados presenciales completados y metadatos necesarios. Descarta byes, marcadores DQ reconocibles y participantes desconocidos. La elegibilidad final de eventos y DQ ambiguos aún requiere revisión.
- Publicación por el mismo FTP que usa el portafolio, limitada a una carpeta fija, con sustitución de cada archivo después de completar su subida. `public.json` se sube al final; no se borran archivos existentes de otros proyectos. La raíz de la cuenta se verifica en la primera ejecución real.
- El ranking usa un método propio transparente y puntos TTS estimados desde el [tierer público de UltRank](https://github.com/kenniky/ultrank-scoring). No calcula la posición exacta de UltRank ni confirma la elegibilidad nacional. El rastreo internacional solo alcanza a jugadores descubiertos localmente o añadidos con fuente documentada.
- [Plan de criterios para una lista nacional verificable](PLAN-RANKING.md) y [auditoría reproducible de la captura inicial](AUDITORIA-PILOTO-2026-09-28.md). El flujo diario guarda una auditoría de cada corte como artefacto de GitHub Actions.

## Vista local

Desde la raíz del repositorio:

```sh
python3 -m http.server 4317 --bind 127.0.0.1 --directory ranking-smash-ultimate
```

Abrir `http://127.0.0.1:4317/`. Para comprobar la ruta de despliegue, servir la raíz del repositorio solo en la máquina local y abrir `/ranking-smash-ultimate/`; no publicar el árbol del repositorio entero.

## Regenerar el piloto con datos reales

```sh
python3 scripts/smash/discover.py --start 2026-01-01 --end 2026-09-29
python3 scripts/smash/discover_abroad.py scripts/smash/data/national.json --curation scripts/smash/curation.json --fetch
python3 scripts/smash/fetch_tts.py
python3 scripts/smash/combine.py scripts/smash/data/national.json scripts/smash/data/abroad.json scripts/smash/data/combined.json
python3 scripts/smash/rank.py scripts/smash/data/combined.json scripts/smash/data/pilot-ranking.json --curation scripts/smash/curation.json --points-csv scripts/smash/data/ultrank_players.csv
python3 scripts/smash/publish_ranking.py scripts/smash/data/combined.json scripts/smash/data/pilot-ranking.json ranking-smash-ultimate/data/public.json --curation scripts/smash/curation.json
```

El final es exclusivo en UTC. Usar `STARTGG_TOKEN` en el entorno o la entrada oculta interactiva. No poner el token en código ni en el frontend. No ejecutar recolectores simultáneos. El paso extranjero se puede reanudar desde su captura guardada; si aparecen eventos nuevos, documentarlos en `curation.json` como aprobados o excluidos antes de continuar con `--fetch`. La tabla TTS y las capturas crudas se guardan en `scripts/smash/data/`, ignorada por Git; solo la exportación pública se versiona.

Para repetir el estudio sin tocar el top público, ejecutar el workflow manual `smash-study-small-events.yml`, descargar su artefacto privado `national.json` y calcular con `study_small_events.py`, pasando la última captura combinada extranjera, `curation.json`, la tabla TTS fijada y el destino `ranking-smash-ultimate/data/analisis-torneos.json`. Pasar además `--published-public` apuntando al corte histórico de BT-PILOTO-1 (no al corte actual de BT-PILOTO-3): el programa exige que el escenario base reproduzca exactamente las cien posiciones, eventos y sets publicados. El estudio usa jugadores con un set competitivo para estimar puntos y contar valorados; esto es conservador frente a la revisión oficial de UltRank. Revisar formatos, restricciones de participación, DQ y series semanales antes de adoptar eventos que superen el umbral numérico.

## GitHub Actions

`smash-check.yml` verifica código en pushes y pull requests. No publica.

`smash-publish.yml` descubre eventos guatemaltecos e internacionales completos, verifica que todos los internacionales hallados tengan decisión en `curation.json`, descarga la tabla TTS fijada, calcula el piloto y publica solo si todos los pasos anteriores terminan correctamente. Un evento extranjero nuevo detiene la actualización hasta su revisión. Las capturas privadas se conservan 7 días en `smash-gt-capturas`; tras revisar `curation.json`, el campo manual `resume_run_id` permite retomar esa misma captura, sin repetir el catálogo nacional ni los historiales ya consultados. Solo acepta artefactos de este workflow en `main`; las validaciones de coincidencia y cobertura siguen vigentes. La programación exige `SMASH_SYNC_ENABLED=true`.

`smash-deploy-snapshot.yml` permite publicar manualmente la captura pública ya versionada, sin consumir de nuevo la API de start.gg. Su opción `assets_only=true` publica únicamente HTML, estilos, JavaScript y el formulario, conservando el corte actual en el servidor. Sin esa opción sirve para la primera publicación o para recuperar una subida fallida; el corte semanal usa el flujo completo.

Configuración necesaria:

- Secret `STARTGG_TOKEN`: Personal Access Token de start.gg.
- Secret `SMASH_FEEDBACK_ADMIN_HASH`: hash bcrypt de la clave del panel privado de opiniones; es obligatorio para cualquier despliegue de Smash GT.
- Secrets existentes: `FTP_SERVER` (hostname sin protocolo), `FTP_USERNAME`, `FTP_PASSWORD`. Se espera el mismo directorio inicial y el mismo protocolo FTP usado por el workflow del portafolio.
- Variable opcional `SMASH_START`: inicio de consulta, por defecto `2026-01-01`. No es una declaración de temporada oficial.
- Variable `SMASH_SYNC_ENABLED=true`: habilita las ejecuciones programadas. Sin esta variable, los trabajos programados se omiten; la ejecución manual sigue disponible.
- Variable `SMASH_RELEASE_MODE=testing`: actualiza a diario a las 12:23 UTC / 06:23 Guatemala.
- Variable `SMASH_RELEASE_MODE=weekly`: actualiza los domingos a las 00:00 en `America/Guatemala`, incluso mientras el ranking es piloto. Es el modo público previsto desde esta fase.
- Variable `SMASH_RELEASE_MODE=production`: conserva el mismo horario semanal cuando se aprueben elegibilidad, torneos y reglas finales. Un valor ausente no activa ninguna programación.

El ranking piloto se publicó en `https://ingporras.com/ranking-smash-ultimate/` el 28 de septiembre de 2026. `SMASH_SYNC_ENABLED=true` habilita la programación; el workflow de publicación general excluye la carpeta del ranking para conservarla.

GitHub puede retrasar ejecuciones programadas, especialmente a la hora en punto, y desactivarlas por inactividad en repositorios públicos; la página siempre muestra cuándo se obtuvieron los datos. La frecuencia del navegador no cambia la frecuencia de consulta de start.gg.

## Comprobación

```sh
python3 -m unittest discover -s scripts/smash -v
node --check ranking-smash-ultimate/app.js
node --check ranking-smash-ultimate/metodologia.js
git diff --check
```

Veinte pruebas de datos y publicación local, incluidas las exclusiones DQ, la cobertura internacional, el requisito de captura completa y las candidaturas documentadas. Vista local revisada con 100 posiciones, búsqueda y detalle de jugador.

`STARTGG_TOKEN` está guardado en GitHub Secrets y la captura completa pasó en GitHub Actions. Conviene rotarlo porque se compartió en el chat: primero sustituir el secreto de GitHub por el token nuevo y después revocar el anterior en start.gg. No se guarda el valor en archivos del repositorio ni se incluye en la exportación.

La ejecución completa del 29 de septiembre de 2026 importó y calculó de nuevo el piloto y publicó por FTP. El JSON servido en el dominio confirma la actualización de ese corte.

Pendientes: revisar la elegibilidad de jugadores y eventos con la comunidad, localizar jugadores guatemaltecos que compiten solo en el extranjero, rotar el token y reexaminar las fuentes TTS cuando cambie la temporada.

## Estudio fechado del top 20 y constancia (3 de octubre de 2026)

`analisis-top20.html` conserva el corte del 2 de octubre, 16:33 Guatemala, sin modificar el ranking. `study_top20.py` exige reproducir exactamente las posiciones, puntuaciones, actividad, eventos, sets, fecha y método publicados antes de generar la comparación. Usa todos los clasificados en las simulaciones de bonos, prueba retirar cada evento y recalcula también sin el bloque internacional. El indicador de convergencia es un diagnóstico privado opcional y no cambia el cálculo habitual. Los bonos son hipótesis, no reglas aprobadas.

Regeneración manual: `python3 scripts/smash/study_top20.py <combined.json_del_corte> scripts/smash/curation.json scripts/smash/data/ultrank_players.csv <public.json_del_mismo_corte> ranking-smash-ultimate/data/analisis-top20.json`. Revisar los hallazgos antes de actualizar el estudio; la página detecta si el ranking tiene otro corte y se identifica como histórica. La publicación semanal no regenera ni adopta los bonos.

## Interruptor de alcance (6 de octubre de 2026)

`public.json` mantiene la clasificación combinada como raíz y añade `localRanking`, calculada de nuevo sobre eventos y sets GT del mismo corte. No se filtran ni renumeran posiciones combinadas: se reajustan los rivales y la elegibilidad local. La consulta inicial mantiene incluidos los internacionales; cambiar de vista conserva la búsqueda y Top 100/listado completo, actualiza estadísticas e historial, y reinicia el filtro de resultados para evitar combinar alcances. La selección se conserva durante las actualizaciones de la página.

La exportación semanal usa `--include-local --points-csv` con la misma tabla TTS del cálculo principal. Ambas vistas se publican dentro de un solo JSON para impedir cortes desparejados. Los puestos anteriores locales proceden exclusivamente del `localRanking` del corte anterior, y el primer corte local no muestra movimientos. El servidor y el navegador rechazan vistas con fechas, métodos o eventos locales incompatibles. El catálogo de metodología acepta `?scope=guatemala` para consultar la evidencia de esa vista.

## Fichas de actividad (6 de octubre de 2026)

Cada clasificado de ambas vistas publica `activity.months` y un registro `activity.events` por ID con victorias y derrotas. Los meses usan la fecha local del evento en Guatemala y solo sets competitivos de eventos admitidos. Cada resultado lleva `eventId`, para consultar en la ficha todos los sets o únicamente los de un torneo. El calendario distingue meses sin registro de los posteriores al corte. No se interpreta la falta de cobertura como inactividad comprobada.

La exportación semanal incorpora estos campos sin cambiar fuerzas, puntuaciones, reglas ni movimientos. El despliegue coteja cada registro con los sets exportados (el orden de `playerIds` es ganador/perdedor), con los totales de cada jugador y con las fechas del catálogo. La interfaz tolera capturas antiguas sin actividad durante una publicación y valida la coherencia del registro nuevo. `metodologia.html#puntos-en-claro` explica los cuatro casos de victoria/derrota, la fuerza retrospectiva de rivales y la constancia; no se adoptó ningún bono.

Próximo bloque de producto: top 15 por organizador y temporada. Antes de atribuir eventos a una persona, hace falta un catálogo verificable de organizadores y torneos; los nombres parecidos por sí solos no prueban quién los organizó. Siguen pendientes la elegibilidad de ese top particular y el contexto de fuerza elegido.
