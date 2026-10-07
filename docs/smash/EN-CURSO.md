# Base instalada — siguiente fase (7 de octubre de 2026)

## Estado vigente

- El dueño confirmó: ejecutó `install.sql` en phpMyAdmin y todo terminó correctamente. Base de la captura: `ivcjgjlk_smash`. Confirmación del dueño, no conexión/verificación directa del agente.
- PR #1 del repo nuevo fusionada en `main`, commit `cb89570`. Preparó v1 `001_accounts_competition`: 31 tablas/87 selecciones esperadas. CI correcto: 46 Python + 12 Node y 8 pruebas por motor (MySQL 8.0/MariaDB 10.11), run `37574948355`.
- No reinstalar tablas. Archivo observado sin abrir contenido: /home/ivcjgjlk/private-smash/config.local.php. Conector y diagnóstico publicados: PR #4 `a29355e`, PR #5 `e8e7d55`, PR #6 `8d509c2`; último despliegue `37578387425`, correcto. Conexión real pendiente de leer el diagnóstico del hosting; no pedir contraseñas por chat.
- La web aún lee JSON y la encuesta aún usa `feedback-data/respuestas-2026.php`; no se importaron cortes ni respuestas a MySQL.
- Dominios/repos: sitio activo https://rankingsmashbros.com/, repo Bucaro-19/rankingsmashbros. Graduación es legado.

## Instrucción nueva del dueño

Toda pantalla nueva debe solicitarse primero a **Claude Design** y seguir su handoff. Documentar funciones/estados en un brief y entregarlo al dueño; no inventar la pantalla en código. Backend/importadores pueden avanzar sin pantallas. Regla guardada en AGENTS.md y CLAUDE.md.

## Conexión PHP — publicada, comprobación de producción pendiente

- database.php carga únicamente el archivo privado hermano del sitio, valida formato y conecta mediante PDO con utf8mb4, UTC y prepared statements nativos. No imprime secretos/excepciones.
- opiniones.php?diagnostico=base ofrece cuerpo JSON de conteos/versiones solo a sesión administrativa válida. Navegaciones que aceptan text/html reciben text/plain; clientes API application/json. Anónimo 401; POST 405. El panel existente incluye el enlace «Comprobar conexión a la base de datos» únicamente tras autenticarse. No pantalla nueva ni cambios a respuestas.
- El dueño renovó la sesión en Chrome; el panel mostró 12 respuestas antes y después de publicar. La herramienta de Chrome devolvió ERR_BLOCKED_BY_CLIENT al abrir el diagnóstico, tanto por navegación directa como por clic en su enlace. Cambiar el formato no resolvió ese bloqueo. Se pidió al dueño abrirlo manualmente y compartir únicamente su resumen saneado. No atribuir el bloqueo a una causa no comprobada ni asumir error/success de MySQL. Nunca extraer cookies ni contraseñas.
- Pruebas locales: configuración privada, supresión de salida y sesiones; 6 contratos HTTP; 46 Python + 12 Node. Última CI `37578278589`/`37578275593`: todos los checks correctos, incluida conexión PDO real sobre MySQL 8.0/MariaDB 10.11. Esas bases son desechables, no el hosting.
- Último despliegue assets_only=true: `37578387425`, correcto. Verificación HTTP real: diagnóstico anónimo 401/login_required en ambos formatos y cache no-store/private; acceso directo a database.php 403; inicio, encuesta y opiniones 200. public.json idéntico tras los tres despliegues (SHA-256 `1e681141bf4d043319593effc3153f44a7ec38531deef8a427f76c2573a24df1`). No se importaron ni modificaron datos SQL/encuesta.
- Próxima acción inmediata: recibir el diagnóstico manual del dueño (o leerlo mediante una conexión de navegador funcional) y registrar engine/version/schemaReady/tableCount/counts. No declarar conexión exitosa hasta obtener esa respuesta del hosting. Si devuelve un error, corregir solo la causa comprobada sin pedir secretos.

## Próximo trabajo

Leer `SIGUIENTE-FASE.md`: cerrar comprobación real de la conexión publicada; paquete/importación transaccional e idempotente del corte real (faltan tournamentId/entrantIds en el JSON público), manteniendo JSON público; migración de encuesta con respaldo y conteos; después OAuth y perfil según handoff de Design. Mantener método y calendario semanal. OAuth no garantiza cuota independiente por usuario; consultar datos compartidos desde base/caché.

Este relevo documenta instalación y conector publicados; falta comprobar la conexión de producción autenticada y después implementar importadores. Consultar Git/Actions antes de retomar.

---
## Archivo histórico del rediseño (trabajo completado)

Las listas de pendientes anteriores se conservan como historial; el estado vigente está arriba.


# Rediseño y mains automáticos — 6 de octubre de 2026

## Pedido actual
Recrear el handoff de Claude Design con alta fidelidad: Big Shoulders Display + Archivo, fondo #0B0F1A, celeste #49A6E9, cortes diagonales, ticker, hero #1, podio 2-1-3, barras, búsqueda y chips de mains, panel lateral para TODOS, adelanto visual de elegir main (sin cuentas reales). Conservar cálculos/validaciones y ambas vistas. Añadir extracción real de personajes por game, schema nuevo y DLC completos. Crear estos documentos para continuidad.

## Estado
- Rediseño publicado desde `main` (ver "Publicado" abajo).
- Diseño recreado y publicado. Carpeta del handoff y `.DS_Store` son archivos del usuario; no borrarlos ni agregarlos indiscriminadamente.
- Confirmado en docs oficiales: sets → games → selections → character. Falta prueba autenticada del vínculo `selection.entrant.id` usando token ya guardado en Actions.
- No hay STARTGG_TOKEN en entorno local. No solicitar que lo peguen al chat. Consultas mediante Actions.
- Plan: enriquecimiento de personajes independiente, en lotes pequeños y con caché; no recalcular el ranking para añadir datos. Primero habilitar pipeline/prueba de API, después rediseño y publicación validada.
- Solo contar selecciones registradas de games en sets competitivos admitidos. No deducir personajes de aliases. Orden por games, empate determinista; mostrar principal y hasta 2 secundarios. Informar cobertura y uso repartido.
- marcrd incluye Piranha Plant; DLC restantes necesitan fuente oficial/archivos locales. API de árbol: `/tmp/smash-asset-paths.txt`. Sora oficial: https://www.smashbros.com/assets_v2/img/fighter/sora/main.png; falta resolver stock icons DLC.

## Capturas reproducibles disponibles en esta máquina
- `/tmp/smash-scope-oct4/`: combined.json, pilot-ranking.json, previous-public.json (Oct2), nacional/extranjero.
- Tabla TTS fijada: `scripts/smash/data/ultrank_players.csv` (ignorada).
- `/tmp/smash-activity-before.json`: JSON previo a añadir activity. NO usar para desplegar.
- Artefactos de run semanal `37198767448` (Oct4), capturas privadas. Expiran: comprobar disponibilidad.
- Corte vivo debe verificarse siempre: https://ingporras.com/ranking-smash-ultimate/data/public.json

## Pendientes de esta entrega
1. Extracción/caché/tests de personajes; consultar games reales vía Actions, medir faltantes; extender schema sin debilitar validaciones.
2. Assets y catálogo de slugs, incluidos DLC, fallback `?`, atribuciones.
3. HTML/CSS nuevo aislado de encuesta/metodología (comparten estilos antiguos); adaptar render sin sustituir reglas.
4. Panel todos, rivales frecuentes con IDs, actividad/historial existentes, flechas y chips; elegir main solo demo.
5. Pruebas, comparación de campos de ranking antes/después, QA móvil/escritorio, CI, despliegue y verificación.
6. Actualizar este archivo con resultados, commits, ejecuciones y pasos exactos pendientes.

## Avance técnico
- PR #23 fusionado: `d850aa4`. Pipeline de personajes, caché y compatibilidad schema 2/3; cálculo y exportación previa intactos. `smash-characters.yml` solo produce artefactos, NO despliega.
- Consulta autenticada terminada: run `37540350390` (captura origen `37198767448`), 2648 sets consultados, 175 de 188 clasificados con personaje registrado. Artefacto `smash-mains` (caduca a los 14 días).
- Backend añade mains al JSON ya exportado mediante characters.py. El workflow semanal invoca este paso después de exportar ambas vistas. Mains se calculan por scope; selecciones duplicadas se deduplican por game/entrant/character, ambiguas se omiten y cuentan como tales, games sin ganador se omiten.

## Relevo Codex → Claude (6 de octubre, tarde)
Codex dejó el rediseño sin commit en la carpeta principal (rama local `feat/smash-design-ui`, sin commits propios). Claude copió ese estado a la rama `claude/smash-folder-review-f38d72` y continuó ahí. **Continuar desde esa rama (o desde `main` si su PR ya se fusionó), no desde los cambios sin commit de la carpeta principal: quedaron obsoletos.** No se borraron; el dueño decide cuándo descartarlos. La carpeta `design_handoff_smash_gt_ranking/` sigue sin versionar en la carpeta principal.

Hecho en esta rama:
- UI nueva completa en `index.html`, `app.js`, `arena.css` (bloque `.smash-redesign` al final; los estilos viejos de arriba siguen porque metodología/encuesta los comparten) y `characters.js` (86 personajes, IDs de start.gg).
- `data/public.json` del repo: mismo corte del 4 de octubre, schema 3 con `mains`, `mainCoverage` y `results[].playerTags`. Comparado contra producción: todos los demás campos de ambas vistas son idénticos (puestos, puntos, sets, eventos, actividad).
- Correcciones de Claude: alias `Simon Belmont` y `Duck Hunt` (start.gg los nombra distinto al catálogo y salían con `?`); retratos locales reducidos (ver ASSETS.md); en móvil el panel ya no hereda el padding viejo de `#player-dialog`, el marcador G–P no se parte y los chips de mains van en una fila con scroll horizontal.
- QA en navegador (1024 px y 375 px): hero, ticker, podio 2-1-3, filas, chips, búsqueda, cambio de alcance, panel con mains/torneos/rivales/calendario/sets, carta de demo y metodología con schema 3. Sin errores de consola ni scroll horizontal.
- Pruebas: 46 de Python, 12 de Node, `node --check` de `characters.js` y `app.js`, `git diff --check`.

## Publicado (6 de octubre, noche)
- PR #24 fusionado en `main` (`4e37fac`). `smash-deploy-snapshot.yml` con `assets_only=false`: run `37543142250`, correcto.
- Verificado en https://ingporras.com/ranking-smash-ultimate/: schema 3, corte 2026-10-04T11:43:18, 188 clasificados en ambas vistas, 175 con personaje, 25 archivos en `assets/characters/`, UI nueva cargando sin errores de consola ni imágenes rotas, panel de jugador con mains.
- La rama `claude/smash-folder-review-f38d72` ya no hace falta. Trabajar desde `main`. Los cambios sin commit de la carpeta principal (rama local `feat/smash-design-ui`) son una copia vieja de lo ya publicado: descartarlos antes de seguir, con permiso del dueño.

## Pendiente
0. Migración a repo y dominio propios: ver `MIGRACION.md` (sitio ya publicado en rankingsmashbros.com; falta confirmar el semanal del domingo y redirigir la URL vieja). Base de datos propuesta: `BASE-DE-DATOS.md`. Siguientes fases de producto: orden en `scripts/smash/ACUERDOS-2026-10-01.md` (toca el top 15 por organizador; después perfiles, agenda e inicio de sesión).
1. Domingo: comprobar que el semanal (`smash-publish.yml`) publica schema 3 con mains por sí solo y que las flechas de movimiento aparecen.
2. Decisiones abiertas para el dueño: (a) start.gg registra "Random Character" (id 1746); hoy se muestra tal cual con `?` y es el más usado de Zigma y keks; (b) no se probó a 1366 px o más, revisar hero y podio en pantalla grande; (c) el botón del header dice "Próximamente: tu cuenta" en vez de "Crear cuenta" del handoff, a propósito porque no hay cuentas.
3. Fuera de esta entrega: cuentas reales/OAuth, donaciones, agenda, top 15 por organizador, rotación del token de start.gg.
