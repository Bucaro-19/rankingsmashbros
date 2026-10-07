# Prompt para Claude Design — rediseño de «Método» y «Tu opinión»

Rediseña dos páginas que ya existen en **Smash GT** (https://rankingsmashbros.com/), la web del ranking de Super Smash Bros. Ultimate de Guatemala, para que tengan la misma línea gráfica que el inicio, las cuentas y el panel. Hoy usan un estilo anterior y se sienten de otro sitio. **No cambies el contenido ni las reglas: es un rediseño visual y de lectura.**

Referencia obligatoria: el inicio actual (https://rankingsmashbros.com/) y los handoffs de cuentas v2 y del panel. Big Shoulders Display para títulos y cifras, Archivo para texto, fondo #0B0F1A, paneles #121829, acento celeste #49A6E9, amarillo #FFD23F, verde #5BE38A, rojo #FF4D2E, radio 0, cortes diagonales y botones inclinados −10°. Mismo encabezado y pie que el inicio, con el mismo comportamiento de «Tu cuenta». Diseña móvil de 375–390 px y escritorio de 1440 px. Se implementará en HTML/CSS/JS y PHP; entrega HTML/CSS o una referencia inspeccionable, con notas de interacción.

## Página 1: Método (https://rankingsmashbros.com/metodologia.html)

Es una página larga de lectura. Explica a la comunidad cómo se arma el ranking. Conserva todas sus secciones y textos, en este orden:

1. «Así se arma» (introducción).
2. «Qué cuenta»: qué torneos y qué sets entran.
3. «Cómo se ordena», en tres pasos: miramos a quién venciste, ajustamos cuánto informa cada set, calculamos una fuerza conjunta.
4. «Qué dice cada resultado»: cuadro de cuatro casos (ganar o perder contra alguien más fuerte o más débil), de dónde sale la fuerza del rival y qué pasa con la constancia.
5. «Smash GT y TrueSkill»: tabla comparativa de cinco filas, una explicación «con peras y manzanas» y lo observado en otra liga.
6. «Qué tomamos de UltRank»: dos columnas, «Sí usamos» y «No replicamos».
7. «Torneos del corte»: lista larga cargada con datos reales (unos 40 torneos) con nombre, fecha, país, jugadores activos y si cuenta en cada vista. Tiene el selector Solo Guatemala / + Internacional.
8. «Lo que falta decidir».

Qué necesito del diseño:
- Que se lea cómodo en el teléfono: bloques cortos, aire, jerarquía clara, nada de tablas que obliguen a desplazarse de lado. La tabla comparativa debe convertirse en filas apiladas en móvil.
- Un índice de secciones: fijo o desplegable en móvil, lateral en escritorio.
- Los pasos numerados y el cuadro de cuatro casos como piezas visuales fuertes, con el lenguaje del inicio.
- La lista de torneos con estados de carga, error y vacío, y una forma cómoda de recorrer 40 filas en móvil.
- Avisos de «piloto» y «esto puede cambiar» sobrios, sin alarmar.

## Página 2: Tu opinión (https://rankingsmashbros.com/encuesta.php)

Es un cuestionario anónimo de seis preguntas más dos campos opcionales. Conserva las preguntas, sus opciones y sus textos de ayuda:

1. Desde dónde participas en la escena (opción única).
2. Quién debería poder aparecer en el ranking nacional (opción única).
3. Cuánto debe jugar una persona para aparecer en el top (opción única), con tres ayudas breves: qué torneo cuenta, qué set cuenta y una explicación «con peras y manzanas».
4. Cómo tratar los torneos en el extranjero (opción única).
5. Qué tan clara es la explicación (escala del 1 al 5).
6. Qué tanta confianza te da el piloto actual (escala del 1 al 5).
- Enlace de start.gg que debamos revisar (opcional).
- Comentario libre (opcional, hasta 2,000 caracteres).
- Nota de privacidad: no pedimos nombre, correo ni cuenta, y no guardamos la IP en las respuestas.

Qué necesito del diseño:
- Opciones como tarjetas grandes y cómodas al tacto (72 px o más), con el mismo estilo de las casillas de «¿Qué te interesa?» de cuentas v2. Son radios reales: una sola opción por pregunta.
- Escalas del 1 al 5 con los extremos rotulados, fáciles de tocar.
- Las ayudas de la pregunta 3 plegables, para que no tapen la pregunta.
- Indicador de avance (pregunta 3 de 6) sin partir el formulario en pasos obligatorios: debe poder enviarse de una vez.
- Estados: error de validación por pregunta (con texto, no solo color), enviando, «¡Respuesta recibida!», error al guardar con las respuestas conservadas, y «ya respondiste desde este navegador».
- La nota de privacidad visible antes del botón de enviar.
- Funciona sin JavaScript: es un formulario HTML que se envía al servidor. Las mejoras con JavaScript son opcionales.

## Para ambas

- Contraste alto, foco visible (contorno amarillo de 3 px), áreas táctiles de 44 px o más, movimiento reducido respetado.
- No inventes secciones, cifras ni reglas nuevas. Si un texto te parece largo, propón cómo presentarlo, no lo recortes.
- Entrega lista de componentes, estados y qué reutilizas del inicio, cuentas v2 y panel.
