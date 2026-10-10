# Láminas del top por organizador

Entrega del 10/oct/2026, rama `feat/organizer-download-slides`. Handoff local `laminas/README.md`, `LaminaJugador.dc.html` y `LaminaTop.dc.html`: referencia de composición, campos, límites y zonas seguras; no se porta support.js ni su dataset. Sin migración o cambio del ranking nacional. No requiere un servicio de imágenes, ZIP o render del servidor.

## Acceso y contrato privado

`GET organizador-api.php`, `state=data`, agrega **`data.slides`**. Se construye **después** de comprobar sesión, contexto propio/membresía y premium vigente del visitante o rol admin. Cada coorganizador paga su propio premium. Los estados login, interest, premium, expired y forbidden no contienen las láminas ni sus datos. El enlace público /top/{slug} y tops-api.php **no agregan** este campo ni estas estadísticas. La respuesta privada conserva `Cache-Control: no-store, private`.

`organizer-slides.php` solo define funciones de lectura, está negado por .htaccess y se sube antes del API que lo requiere. El API sigue usando smash_org_premium (smash_premium_status y excepción admin). No se replica la decisión en el navegador. Los IDs internos de jugadores solo se conservan temporalmente al construir la proyección y se quitan de top/rest; no se entregan IDs de cuentas, correos, datos de pago o nombres reales.

```text
slides: {
  schemaVersion: 1,
  organizer: {name, topSize: 5|10|15, coorganizers: [nombre], seasonYear, cutDate},
  players: [{
    rank, tag,
    mains: [{characterId: string, name, slug, games}],  // hasta tres, o []
    setsWon, setsLost,
    vsTop5: {won, lost} | null,
    results: [{name, date, placement: entero positivo, wins: [{rank, tag, won, mainSlug|null}]}]
  }]
}
```

- Jugadores: solo los que ya figuran en el top elegido, orden idéntico, sin completar filas. No se cambian puntos, ajuste BT, elegibilidad, tablas de instantánea, cálculo nacional o public.json. El parámetro interno `withIds` no modifica la matemática ni la respuesta pública.
- Base: el mismo ledger del organizador, `cut_events`/`cut_set_results` combinado, último corte publicado, torneos propios o confirmados y **20+ activos**. Los pequeños/contexto 006, torneos ajenos y temporadas anteriores no entran. No hay llamada a start.gg por visita.
- Personajes: conteo por game con ganador conocido, dos entrants de singles mapeados a una persona cada uno, selección única por jugador/game; duplicados se cuentan una vez y selecciones ambiguas se omiten. Uso descendente, empate por characterId de forma lexicográfica como player_mains. Se entregan main + dos secundarios. Random (1746) no identifica un personaje real y se omite en esta proyección; no se modifica ningún main publicado o elección de cuenta.
- Contexto mutable: set actual debe seguir siendo competitivo/terminado y coincidir con el source_hash, participantes, ganador y marcadores de su resultado del corte. Los games tienen sincronización no posterior a characterCapturedAt (o generatedAt si falta). Un set corregido después no atribuye personajes a su resultado antiguo; récords y puestos siguen saliendo del ledger inmutable.
- **Puesto final:** solo `entrants.final_placement`, un único entrant de singles para ese jugador/evento, sincronizado no después del mismo límite. Null, sincronización desconocida/posterior o entradas ambiguas: se omite ese resultado; jamás se estima a partir del bracket o G–P. Si hay dos eventos admitidos en un torneo, son resultados separados y su nombre añade el evento: no se finge un puesto agregado del torneo.
- Resultados destacados: hasta tres, mejor puesto primero, después fecha más reciente y nombre. Otros: hasta seis horizontal/cuatro vertical. El API puede entregar todos los resultados conocidos y el dibujo limita los campos según plantilla.
- Victorias destacadas: solo victorias contra jugadores que están en **ese mismo top elegido**, ordenadas por mejor puesto del rival (menor número), agrupadas por rival/evento. Máximo cuatro por resultado; vertical/historia dibuja tres. El icono rival usa sus personajes de estos mismos torneos. Sin victorias se dibuja la caja punteada; sin puesto conocido no se crea la tarjeta.
- vsTop5: sets G–P contra puestos 1–5 que realmente existen en ese top, excluyendo al propio jugador. Null significa que no hubo enfrentamientos; el PNG dibuja «—». Los G–P globales son los mismos del top; el porcentaje decorativo de la plantilla se deriva de esos conteos en el navegador, no se almacena ni altera el cálculo.

## Generación y descarga

En Mis torneos, detalle desplegable «Descargar láminas» junto al top. Componentes existentes de cuenta, sin pantalla nueva. Selecciona Horizontal, Publicación o Historia y Top completo o jugador. Un PNG individual muestra vista previa; «Descargar todas · ZIP» reúne **una del top + una por cada jugador real**, en el formato seleccionado (máximo 16). Nombres incluyen puesto/tag/formato o top/organizador/formato, sin rutas o caracteres de control.

Canvas nativo a 1×, sin html-to-image, Puppeteer ni dependencia de ejecución. ZIP32 store-only con CRC32; no compresión adicional porque PNG ya está comprimido. Techo duro 64 MiB de imágenes y 16 entradas, comprobado también durante la generación; sobrepasarlo deja descargar PNG individuales. Generación secuencial, liberando cada canvas del ZIP. Cambiar de contexto o cerrar la pestaña descarta un trabajo cuya sección ya no está conectada. Controles deshabilitados y progreso accesible durante el trabajo; fallo permite reintentar. No se guardan estadísticas en localStorage ni se suben PNG al servidor.

Antes de dibujar se esperan FontFaceSet.load + fonts.ready; se exige al menos una cara realmente cargada por familia y se comprueba fonts.check. Sin fuentes, se informa el error y no se produce PNG con tipografía de respaldo. Big Shoulders Display 900 y Archivo 700 desde la hoja que ya usa cuenta.html. Recursos de personajes y logo salen del propio dominio; imagen de personaje fallida puede usar iniciales, conservando su nombre conocido.

Medidas y zonas de contenido:

| Formato | PNG | Contenido importante |
| --- | --- | --- |
| Horizontal | 1920 × 1080 | x 96–1824, y 64–1040 |
| Publicación | 1080 × 1350 | x 64–1016, y 60–1306; puesto/tag/estadísticas/torneos dentro del recorte central y 135–1215 |
| Historia | 1080 × 1920 | layout vertical desplazado 250 px; contenido y 250–1600; arriba 250 y abajo 320 solo decoración |

Tag máximo 20 caracteres en el dibujo (más largo se trunca con …); tipografía adaptada a largo y ancho. Organizador de etiqueta hasta 60, nombre del top adaptado a dos/tres líneas, crédito de hasta 10 coorganizadores con límite visual de líneas. Pie fijo **completo**, envuelto y ajustado, nunca truncado: «Top de {organizador} · solo sus torneos · no es el ranking nacional · rankingsmashbros.com».

No aparecen años anteriores, nombres reales, redes, logos de torneos, niveles S+/A, logos Nintendo o símbolo Smash. Se conserva el logo actual de Ranking Smash Bros. El diseño se recrea en primitivas Canvas para obtener PNG exacto sin servicio; no se importan los componentes del prototipo. Si falta posición no se dibuja la tarjeta del torneo, aunque haya sets allí: es un requisito de la plantilla, no ausencia de actividad.

## Recursos y coste de publicación

La carpeta existente solo tenía 25 PNG (principalmente DLC). Se conservan y se añaden **147** espejos locales del catálogo ya utilizado por characters.js: **23 095 305 bytes** adicionales; total **172 PNG / 29 435 523 bytes**. FILES los recoge mediante su allowlist existente. No cambian las URLs de characters.js ni el seed SQL. Procedencia y SHA-256 en [LAMINAS-ASSETS.json](LAMINAS-ASSETS.json); arte y crédito marcrd/recursos DLC ya reconocidos por el sitio. Nada viene del dataset de ejemplo del handoff.

Esto aumenta los bytes de un despliegue assets-only; no introduce consultas a start.gg, costes por render, tabla nueva o servicio. Cada exportación carga los personajes que necesita; caché de imágenes públicas en memoria para las siguientes descargas. No se precargan los 172 archivos por visita.

## Validación y límites comprobados

- Cinco HTTP nuevos con SQL inventado: gratis/vencido/anónimo/ajeno sin payload, coorganizador con premium propio, admin, games vacíos, placements desconocidos/posteriores, personajes ambiguos/correcciones, extranjeros/pequeños ajenos omitidos, destacados por rival y puntos idénticos. /top y directorio públicos sin slides.
- Seis Node con @napi-rs/canvas **solo para pruebas**, versión fijada 0.1.80: PNG reales en las seis variantes, safe boxes, tag 20, sin main, un torneo, cero victorias, top 5/10/15 y 0/1/2 jugadores; ZIP con 16 PNG leído por zipfile y CRC/dimensiones correctos; techos, rutas/duplicados, fuentes fallidas y campo privado. La dependencia no se publica ni ejecuta en el sitio.
- Regresión: 13 HTTP de organizador, ocho HTTP del directorio, ocho Node de organizador y 93 Python de pipeline. CI ejecuta ambos motores MySQL 8.0/MariaDB 10.11 y PHP 7.4/8.1.
- Navegador local con sesión y SQL inventados: descargas PNG reales 1920×1080, 1080×1350 y 1080×1920, retrato, ausencia de personaje, vista previa y ZIP. Controles a 1280/375 px sin desborde (1265/1265 y 360/360). Top de 15 produce 16 láminas; top con tres produce cuatro. Archivos y capturas bajo `/tmp/smash-org-laminas-20261010/`.
- Muestra local de 15 jugadores inventados: proyección 2060 bytes, vista completa con enriquecimiento **4,14 ms / 2 MiB de pico PHP**. Es una muestra pequeña, **no una medición de producción o del máximo**. Consulta de selecciones tiene techo de 150 000 filas; superarlo da error de lectura, nunca una lista parcial presentada como completa. Sin índices/migración nuevos.

No se consultó ni escribió producción, no se publicó ni fusionó. Ver EN-CURSO para PR y CI. Al integrar ambas tareas, conservar sus dos registros si EN-CURSO produce conflicto de inserción.
