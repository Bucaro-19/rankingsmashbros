# Brief para Claude Design — «Próximos torneos»

Nueva pantalla pública y gratuita de Smash GT: la agenda de torneos de Super Smash Bros. Ultimate en Guatemala que todavía no se juegan. Misma línea gráfica del sitio (tokens, encabezado y pie de `paginas.css`), móvil primero a 375 px y escritorio a 1440 px.

## Para qué sirve

Que un jugador vea en diez segundos qué torneo hay cerca, cuándo es, cuánto falta y dónde inscribirse. La inscripción ocurre en start.gg; Smash GT solo enlaza.

## Datos que habrá por torneo

Nombre; fecha y hora de inicio (hora de Guatemala); ciudad y departamento; lugar y dirección cuando start.gg los tenga; si la inscripción está abierta y cuándo cierra; inscritos hasta ahora; si es presencial u online; enlace a start.gg; eventos del torneo (singles, dobles). Pueden faltar el lugar, el cierre de inscripción y los inscritos.

**No habrá** precio, premios ni quién está inscrito: no se inventan ni se prometen.

## Qué diseñar

1. **Lista de torneos** ordenada por fecha, agrupada por «Esta semana», «Este mes» y «Más adelante». Cada tarjeta: fecha grande (día y mes), cuenta regresiva en texto («en 3 días», «mañana», «hoy»), nombre, ciudad, estado de inscripción con glifo y texto (abierta / cierra en N días / cerrada / no informada), inscritos, y el botón «Inscribirme en start.gg ↗».
2. **Filtro por zona:** departamento o ciudad (lista corta que sale de los torneos existentes) y la opción «Cerca de mí», que pide permiso de ubicación al navegador. Texto fijo junto al botón: «Tu ubicación se usa solo en tu teléfono para ordenar la lista; no se envía ni se guarda.» Estados: permiso negado, ubicación no disponible, y torneo sin coordenadas («sin distancia»).
3. **Filtro por tipo:** presencial / online, y «solo los que cuentan para el ranking» (presencial, singles), explicando en una línea que el torneo debe llegar a 20 jugadores activos para entrar al ranking y que eso se sabe hasta que termina.
4. **Detalle del torneo** (desplegable en la misma tarjeta o ficha aparte, propón): eventos, dirección con enlace a mapas, cierre de inscripción y la aclaración «Datos de start.gg, actualizados el DD/MM/AAAA HH:MM».
5. **Estados:** cargando; sin torneos próximos («No hay torneos anunciados todavía»); sin torneos en la zona elegida (con atajo a ver todo el país); datos desactualizados (más de 48 horas sin actualizar); error.
6. **Entrada desde la portada:** un bloque corto «Próximo torneo» con el más cercano en fecha y enlace a la agenda, y el enlace «Torneos» en la navegación.

## Reglas

- Estados siempre con glifo y texto, nunca solo color. Áreas táctiles de 44 px o más. Foco visible.
- Fechas en formato de Guatemala (DD/MM/AAAA, hora de 12 h con a. m./p. m.).
- Nada de mapas incrustados ni servicios de terceros: solo un enlace a mapas.
- Pie fijo: «Agenda tomada de start.gg. Smash GT no organiza estos torneos ni cobra inscripciones.»

## Entrega

README con medidas, textos exactos y estados, y los `.dc.html` con datos inventados, como en los paquetes anteriores.
