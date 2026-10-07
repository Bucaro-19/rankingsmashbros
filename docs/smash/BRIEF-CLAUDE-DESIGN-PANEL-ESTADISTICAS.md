# Prompt para Claude Design — panel de estadísticas del dueño

Diseña una pantalla nueva para **Smash GT**, la web del ranking de Super Smash Bros. Ultimate de Guatemala en https://rankingsmashbros.com/. Es un **panel privado para una sola persona, el dueño del sitio**, donde ve cuánta gente entra y cuánta se registra. No es una pantalla pública ni un producto para organizadores.

Usa la web actual y los handoffs anteriores como referencia: Big Shoulders Display para títulos y cifras, Archivo para texto, fondo #0B0F1A, acento celeste #49A6E9, cortes diagonales y la estética de arena. Aquí manda la lectura rápida de números: aire, jerarquía clara y nada de decoración que compita con los datos. Diseña móvil de 375–390 px (el dueño lo abrirá sobre todo desde el teléfono) y escritorio de 1440 px. Se implementará en HTML/CSS/JS y PHP; entrega HTML/CSS o una referencia inspeccionable, y notas de interacción. Los números del prototipo son ejemplos.

## Qué datos existirán

Solo estos; no diseñes métricas que no estén en la lista.

- **Vistas de página por día** y por página: inicio/ranking, metodología, cuenta, encuesta y análisis.
- **Visitantes distintos por día** y en un periodo (7, 30 y 90 días, y temporada). Se cuentan por navegador: una persona con teléfono y computadora cuenta como dos. Debe poder decirse en una nota breve.
- De esos visitantes, **cuántos tenían sesión iniciada**.
- **Cuentas registradas**: total, nuevas por día y cuántas siguen vinculadas.
- **Cuántos entraron hoy/ayer** y comparación con el periodo anterior equivalente.
- Fecha y hora de la última actualización de los datos (hora de Guatemala).

No hay país, ciudad, dispositivo, navegador, fuente de tráfico ni tiempo en página: no se recogen. No hay datos por persona; no diseñes listas de visitantes.

## Qué debe poder hacer

- Ver de un vistazo: visitantes de hoy, de los últimos 7 y 30 días, y cuentas registradas.
- Cambiar el periodo (7 / 30 / 90 días / temporada 2026).
- Ver la evolución diaria de visitantes y vistas en una gráfica simple, legible en móvil, con los valores accesibles también como texto o tabla.
- Ver qué páginas se visitan más en el periodo.
- Ver registros nuevos en el periodo junto a los visitantes, para leer la proporción.
- Volver al sitio y cerrar sesión.

## Estados

- Carga, error al consultar y «sin datos todavía» (el contador empieza el día que se publica; los primeros días casi todo estará vacío y no debe verse roto).
- Día en curso marcado como parcial.
- Acceso denegado: una cuenta que no es la del dueño ve un mensaje sobrio, sin datos ni pistas de lo que hay dentro.
- Sesión vencida: invitar a entrar de nuevo.

## Criterios de entrega

- Contraste alto, foco visible, cifras con etiquetas de texto; no depender solo del color para subir/bajar. Movimiento reducido respetado.
- Sin tablas apretadas en móvil: tarjetas o filas apiladas.
- Entregar lista de componentes, estados, comportamiento del selector de periodo y qué se oculta cuando un dato falta. No incluir exportaciones, alertas, metas ni comparativas entre países: son fases futuras.
