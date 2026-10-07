# Prompt para Claude Design — ingreso y perfil Smash GT

Diseña la siguiente fase de **Smash GT**, una web de ranking de Super Smash Bros. Ultimate de Guatemala en https://rankingsmashbros.com/. Usa la web actual y el handoff original como referencia; conserva Big Shoulders Display para títulos, Archivo para texto, fondo #0B0F1A, acento celeste #49A6E9, cortes diagonales, barras de puntos y estética de arena competitiva. Da espacio al contenido y prioriza lectura cómoda en celular.

Entrega tres vistas conectadas: **ingreso con start.gg**, **mi perfil** y **edición de mis personajes**. Diseña móvil de 375–390 px y escritorio de 1440 px, con componentes, estados y navegación claros. Será implementado en HTML/CSS/JS y PHP; entrega HTML/CSS o una referencia inspeccionable, assets y notas de interacción. Los datos del prototipo son ejemplos, nunca un cálculo nuevo.

## Ingreso y primera vinculación

- Un CTA «Continuar con start.gg». No pedir contraseña de start.gg ni token API.
- Explicar brevemente que vinculamos su identidad para mostrar su perfil. La autorización ocurre en start.gg y regresa a nuestra web.
- Diseñar estados de carga, autorización cancelada, error y cuenta vinculada; primera vinculación con jugador encontrado, sin jugador vinculado y jugador sin actividad/rank suficiente. No identificar jugadores solo por su alias ni permitir reclamar un perfil ajeno con un enlace.
- Permitir indicar jugador, organizador o ambos como intereses del perfil. Explicar que organizar se verifica por torneo; elegirlo no habilita reportes ni administración.

## Mi perfil

- Alias, foto si existe, mains, enlace público de start.gg y temporada 2026/fecha del corte.
- Puesto nacional y puntos, cambio de puesto cuando hay corte previo, victorias/derrotas y actividad. Los participantes fuera del top 100 también pueden consultar gratis su puesto básico cuando están clasificados. Mostrar estados sin puesto/actividad insuficiente, con requisitos comprensibles.
- Selector «Solo Guatemala» / «+ Internacional». Son dos rankings distintos; al cambiarlo actualizan puesto, puntos, récord, mains e historial usado en ese corte. Etiqueta visible del alcance. Si no hay corte anterior, mostrar «Sin comparación previa».
- Torneos e historial con fecha, lugar/país cuando existe, sets, resultado y enlace a start.gg; diferenciar actividad general y torneos que cuentan en el ranking. Acceso al detalle de un rival reutilizando el estilo del panel existente.
- Diseñar vacíos, carga y errores sin inventar datos. No confundir país de perfil con nacionalidad comprobada ni usar cero como puesto.

## Edición de mains

- Diferenciar «Personajes detectados en torneos» de «Mis personajes elegidos»: un principal y hasta dos secundarios, búsqueda por nombre e íconos; confirmar guardado, cambios pendientes y error.
- Los mains elegidos sirven para personalizar el perfil; no cambian puntos, resultados ni lo reportado por start.gg.
- Organizador, agenda, torneo en vivo, reportes y notificaciones pertenecen a fases posteriores: no presentar acciones operativas que todavía no están implementadas. En esta entrega mantener el foco en ingreso/perfil/mains, sin paywall.

## Criterios de entrega

- Buen contraste, foco visible, etiquetas accesibles y controles cómodos al tacto; no depender solo de color/flechas para cambios de puesto. Animaciones breves, opción de movimiento reducido.
- Reutilizar identidad, assets y panel actuales. Evitar tablas apretadas o bloques largos sin aire.
- Incluir lista de componentes, estados, comportamiento del selector, datos requeridos y qué debe ocultarse si falta información. Diseño listo para que Claude Code lo implemente cuando backend/OAuth estén disponibles.

