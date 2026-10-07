# Smash GT — contexto para Claude u otro agente

## Producto y restricciones
- Web: https://ingporras.com/ranking-smash-ultimate/ en BanaHosting, HTML/CSS/JS vanilla, PHP para encuesta anónima y panel privado de opiniones.
- Repo `Bucaro-19/rankingsmashbros`, público por decisión del dueño (6 de octubre de 2026). Dominio comprado: `rankingsmashbros.com`; migración en `MIGRACION.md`. Hasta completarla, producción sigue en la URL de arriba y la publica el repo viejo `Bucaro-19/rsvp-graduacion`. El cálculo corre en Actions; el navegador solo presenta resultados.
- Ranking experimental 2026, no oficial ni fórmula exacta de UltRank. Perfiles de país GT y excepciones documentadas son candidatos, no nacionalidad verificada.
- Torneos locales: 20 participantes activos (un set competitivo cada uno), incluyendo interior del país. Extranjeros: 64 activos. Jugadores: 2 eventos y 4 sets, participación local; DQ/bye/WO no cuentan.
- BT-PILOTO-3: Bradley–Terry regularizado, pesos TTS estimados de tabla fijada y repeticiones de rivales. No cambiar pesos ni elegir posiciones a mano.
- Top 100 principal; búsqueda y puesto básico de todos gratuitos. Donaciones/premium, OAuth, agenda y top 15 por organizador siguen pendientes.
- Constancia: estudio publicado, sin bono aprobado. Calendario de meses, torneos y sets en la ficha. Consulta gratuita sin cuenta.

## Arquitectura
- `discover.py` captura GT; `discover_abroad.py` descubre y revisa eventos extranjeros; `combine.py` reúne capturas; `rank.py` calcula; `publish_ranking.py` exporta; `deploy.py` valida y publica por FTP.
- `public.json` contiene ranking combinado en raíz y `localRanking` calculado independientemente con solo GT. Mismo corte/método. Flechas: `previousRank` solo si existe `previousCutAt` de misma vista, temporada y método.
- `activity.events`: ID de evento, victorias, derrotas por jugador. `activity.months`: meses locales GT del evento. Cada `result` tiene `eventId`, `playerIds` en orden ganador/perdedor y marcador. Catálogo `events` aporta metadatos y enlaces.
- No filtrar/renumerar puestos combinados para simular la vista GT. No usar `analisis-top20.json` como historial de todos: es un estudio histórico del 2 de octubre.
- `data/public.json` puede ser más viejo en Git que en producción: comprobar antes de reemplazar. La publicación semanal no hace commit del corte.

## Operación
- Secretos solo en GitHub Secrets: STARTGG_TOKEN, FTP_SERVER/USERNAME/PASSWORD, SMASH_FEEDBACK_ADMIN_HASH. No imprimir ni copiar tokens al repo/documentación. El token compartido en chat necesita rotación por el dueño; no reutilizar desde mensajes.
- Actualización: `.github/workflows/smash-publish.yml`. Variables `SMASH_SYNC_ENABLED=true`, `SMASH_RELEASE_MODE=weekly`: domingo 00:00 Guatemala; puede demorar. Conservar último corte ante fallo/importación parcial.
- `.github/workflows/smash-deploy-snapshot.yml`: `assets_only=true` preserva public.json; false sube snapshot versionado. JSON se renombra al final. No borrar feedback-data ni otros proyectos.
- Flujo usado: rama → PR → CI → merge → workflow → verificar datos y navegador. Adjuntar PR al hilo si la herramienta está disponible.
- Pruebas: `python3 -m unittest discover -s scripts/smash -q`, `node --test scripts/smash/test_app.cjs`, `node --check ranking-smash-ultimate/app.js`, `git diff --check`.
- Vista local: `python3 -m http.server 4323 --bind 127.0.0.1 --directory ranking-smash-ultimate`.

## Referencias
- Acuerdos: `scripts/smash/ACUERDOS-2026-10-01.md`.
- Operación y metodología: README.md, METODOLOGIA.md, PLAN-RANKING.md en scripts/smash.
- Rediseño y mains: estado vivo en `EN-CURSO.md`. Último avance previo: PR #22, commit 6b5192c. Calendarios y torneos por jugador publicados, 50 pruebas correctas. Corte Oct4: 188 clasificados, 42 eventos combinados / 39 locales. Actividad generada sin cambiar puntos/puestos.
