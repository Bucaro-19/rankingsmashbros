# Smash GT: importación y publicación

Página: `ranking-smash-ultimate/`. Destino previsto: `https://ingporras.com/ranking-smash-ultimate/`.
Esta es la implementación activa. El prototipo anterior de datos se conserva en `../SmashRankingGT`, fuera de este repositorio.

## Estado

- Web estática sin dependencias de compilación: búsqueda, filtros nacionales/internacionales, detalle de jugador, estados vacíos/error y consulta del archivo público cada 60 segundos mientras la página está visible. La página `metodologia.html` explica el cálculo y lista los torneos incluidos y exclusiones documentadas usando el mismo JSON que el top.
- La vista local contiene un **top 100 piloto de 2026**, calculado con 23 eventos guatemaltecos y tres extranjeros y 6,739 sets competitivos del primer corte. El periodo comienza el 1 de enero de 2026 y termina en la fecha local visible de cada consulta. Se observaron 155 candidatos con al menos dos eventos y cuatro sets; la página muestra los primeros 100. Véase [METODOLOGIA.md](METODOLOGIA.md).
- Cada corte semanal muestra el cambio de puesto frente al corte público anterior de la misma temporada y versión del método. La primera comparación puede ser con el último corte de pruebas; la fecha exacta está en el JSON. La edición 2026 seguirá siendo provisional hasta la revisión comunitaria de nacionalidad y torneos. Al cerrar 2026 se debe guardar su corte final antes de configurar 2027.
- `encuesta.php` recibe opiniones anónimas sin GitHub ni otro servicio: no pide identidad ni registra IP en la respuesta. Guarda una línea JSON por respuesta en `ranking-smash-ultimate/feedback-data/respuestas-2026.php`, después de una primera línea PHP que bloquea acceso directo; además, la carpeta se protege con `.htaccess` y se conserva entre despliegues. Revisar respuestas desde el administrador de archivos del alojamiento, omitiendo la primera línea; no compartir el archivo públicamente. Antes de difundir la encuesta, verificar que `feedback-data/.htaccess` devuelve acceso denegado y que el formulario puede escribir.
- `analisis-torneos.html` compara el corte actual con la excepción TTS estimada de 200 puntos/dos jugadores valorados y con mínimos exploratorios de 24 y 16 activos. Se capturaron 37 eventos locales con menos de 32 inscritos; dos superan la excepción numérica tras descartar Squad Strike y formatos especiales. Ningún evento de The Oven la supera. Esta página es una simulación fechada: la publicación semanal conserva 32 inscritos y 32 activos hasta que se apruebe una nueva regla. Sus resultados extranjeros se mantienen fijos al corte anterior indicado en la página.
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

Para repetir el estudio sin tocar el top público, ejecutar el workflow manual `smash-study-small-events.yml`, descargar su artefacto privado `national.json` y calcular con `study_small_events.py`, pasando la última captura combinada extranjera, `curation.json`, la tabla TTS fijada y el destino `ranking-smash-ultimate/data/analisis-torneos.json`. Pasar además `--published-public ranking-smash-ultimate/data/public.json`: el programa exige que el escenario base reproduzca exactamente las cien posiciones, eventos y sets publicados. El estudio usa jugadores con un set competitivo para estimar puntos y contar valorados; esto es conservador frente a la revisión oficial de UltRank. Revisar formatos, restricciones de participación, DQ y series semanales antes de adoptar eventos que superen el umbral numérico.

## GitHub Actions

`smash-check.yml` verifica código en pushes y pull requests. No publica.

`smash-publish.yml` descubre eventos guatemaltecos e internacionales completos, verifica que todos los internacionales hallados tengan decisión en `curation.json`, descarga la tabla TTS fijada, calcula el piloto y publica solo si todos los pasos anteriores terminan correctamente. Un evento extranjero nuevo detiene la actualización hasta su revisión. La programación exige `SMASH_SYNC_ENABLED=true`.

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
