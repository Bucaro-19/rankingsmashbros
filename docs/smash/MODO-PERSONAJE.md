# Prepara el set por personaje

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

El selector y las guías quedan para una segunda entrega con el diseño y la revisión de contenido. La primera mejora modifica solo la ficha técnica y la etiqueta de la muestra que ya existen.
