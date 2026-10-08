# Prompt para Claude Design — top 15 por organizador (premium)

Diseña una función nueva para **Smash GT**, la web del ranking de Super Smash Bros. Ultimate de Guatemala en https://rankingsmashbros.com/: el **top 15 de un organizador**. Un organizador de torneos ve y comparte el ranking de los 15 mejores jugadores **de sus propios torneos** del año. Es la segunda función premium, después del análisis de rival.

Usa la web actual y los handoffs anteriores (inicio, cuentas v2, panel, premium, análisis de rival) como referencia: Big Shoulders Display para títulos y cifras, Archivo para texto, fondo #0B0F1A, paneles #121829, celeste #49A6E9, amarillo #FFD23F, verde #5BE38A, rojo #FF4D2E, radio 0, cortes diagonales, botones inclinados −10° y retratos de personajes. Diseña móvil de 375–390 px y escritorio de 1440 px. Se implementará en HTML/CSS/JS y PHP; entrega HTML/CSS o una referencia inspeccionable, con notas de interacción. Los datos del prototipo son ejemplos.

## Quién la usa y dónde vive

- La usa una cuenta con el interés «Organizador» marcado y con premium activo. Vive como una cuarta pestaña de la cuenta, «Mis torneos», junto a Mi perfil, Mis personajes y Premium.
- Hay además una **vista pública para compartir**: una página con el top 15 de ese organizador que cualquiera puede abrir con un enlace, sin cuenta. Es la pieza que el organizador publica en sus redes; debe verse bien en una captura de pantalla del teléfono.

## Qué datos existirán

Solo estos; no diseñes métricas fuera de la lista.

1. **Mis torneos del año:** lista de torneos de Smash Ultimate que start.gg registra a nombre de esa cuenta, con nombre, fecha, lugar si existe, jugadores activos, sets válidos y enlace a start.gg. Cada torneo tiene un estado:
   - «Cuenta»: entra al top.
   - «No cuenta», con motivo: dobles u otro formato, sin sets válidos, o fuera de la temporada.
   - «Por confirmar»: el sistema no pudo comprobar que el torneo es de esa cuenta (por ejemplo, es coorganizador y no el dueño en start.gg). Puede pedir revisión.
2. **El top 15:** puesto, alias, personaje más usado, puntos, sets ganados y perdidos y torneos jugados, **contando solo los torneos de ese organizador**. Debajo del top, el resto de la lista completa plegada.
3. **Resumen:** cuántos torneos cuentan, cuántos jugadores distintos participaron, cuántos sets, periodo cubierto y fecha del corte.
4. **Detalle de un jugador:** sus torneos con ese organizador, su récord y contra quién jugó.

No hay asistencia por torneo en vivo, premios, pagos de inscripción ni datos de contacto de jugadores.

## Reglas que el diseño debe dejar claras

- Es un ranking **distinto** del nacional: usa solo los torneos de ese organizador. Un jugador puede ser #3 aquí y #40 en el nacional. Debe verse siempre el nombre del organizador, el periodo y el número de torneos; nunca debe confundirse con el ranking de Smash GT.
- **Pocos torneos, poca certeza.** Con uno o dos torneos el top dice poco. Diseña ese caso primero: un aviso de «muestra pequeña» visible y el top igual mostrado, sin dramatizar. Con cero torneos que cuenten, no hay top: se explica por qué.
- Mínimo para aparecer en el top: haber jugado sets válidos en torneos de ese organizador. Si el servidor exige un mínimo de torneos o sets, se mostrará como texto; reserva el espacio.
- Marcar «Organizador» en la cuenta es solo un interés: lo que decide qué torneos son suyos es start.gg, no lo que la persona declare.
- Pagar no da puntos ni cambia puestos, ni en este top ni en el nacional.

## Estados

- Sin sesión; sin el interés de organizador (invita a marcarlo en su perfil); sin premium (bloqueado, con la invitación sobria a premium y sin cifras falsas); premium vencido.
- Sin torneos encontrados a su nombre (explica qué se busca y cómo pedir revisión).
- Con torneos pero ninguno cuenta.
- Muestra pequeña (1–2 torneos) y caso normal.
- Torneos «por confirmar» con la acción de pedir revisión y su resultado (enviada, aprobada, rechazada con motivo).
- Carga, error, y datos desactualizados («actualizado con el corte del DD/MM/AAAA»).
- Vista pública: normal, enlace desactivado por el organizador, y organizador sin premium vigente.

## Qué debe poder hacer

- Ver su lista de torneos y entender por qué cada uno cuenta o no.
- Ver el top 15 y abrir el detalle de un jugador.
- Activar o desactivar el enlace público y copiarlo.
- Pedir revisión de un torneo que no aparece o que quedó «por confirmar».
- En la vista pública: ver el top, el resumen y los torneos usados, con un enlace discreto a Smash GT.

## Criterios de entrega

- Contraste alto, foco visible (contorno amarillo de 3 px), áreas táctiles de 44 px o más, movimiento reducido respetado. Los estados se indican con glifo y texto, nunca solo con color.
- La vista pública debe caber bien en una captura vertical de teléfono: organizador, periodo y top 15 legibles sin desplazarse demasiado.
- Entrega lista de componentes, estados, textos exactos de los avisos (muestra pequeña, por confirmar, no cuenta) y qué se oculta cuando falta un dato.
