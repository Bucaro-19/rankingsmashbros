# Prompt para Claude Design — análisis del rival (premium)

Diseña una pantalla nueva para **Smash GT**, la web del ranking de Super Smash Bros. Ultimate de Guatemala en https://rankingsmashbros.com/. Es la primera función **premium**: un jugador con cuenta elige a un rival (por ejemplo, el que le toca en un torneo) y recibe un análisis para preparar el set: qué tan parejo está, con qué personaje le conviene jugar y cómo le ha ido a ese rival.

Usa la web actual y los handoffs anteriores (ranking, cuentas v2, panel) como referencia: Big Shoulders Display para títulos y cifras, Archivo para texto, fondo #0B0F1A, acento celeste #49A6E9, amarillo #FFD23F, cortes diagonales, retratos de personajes y estética de arena. Diseña móvil de 375–390 px (se usará de pie, en el torneo, con prisa) y escritorio de 1440 px. Se implementará en HTML/CSS/JS y PHP; entrega HTML/CSS o una referencia inspeccionable, y notas de interacción. Los datos del prototipo son ejemplos.

## Cómo se llega

- Desde el perfil propio: botón «Analizar rival» en el panel de rival que ya existe (el que muestra puesto, puntos y sets entre ambos).
- Desde un buscador de jugadores dentro de la pantalla: por alias, entre los jugadores del corte.
- Diseña también la versión bloqueada para quien no es premium: ve el nombre del rival y lo que es gratis (puesto, puntos, récord entre ambos) y una invitación sobria a hacerse premium, sin cifras falsas ni datos difuminados que parezcan reales.

## Qué datos existirán

Solo estos; no diseñes métricas que no estén en la lista.

1. **Los dos jugadores:** alias, foto si existe, puesto y puntos en la vista activa (Solo Guatemala / + Internacional), personajes elegidos por mí y personajes detectados de ambos con porcentaje de uso.
2. **Probabilidad estimada de ganar el set**, en porcentaje, calculada con los puntos del ranking de ambos. Es una estimación del modelo, no una promesa: debe verse como tal, con una frase que lo diga y sin lenguaje de apuesta.
3. **Historial entre ambos:** récord de sets, lista de sets con torneo, fecha y marcador, y racha reciente.
4. **Forma reciente del rival:** sus últimos torneos con resultado de sets, y contra qué nivel de rivales gana y pierde (por tramos de puesto: top 10, 11–50, 51–100, sin puesto).
5. **Matchup de personajes**, que es el centro de la pantalla:
   - «Con qué juega él»: sus personajes y cuánto usa cada uno.
   - «Cómo me va contra quienes usan ese personaje»: mi récord de sets contra jugadores cuyo personaje más usado es ese.
   - «Cómo le va a él contra mis personajes»: su récord contra jugadores cuyo personaje más usado es cada uno de mis elegidos.
   - Recomendación: cuál de mis personajes conviene y cuál no, **solo cuando hay suficientes sets**. Cada recomendación muestra su muestra («basado en 7 sets») y un nivel de confianza en palabras: alta, media, baja.
6. **Más adelante (diseñar el espacio, marcado como «próximamente»):** récord personaje contra personaje por game, cuando el sitio empiece a guardar las selecciones de cada game. Hoy no existe.

No hay datos de escenarios, combos, frame data ni estilo de juego. No hay nada «en vivo» del torneo en curso todavía.

## Reglas que el diseño debe respetar

- **Muestra pequeña es el caso normal.** Muchos cruces tendrán 0, 1 o 2 sets. Diseña primero ese estado: «Sin datos suficientes» con lo poco que haya, nunca un porcentaje con apariencia de certeza. Nada de 100% por un solo set.
- Un personaje detectado es el que start.gg registró; muchos sets no registran personaje. Mostrar la cobertura («personaje registrado en 31 de 45 sets»).
- Un rival sin puesto no es un rival débil: puede ser extranjero o tener poca actividad en el corte.
- No depender solo del color para decir conviene / no conviene: texto e ícono.
- Tono: consejo de un compañero, no veredicto. Evitar «vas a perder».

## Estados

- Carga, error, rival sin datos en el corte, yo sin jugador vinculado, yo sin personajes elegidos (invitar a elegirlos), rival sin personajes detectados, y sin sets entre ambos.
- Bloqueado (no premium) y premium vencido.
- Cambio de vista Solo Guatemala / + Internacional.

## Criterios de entrega

- Contraste alto, foco visible, áreas táctiles de 44 px o más, movimiento reducido respetado.
- En móvil, lo primero que se ve sin desplazarse: los dos jugadores, la probabilidad estimada y la recomendación de personaje con su confianza.
- Entregar lista de componentes, estados, qué se oculta cuando falta un dato y los textos exactos de los avisos de muestra pequeña.
