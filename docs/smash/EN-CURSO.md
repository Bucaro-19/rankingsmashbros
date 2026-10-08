# Cuentas, ranking e historial — 7 de octubre de 2026, Guatemala

## Codex — SEO técnico preparado, 8/oct (PR pendiente; sin publicar)

Rama `feat/technical-seo`, desde `origin/main` `a6cec03` (#56). Auditoría previa: árbol limpio, mismo origin `Bucaro-19/rankingsmashbros`, CI main `37828965177` correcta. Los cambios posteriores de Claude #57 (`01babf6`, caché y tolerancia de la portada) se conservaron al actualizar la rama sobre `01babf6` (CI main `37830748351` correcta). Detalle/relevo: [SEO-TECNICO.md](SEO-TECNICO.md).

- Robots + sitemap para cuatro páginas públicas; canonical/social propios y JSON-LD WebSite/Organization en portada. Cuenta: solo noindex; análisis ya lo tenía. Imagen OG preparada **comentada** (falta imagen aprobada de Claude Design); encuesta fuera del sitemap hasta decisión del dueño en PR, sin tocarla. Sin cambios en diseño, cálculo, JSON, premium, visitas ni módulos de organizadores.
- Sitemap generado por deploy.py; fechas reales de corte/estudios, no reloj del deploy. En assets-only lee solo el JSON público vigente por FTP; si no puede comprobar fechas falla antes de subir. Metadata se renombra al final, después del corte; fallos se reportan, no quedan silenciosos. FILES/test_publish y prueba SEO incluidos. Mismo grupo de concurrencia preservado.
- www y HTTP respondían 200 sin redirigir en comprobación HEAD de producción (8/oct). Se prepara redirección 308 al HTTPS sin www, sin bucles en prueba TLS local, preservando ruta/query/método y excluyendo validación de certificados. No se cambió el servidor real.
- 59 pruebas de pipeline/SEO y 12 JS correctas; XML, JSON-LD y contratos validados. Chrome: 6 páginas × escritorio 1440 y móvil 375, texto/estructura visual iguales a main, sin overflow; 24 capturas y comparación en `/tmp/smash-seo-review/`. Apache local: redirecciones HTTP/TLS, POST, hosts locales, ACME y MIME correctos. CI final pendiente del push.
- Propuesta sin JS: ampliar el noscript existente con resumen top 10 generado del corte y escapado; **no implementada**, porque el encargo pide propuesta y la presentación sin JS requiere aprobación/handoff si cambia. Search Console: pasos exactos DNS TXT o HTML + envío de sitemap en la guía y la PR, **no registrado por el agente**.
- Pendiente: aprobar imagen y decidir promoción de encuesta, revisar PR y dar orden de fusión/despliegue. Nunca se escribió SQL ni se desplegó esta entrega.


## Carga inicial de games aplicada y portada más tolerante a la red (8/oct)

- **Carga inicial de games (#43) aplicada en producción por orden expresa del dueño**, desde su Mac, en una sola transacción: `context_imported`, corte 1, 21.8 s. Verificado con SELECT: **4,787 games y 9,530 selecciones**; sigue 1 corte, 376 posiciones y el mismo hash original `ecb1d4a5…`. Se llamó a `import_context(apply=True)` con 20 s de conexión porque el límite de 10 s de la orden `load` falla con la red lenta del dueño. Falta que el dueño confirme en `analisis.html` que ya aparecen los cruces por personaje.
- **Aviso «No pudimos actualizar» en la portada:** la portada volvía a descargar `public.json` completo (3 MB; 180 KB comprimido) cada 60 s con `no-store`, y un solo fallo mostraba el aviso. Ahora `public.json` se sirve con `no-cache` (se revalida siempre; si el corte no cambió, responde 304) y las comprobaciones de fondo callan mientras haya un corte completo en pantalla: el aviso sale si el visitante pulsó «Actualizar», si no hay ningún corte cargado o tras tres fallos seguidos.

## Simulación de la carga inicial de games y encargo de SEO (8/oct)

- **Webhook real de Recurrente confirmado:** un aviso `intent.succeeded` firmado por Recurrente llegó a las 18:38 UTC y quedó registrado como `ignored` (correcto para ese tipo). El ejemplo `subscription.create` falla a propósito: trae una suscripción inventada que Recurrente no reconoce. Sin pago real todavía.
- **Simulación de la carga inicial de games (#43), solo lectura, por orden del dueño:** `validated_no_writes`. Corte 1; 3,837 sets de contexto; existentes 0 games / 0 selecciones; esperados **4,787 games / 9,530 selecciones**, iguales a los conteos locales de Codex. Hash original `ecb1d4a5…`, hash de contexto `853b8788…`. 11.5 s. La orden `load` de la herramienta falló tres veces con `context_rejected` por su tiempo de conexión de 10 s con la red del dueño lenta (latencia media ~550 ms); la misma función llamada con 20 s de conexión pasó. **No se escribió nada**; `--apply` necesita la orden expresa del dueño.
- **[Encargo para Codex](ENCARGO-CODEX-SEO.md):** bases técnicas de SEO (robots, sitemap, canonical, Open Graph, datos estructurados, `noindex` en lo privado). Hoy `robots.txt` y `sitemap.xml` responden 404.

## Migración 005 aplicada en producción y premium en modo real (8/oct)

- **Migración `005_organizer_tops` aplicada** por orden expresa del dueño, desde su Mac. La primera ejecución perdió la conexión a mitad (error 2013) y dos reintentos se quedaron colgados por la red; la migración es repetible y terminó completa. Verificado con SELECT: 42 tablas, marcador `005_organizer_tops` presente, las cinco tablas nuevas con sus 15 restricciones, y sin cambios en lo existente (1 corte, 376 posiciones, 2 cuentas). `tournament_catalog` está vacía: la llena el siguiente corte nuevo (domingo 11/oct); el corte del 4/oct ya importado no la rellena.
- En producción `/top/{slug}` ya responde «No encontramos este top» (404) en vez del 503 anterior. La pestaña «Mis torneos» sigue oculta hasta que el catálogo tenga filas.
- **Premium en modo real:** el dueño registró el webhook de producción en Recurrente y guardó su secreto en el archivo privado del servidor. Su pestaña Premium ya no muestra «Modo de prueba» y ofrece los planes. El webhook rechaza una firma falsa con 401. **Falta confirmar** que un aviso firmado por Recurrente llega y queda registrado (`premium_events` no tiene ninguno nuevo desde la prueba del 7/oct); no se ha hecho ningún pago real.
- Pendiente: marcar «Top por organizador» como disponible en la pestaña Premium cuando el catálogo esté cargado; simulación de la carga inicial de games (#43) cuando el dueño la pida.

## Codex — catálogo semanal en SQL, 7/oct (PR #52; sin producción)

[PR #52](https://github.com/Bucaro-19/rankingsmashbros/pull/52), rama `feat/tournament-catalog-sql` desde `origin/main` **8282223** (#50), actualizada sobre **28de811** (#51) conservando los módulos y las notas de Claude. Auditoría previa: árbol limpio, origin `Bucaro-19/rankingsmashbros`, CI de main correcta ([37718094855](https://github.com/Bucaro-19/rankingsmashbros/actions/runs/37718094855)). `main` está ocupado en un worktree de Claude; se creó la rama directamente desde el remoto actualizado, sin modificar ese checkout.

- Paquete privado **V3** únicamente cuando `tournamentCatalog` es una lista, incluido `[]`. Captura ausente/null genera el V2 anterior exactamente; comprobado contra el código base y hashes de fixture V1/V2 fijados. `public.json`, mains, cálculo, elegibilidad y `discover.py` intactos. No consultas nuevas a start.gg.
- Exportación normalizada de las 11 columnas de 005: fechas UTC (inicio del torneo, no del evento), ID de creador nullable, nombres/ciudad y longitudes, slug ajeno a `tournament/` → NULL, motivos admitidos, IDs y eventos únicos. Los excluidos quedan solo en el catálogo; no se incorporan sets al ranking.
- Python/PHP reemplazan toda `tournament_catalog` con **DELETE + INSERT + comparación de las 11 columnas**, dentro de la transacción del corte. El marcador 005 ausente omite el catálogo (`migration_missing`) y el corte se publica normalmente; una instalación marcada pero rota se rechaza. Null/ausente y paquetes V1/V2 no leen ni modifican el catálogo.
- Repetición = `already_imported`: conserva el hash y no reescribe el catálogo, aunque después se instale 005 o ya exista un corte posterior. **Instalar 005 después de un corte sin catálogo no hace backfill**: el siguiente corte nuevo con catálogo lo llena. Carga extraordinaria aparte necesita nueva orden del dueño.
- 11 pruebas nuevas: contratos/hash, validación rehasheada, paridad tabla por tabla, reemplazo/vaciado, rollback del catálogo y del corte, reenvío antiguo, ausencia de 005, instalación posterior y HTTP real → cola → worker con/sin 005. Correctas en MariaDB local desechable y en **MySQL 8.0/MariaDB 10.11 en CI**, matriz completa y contratos correctos sobre el commit de implementación `dca4efc`: [run 37719296538](https://github.com/Bucaro-19/rankingsmashbros/actions/runs/37719296538). Regresiones locales correctas: 51 de pipeline, 14 de importación, 9 de contexto, 13 de carga semanal y 18 de transporte/worker. Revisar también los checks actuales de la PR tras actualizar la documentación/base.
- Medición **sintética local** (no producción): 5,000 games + 10,000 selecciones + 1,000 filas de catálogo; JSON **1,621,930 bytes**, gzip **72,055 bytes**, pico worker PHP **31,457,280 bytes** (30 MiB), **0.570 s**. Mismo tamaño y pico en CI: worker **3.736 s MariaDB / 4.456 s MySQL**. Límites 32 MiB/4 MiB/512M conservados y probados.
- **Sí se puede fusionar y desplegar antes del 11/oct sin aplicar 005**, con CI verde y orden del dueño: la ruta sin migración termina con `sync_jobs=succeeded`. Primero instalar los assets compatibles V3 (`assets_only=true`); no lanzar un corte manual. Detalle, estados y comando de migración para el dueño en [IMPORTACION-RANKING.md](IMPORTACION-RANKING.md) y [CARGA-SEMANAL-SQL.md](CARGA-SEMANAL-SQL.md).
- No se accedió a producción, no se aplicó 005 allí, no hubo fusión/despliegue, ni cambios en organizador/top/cuentas o pantallas.

## Claude Code — top por organizador programado; falta el dato en producción (7/oct, noche)

Detalle y contrato en [TOP-ORGANIZADOR.md](TOP-ORGANIZADOR.md).

- **Fusionados por orden del dueño:** #43 (carga inicial de games) y #46 (Tu opinión) de Codex. En #46 se resolvió el cruce de este archivo conservando ambos bloques. **Ninguno se ha desplegado**; la escritura de producción de #43 sigue sin orden.
- **#48:** la captura semanal guarda quién creó cada torneo (`tournamentCatalog`). Consulta aparte y opcional: si falla, el corte sigue igual. Comprobada contra start.gg (run `37716893894`): 63 torneos, 63 con creador, 62 con ciudad, 17 creadores, 2 consultas.
- **#49:** migración `005_organizer_tops` (5 tablas, repetible) y [encargo para Codex](ENCARGO-CODEX-CATALOGO-ORGANIZADORES.md) de llevar el catálogo a SQL. **No aplicada en producción**: el dueño no tiene acceso a cPanel ni a su red.
- **Esta entrega:** biblioteca, API, pestaña «Mis torneos», página pública `/top/{slug}`, coorganizadores por invitación, tamaño 5/10/15 y revisiones. La pestaña solo aparece cuando `tournament_catalog` tiene filas, así que publicar esto no cambia nada visible todavía.
- Decisiones nuevas del dueño: coorganizadores (varios), top 5/10/15, guardar el creador. Decisiones mías, revisables, en la tabla de TOP-ORGANIZADOR.md; la principal: por ahora cuentan solo los torneos que también entran al ranking nacional.
- **Corrección del dueño (7/oct, noche):** cada cuenta paga su propio premium; el del organizador ya no cubre al equipo. Unirse como coorganizador es gratis y su nombre aparece («Coorganizan: …») en la pestaña y en la página pública. Orden de desplegar main, que incluye Tu opinión (#46).
- **Desplegado** main `28de811` con `assets_only=true`: el primer intento (`37719525937`) se cortó por tiempo de espera del FTP y dejó archivos mezclados unos minutos; el segundo (`37719680287`) terminó bien. Comprobado en producción: inicio, cuenta, método, análisis y Tu opinión rediseñada (marcador SQL presente) responden 200; `cuenta.js`, `cuenta.html`, `organizador.js` y `encuesta.css` idénticos a main; `organizador.php` 403; la pestaña «Mis torneos» sigue oculta y `/top/{slug}` responde «No pudimos cargar este top» (503) porque faltan las tablas de la migración 005; `public.json` sin cambios (`1e681141…`).
- **Error de Claude Code, pendiente de decisión del dueño:** al fusionar el PR de documentación (#53) se ejecutó la fusión sobre el **#52 de Codex** (catálogo de organizadores en SQL, paquete V3), que quedó en main como `ccc42ce` **sin la orden del dueño**. Tenía la CI en verde. **No se desplegó**: producción sigue con el importador anterior. Según la propia PR, es seguro tenerlo antes del domingo porque la publicación semanal sube los archivos del sitio antes de enviar el paquete; no lo he verificado por mi cuenta. El dueño decide si se conserva (y se despliega) o se revierte. **Resuelto (8/oct):** el dueño delegó la decisión; se conserva. Comprobado antes: `smash-publish.yml` ejecuta `deploy.py` antes de `publish_sql.py send`, y el importador con 005 ausente devuelve `migration_missing` sin fallar. Desplegado main `db11ff6` con `assets_only=true` (run `37727209748`, correcto); después, `publish_sql.py diagnostic` autenticado respondió `ok: true`, PHP 8.1, bandeja escribible; `ranking-import.php` y `ranking-sync-lib.php` 403; `public.json` sin cambios. No se envió ningún paquete ni se escribió en la base.
- Coorganizadores, selector de tamaño, invitación recibida y revisiones del dueño usan componentes existentes sin diseño propio: [adenda para Claude Design](BRIEF-CLAUDE-DESIGN-TOP15-ADENDA.md).
- Incidente sin efecto: al probar la migración en la base desechable, el cliente `mariadb` leyó la configuración por defecto del Mac e intentó conectarse al servidor real con el usuario de pruebas; el servidor lo rechazó. No hubo lectura ni escritura. Desde entonces el cliente local se usa con `--no-defaults`.
- Próximo paso: PR de Codex con el catálogo; después, migración 005 con orden del dueño, verificación en producción con el top del propio dueño y activar la mención en la pestaña Premium.

## Codex — Tu opinión, rediseño independiente (7/oct)

[PR #46](https://github.com/Bucaro-19/rankingsmashbros/pull/46). Rama `feat/opinion-redesign` desde main `66f3004` actualizado (pantalla de Claude #42 ya incorporada); rebase sobre `31f7b96` para conservar también las notas de organizadores #44/#45, sin editar sus módulos. Antes de editar: árbol limpio, mismo origin `Bucaro-19/rankingsmashbros`, CI/despliegue de main correctos (`37713334860`, `37713467256`). Sin tocar los archivos de análisis, cuentas, panel, premium, metodología ni las bases compartidas de estilo/cabecera.

- Handoff local `design_handoff_smash_gt_metodo_opinion/`, Página 2 / Encuesta.dc.html. Encabezado/pie copiados de Método; usa `arena.css`, `paginas.css`, `cabecera.js`. Paneles con más aire, ayudas Q3 en cuatro details cerrados, escalas Q5/Q6 con radios 1–5, progreso sticky, privacidad antes de CTA y estados del servidor. JS nuevo opcional: progreso/contador/enviando; sin requests, almacenamiento ni visitas. Incluido en allowlist de publicación; no se publicó.
- Preguntas, opciones, ayudas y name/value preservados desde el formulario anterior. **Bloque de validación/nonce/límites/SQL/session rate limit idéntico byte a byte**, SHA-256 `dd3196bae5090d89c3a465312320de9ec1f56f5e30f09065aa99f10913940f82`. Solo se añaden datos/helpers de presentación: selección válida escapada y textos repintados después de errores. Marcador SQL y require survey conservados; `opiniones.php` y `survey.php` intactos. No se leyeron comentarios de producción.
- Pruebas locales: 14 de encuesta (12 HTTP + 2 estáticas), 48 de pipeline/publicación, PHP/JS y diff correctos. Las aserciones existentes de seguridad, almacenamiento, privacidad y reintento se conservan. El contador global se reemplazó por un probe del constructor PDO **solo en la copia temporal del test**: exige los mismos cero/una conexión de la app, ignora conexiones de salud externas; no se cambia database.php productivo.
- Revisión en Chrome local, fuente y sesiones inventadas, base desechable: escritorio 1440 y móvil 375, inicio/parcial, ayudas abiertas/cerradas, escalas, validación, enlace inválido, enviando, guardado, fallo/reintento, ya respondiste, y JS desactivado (inicio/fallo/guardado). Sin overflow horizontal ni errores JS. 18 vistas comprobadas, 28 capturas temporales `/tmp/smash-initial-context/review/`; documentación reproducible en [OPINION-REDISENO.md](OPINION-REDISENO.md). CI completa correcta sobre `0633176`: [run 37715216663](https://github.com/Bucaro-19/rankingsmashbros/actions/runs/37715216663) y `37715213097`, MySQL 8.0, MariaDB 10.11 y contratos. Primer intento detectó otra comprobación de presentación en test_survey_storage.php que buscaba opciones literales en el template; ahora comprueba el HTML GET realmente renderizado, conservando intactos todos los contratos de almacenamiento y validación.

### Primera tarea: carga inicial — PR #43

[PR #43](https://github.com/Bucaro-19/rankingsmashbros/pull/43), rama separada `feat/initial-game-context`, sin fusionar/desplegar. CLI de contexto con simulación SQL READ ONLY por defecto y orden expresa para --apply. Hash original preservado; fuente recuperada sin start.gg; **4,787 games / 9,530 selecciones**, JSON 1,471,290 / gzip 92,604 bytes, pico CLI local 257,785,856 bytes. Nueve pruebas del contexto correctas en ambos motores; CI completa correcta sobre `fa9f38c` (`37715308425`, `37715303307`); también `37713902599` tras reintentar el fallo preexistente del contador global de encuesta. Simulación de producción **pendiente**: IP del router rechazada, el dueño no puede abrir cPanel ahora. No se escribió producción. Comandos y medidas en IMPORTACION-RANKING.md de esa PR (no incorporada aún a main). Tres paquetes guardados con permisos 600 en `~/.smash-gt-context-oct4-20261007/` (700), fuera de Git y de /tmp; copia verificada byte a byte. Si llega un corte posterior, no forzar el Oct4.

Ambas entregas requieren revisión y orden del dueño para fusionar/desplegar. La carga inicial también requiere primero acceso de lectura, simulación remota exitosa y una orden expresa de escritura.

## Codex — carga inicial de contexto, 7/oct (sin escritura de producción)

[PR #43](https://github.com/Bucaro-19/rankingsmashbros/pull/43), sin fusionar ni desplegar. Rama `feat/initial-game-context`, desde main `8f2e53a` (actualizada sobre `31f7b96` tras #42/#44/#45), árbol limpio al iniciar; remoto `Bucaro-19/rankingsmashbros`. CI y despliegue de #40 comprobados correctos (`37707601298`, `37707771272`); #41 es el encargo actual. Claude trabaja aparte en `feat/rival-analysis-screen`; no se tocaron sus archivos.

- CLI `game_context.py`: paquete solo games/selecciones + prueba original independiente; simulación SQL READ ONLY por defecto, `--apply` explícito, bloqueo común, anclaje/paridad y rechazo de contexto posterior. Solo inserta ambas tablas vacías; repetición exacta `already_imported`; rollback completo. Sin start.gg, migración ni cambio público/cálculo/mains.
- Recuperados artefactos ya existentes; hashes original V1/V2 exactamente reproducidos. Contexto esperado **4,787 games / 9,530 selecciones**, 3,837 sets; JSON 1,471,290 / gzip 92,604 bytes. En base local desechable: simular 1.479 s, aplicar 1.941 s, repetir 1.606 s; pico máximo CLI 257,785,856 bytes (<512 MiB). Nueve pruebas locales correctas; nueve pruebas del contexto correctas en MySQL 8.0/MariaDB 10.11. Tras actualizar la base, matriz completa y contratos correctos sobre `fa9f38c` en [run 37715308425](https://github.com/Bucaro-19/rankingsmashbros/actions/runs/37715308425) y `37715303307`. También matriz completa y job de contratos correctos en [run 37713902599](https://github.com/Bucaro-19/rankingsmashbros/actions/runs/37713902599) sobre `93391f8`. El primer intento MySQL falló solamente en la prueba preexistente del contador global de conexiones de encuesta (227 frente a 226); reintento correcto sin cambios. La solución estable de esa prueba pertenece a la PR independiente de Tu opinión.
- **Producción pendiente de simulación:** conexión rechazada por IP del router actual; el dueño contestó que no puede entrar a cPanel ahora. No se insistió ni se cambió el acceso. Nunca se escribieron datos de producción ni se leyeron comentarios. Conteos/tiempos anteriores son LOCALES, no una simulación remota exitosa.
- Paquetes originales/contexto conservados fuera de /tmp y Git en `~/.smash-gt-context-oct4-20261007/`, copia byte a byte verificada, carpeta 700/archivos 600. Comandos exactos y recuperación de fuentes en [IMPORTACION-RANKING.md](IMPORTACION-RANKING.md). Revisar simulación antes de pedir la orden de aplicación. No fusionar ni desplegar esta entrega sin la orden del dueño. Si llega el 11/oct antes, no forzar el contexto viejo.
- Segunda tarea independiente: rediseño de Tu opinión según handoff, entregado en [PR #46](https://github.com/Bucaro-19/rankingsmashbros/pull/46) desde main; incluye la solución del contador de conexiones de encuesta. No son PR apiladas.

## Top 15 por organizador — decisiones del dueño y brief (7/oct, madrugada)

- El dueño decidió: lo usa quien tiene el **rol de organizador** (y premium), y el top cuenta **solo a quienes participaron en los torneos de ese organizador**. Brief para Claude Design: [BRIEF-CLAUDE-DESIGN-TOP15-ORGANIZADOR.md](BRIEF-CLAUDE-DESIGN-TOP15-ORGANIZADOR.md), entregado al dueño.
- **Verificado el 7/oct con una consulta real** (workflow `smash-probe-owners.yml`, run `37714873563`, solo lectura y con salida agregada): start.gg expone `Tournament.owner` con el token del sitio. De los 40 torneos del corte consultados, los 40 devolvieron dueño; son **14 dueños distintos** y los cinco con más torneos tienen 8, 8, 5, 5 y 3. El filtro `tournaments(query:{filter:{ownerId}})` también funciona: para un dueño devolvió 15 torneos de Ultimate del año, incluidos los 8 que están en el corte (el resto no entró al corte por las reglas de admisión). El dueño es quien **creó** el torneo; los coorganizadores no aparecen (`admins` es solo para administradores), por eso se mantiene el estado «por confirmar» con revisión manual. Pendiente de diseño técnico: guardar el dueño en la captura semanal (`tournaments` no tiene esa columna: requiere migración) para no consultar a start.gg por visita.
- **Decidido por el dueño (7/oct):** los puntos de ese top se calculan **solo con los sets de los torneos de ese organizador**, con el mismo modelo del ranking. Es un cálculo nuevo y aparte: no toca el ranking publicado ni `public.json`. Sigue abierto el mínimo de actividad para aparecer; el brief ya pide diseñar el caso de muestra pequeña.
- Premium real sigue pendiente: el dueño aún no tiene acceso a cPanel.

## Pantalla del análisis de rival — publicada (Claude Code, 7/oct)

Implementa el handoff `design_handoff_smash_gt_analisis/` sobre la API de Codex (ANALISIS-RIVAL.md). Dirección: `analisis.html?rival=<playerId>&scope=gt|intl`; sin `rival` abre el buscador.

- Archivos: `analisis.html`, `analisis.css`, `analisis.js` y `analisis-model.js` (reglas de presentación puras, 5 pruebas en `test_analisis.cjs`). Reutiliza `paginas.css` y `cabecera.js`.
- Entradas: botón «Analizar rival →» en el panel de rival del perfil (conserva rival y vista) y enlaces desde la pestaña Premium, donde el análisis ya no dice «Próximamente».
- Estados: buscador con sugerencias de rivales ya enfrentados, carga, error con código, sin sesión, sin jugador vinculado, bloqueado y vencido (solo datos gratis y la tarjeta premium, sin cifras falsas), y completo: tarjeta VS, probabilidad estimada (entre 10% y 90%, con su aviso), recomendación con confianza y muestra, matchup (uso, récord contra sus personajes y de él contra los míos, cruce por game con selector), historial con racha y forma reciente con tramos.
- Reglas del diseño aplicadas en el navegador: récords siempre en conteo; porcentaje y barra solo con 10 o más; «Muestra pequeña» por debajo; «Sin sets/games registrados» con cero. El aviso de recomendación usa 150 games, como fijó la API.
- **Diferencias con el diseño:** no hay puesto final ni inscritos por torneo del rival (la API los envía `null`); el uso de personajes del rival se muestra con games y porcentaje calculado de `games/totalGames`; la tarjeta premium enlaza a la pestaña Premium en lugar de repetir el selector de planes; se añadió el tramo «101 o más» que entrega la API.
- Revisado en navegador a 375 px contra la API real en base local (cuenta dueña y cuenta gratis, ambas vistas, buscador) y contra una respuesta inventada completa para ejercitar recomendaciones, barras y cruce por game. La disposición de dos columnas de escritorio no se pudo ver: el panel del navegador no ensanchó la ventana.
- En producción los cruces por game dirán «Sin games registrados» hasta que se cargue el corte del 4/oct (encargo de Codex) o llegue el corte del domingo 11.

## Reparto vigente — 7/oct, madrugada

- **Codex:** carga inicial de games del 4/oct (herramienta y simulación; escritura solo con orden del dueño) y rediseño de «Tu opinión». Encargo: [ENCARGO-CODEX-OPINION-Y-CARGA-INICIAL.md](ENCARGO-CODEX-OPINION-Y-CARGA-INICIAL.md). Sus PR #36 (games por corte) y #40 (API del análisis) están fusionadas y publicadas por orden del dueño (`656b7af`, `47a9181`; despliegues `37706467920` y `37707771272`).
- **Claude Code:** pantalla del análisis de rival sobre la API de #40, en la rama `feat/rival-analysis-screen`.
- **Premium en real, a medias:** el dueño dice haber puesto la llave real en el archivo privado del servidor, pero no pudo terminar (no tiene acceso a cPanel por ahora). El `webhook_secret` de ese archivo sigue siendo el del sandbox y **no hay webhook de producción registrado**. Comprobado por HTTP solo que la configuración sigue siendo válida; no se sabe desde fuera si la llave activa es de prueba o real. Pendiente: registrar el webhook de producción y actualizar el secreto. Mientras tanto un pago se activaría al volver (consulta directa a Recurrente), pero los avisos de renovación o cancelación serían rechazados por firma.

## API de análisis de rival — Codex, 7/oct

Servidor entregado en `feat/rival-analysis-api`, [PR #40](https://github.com/Bucaro-19/rankingsmashbros/pull/40), **sin fusionar ni desplegar; espera revisión y orden del dueño**. Contrato final e integración para Claude Code: [ANALISIS-RIVAL.md](ANALISIS-RIVAL.md). No incluye pantallas ni toca los módulos asignados a Claude.

- `analisis-api.php` + biblioteca protegida `analisis.php`: «yo» de la sesión, gratis solo perfiles y récord; gate real antes de construir/enviar datos premium. Premium desde `smash_premium_status`, admin desde `smash_stats_is_owner`; sin consultas a proveedores. Transacción del análisis solo lectura.
- Historial, forma, tramos (incluye puesto real >100), personajes por set y por game, escena del corte y recomendaciones con confianza del diseño. Puesto final/inscritos por torneo siguen null. Funciona con games vacíos; no altera mains/cobertura publicados ni `public.json`.
- Precisiones para la pantalla: probabilidad con constante **400** por el modelo publicado; umbral **150 games** cuando no hay sets propios (la frase de 80 del diseño contradice su tabla); detectados con **conteos**, no `share`; `access.full` habilita también al dueño sin pago. Todos los detalles y errores están en el contrato.
- Local: contratos puros PHP y 13 pruebas Python (11 HTTP) correctos en MariaDB desechable. CI comprobada en MySQL 8.0/MariaDB 10.11: [run 37706831774](https://github.com/Bucaro-19/rankingsmashbros/actions/runs/37706831774), tres jobs correctos sobre `a030e9b`; la actualización final de documentación/legibilidad requiere sus propios checks verdes. En copia local del 4/oct con games de caché: ~47–52 ms, pico 44 MiB, usando índices existentes; no propone migración. No se midió BanaHosting.
- **PR #36 ya fue fusionada por el otro flujo** en main `656b7af` mientras se preparaba esta entrega. Su carga inicial sigue requiriendo orden expresa; esta API admite tablas vacías y también games cargados. No se repitió aquí la lectura de producción. Esta entrega no escribe producción, no fusiona ni despliega. La carga del domingo conserva el circuito actual.

## Pestaña Premium y primer pago real de prueba — publicado (Claude Code, 7/oct)

- **Circuito de pago comprobado en el sandbox con el dueño:** pagó un checkout mensual de 3 USD con la tarjeta de prueba de Recurrente. El webhook `subscription.create` llegó a producción, pasó la verificación de firma y dejó su cuenta `active` con `current_period_end` 2026-11-07 (lectura directa de la base: una fila en `premium_subscriptions`, dos avisos en `premium_events`, uno sincronizado y uno ignorado). Los campos de una suscripción pagada coincidieron con lo supuesto de la documentación.
- **Pestaña Premium** según el handoff `design_handoff_smash_gt_premium/`: planes (anual marcado por defecto), condiciones antes de pagar, regreso del pago con «Confirmando…» (consulta cada 3 s, máximo 30 s), éxito, «todavía no lo vemos», pago cancelado, administrar, confirmación de cancelación en línea, cancelada, pago vencido y terminado. Distintivo «Premium» junto al alias y aro amarillo en el avatar. Archivo nuevo `premium.js`; `premium-api.php` añade `startedAt`.
- **Diferencias con el diseño, a propósito:** (1) no hay estado «rechazado» al volver, porque Recurrente no devuelve al sitio un pago rechazado; (2) en pago vencido no hay botón «Actualizar forma de pago»: falta comprobar cómo expone Recurrente ese cambio de tarjeta; (3) «Análisis del rival» aparece como «Próximamente» hasta que exista la pantalla; (4) aviso «Modo de prueba» mientras el servidor use la llave de prueba; (5) el texto introductorio bajo el título es propio, el diseño no lo fijaba.
- Sigue en **modo prueba**: nadie puede pagar dinero real hasta cambiar a la llave `sk_live_` y registrar el webhook de producción.
- Revisado en navegador local con suscripciones inventadas: sin premium, activa, confirmación y Esc, cancelada, vencida y terminada.

## Rediseño de Método — publicado (Claude Code, 7/oct)

Primera mitad del handoff `design_handoff_smash_gt_metodo_opinion/` (carpeta local del dueño). «Tu opinión» (`encuesta.php`) va en la siguiente entrega y reutiliza `paginas.css` y `cabecera.js`.

- `metodologia.html` reescrita con el encabezado y pie del inicio, índice (barra plegable en móvil, columna lateral en escritorio, sección actual marcada), franja de cifras, pasos numerados, cuadro de cuatro casos como tabla real con forma de tarjetas, comparación con TrueSkill que se apila en móvil, y lista de torneos agrupada por mes con búsqueda, «Ver los N torneos» e insignias por vista.
- **El contenido no cambió:** una comprobación automática al generar la página confirmó que todos los párrafos del texto anterior siguen presentes; lo único sustituido es el pie viejo por el pie común del sitio. Se conservan los anclajes `#torneos`, `#puntos-en-claro` y `#trueskill`, y el selector de vista sigue siendo un enlace `?scope=guatemala`.
- Archivos nuevos: `paginas.css` (base común de las páginas de lectura) y `cabecera.js` (el aviso de sesión del encabezado, que antes vivía dentro de `app.js`; ahora lo comparten inicio y Método). `metodologia.css` y `metodologia.js` reescritos. Sin cambios en datos ni en el cálculo.
- Revisado en navegador contra copia local: escritorio y 375 px, ambas vistas, búsqueda, «ver todos», índice, sin desbordamiento horizontal ni errores propios en consola.

## Reparto vigente — 7/oct, cierre de la noche

- **Codex:** datos del análisis de rival, solo servidor. Encargo y prompt: [ENCARGO-CODEX-API-ANALISIS-RIVAL.md](ENCARGO-CODEX-API-ANALISIS-RIVAL.md). La PR #36 (personajes por game) fue fusionada por el otro flujo en `656b7af`; la carga inicial requiere su propia orden y verificación.
- **Claude Code:** rediseño de Método y Tu opinión (handoff `design_handoff_smash_gt_metodo_opinion/`, en curso en la rama `feat/metodo-opinion-redesign`), después la pantalla del análisis de rival (handoff `design_handoff_smash_gt_analisis/`) y la pestaña Premium cuando llegue su diseño.
- **Premium en modo prueba, encendido en producción:** el dueño subió `private-smash/recurrente.local.php` con la llave de prueba y el secreto del webhook del sandbox, registrado por Claude Code con su orden. Comprobado por HTTP: `premium-api.php` responde `available: true` y el webhook exige firma (401 sin ella). Falta el pago de prueba del dueño.

## Codex: games y selecciones SQL — PR #36 fusionada en main (7/oct)

**Actualización:** fusión externa a la entrega de esta API en `656b7af`. Lo siguiente registra las comprobaciones originales, anteriores a esa fusión; no constituye verificación de un despliegue ni de una carga inicial posterior.

Encargo [ENCARGO-CODEX-SELECCIONES-POR-GAME.md](ENCARGO-CODEX-SELECCIONES-POR-GAME.md). Rama **`feat/game-selections-sql`**, iniciada desde main `4e5bb2d` / PR #34 y actualizada sobre `e9d308d` (premium de Claude, PR #35). **PR de esta entrega: [#36](https://github.com/Bucaro-19/rankingsmashbros/pull/36).** Al empezar: árbol limpio, origin `Bucaro-19/rankingsmashbros`, main actualizado, CI `37701181158` y despliegue `37700879178` correctos; `SMASH_SQL_SYNC_ENABLED=true` verificado. Este encargo exige orden del dueño antes de fusionar/desplegar; no usar la autorización de Claude para sus propias entregas.

- Paquete privado V2: games/selecciones reales, cobertura explícita y comprobación de mains exactamente iguales a la captura/public. V1 sigue legible y repetible con el hash original. No hay migración, cambio público de esquema ni nueva consulta a start.gg. Se persiste el snapshot que el workflow ya enriquecía en memoria.
- Ambos importadores reemplazan games por set en la transacción del corte nuevo y verifican paridad. Captura vacía y DQ limpian el contexto; fuera de cobertura conserva; corrección de picks/ganador/game retirado reemplaza; cambio de slots de un set competitivo cubierto o game trasladado a otro set rechaza todo. Repetir un corte antiguo no revierte contexto más reciente; instantáneas inmutables.
- Solo se cambiaron exportador/importadores, una opción del workflow, tests/herramienta offline y documentos. Cuentas, premium, panel, encuesta, visitas, UI, cálculo y `public.json` intactos. Claude puede seguir su entrega paralela; para matchup usar ganador de game y dos picks válidos, nunca completar datos ausentes desde mains.
- Lectura directa de producción **READ ONLY**: cutId 1 publicado con hash original `ecb1d4a5cd44f87250537a85d0d166fa6f9824ff3408f0b55c98ac6102fd9e45`; games/selecciones=0; 87 IDs de catálogo coinciden. HTTP confirma public SHA-256 `1e681141bf4d043319593effc3153f44a7ec38531deef8a427f76c2573a24df1` y public idéntico al paquete original. **No se escribió producción.**
- Medición Oct4 real, solo base local desechable: 4,787 games, 9,530 selecciones; 10,429,237 bytes JSON / 1,159,150 gzip (+16.4%/+8.9%); worker 150,945,792 bytes (144 MiB), ~2.42 s bajo 512M. Paridad Python/PHP en las 14 tablas comparadas. Mac MariaDB 13.0.2 / PHP 8.5.3; falta medición V2 en BanaHosting PHP 8.1 tras autorización. Detalles/reproducción en IMPORTACION-RANKING.md.
- Pruebas locales: 48 del ranking, 14 del paquete/importador, 13 del cargador y 18 de transporte/PHP/SQL; incluye 5,000 games / 10,000 selecciones bajo límites. Sintaxis PHP y catálogo/seed correctos. CI comprobada en MySQL 8.0 y MariaDB 10.11: [run 37703150785](https://github.com/Bucaro-19/rankingsmashbros/actions/runs/37703150785), tres jobs correctos sobre la implementación `5efa913`. Tras rebase de documentación sobre la entrega de Claude, comprobar los checks de la PR #36 antes de autorizar fusión; no se modificó su código de premium.

**Pendiente:** comprobar publicación y, por orden del dueño, la carga inicial. **Backfill Oct4:** propuesta concreta solo de contexto en IMPORTACION-RANKING.md; no implementada ni ejecutada. No reenviar el V2 reconstruido como corte normal ni cambiar el hash de cutId 1. Necesita paso manual/herramienta con simulación, bloqueo, anclaje al hash original y comprobación de que no pisa contexto posterior. Si pasa el 11/oct, usar captura del último corte y comparar antes de añadir contexto viejo. Automatización continúa como hoy hasta publicación de la extensión; no tocar cron ni variables.

## Cobros de premium con Recurrente — servidor listo, sin pantallas (Claude Code, 7/oct)

Documento: [PREMIUM.md](PREMIUM.md). Biblioteca `premium.php`, `premium-api.php`, `recurrente-webhook.php` y migración `004_premium.sql`. El dueño guardó su llave de **prueba** de Recurrente en su Mac; se comprobó contra el sandbox (cuenta Ingporras, ambiente `sandbox`) sin imprimirla. Premium queda **apagado** en producción hasta que exista el archivo privado. El panel del dueño ya muestra cuántas cuentas son premium.

- **Aviso para Codex y cualquier agente:** el checkout principal de la Mac (`rankingsmashbros/`) lo está usando Codex en `feat/game-selections-sql`. Claude Code trabaja en un worktree aparte; no cambiar de rama ni tocar los cambios sin commit de ese checkout.
- El archivo de la llave no estaba ignorado por Git: se añadió a `.git/info/exclude` del checkout del dueño y a `.gitignore` en esta entrega (`recurrente.local.php`, `recurrente.local.txt`).

## Decisiones del dueño para premium y reparto de trabajo — 7/oct, noche

- **Precio:** 3 USD al mes o 24 USD al año. **Pasarela:** Recurrente. El puesto, el perfil y el historial con rivales siguen gratis; pagar no cambia puntos.
- **Encargo paralelo a Codex:** guardar en SQL los personajes de cada game para el matchup exacto. Documento y prompt: [ENCARGO-CODEX-SELECCIONES-POR-GAME.md](ENCARGO-CODEX-SELECCIONES-POR-GAME.md). Las tablas ya existen; falta llevar los datos al paquete y a los dos importadores. Codex no toca cuentas, contador, panel ni premium.
- **Claude Code:** integración de cobros con Recurrente y la condición premium de las cuentas. Requiere que el dueño tenga cuenta en Recurrente y deje sus llaves en un archivo privado del servidor (nunca por chat). Las pantallas de premium esperan el handoff del brief BRIEF-CLAUDE-DESIGN-ANALISIS-RIVAL.md.
- **Briefs entregados al dueño para Claude Design:** análisis de rival (premium) y rediseño de Método y Tu opinión (BRIEF-CLAUDE-DESIGN-METODO-Y-OPINION.md).
- **Regla nueva del dueño:** Claude Code puede fusionar y desplegar (`assets_only=true`) sus propios cambios sin pedir permiso cada vez. Siguen necesitando orden expresa: migraciones y escrituras en la base de producción, publicar un corte nuevo, y fusionar cambios de otro agente.
- PR #33 fusionada (`12273f7`) y desplegada (`37700879178`): el enlace al panel aparece solo para la cuenta `admin`; comprobado por HTTP que la API anónima no incluye la clave `panel`. `public.json` idéntico.

## Enlace al panel solo para el dueño y preparación de premium — publicado (Claude Code, 7/oct)

- Pedido del dueño después de ver el panel: un acceso visible solo para él. `account-api.php` añade `panel: true` únicamente a la cuenta con rol `admin` (las demás no reciben la clave); `cuenta.html` muestra «Panel privado ↗» junto a las pestañas y el inicio muestra «Panel» en el encabezado tras confirmar con el servidor. Pruebas HTTP: cuenta normal sin la clave, dueño con ella. Revisado en navegador local con ambas cuentas.
- **Brief para Claude Design del análisis de rival (premium):** [BRIEF-CLAUDE-DESIGN-ANALISIS-RIVAL.md](BRIEF-CLAUDE-DESIGN-ANALISIS-RIVAL.md). Define los únicos datos que existirán.
- **Hallazgo que condiciona premium:** en producción `games` y `game_selections` están vacías (0 filas); solo existen los personajes agregados por jugador (`player_characters`, 175 jugadores). El matchup personaje contra personaje por game **no se puede calcular hoy**. Lo que sí se puede: probabilidad estimada con los puntos del ranking, historial entre ambos, forma reciente y récord contra jugadores cuyo personaje más usado es X (aproximación, con muestra pequeña). Guardar las selecciones por game requiere ampliar la captura semanal; es una entrega propia.
- Decisiones del dueño pendientes para premium: proveedor de cobro disponible en Guatemala, precio y modalidad (mensual, por temporada o pago único).

## Publicación del 7/oct por la noche — perfil v2 y panel del dueño (Claude Code)

Por orden explícita del dueño: PR #30 (`aee2479`) y PR #31 (`87c4e0a`) fusionadas, CI de main correcta y despliegue `37699120256` (`assets_only=true`) correcto. `public.json` idéntico (SHA-256 `1e681141bf4d043319593effc3153f44a7ec38531deef8a427f76c2573a24df1`).

- **Rol `admin` concedido** a `users.id = 1` (Bucaro19) en una transacción, por su orden («dame el rol de admin»): 1 fila insertada; es el único admin.
- Comprobado en producción por HTTP, sin sesión: `panel.php` 401 con «Tu sesión venció» y sin cifras ni script del panel; `panel-api.php` 401 `login_required`; `stats.php`, `visits.php` y `accounts.php` 403; `cuenta.html` sirve `cuenta.js` v3 con el panel de rival; API de cuenta anónima correcta.
- **No comprobado directamente:** el panel y el perfil v2 con la sesión real del dueño (no se usan sus cookies). Pendiente de que él los abra.
- **Pedido nuevo del dueño:** ver en el panel cuántos usuarios crearon cuenta (ya está: «Cuentas registradas» y «Registros nuevos») y **cuántos son premium cuando exista**. Añadir esa cifra al panel en la entrega de premium, con su ajuste de diseño.

## Panel privado del dueño — publicado (Claude Code, 7/oct)

El dueño entregó el handoff `design_handoff_smash_gt_panel/` y se implementó completo: [PANEL-DUENO.md](PANEL-DUENO.md). **Estado: rama `feat/owner-panel`, apilada sobre `feat/cuentas-v2` (fusionar primero el PR del perfil v2). Falta fusionar, desplegar y conceder el rol `admin` a la cuenta del dueño (`users.id = 1`, Bucaro19) con su visto bueno; sin ese rol nadie puede abrir el panel.** No necesita migración.

- Acceso solo con rol `admin`; 401 sin sesión, 403 sin pistas para otras cuentas.
- Cifras calculadas en `stats.php` desde el contador y las cuentas; periodos de días completos, distintos reales, semanas y comparación solo cuando hay historia.
- Producción hoy está en el «primer día»: el contador empezó el 7/oct, así que al publicarlo el dueño verá Hoy y las cuentas; los periodos dirán «Sin datos todavía» hasta el 8/oct.
- Pruebas SQL, HTTP y de modelo en verde; revisión en navegador en escritorio y móvil.

## Perfil v2 con historial de sets y panel de rival — en PR, sin publicar (Claude Code, 7/oct)

Tercer punto de la hoja de ruta (la parte gratuita). Implementa el handoff de Claude Design `design_handoff_smash_gt_cuentas_v2/` (carpeta local del dueño, sin versionar; su README nombra el repo anterior, el correcto es este). **Estado: rama `feat/cuentas-v2`; falta fusionar y desplegar. No necesita migración.**

- Vinculación: tarjeta de cuenta con el estado del jugador, intereses como dos casillas (Jugador / Organizador) con la nota de verificación por torneo, y «¿No eres tú? Usar otra cuenta».
- Perfil: datos de start.gg (país declarado, perfil público), personajes elegidos y detectados con porcentaje por vista, texto de alcance, movimiento explícito («Subiste n puestos · antes #x»), barra hacia el #100, panel de requisitos con medidores y atajo a la otra vista, y estado «sin jugador vinculado».
- Historial: filtros con conteo, insignia «Cuenta en ranking / Solo actividad» con motivo, y sets desplegables por torneo con G/P, rival, puesto del rival y marcador.
- Panel de rival: puesto y puntos en la vista activa, récord contra ti y la lista de sets entre ambos, con enlace a start.gg. Se cierra con Esc, con × o al tocar fuera, y devuelve el foco.
- Datos: todo sale del corte publicado. `account-api.php` añade `profile.rivals` (alias, enlace, personaje más usado y puesto/puntos por vista de cada oponente). Un rival sin puesto en la vista dice «sin puesto»; no se inventan posiciones. El marcador se lee del texto publicado por start.gg; en 25 de 2,648 sets (victorias sin marcador) se muestra «—».
- **No incluido:** evolución entre cortes y lectura desde SQL (solo hay un corte en la base; se añadirá cuando existan varios), ciudad del torneo, puesto final y número de inscritos por evento (no están en el corte publicado), y la carga animada de tres pasos del ingreso (la autorización es una redirección completa a start.gg).
- Pruebas: 10 de `test_accounts.cjs` (movimiento, requisitos, marcador, enfrentamientos) y paridad de `rivals` en `test_accounts.php`. Revisión en navegador contra copia local con base desechable, en escritorio y a 375 px, con cuatro jugadores: con puesto, con actividad suficiente pero sin puesto, con actividad insuficiente y sin jugador; sin errores de consola ni desbordamiento horizontal. El panel de rival se comprobó por geometría y contenido (el panel del navegador estaba oculto y no refrescaba capturas).

## Contador de visitas — publicado el 7 de octubre (Claude Code)

Segundo punto de la hoja de ruta. **Estado: PR #29 fusionada (`9f939d1`), despliegue `37694700196` correcto y migración 003 aplicada por orden del dueño (35 tablas; cuts=1, users=1, survey_responses=16 sin cambios).** Documento: [VISITAS.md](VISITAS.md). Comprobado en producción: `visits.php` 403, `visita.php` GET 405 y origen ajeno 403, y una visita real desde navegador quedó contada (1 vista de inicio, 1 visitante, 1 red). `public.json` idéntico. El brief del panel se actualizó con los datos reales (sin encuesta, con redes distintas).

- Archivos nuevos: `visits.php` (biblioteca, denegada en `.htaccess`), `visita.php`, `visita.js` y la etiqueta en cinco páginas. La encuesta y el panel de opiniones no se cuentan.
- Migración `003_visit_networks.sql`: tabla `site_network_days`. Sin ella el contador no cuenta y no rompe nada.
- Identidad por cookie propia firmada; la IP solo como HMAC con clave privada autogenerada en `private-smash/visits.key`. Decisión y límites en VISITAS.md.
- Solo recoge datos. El panel espera el handoff de Claude Design; el handoff `design_handoff_smash_gt_cuentas_v2/` que dejó el dueño es el perfil renovado con panel de rival, **no** el panel de estadísticas.
- También: `cuenta.js` cambia de versión en `cuenta.html` (el despliegue anterior no la cambió y un navegador con la versión en caché no guardaba la pista del encabezado) y `.gitignore` excluye `design_handoff_*/`.
- Pruebas locales en MariaDB desechable y navegador; siete fallas provocadas detectadas por las pruebas.

## Sesión persistente — publicada el 7 de octubre (Claude Code)

Primer punto de la hoja de ruta, aprobado por el dueño («lo normal, como Facebook»). **Estado: PR #27 fusionada (`fcd2985`), desplegada y con la migración 002 aplicada en producción.** Falta que el dueño vuelva a entrar con start.gg una vez para recibir la cookie y confirme que ya no se le pide. Detalle en CUENTAS-OAUTH.md, «Mantener la sesión iniciada».

- CI de main `fcd2985` correcta; despliegue `37688777954`, `assets_only=true`, correcto. `public.json` idéntico (SHA-256 `1e681141bf4d043319593effc3153f44a7ec38531deef8a427f76c2573a24df1`).
- Migración 002 aplicada desde la Mac del dueño por su orden explícita («aplica la migración 002»): de 31 a 34 tablas, `schema_migrations` con ambas versiones, las tres tablas nuevas InnoDB utf8mb4 y vacías. Sin cambios en lo existente: cuts=1, users=1, survey_responses=16, rankings=376.
- Producción comprobada por HTTP: API anónima `ok`, `authenticated=false`, `oauthReady=true`; una cookie `smash_recordar` inventada devuelve 200 sin sesión y el servidor la borra (`Secure; HttpOnly; SameSite=Lax`), lo que confirma código nuevo y lectura de `user_sessions`. Bibliotecas 403; encuesta, opiniones y cuenta 200.
- No comprobado todavía: emisión y uso de la cookie con la cuenta real (requiere una autorización del dueño en start.gg).
- **Encabezado de la página principal** (pedido del dueño el mismo día, en PR aparte): el enlace «Tu cuenta · Beta» muestra el alias cuando hay sesión. `cuenta.js` guarda el alias como pista visual en `localStorage` (`smashgt.cuenta`) y `app.js` la confirma con `account-api.php`; quien nunca inició sesión no genera ninguna petición de cuenta. La pista no autentica nada. Probado en navegador contra copia local con base desechable: sin sesión, con sesión y después de cerrar sesión.
- **Decisión del dueño para el contador de visitas:** autorizó usar también la IP («si jalemos la ip no hay problema»). Diseño previsto: guardar una huella con clave privada, no la IP en claro; documentar el cambio de la regla de privacidad en esa entrega.

- Cookie propia `smash_recordar` de 90 días que se renueva con el uso; en SQL solo su SHA-256 (`user_sessions`). Sin tokens de start.gg, IP ni navegador. Cerrar sesión termina ese navegador; desvincular termina todos.
- Cambio deliberado respecto a la entrega de cuentas: iniciar sesión en un segundo dispositivo **ya no cierra** el primero. La versión de la conexión solo cambia al volver a vincular después de desvincular.
- Migración nueva `docs/smash/migrations/002_sessions_visits.sql` (3 tablas: `user_sessions`, `site_visit_days`, `site_visitor_days`). Las dos de visitas quedan creadas para la siguiente entrega; ningún código las usa todavía.
- Orden seguro: el código se puede publicar antes de la migración. Sin la tabla, el ingreso funciona como hoy (sesión de navegador de ocho horas) y simplemente no emite la cookie.
- El diagnóstico del panel ahora informa `migrations`; tras aplicar la 002 debe listar ambas versiones y `tableCount` 34.
- Pruebas locales en MariaDB desechable (13.0.2): `test_schema.py` 9, `test_accounts.php`, `test_accounts_http.py` 8, diagnóstico, importadores, encuesta y sincronización; 48 de Python del ranking y Node sin cambios. Nada probado aún en producción ni con el proveedor real.

**Brief listo para el dueño:** [BRIEF-CLAUDE-DESIGN-PANEL-ESTADISTICAS.md](BRIEF-CLAUDE-DESIGN-PANEL-ESTADISTICAS.md), para pedir a Claude Design el panel de estadísticas. Define los únicos datos que existirán; el contador de visitas del servidor es la siguiente entrega y no necesita esperar el diseño.

## Pedidos nuevos del dueño — 7 de octubre

Panel administrativo de estadísticas, sesión persistente, historial/rivales gratis, análisis de contrincante y top 15 por organizador como premium, y ranking por país a futuro. Registro y estado técnico en [HOJA-DE-RUTA-DUENO-2026-10-07.md](HOJA-DE-RUTA-DUENO-2026-10-07.md). Nada implementado; el orden propuesto espera confirmación del dueño.

## Carga automática a SQL — activada el 7 de octubre (Claude Code)

**Estado: `SMASH_SQL_SYNC_ENABLED=true` desde el 7/oct 20:32 UTC, activada por orden explícita del dueño después de la prueba del circuito real.** Falta por ocurrir la primera carga de un corte nuevo (domingo 11/oct).

- Pasos del dueño en cPanel, según la salida que pegó: `/usr/local/bin/php` es PHP 8.1.34 CLI con mbstring, pdo_mysql y zlib; `private-smash/sync.local.php` con permisos 600 (122 bytes); worker manual `{"ok":true,"status":"idle"}`; un solo cron `*/5 * * * *` con el comando documentado (captura de pantalla de Cron Jobs).
- Verificado directamente desde la Mac del dueño: `publish_sql.py diagnostic` devolvió `ok:true`, `phpVersion` 8.1, `memoryLimit` 2048M, `maxExecutionTime` 30 e `inboxWritable:true`. La clave se leyó del archivo local solo hacia el entorno del subproceso; no se imprimió.
- `publish_sql.py check` validó el paquete original (`/tmp/smash-ranking-package.json`, hash `ecb1d4a5cd44f87250537a85d0d166fa6f9824ff3408f0b55c98ac6102fd9e45`); `send` devolvió `sql_synchronized`, `jobId` 1, transporte `dce58f65d9d8abecc775fb6d3058b3fb7242848d477875fbff6851c98f7ed1e0`.
- Lo procesó el cron real, no una ejecución manual: `sync_jobs` id 1, `ranking_import`, `succeeded`, inicio 20:30:02 UTC (tick de cinco minutos), fin 20:30:04, sin `error_code`. Línea del registro del worker pegada por el dueño: `already_imported`, `cutId` 1, pico de memoria 141082624 bytes (~134.5 MiB, con límite de 512M).
- Sin duplicados: antes y después 1 corte publicado (cutId 1), 188 posiciones por vista, 8985 sets, 3435 jugadores, 81 `cut_events`, 5272 `cut_set_results`. Un segundo `send` del mismo paquete devolvió el mismo `jobId` 1; `sync_jobs` sigue con una fila.
- `public.json` sin cambios: SHA-256 `1e681141bf4d043319593effc3153f44a7ec38531deef8a427f76c2573a24df1`.
- La publicación programada ya dispara en este repositorio: run `37670973001` (7/oct 18:58 UTC, evento `schedule`, omitido por no ser domingo). Queda resuelta la duda anotada más abajo.
- **Pendiente de comprobar el domingo 11/oct o el lunes 12:** que `smash-publish.yml` publique el corte nuevo y que su paso de SQL termine `sql_synchronized` con un `cutId` 2. Si la web se publica y SQL falla, la ejecución queda en rojo: reenviar el paquete de ese corte (artefacto `smash-gt-paquete-sql`) con `publish_sql.py send`, o usar el respaldo `weekly_ranking_load.py`; no borrar cortes.
- Observación: la CI de `main` `37667860684` seguía con el job de MariaDB 10.11 en curso más de hora y media después de iniciar (los otros dos jobs correctos); parece el atasco de entorno ya descrito, no un fallo de pruebas.

## Relevo vigente a Claude Code

El dueño pidió detener a Codex y documentar la continuidad. Leer primero **[RELEVO-CLAUDE-CONTINUACION.md](RELEVO-CLAUDE-CONTINUACION.md)**: prompt listo, estado comprobado, configuración de BanaHosting (ya completada, ver bloque anterior) y opciones para avanzar remotamente. Recomendación: historial disponible desde SQL/estadísticas de rivales; el dueño no seleccionó todavía ese módulo ni agenda/estudio TrueSkill. Esta entrega solo documenta; no cambia código, datos ni producción.

## Encargo vigente — dueño remoto y transparencia del método

- El dueño está trabajando remotamente y pidió dejar por escrito los pasos que requieren su computadora/cPanel. Guía: [PENDIENTES-DUENO-BANAHOSTING.md](PENDIENTES-DUENO-BANAHOSTING.md). No pedir claves por chat; el archivo local ya existe. El agente puede continuar diagnóstico/envío/lecturas/activación después de recibir evidencia de la configuración del servidor.
- Revisión directa antes de esta entrega: `SMASH_SQL_SYNC_ENABLED=false`, receptor POST 503 `sync_not_configured`, public.json SHA-256 `1e681141bf4d043319593effc3153f44a7ec38531deef8a427f76c2573a24df1`. No se ha confirmado subida del archivo ni cron; no activar SQL todavía.
- Se preparó la explicación pública en la página existente `metodologia.html#trueskill`: Bradley–Terry regularizado frente a TrueSkill clásico, incertidumbre, actualización, pesos, repeticiones y actividad. Rankup 2024 declara separar puntos de invitacionales del ranking TrueSkill; sus parámetros exactos no están detallados en la página revisada. Fuentes enlazadas de Microsoft y de la liga.
- El dueño autorizó publicar esta información. No se modifica cálculo, contrato/validación ni `public.json`; no se implementó una simulación TrueSkill ni se cambió el orden de jugadores. Se reutiliza la pantalla de metodología, sin pantalla nueva que necesite handoff.
- Validación local: 48 pruebas del ranking/exportación/despliegue correctas, `git diff --check` correcto, HTML con IDs únicos y fragmentos válidos. Revisión visual en navegador: tabla de escritorio y filas apiladas en iframe de 390 px legibles. JavaScript de metodología sigue cargando torneos/datos. No se modificaron scripts del modelo ni datos.
- CI de la PR detectó una prueba de paridad intermitente: comparaba `players.updated_at` generado por SQL en importaciones ejecutadas en segundos distintos. Solo esa comparación entre importadores omite ese metadato de reloj; conserva fechas del paquete/fuente y todas las columnas de resultados. Snapshots de rollback/conflicto mantienen el timestamp. Corrección limitada a pruebas, sin tocar importadores de producción.
- **Publicado y verificado:** PR #23 fusionada en `82858eb`; evidencia de cierre abajo. Siguen pendientes los pasos de configuración privada/cron y la prueba real de SQL del dueño; no confundir publicación de información con activación de la automatización.

### Cierre — guía del dueño y comparación pública

- CI del último commit de PR #23: `37665496993` y `37665508275`, completas/correctas (check y MySQL 8.0/MariaDB 10.11). Dos jobs detenidos instalando dependencias se cancelaron y se reintentaron; ambos terminaron correctamente. No se ignoró el fallo inicial de la prueba de timestamps: quedó corregido solo en el test.
- Despliegue `37666259662` desde main `82858eb`, `assets_only=true`, correcto. URL para compartir: **https://rankingsmashbros.com/metodologia.html#trueskill**. Página y CSS servidos coinciden byte por byte con main; vista en navegador con cinco filas de comparación y catálogo cargado (42 eventos/7,526 sets en la vista combinada).
- `public.json` idéntico antes/después, SHA-256 `1e681141bf4d043319593effc3153f44a7ec38531deef8a427f76c2573a24df1`. No recálculo, cambios de posiciones, contrato ni esquema.
- API anónima: ok=true, authenticated=false, oauthReady=true; encuesta/opiniones 200; worker y bibliotecas de sincronización/importación 403. No se enviaron paquetes ni se escribió en SQL durante esta entrega.
- Archivo privado local conservado, ignorado y con permisos 600. `SMASH_SQL_SYNC_ENABLED=false` comprobado tras publicar. El dueño todavía debe subir el archivo privado, comprobar PHP/worker y crear el cron; guía práctica PENDIENTES-DUENO-BANAHOSTING.md. Diagnóstico autenticado, prueba con cron real y activación siguen pendientes.
- Los documentos de operación/continuidad enlazan la guía. La evaluación empírica de TrueSkill con los mismos sets no se ejecutó ni se encargó; no sustituir el modelo actual basándose solo en la comparación conceptual.

## Cuentas — nueva entrega de Codex

- Revisadas entregas de Claude Code: encuesta en SQL y cierre de migración, cargador semanal operado desde la Mac, sin reinstalar tablas. Base de trabajo `main` en `99d65c3`.
- Handoff de Claude Design leído e implementado: ingreso, elección de intereses, perfil y editor de mains. Backend OAuth/sesiones y preferencias sobre las tablas existentes; sin cambios al cálculo ni JSON. Detalles/activación: [CUENTAS-OAUTH.md](CUENTAS-OAUTH.md).
- El dueño ya registró **OAuth Application** y configuró el archivo privado. API real con `oauthReady=true`; vinculación real del propietario comprobada en Chrome. Tokens descartados después de verificar identidad; reportes/agenda y sincronización personal quedan para otra fase.
- Pruebas locales con base desechable: vinculación por IDs, roles sin permisos administrativos, guardado/rollback, revocación y paridad de ambas vistas. No se creó ningún usuario real ni se usaron tokens de producción. CI y publicación cerradas; pendiente la prueba real de OAuth tras el registro de la aplicación.

## Cierre de cuentas — publicado y comprobado

- PR #18 fusionada el 7/oct: `4229d26`. CI `37654934247` (push) y `37654969407` (PR), correctas en los tres jobs; incluyen MySQL 8.0, MariaDB 10.11 y lint PHP 7.4/8.1.
- Despliegue `37655240917`, correcto, `assets_only=true`, desde `main`. Sitio: https://rankingsmashbros.com/cuenta.html. Ingreso desactivado: API real devuelve `ok=true`, `authenticated=false`, `oauthReady=false` y `no-store, private`.
- Verificado directamente por HTTP y navegador: pantalla de ingreso 200, biblioteca `accounts.php` 403, escritura sin CSRF 403, encuesta y opiniones 200. JSON íntegro conservado, SHA-256 `1e681141bf4d043319593effc3153f44a7ec38531deef8a427f76c2573a24df1`.
- Lectura SQL real de conteos (sin escritura): `users=0`, `survey_responses=16`. No se crearon cuentas sintéticas en producción. Perfil/editor/guardado, filtros y sets revisados en base local desechable; también versión móvil a 390 px sin desbordamiento.
- Configuración registrada por el dueño: **OAuth Application**, retorno exacto `https://rankingsmashbros.com/oauth.php`, alcance `user.identity`, credenciales en `private-smash/oauth.local.php`. Pasos completos y ejemplo seguro: CUENTAS-OAUTH.md. No pedir secrets por chat ni configurar tokens de usuarios desde mensajes antiguos.
- Próxima acción técnica, después de configurar: probar autorización/cancelación reales, vinculación del jugador, guardado, cierre y desvinculación. No afirmar que el proveedor fue probado por pasar tests simulados.

## Activación OAuth y protección local — actualización del dueño

El dueño confirmó que registró la aplicación, subió `oauth.local.php` al archivo privado del servidor y puso `enabled=true`. Codex comprobó directamente que `account-api.php` devuelve `ok=true`, `authenticated=false` y **`oauthReady=true`**. La configuración pasó la validación del backend y posteriormente se completó la autorización real en Chrome.

El dueño había colocado su client secret en el ejemplo local versionado. Se preservó el contenido en `docs/smash/config/oauth.local.php` (permisos 600, ignorado por Git) y se restauró `oauth.local.php.example` con placeholders. No se imprimió el secreto. La comparación de su valor contra el índice, archivos versionados y objetos del historial local disponible no encontró coincidencias; no se declara una auditoría de clones o fuentes externas.

El cierre documental anterior estaba en `docs/accounts-activation`, commit `5cd9afe`, sin PR por errores de GitHub. Esta entrega incorpora ese cierre y la protección de credenciales a una rama nueva; no duplicar la entrega de código ni desplegar otra vez por cambios de documentación/.gitignore. La vinculación real del propietario fue comprobada; ver evidencia siguiente.

## Vinculación real comprobada — Bucaro19

- En Chrome, el proveedor reconoció la aplicación registrada por el dueño, `rankingsmashbross`, con enlace a `https://rankingsmashbros.com/` y permiso exclusivo de información básica. Se completó Approve y el callback regresó a la cuenta autenticada.
- Perfil real observado: Bucaro19 y enlace `https://www.start.gg/user/7a6063d8`, coincidente con el perfil que el dueño compartió al iniciar el proyecto. Foto, país GT de perfil, intereses jugador/organizador, ranking combinado #177 (1276 puntos), cuatro eventos disponibles y mains detectados Lucas/Hero/Incineroar. El puesto pertenece al corte Oct4; no es una recalculación nueva ni nacionalidad verificada.
- Lectura directa posterior confirmó un usuario y una vinculación activa con **ambas columnas de tokens NULL**. No se imprimieron credenciales, códigos, state ni tokens. Cuenta real del propietario; no se agregó una cuenta sintética de pruebas.
- La consulta GraphQL de identidad y el intercambio de código funcionan con el proveedor real. Guardado, cancelación, revocación y rollback tienen pruebas desechables previas; no se hicieron cambios arbitrarios a mains ni cierre/desvinculación de la sesión real del dueño.
- Pestaña del perfil conservada en Chrome para el dueño. Continúan pendientes agenda/torneo en curso, verificación de organizadores, reportes y notificaciones; nuevas pantallas requieren handoff de Claude Design.

## Redespliegue solicitado por el dueño — 7/oct

- La entrega de protección y cierre OAuth ya estaba fusionada: PR #19, `main` en `0328693`. No quedaron PR abiertas de Claude ni cambios locales pendientes; CI de main `37657991274` correcta.
- A petición explícita del dueño se volvió a publicar desde `main` con `assets_only=true`: [run 37658175611](https://github.com/Bucaro-19/rankingsmashbros/actions/runs/37658175611), terminado correctamente. No se recalculó el ranking ni se reemplazó el corte.
- Verificación HTTP posterior: index/cuenta, JS y estilos servidos coinciden byte por byte con main; encuesta/opiniones 200; accounts.php, database.php y feedback-data/ 403. API anónima 200, `oauthReady=true`, `authenticated=false`, `Cache-Control: no-store, private`. La autorización real de Bucaro19 fue comprobada antes de este redespliegue, según la sección anterior.
- `data/public.json` idéntico antes/después: SHA-256 `1e681141bf4d043319593effc3153f44a7ec38531deef8a427f76c2573a24df1`, corte 2026-10-04T11:43:18.348499+00:00, 188 jugadores por vista.
- Archivo OAuth local conservado e ignorado, ejemplo sin credenciales. Protección adicional en `.git/info/exclude` para conservar la exclusión local al cambiar de rama; no es un archivo para publicar. El despliegue no incluye los archivos de configuración privados.
- Continúan los pendientes de operación semanal/SQL y módulos posteriores descritos arriba. Este cierre solo registra el redespliegue verificado y no requiere volver a publicar documentos.

## Automatización SQL en BanaHosting — nueva entrega

El dueño eligió BanaHosting para funcionar con la Mac apagada. Implementado receptor HTTPS autenticado + cola privada + importador PHP/worker CLI + paso Actions; sin migración ni cambio de cálculo. Detalles, límites y activación: CARGA-SEMANAL-SQL.md, bloque vigente. Paridad Python/PHP tabla por tabla, 11 casos locales y paquete real Oct4 verificados en base desechable. Preparado; configuración/cron y prueba del circuito de producción aún pendientes. No afirmar que ya está programado ni activar variable antes de validar servidor.

## Cierre de entrega SQL en hosting — publicado, activación pendiente

- PR #21 fusionada en `5963fbe`. CI `37661548814` y `37661557318` completas/correctas: contrato/JS/lint PHP y ambos motores MySQL 8.0/MariaDB 10.11; incluyen las 11 pruebas nuevas. Sin cambios de esquema.
- Despliegue `37661808161`, desde main y `assets_only=true`, correcto. HTTP real posterior: receptor GET 405, bibliotecas/worker 403; cuenta API con `oauthReady=true`; encuesta/opiniones 200. JSON íntegro sin cambios, SHA-256 `1e681141bf4d043319593effc3153f44a7ec38531deef8a427f76c2573a24df1`.
- Recepción POST en producción devuelve 503 `sync_not_configured`, coherente con archivo privado todavía ausente. Lectura SQL directa: cuts=1, users=1, ranking_import_jobs=0. No se cargó un corte ni se crearon trabajos de prueba en producción.
- Generada clave aleatoria en `docs/smash/config/sync.local.php`, ignorado/permisos 600; preservada fuera del índice. Se guardó el mismo valor por stdin como secreto GitHub `SMASH_SQL_SYNC_KEY`, sin mostrarlo. Variable `SMASH_SQL_SYNC_ENABLED=false`, comprobación/activación pendientes. No imprimir archivo ni secreto.
- **Siguiente acción del dueño:** copiar archivo privado a `/home/ivcjgjlk/private-smash/sync.local.php`, comprobar PHP CLI/worker y crear cron cada cinco minutos según CARGA-SEMANAL-SQL.md. La cuenta FTP del despliegue solo ve el sitio, no la carpeta privada ni crontab; no se supone que esto ya está hecho.
- Después Codex puede ejecutar diagnóstico autenticado, reenvío idempotente del paquete original Oct4, lectura de paridad/job y activar la variable si el circuito funciona. Primer nuevo corte/disparo semanal del 11/oct sigue pendiente de ocurrir; no crear recaptura con hash diferente ni dar por verificado el cron.

## Estado vigente

- El dueño compartió el resultado real del diagnóstico privado: connection=connected, MariaDB 11.4.13, schemaVersion=001_accounts_competition, tableCount=31, missingTables=[], engineCompatible=true y schemaReady=true. Base de la instalación: `ivcjgjlk_smash`. Evidencia recibida del dueño el 6/oct/2026 (Guatemala), no lectura directa del agente mediante navegador.
- PR #1 del repo nuevo fusionada en `main`, commit `cb89570`. Preparó v1 `001_accounts_competition`: 31 tablas/87 selecciones esperadas. CI correcto: 46 Python + 12 Node y 8 pruebas por motor (MySQL 8.0/MariaDB 10.11), run `37574948355`.
- No reinstalar tablas. Archivo observado sin abrir contenido: /home/ivcjgjlk/private-smash/config.local.php. Conector y diagnóstico publicados: PR #4 `a29355e`, PR #5 `e8e7d55`, PR #6 `8d509c2`; último despliegue `37578387425`, correcto. Conexión y esquema confirmados por el diagnóstico compartido; no pedir contraseñas por chat.
- Conteos iniciales del diagnóstico (antes de importar): characters=87 y demás tablas consultadas=0. Primera carga real completada por Codex el 7/oct/2026: cutId=1, status=published, 188 rankings combined + 188 guatemala, 3435 jugadores de contexto, 43 torneos, 47 eventos, 4498 entrants, 8985 sets y 17970 slots. Usuarios siguen en cero. Posteriormente el dueño ejecutó el importador de Claude: 13 respuestas SQL, incluida 1 prueba interna; conteos/hashes únicos verificados directamente por Codex.
- La web pública sigue leyendo JSON. Desde el 7/oct la encuesta y el panel usan SQL (ver «Encuesta y panel en SQL» abajo); `feedback-data/respuestas-2026.php` quedó congelado como archivo histórico. El corte/historial ya están en SQL.
- Dominios/repos: sitio activo https://rankingsmashbros.com/, repo Bucaro-19/rankingsmashbros. Graduación es legado.

## Instrucción nueva del dueño

Toda pantalla nueva debe solicitarse primero a **Claude Design** y seguir su handoff. Documentar funciones/estados en un brief y entregarlo al dueño; no inventar la pantalla en código. Backend/importadores pueden avanzar sin pantallas. Regla guardada en AGENTS.md y CLAUDE.md.

## Conexión PHP — publicada y confirmada por el diagnóstico del dueño

- database.php carga únicamente el archivo privado hermano del sitio, valida formato y conecta mediante PDO con utf8mb4, UTC y prepared statements nativos. No imprime secretos/excepciones.
- opiniones.php?diagnostico=base ofrece cuerpo JSON de conteos/versiones solo a sesión administrativa válida. Navegaciones que aceptan text/html reciben text/plain; clientes API application/json. Anónimo 401; POST 405. El panel existente incluye el enlace «Comprobar conexión a la base de datos» únicamente tras autenticarse. No pantalla nueva ni cambios a respuestas.
- El dueño renovó la sesión en Chrome; el panel mostró 12 respuestas antes y después de publicar. La herramienta de Chrome devolvió ERR_BLOCKED_BY_CLIENT al abrir el diagnóstico, tanto por navegación directa como por clic en su enlace. Cambiar el formato no resolvió ese bloqueo, pero el dueño lo abrió manualmente y compartió la respuesta exitosa. La limitación de la herramienta no bloquea la siguiente fase ni requiere más cambios a ciegas. Nunca extraer cookies ni contraseñas.
- Pruebas locales: configuración privada, supresión de salida y sesiones; 6 contratos HTTP; 46 Python + 12 Node. Última CI `37578278589`/`37578275593`: todos los checks correctos, incluida conexión PDO real sobre MySQL 8.0/MariaDB 10.11. Esas bases son desechables, no el hosting.
- Último despliegue assets_only=true: `37578387425`, correcto. Verificación HTTP real: diagnóstico anónimo 401/login_required en ambos formatos y cache no-store/private; acceso directo a database.php 403; inicio, encuesta y opiniones 200. public.json idéntico tras despliegues y carga SQL (SHA-256 `1e681141bf4d043319593effc3153f44a7ec38531deef8a427f76c2573a24df1`). El importador CLI no requiere un nuevo despliegue del sitio.
- Conexión y primera carga cerradas: lectura y escritura transaccional verificadas directamente desde la Mac. Solo se crearon datos de contexto y un corte; el frontend y la encuesta conservan su almacenamiento actual.

## Próximo trabajo

### Encuesta y panel en SQL — publicado el 7 de octubre (Claude Code)

- **Producción escribe y lee la encuesta en `survey_responses`.** PR #13 fusionada (`033bd6a`), despliegue `37647575579` correcto. Contratos, protocolo ejecutado y evidencia: MIGRACION-ENCUESTA.md, «Entrega 2» y «Transición en producción».
- Base al publicar: 14 filas (13 de comunidad + 1 prueba), todas importadas de los dos archivos y comparadas fila por fila. El archivo del sitio nuevo quedó congelado (440) con dos respaldos en `private-smash/`.
- Verificado después: una respuesta de prueba real entró por el formulario nuevo y quedó con `is_test=1` (15 filas: 13 de comunidad, 2 de prueba); el diagnóstico del panel, abierto por el dueño, dio `phpVersion=8.1`.
- **Migración cerrada el 7/oct:** dominio anterior redirigido (`rsvp-graduacion#26`), su archivo congelado e importado, y la prueba del dueño marcada `is_test=1`. Estado final: 16 filas, 13 de comunidad y 3 de prueba. Evidencia en MIGRACION-ENCUESTA.md, «Cierre».
- No revertir el PR ni desplegar ramas anteriores: `deploy.py` rechaza páginas de encuesta que no sean las de SQL y los despliegues solo corren desde `main`.
- Hallazgo para el dueño: el repositorio es público, así que los artefactos de Actions los puede descargar cualquier usuario con sesión en GitHub.
- Handoff de Claude Design para cuentas ya entregado por el dueño: carpeta local `SmashRankingGT/design_handoff_smash_gt_cuentas/` (fuera de este repo, sin versionar). Su README nombra el repo `rsvp-graduacion`; el correcto es este. Implementación en esta entrega; configuración habilitada y autorización real comprobada con el propietario.

### Carga semanal del ranking a SQL — preparada, sin activar (Claude Code)

- PR #14 fusionada (`0c727fc`): cargador de un comando operado desde la Mac del dueño (`scripts/database/weekly_ranking_load.py`) y artefacto propio del paquete SQL con 90 días. Documento: CARGA-SEMANAL-SQL.md. Nada programado.
- **Siguiente acción, lunes 12 de octubre:** comprobar que la publicación del domingo 11 terminó bien y dejó el artefacto `smash-gt-paquete-sql`; después, desde la Mac, `status`, `load` (simulación) y `load --apply`. Es la primera prueba real de la descarga y del segundo corte.
- **Vigilar antes del domingo:** al cierre de esta entrega (7/oct, 16:05 UTC) el workflow `smash-publish.yml` todavía no había generado ninguna ejecución programada en este repositorio, ni el tick diario de las 12:23 UTC que debe aparecer como omitido. En el repositorio anterior ese tick llegó con unas seis horas de retraso, así que puede ser demora de GitHub. Si el jueves sigue sin aparecer ninguno, la publicación del domingo podría no dispararse sola: lanzarla a mano con `workflow_dispatch` desde `main`. El primer tick también es la primera evaluación real de la condición `if` del trabajo, que ahora exige `main`.

### Ranking/historial — entrega completada por Codex

- PR #9 fusionada en main, commit e685fb2. Checkout separado /tmp/smash-ranking-db-import; el principal queda disponible para Claude. Reparto y prompt: TRABAJO-PARALELO-2026-10-07.md.
- ranking_package.py genera paquete determinista desde combined.json y public.json sin recalcular ni consultar API. import_ranking.py valida y escribe con transacción/bloqueo/paridad; modo predeterminado de simulación. Guía IMPORTACION-RANKING.md.
- Lectura directa desde la Mac confirmada mediante configuración privada ya provisionada: MariaDB 11.4.13 y cuts=0. No se imprimieron credenciales. La simulación real del corte Oct4 terminó validated_no_writes: 3435 jugadores de contexto, 43 torneos, 47 eventos, 4498 entrants, 8985 sets y 17970 slots; vistas de 188 jugadores cada una (42/39 eventos y 2648/2624 resultados). No confundir jugadores de contexto con clasificados guatemaltecos.
- Primera importación real: imported/cutId=1; repetición: already_imported/cutId=1. Consulta directa confirmó published, generated_at=2026-10-04 11:43:18.348499, 188 jugadores por vista, players=3435, sets=8985, users=0 y survey_responses=0. Hash del paquete: ecb1d4a5cd44f87250537a85d0d166fa6f9824ff3408f0b55c98ac6102fd9e45. El importador verificó paridad completa antes de publicar y nuevamente al repetir; no fabricó el corte anterior.
- CI 37581615922 y 37581612335 correcta: 46 pruebas Python del ranking, 12 Node, 4 contratos del paquete y 6 casos SQL reales por motor (MySQL 8.0/MariaDB 10.11), además de las pruebas de esquema/conector existentes.
- La encuesta queda asignada a Claude para preparar código/tests, sin activar escritura SQL todavía. SQL semanal automático aún pendiente: Actions prepara artefacto privado; no tiene acceso remoto a MySQL. No abrir ese acceso a las IP variables de Actions.

### Encuesta — revisión de PR #10

- Claude entregó importador CLI repetible, pruebas inventadas y MIGRACION-ENCUESTA.md. El dueño ya ejecutó una primera copia en cPanel; el archivo sigue siendo la fuente de encuesta/opiniones.
- Codex verificó directamente solo agregados de producción: 13 filas, 13 hashes distintos, 1 is_test. Sin leer comentarios ni ejecutar escrituras.
- PR #10 revisada y fusionada en main `972225d`: protección de la transacción del llamador y regresión; integración en CI MySQL 8.0/MariaDB 10.11 con extensiones SQLite/mbstring explícitas. Sintaxis y suite SQLite locales correctas. CI `37582761629` correcta sobre `b7d842a`; suite nueva confirmada en logs sobre MySQL 8.0.46 y MariaDB 10.11.19. Checks del commit final correctos: `37582899820` y `37582895363`.
- Pendientes: repetición real con versión revisada, hash/tamaño del respaldo y comparación de valores. Después, transición controlada del archivo a SQL con pausa de envíos y verificación final; no activar doble escritura ni asumir que el despliegue FTP es atómico.

Siguiente: completar la transición de encuesta y preparar transporte privado/autenticado para automatizar la carga SQL semanal. Mantener JSON público y método/calendario actuales. Después OAuth y perfil según handoff de Design. OAuth no garantiza cuota independiente por usuario; consultar datos compartidos desde base/caché.

El dueño encargó esa continuación a Claude Code. Relevo/prompt vigente en **RELEVO-CLAUDE-CODE-2026-10-07.md**; sustituye el encargo paralelo anterior, ya cumplido. Prompt de ingreso/perfil/mains para el dueño en **BRIEF-CLAUDE-DESIGN-CUENTAS.md**. Codex solo preparó el relevo y el brief; no inició la transición ni OAuth y no envió mensajes a otras sesiones.

Este relevo documenta instalación, conector y primera importación/repetición de ranking completadas. Encuesta y automatización SQL pendientes. Consultar Git/Actions antes de retomar.

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
