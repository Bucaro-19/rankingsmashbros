# Prepara el set por personaje

## Selector y consulta — 11/nov/2026 GT

La pestaña «Por personaje» de `preparar.html` incorpora el handoff `design_handoff_smash_gt_prepara_el_set`. Busca por nombre sin distinguir acentos y usa los íconos locales. Desde «Por jugador» puede sugerir el main que llegó en el análisis. La selección de la consulta queda en el URL. Se puede abrir directamente `preparar.html?mode=character&target=link&scope=gt`. La vista arranca en Solo Guatemala cuando falta el alcance y permite ver también + Internacional.

`GET analisis-api.php?mode=character&target=link&scope=gt` usa el acceso de análisis existente. Devuelve `mode`, `target`, `scope`, `generatedAt`, `state`, `access`, `premium` y `sample`. `sample.status` vale `available`, `empty` o `cut_not_synced`. `sample.minimum` describe los umbrales y `sample.availableCrosses` es el número de cruces que los alcanzan.

- Con acceso completo, `mine` lista las elecciones del perfil en orden y con su rol. `crosses` contiene `{slug, gamesWon, gamesLost, sets, events, pairs, trend}`. Cada game cuenta una vez desde el personaje de la fila. Sets, eventos y parejas de jugadores se cuentan sin duplicados. La tendencia es `favorable`, `unfavorable`, `balanced` o `small`.
- En acceso gratis o vencido, `preview` contiene como máximo un cruce con muestra suficiente, seleccionado por cantidad de games, sets y slug. `mine`, `crosses` y las fichas quedan reservados al acceso completo.
- Las fichas reutilizan `toolkit`, `punishable` y `frameDataSource`. «Cómo jugar el cruce» muestra el vacío hasta que existan consejos con revisión y atribución.

La consulta lee games de eventos admitidos en el alcance solicitado. Busca el mismo snapshot público en SQL y usa `synced_at <= characterCapturedAt`. Aplica los filtros de games verificables de análisis, excluye espejos y consulta solo los games donde hay una selección del personaje solicitado. La tendencia exige 20 games, 5 sets, 2 eventos y 3 parejas distintas, con dirección a partir de 60% de victorias o derrotas. Los personajes propios aparecen primero y distinguen muestra pequeña, sin selecciones y espejo. Los demás cruces pequeños se agrupan en un desplegable.

Medición de solo lectura en el corte 8 del **8/nov/2026**:

| Alcance | Games válidos | Cruces distintos | Muestra suficiente | Tendencia favorable para un lado |
| --- | ---: | ---: | ---: | ---: |
| Solo Guatemala | 5.598 | 1.238 | 32 | 21 |
| + Internacional | 6.234 | 1.316 | 37 | 24 |

Validación de cuenta gratis, vencida, Premium, perspectiva inversa, alcance, ausencia de selecciones, corte desincronizado y picks ambiguos o posteriores. Pruebas locales con MariaDB desechable. Chrome a 375 y 1440 px verificó búsqueda, teclado, enlace desde el rival, cambio de alcance, reintento, fichas y adelanto.

## Cobertura medida el 6 de noviembre de 2026

Lectura agregada en una transacción SQL de solo lectura. Corte 7, generado el 2 de noviembre de 2026 a las 07:31:56 UTC. La muestra combina torneos de Guatemala y del extranjero admitidos en ese corte. Se incluyen games competitivos con ganador, dos jugadores distintos, un pick inequívoco por lado y captura hasta la fecha de personajes del corte. Se excluyen Random y espejos para esta medición.

| Medición | Total |
| --- | ---: |
| Games con picks distintos y válidos | 6.234 |
| Cruces distintos, contando A–B una sola vez | 1.316 |
| Cruces con 20 games, 5 sets, 2 eventos y 3 parejas de jugadores como mínimo | 37 |
| Cruces de esa muestra con un lado que ganó al menos 6 de cada 10 games | 24 |

Estos umbrales son una propuesta para probar cobertura. La proporción describe el resultado observado. La habilidad de los jugadores, sus cambios de personaje y la concentración de resultados por evento también influyen. Por eso, mostrar ganados–perdidos y los tamaños de muestra, con el rótulo «Tendencia en los torneos del corte».

## Fichas técnicas recuperadas

La primera entrega muestra opciones fuera del escudo para Ice Climbers, Joker, Ken, Lucario, Marth, Roy y Ryu con los datos ya guardados. El golpe más rápido puede venir como `null` dentro de una ficha parcial. Cuando solo hay datos del personaje rival, se muestran sus ventanas de castigo y se indica que faltan opciones propias para comparar. Steve sigue sin ficha propia y conserva los castigables verificados cuando es el rival. Las formas agrupadas de Pokémon Trainer y Pyra/Mythra siguen pendientes de un contrato que distinga sus formas.

## Brief para Claude Design

Diseña una variante de «Prepara el set» para móvil de 375 px y escritorio. Mantén los tokens, encabezado, iconos y tarjetas actuales. Permite alternar entre «Por jugador» y «Por personaje». En la segunda opción puedo elegir el luchador que quiero estudiar aunque no conozca el tag del rival o el sitio no tenga su main. Si vengo del análisis de un jugador con main detectado, puede aparecer preseleccionado. Cualquier selección manual debe identificarse como parte de la consulta, sin asociarla al historial del jugador.

- **Cruces observados.** Mostrar primero mis personajes elegidos y luego los demás cruces con muestra suficiente. Incluir récord G–P desde una perspectiva rotulada, games, sets, eventos y fecha del corte. Separar tendencia favorable, desfavorable y sin dirección clara. Diferenciar muestra pequeña de ausencia de selecciones. No usar etiquetas como «counter garantizado».
- **Cómo jugar el cruce.** Dejar espacio para consejos originales revisados, con autor, fecha, enlace de referencia y una acción concreta para practicar. Si falta guía, mantener visibles las estadísticas o la ficha técnica. Las opiniones de jugadores y las estadísticas van en bloques separados.
- **Herramientas técnicas.** Reusar la ficha de frames y el cálculo de ventana de castigo. Diseñar los estados con ficha completa, parcial, solo datos del rival y sin ficha.
- **Estados.** Incluir carga, error, sin personaje propio elegido, rival sin historial, cruce con datos escasos y acceso Premium bloqueado. La cuenta sin acceso recibe solo el adelanto permitido por el servidor.

## Datos y operación propuestos

Usar los picks de cada game y los torneos del corte para la primera versión. Agregar por pareja de personajes en el siguiente corte o leer los agregados existentes cuando haya un contrato para ello. Medir antes de añadir almacenamiento. El sitio consulta datos locales al abrir la ficha. Mantener separadas la muestra de Guatemala, la combinada y cualquier muestra internacional externa que se autorice incorporar en el futuro.

El [estudio de LG SchuStats](https://www.luminosity.gg/news/smash-ultimate-results-based-matchup-charts) sirve como referencia metodológica y enlace de consulta. Analiza sets offline en los que ambos jugadores usaron un solo personaje y declara los cruces de muestra insuficiente. Su unidad y filtros difieren de los nuestros. Antes de incorporar tablas ajenas, comprobar condiciones de reutilización. Para explicaciones de debilidades, aprovechar el borrador existente de 20 fichas como lista de revisión. Sus textos derivados de [SmashWiki](https://www.ssbwiki.com/SmashWiki:Copyrights) necesitan atribución y licencia compatible. Los ejemplos de counters del borrador corresponden a un corte anterior y requieren actualización o quedar identificados como históricos.

Las guías de contenido quedan pendientes de revisión editorial. La agregación del piloto consulta el corte vigente cuando se elige un luchador.
