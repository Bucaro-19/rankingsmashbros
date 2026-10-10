# Pendientes del dueño — para cuando esté frente a la computadora

Lista viva. Actualizada el 9 de octubre de 2026 (auditoría del organizador). Lo que ya se hizo se borra de aquí.

## 1. Claude Design (pegar estos prompts)

### 1.1 Piezas para invitar a la comunidad

> Piezas para invitar a la comunidad a probar Smash GT (rankingsmashbros.com), el ranking piloto de Super Smash Bros. Ultimate en Guatemala. Misma identidad del sitio y de la imagen para compartir ya aprobada: fondo #0B0F1A, celeste #49A6E9, amarillo #FFD23F, texto #F4F1EA, Big Shoulders Display 900 en mayúsculas, bloques inclinados. Sin logos ni arte oficial de Nintendo y sin retratos de personajes. Entrega tres piezas: (1) publicación cuadrada 1080 × 1080 para Facebook e Instagram; (2) historia vertical 1080 × 1920 para WhatsApp e Instagram, con lo importante lejos de los bordes superior e inferior; (3) un carrusel de 4 láminas 1080 × 1080. Mensaje principal: «¿En qué puesto estás?» con la bajada «Buscá tu tag en el ranking de Smash Ultimate de Guatemala». Carrusel: lámina 1, el gancho; lámina 2, «Tu puesto, también fuera del top 100»; lámina 3, «Tu historial y tu récord contra cada rival, gratis» con «Entrá con tu cuenta de start.gg»; lámina 4, llamado a la acción «rankingsmashbros.com» y «Decinos qué mejorar: es un piloto». Todas llevan visible la dirección rankingsmashbros.com y la línea «Proyecto independiente de la comunidad · Ranking piloto». No pongas fechas, puestos ni nombres de jugadores, para que no caduquen, y no menciones premium ni precios. Texto legible en miniatura. Entrega PNG de cada pieza y una vista previa de cómo se ve la historia en un teléfono.

### 1.2 Imagen para compartir con el nombre nuevo

La identidad «Ranking Smash Bros» ya se entregó y está en el sitio. Falta pedir a Claude Design la imagen para compartir de 1200 × 630 con el logo y el nombre nuevos (la actual dice «Smash GT»), y subir `rsb-perfil-1080.png` como foto de perfil de Instagram.

### 1.3 Adenda del top del organizador

El prompt está en [BRIEF-CLAUDE-DESIGN-TOP15-ADENDA.md](BRIEF-CLAUDE-DESIGN-TOP15-ADENDA.md): coorganizadores, selector 5/10/15, invitación recibida, revisiones del dueño y motivos nuevos de «no cuenta». Hoy funcionan con componentes prestados. La auditoría añade nombre del remitente de las revisiones y salida del equipo también gratis; pedir a Claude Design que cierre estos estados, sin pantalla nueva por ahora.

## 2. cPanel y cuentas externas

1. **Reemplazar o retirar la clave del panel de opiniones.** Ya no la necesitas: entras con tu cuenta desde «Opiniones ↗». Pero la clave vieja sigue funcionando y quedó expuesta en un chat. Decirle a Claude Code si se retira ese acceso o se cambia por una clave nueva.
2. **Suscribirse a premium con la propia cuenta** (pestaña Premium, plan de 3 USD): es la prueba pendiente de un pago real de punta a punta. Avisar a Claude Code para que confirme en la base que quedó activa.
3. **Enviar el correo a Ultimate Frame Data** (ultimateframedata@gmail.com) pidiendo permiso para mostrar datos de frames con crédito. El texto está en la conversación del 8/oct; si hace falta, Claude Code lo vuelve a dar.
4. **Decidir si «Tu opinión» aparece en Google** (hoy está fuera del sitemap).

## 3. En la app de Claude (la Mac)

1. Antes de las 2:00 a. m. del viernes 9/oct: dejar la Mac encendida, enchufada, con la tapa y la app abiertas, y dar **Run now** una vez a la tarea «Smash GT: medición de carga…» en «Scheduled» para aprobar los permisos (fuera de la ventana no mide nada).

### 1.4 Agenda: «Posible torneo rankeado»

Ya está programado con componentes existentes (recuadro con ◆, barra de inscritos en singles hacia 20 y «Se confirma cuando termine»; y «No cuenta para el ranking» con su motivo). Pedir a Claude Design que lo revise dentro de la tarjeta y del detalle de «Próximos torneos», a 375 px y escritorio.

### 1.5 Adelanto gratis de las funciones premium

Ya está programado en «Prepara el set» con componentes existentes: «Hallazgo principal · gratis» (un dato real del rival), dos tarjetas «También calculado» con conteos y texto que se desvanece, y un bloque bloqueado con la invitación a premium. Pedir a Claude Design que lo diseñe bien (referencia: la captura de «Diagnóstico de Operación» que mandó el dueño) y que cierre el patrón ya conectado en «Mis torneos»: torneo admitido más reciente (nombre/fecha/enlace), conteos de jugadores, sets y torneos; vacío honesto, fallo de lectura y premium vencido. Reutiliza `.p-box`/`.p-columns`; no tiene diseño nuevo propio. Regla fija: el adelanto es un dato real y las cifras de pago no se muestran ni difuminadas.

## 4. Revisiones que solo el dueño puede hacer

1. Ver «Prepara el set» con su sesión real, con un rival real y en pantalla grande.
2. Revisar el borrador de matchups ([guia/MATCHUPS-BORRADOR.md](guia/MATCHUPS-BORRADOR.md)) y decir si el formato sirve.
3. Lunes 12/oct: confirmar con Claude Code el primer corte automático y que aparece la pestaña «Mis torneos» y «Top por organizador» disponible en Premium. La migración 005 aplicada es confirmación del dueño, no verificación productiva de esta auditoría.
4. Revisar el [PR #86](https://github.com/Bucaro-19/rankingsmashbros/pull/86) de `feat/organizer-readiness` y ordenar la fusión/despliegue cuando corresponda. Auditoría solo inventada/desechable; no hubo cambios productivos ni migraciones. Resolver solicitudes con la cuenta admin en «Mis torneos → Revisiones por resolver»; ya no requiere edición manual de la base. Aprobar organización no hace contar pequeños.

## 5. Claude Design — directorio público de tops

**Pantalla provisional:** `tops.html` reutiliza tarjetas de torneos.css, encabezado, pie y tokens actuales por orden expresa del dueño. Funciona, pero no tiene handoff propio. Pedir el diseño final; no publicar un rediseño sin revisar sus estados y el contrato de [TOP-ORGANIZADOR.md](TOP-ORGANIZADOR.md).

Prompt listo para copiar:

> Diseña «Tops de organizadores» para Ranking Smash Bros, página pública gratis sin iniciar sesión, a 375 px y escritorio 1280 px. Reutiliza cabecera y pie actuales, tarjetas de Próximos torneos, cortes diagonales, fondo #0B0F1A, celeste #49A6E9, amarillo #FFD23F, Big Shoulders Display y Archivo. La pantalla provisional está en tops.html/tops.css/tops.js. Cada tarjeta muestra nombre del organizador, coorganizadores acreditados por nombre (puede haber hasta 10), tamaño Top 5/10/15, cantidad de torneos distintos que lo forman, fecha del corte y adelanto de hasta tres puestos con tag, más «Ver top completo» hacia /top/{slug}. No hay puntos/personajes/avatares ni datos de cuenta disponibles en este directorio. Puede haber menos de tres jugadores o ninguno: no inventarlos. Incluye nombres largos que se ajusten sin desborde y paginación «Ver más tops» en grupos de hasta 12. Aviso siempre visible: «Cada top usa solo los torneos de ese organizador y no es el ranking nacional. Solo cuentan torneos admitidos en el ranking, con 20 jugadores activos o más. Pagar no da puntos ni cambia puestos». Diseña listado, cargando, cargando más, error/reintento sin perder tarjetas previas, lista vacía y tarjeta con pocos jugadores. Vacío exacto: «Todavía no hay tops compartidos. Si organizas torneos, crea el tuyo desde tu cuenta», con enlace a cuenta.html#premium. Solo aparecen tops cuyo dueño activó el enlace público; no sugerir que todos comparten ni añadir búsqueda de cuentas, cambios de reglas, pagos en esta pantalla o datos ficticios productivos. Mantén el enlace «Tops» del menú y el del pie. Entrega referencia HTML/CSS y notas responsive/accesibilidad; no integrar support.js ni dataset de ejemplo. El servidor decide privacidad y el diseño no necesita conocer emails, IDs de cuenta, pagos o premium.
