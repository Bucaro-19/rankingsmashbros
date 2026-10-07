# Smash GT — contexto para Claude u otro agente

## Producto y restricciones
- Web: https://rankingsmashbros.com/ (nueva, desde el 6 de octubre de 2026) y https://ingporras.com/ranking-smash-ultimate/ (anterior, redirigida el 7/oct) en BanaHosting, HTML/CSS/JS vanilla, PHP para encuesta anónima y panel privado de opiniones.
- Repo `Bucaro-19/rankingsmashbros`, público por decisión del dueño (6 de octubre de 2026). Dominio comprado: `rankingsmashbros.com`; migración en `MIGRACION.md`. Este repo publica en el dominio nuevo; el repo viejo `Bucaro-19/rsvp-graduacion` conserva el historial anterior; su URL ya redirige al sitio nuevo. El cálculo corre en Actions; el navegador solo presenta resultados.
- Ranking experimental 2026, no oficial ni fórmula exacta de UltRank. Perfiles de país GT y excepciones documentadas son candidatos, no nacionalidad verificada.
- Torneos locales: 20 participantes activos (un set competitivo cada uno), incluyendo interior del país. Extranjeros: 64 activos. Jugadores: 2 eventos y 4 sets, participación local; DQ/bye/WO no cuentan.
- BT-PILOTO-3: Bradley–Terry regularizado, pesos TTS estimados de tabla fijada y repeticiones de rivales. No cambiar pesos ni elegir posiciones a mano.
- Top 100 principal; búsqueda y puesto básico de todos gratuitos. Donaciones/premium, agenda y top 15 por organizador siguen pendientes. Cuentas y backend OAuth preparados: OAuth configurado y vinculación real de Bucaro19 comprobada; ver CUENTAS-OAUTH.md.
- Constancia: estudio publicado, sin bono aprobado. Calendario de meses, torneos y sets en la ficha. Consulta gratuita sin cuenta.

## Diseño y relevo
- Pantallas nuevas: solicitar primero a Claude Design mediante un brief y esperar el handoff. Instrucción del dueño; backend sin pantallas puede avanzar.
- Claude Code debe leer AGENTS.md/CLAUDE.md, este contexto, EN-CURSO.md y SIGUIENTE-FASE.md, y mantener el relevo actualizado.

## Base de datos (fase actual)
- Acceso directo desde la Mac del dueño: `/opt/homebrew/opt/mysql-client/bin/mysql` (usa `~/.my.cnf`; IP autorizada en Remote MySQL). Reglas y límites en BASE-DE-DATOS.md, sección «Acceso directo a la base». Sin SSH.
- Instalación y conexión PDO confirmadas por el diagnóstico del hosting compartido por el dueño el 6/oct/2026 (Guatemala): MariaDB 11.4.13, schema 001_accounts_competition, 31 tablas, 87 selecciones, missingTables=[], schemaReady=true. Conector publicado en PR #4–#6; último despliegue 37578387425. El agente recibió el resultado, no lo leyó directamente en Chrome (la herramienta bloqueó la página). Los demás conteos están en cero antes de importar. Guía `BASE-DE-DATOS.md`; siguiente fase `SIGUIENTE-FASE.md`: paquete privado/importadores. No reinstalar ni volver a pedir credenciales por rutina.
- OAuth para identidad y acceso autorizado; no garantiza multiplicar cuota. Esta fase descarta tokens después de verificar identidad. Si en el futuro se persisten para sincronización/reportes, cifrarlos con llave fuera de la base/Git. La web actual sigue con JSON.
- Primera importación SQL de Codex completada el 7/oct/2026: PR #9/main e685fb2, cutId=1 publicado, 188 clasificados por vista. Paquete desde captura privada con IDs reales; transacción, paridad y repetición verificadas. 3435 jugadores incluyen rivales extranjeros y no equivalen a guatemaltecos clasificados. Encuesta ya migrada y publicada en SQL (13 respuestas de comunidad + 3 de prueba). El semanal prepara un paquete de importación; cargador desde la Mac entregado por Claude, sin automatización instalada. Los artefactos del repo público son descargables por usuarios de GitHub. Reparto para Claude: TRABAJO-PARALELO-2026-10-07.md.

## Arquitectura
- `discover.py` captura GT; `discover_abroad.py` descubre y revisa eventos extranjeros; `combine.py` reúne capturas; `rank.py` calcula; `publish_ranking.py` exporta; `deploy.py` valida y publica por FTP.
- `public.json` contiene ranking combinado en raíz y `localRanking` calculado independientemente con solo GT. Mismo corte/método. Flechas: `previousRank` solo si existe `previousCutAt` de misma vista, temporada y método.
- `activity.events`: ID de evento, victorias, derrotas por jugador. `activity.months`: meses locales GT del evento. Cada `result` tiene `eventId`, `playerIds` en orden ganador/perdedor y marcador. Catálogo `events` aporta metadatos y enlaces.
- No filtrar/renumerar puestos combinados para simular la vista GT. No usar `analisis-top20.json` como historial de todos: es un estudio histórico del 2 de octubre.
- `data/public.json` puede ser más viejo en Git que en producción: comprobar antes de reemplazar. La publicación semanal no hace commit del corte.

## Operación
- Secretos del pipeline en GitHub Secrets: STARTGG_TOKEN, FTP_SERVER/USERNAME/PASSWORD, SMASH_FEEDBACK_ADMIN_HASH. Credenciales de base y OAuth en archivos privados hermanos del sitio. No imprimir ni copiar secretos al repo/documentación. El token compartido en chat necesita rotación por el dueño; no reutilizar desde mensajes.
- Actualización: `.github/workflows/smash-publish.yml`. Variables `SMASH_SYNC_ENABLED=true`, `SMASH_RELEASE_MODE=weekly`: domingo 00:00 Guatemala; puede demorar. Conservar último corte ante fallo/importación parcial.
- `.github/workflows/smash-deploy-snapshot.yml`: `assets_only=true` preserva public.json; false sube snapshot versionado. JSON se renombra al final. No borrar feedback-data ni otros proyectos.
- Flujo usado: rama → PR → CI → merge → workflow → verificar datos y navegador. Adjuntar PR al hilo si la herramienta está disponible.
- Pruebas: `python3 -m unittest discover -s scripts/smash -q`, `node --test scripts/smash/test_app.cjs`, `node --check ranking-smash-ultimate/app.js`, `git diff --check`.
- Vista local: `python3 -m http.server 4323 --bind 127.0.0.1 --directory ranking-smash-ultimate`.

## Referencias
- Acuerdos: `scripts/smash/ACUERDOS-2026-10-01.md`.
- Operación y metodología: README.md, METODOLOGIA.md, PLAN-RANKING.md en scripts/smash.
- Rediseño y mains: estado vivo en `EN-CURSO.md`. Último avance previo: PR #22, commit 6b5192c. Calendarios y torneos por jugador publicados, 50 pruebas correctas. Corte Oct4: 188 clasificados, 42 eventos combinados / 39 locales. Actividad generada sin cambiar puntos/puestos.
