# Smash GT: importación y publicación

Página: `ranking-smash-ultimate/`. Destino previsto: `https://ingporras.com/ranking-smash-ultimate/`.
Esta es la implementación activa. El prototipo anterior de datos se conserva en `../SmashRankingGT`, fuera de este repositorio.

## Estado

- Web estática sin dependencias de compilación: búsqueda, filtros nacionales/internacionales, detalle de jugador, estados vacíos/error y consulta del archivo público cada 60 segundos mientras la página está visible.
- La vista local contiene un **top 100 piloto**, calculado con 23 eventos guatemaltecos y tres extranjeros y 6,739 sets competitivos de 2026. Se observaron 155 candidatos con al menos dos eventos y cuatro sets; la página muestra los primeros 100. Véase [METODOLOGIA.md](METODOLOGIA.md).
- Diseño de arena en `arena.css`: fondo oscuro, tipografía de combate, acentos rojo/azul/amarillo y una ilustración vectorial propia de dos figuras sobre una plataforma.
- Importador nacional con paginación completa y deduplicación por set. País público como candidatura, no como nacionalidad verificada. El importador anterior de un perfil y sus rivales permanece para pruebas de cobertura.
- Exportación pública separada de las capturas crudas: solo alias, perfil público, resultados presenciales completados y metadatos necesarios. Descarta byes, marcadores DQ reconocibles y participantes desconocidos. La elegibilidad final de eventos y DQ ambiguos aún requiere revisión.
- Publicación por el mismo FTP que usa el portafolio, limitada a una carpeta fija, con sustitución de cada archivo después de completar su subida. `public.json` se sube al final; no se borran archivos existentes de otros proyectos. La raíz de la cuenta se verifica en la primera ejecución real.
- El ranking usa un método propio transparente y puntos TTS estimados desde el [tierer público de UltRank](https://github.com/kenniky/ultrank-scoring). No calcula la posición exacta de UltRank ni confirma la elegibilidad nacional. El rastreo internacional solo alcanza a jugadores descubiertos localmente o añadidos con fuente documentada.

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
python3 scripts/smash/publish_ranking.py scripts/smash/data/combined.json scripts/smash/data/pilot-ranking.json ranking-smash-ultimate/data/public.json
```

El final es exclusivo en UTC. Usar `STARTGG_TOKEN` en el entorno o la entrada oculta interactiva. No poner el token en código ni en el frontend. No ejecutar recolectores simultáneos. El paso extranjero se puede reanudar desde su captura guardada; si aparecen eventos nuevos, documentarlos en `curation.json` como aprobados o excluidos antes de continuar con `--fetch`. La tabla TTS y las capturas crudas se guardan en `scripts/smash/data/`, ignorada por Git; solo la exportación pública se versiona.

## GitHub Actions

`smash-check.yml` verifica código en pushes y pull requests. No publica.

`smash-publish.yml` descubre eventos guatemaltecos e internacionales completos, verifica que todos los internacionales hallados tengan decisión en `curation.json`, descarga la tabla TTS fijada, calcula el piloto y publica solo si todos los pasos anteriores terminan correctamente. La programación sigue desactivada sin `SMASH_SYNC_ENABLED=true`. Un evento extranjero nuevo detiene la actualización hasta su revisión.

`smash-deploy-snapshot.yml` permite publicar manualmente la captura pública ya versionada, sin consumir de nuevo la API de start.gg. Sirve para la primera publicación o para recuperar una subida fallida; la actualización diaria siempre usa el flujo completo.

Configuración necesaria:

- Secret `STARTGG_TOKEN`: Personal Access Token de start.gg.
- Secrets existentes: `FTP_SERVER` (hostname sin protocolo), `FTP_USERNAME`, `FTP_PASSWORD`. Se espera el mismo directorio inicial y el mismo protocolo FTP usado por el workflow del portafolio.
- Variable opcional `SMASH_START`: inicio de consulta, por defecto `2026-01-01`. No es una declaración de temporada oficial.
- Variable `SMASH_SYNC_ENABLED=true`: habilita la ejecución diaria de las 12:23 UTC / 06:23 Guatemala **después** de revisar la primera importación. Sin esta variable, el trabajo programado se omite. La ejecución manual sí funciona sin ella.

El ranking piloto se publicó en `https://ingporras.com/ranking-smash-ultimate/` el 28 de septiembre de 2026. La variable `SMASH_SYNC_ENABLED=true` está configurada para actualizarlo diariamente. El workflow de publicación general excluye la carpeta del ranking para conservarla.

GitHub puede retrasar ejecuciones programadas y desactivarlas por inactividad en repositorios públicos; la página siempre muestra cuándo se obtuvieron los datos. La frecuencia del navegador no cambia la frecuencia de consulta de start.gg.

## Comprobación

```sh
python3 -m unittest discover -s scripts/smash -v
node --check ranking-smash-ultimate/app.js
git diff --check
```

Veinte pruebas de datos y publicación local, incluidas las exclusiones DQ, la cobertura internacional, el requisito de captura completa y las candidaturas documentadas. Vista local revisada con 100 posiciones, búsqueda y detalle de jugador.

`STARTGG_TOKEN` está guardado en GitHub Secrets y la captura completa pasó en GitHub Actions. Conviene rotarlo porque se compartió en el chat: primero sustituir el secreto de GitHub por el token nuevo y después revocar el anterior en start.gg. No se guarda el valor en archivos del repositorio ni se incluye en la exportación.

Pendientes: revisar la elegibilidad de jugadores y eventos con la comunidad, localizar jugadores guatemaltecos que compiten solo en el extranjero, rotar el token y reexaminar las fuentes TTS cuando cambie la temporada.
