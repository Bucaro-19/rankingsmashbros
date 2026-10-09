# Brief para Claude Design — adenda del top del organizador

Continuación del paquete `design_handoff_smash_gt_top_organizador`. La pestaña «Mis torneos» y la página pública ya están programadas con ese diseño. El dueño pidió después cuatro cosas que el paquete no cubre; hoy funcionan con componentes prestados y necesitan diseño propio. Misma línea gráfica, tokens y reglas de accesibilidad del paquete.

## 1. Tamaño del top: 5, 10 o 15

El organizador elige el tamaño. El título pasa a «Top 5 / Top 10 / Top 15» en la pestaña y en la página pública.

- Control de tres opciones junto al título «Top N» (solo lo ve el organizador; un coorganizador no).
- Si hay menos jugadores que el tamaño elegido: «Hay N jugadores con sets suficientes: el top muestra los que hay.»
- La página pública debe verse bien con 5 filas (queda mucho aire en 390 × 844) y con 15.

## 2. Coorganizadores

start.gg solo dice quién creó el torneo. El organizador puede sumar hasta 10 coorganizadores con una invitación de un solo uso.

- Caja «Coorganizadores» en la columna lateral: lista (nombre, «desde el DD/MM/AAAA», «Quitar»), estado vacío, botón «Crear invitación».
- Invitación creada: dirección para copiar, «Copiar invitación», y el texto «Envíasela a una sola persona: sirve una vez y vence en 7 días. Crear otra anula esta.»
- Confirmación al quitar a alguien.
- Texto fijo: «Aparecen como coorganizadores en tu top y en tu página pública. Para verlo desde su cuenta cada uno usa su propio premium. No reciben permisos en start.gg ni pueden cambiar tu enlace.»
- Crédito visible: línea «Coorganizan: {nombres}» bajo el título, en la pestaña y en la página pública (cabe en la captura de 390 × 844 con hasta 10 nombres).

## 3. Quien recibe la invitación

Abre `cuenta.html?invita=…#torneos`.

- Sin sesión: «{Organizador} te invitó como coorganizador» + entrar con start.gg.
- Con sesión: aviso con «Unirme al equipo» y «Ahora no».
- Invitación usada o vencida; invitación propia; ya es miembro.
- Vista del coorganizador: igual que la del organizador pero **sin** interruptor del enlace, selector de tamaño ni caja de coorganizadores. Lleva «Eres coorganizador de {Organizador}» y «Salir del equipo».
- Cada cuenta paga su premium. Coorganizador sin premium: pantalla de premium con «Eres coorganizador de {Organizador}. Tu nombre aparece en su top aunque no tengas premium.» + «Salir del equipo», también sin premium.
- Si la cuenta tiene sus propios torneos **y** es coorganizadora de otros: selector para cambiar de organizador (hoy son botones «Mis torneos / {Organizador}»).

## 4. Revisiones para el dueño del sitio

Solo la cuenta del dueño. Lista de «Pedir revisión» en espera: organizador y nombre de quien la envió, torneo con enlace a start.gg, fecha, si el torneo está o no en el catálogo. Acciones «Aprobar» (con confirmación) y «Rechazar» (motivo obligatorio, máximo 255 caracteres). Estado vacío. Puede vivir en el panel privado o en esta pestaña; propón dónde.

## 5. Motivos nuevos de «no cuenta»

Además de los del paquete: «Menos de 20 activos», «Sin terminar» y «Fuera del ranking» (revisión manual). Mismo chip gris punteado; revisar que los textos largos no rompan la fila en 375 px.

## 6. Adelanto gratis en «Mis torneos» (9/oct)

Ya conectado con componentes existentes, pendiente de diseño definitivo. Un dato principal real: **el torneo más reciente admitido en el corte** (nombre, fecha y enlace). Dos tarjetas «También calculado»: jugadores con sets suficientes y sets válidos; debajo, torneos que cuentan frente a encontrados. Estado sin torneos: hallazgo ausente y ceros reales. Estado de fallo: no se pudo calcular el adelanto. Premium vencido conserva solo este adelanto y el aviso de pausa. Nada de tablas difuminadas: el servidor no envía puestos, puntos, jugadores, récords ni resultados de pago. Ver contrato en TOP-ORGANIZADOR.md.

Mantener «Salir del equipo» para coorganizadores incluso gratis/vencidos. Confirmar que las tarjetas y el nombre largo caben en 375 px. Aprobar una revisión acredita organización; **no** admite por sí mismo el torneo al ranking ni al top. El mínimo de 20 activos no cambia.

## Entrega

Mismo formato del paquete anterior: README con medidas, textos exactos y estados; archivos `.dc.html`. Datos de ejemplo inventados.
