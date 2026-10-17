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
3. **Ultimate Frame Data:** el dueño informa (13/oct) que ya pidió permiso por correo, sin respuesta. Avisar si contestan o solicitan retirar; retirada inmediata del servicio con SMASH_FRAME_FACTS_ENABLED=false y despliegue autorizado. No presentar el silencio como permiso obtenido. Ver FRAMES-ANALISIS.md.
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

## 5. Diseño del directorio de tops

Handoff final recibido en `design_handoff_rsb_tops/`. Implementación en PR propio, ver EN-CURSO.md. Ya no hace falta solicitar este diseño. Se conserva el contrato público: el diseño pide mains, total de tops y una vista ampliada completa que este endpoint no entrega; se omiten, sin añadir datos ni adivinar cifras.

## Legends 7 (14/oct): aprobación y esquema resueltos

El dueño confirma #102 fusionado/desplegado, inserciones de entidades autorizadas (constante true) y 007 aplicada. Ya no hay una autorización o migración pendiente para este alcance. La corrección #103 ya está fusionada/desplegada, SMASH_RIVAL_SYNC_ENABLED=true y el run 38606150069 terminó verde con registrations_unavailable y una consulta. No hace falta volver a activar ni repetir la prueba; evidencia en el primer bloque de [EN-CURSO.md](EN-CURSO.md). Sigue vigente el vencimiento al finalizar el 25/oct GT. No extenderlo ni incorporar otro evento sin nueva orden.

## Mi torneo: diseño provisional autorizado (17/oct)

Sección gratuita en Tu cuenta construida por orden expresa con componentes existentes. No es la pestaña premium «Mis torneos» de organizadores. Contrato/estados: MI-TORNEO.md. Falta referencia final de Claude Design, sin bloquear el funcionamiento autorizado.

**Prompt para Claude Design:** Diseña «Mi torneo» dentro del perfil actual, escritorio y 375 px, conservando encabezado/pie, colores, tipografías y tarjetas. Aviso superior de torneo próximo en 7 días; fecha/hora real de captura y «los horarios los define el organizador»; fase/grupo, horario del pool y primer set en Guatemala y zona local; rival confirmado o probable etiquetado; camino posible si gana (no confirmado); mejor rival con puesto combinado conocido o menor seed si nadie tiene puesto, explicando el criterio; botones existentes Análisis de rival/Prepara el set y lista propia con tag/seed/puesto nullable. Estados: cargando, error con reintento, sin captura, lista de inscritos oculta (inscripción desconocida), no inscrito, pools no publicados, horarios null «Horario aún no publicado», bye verificado, camino desconocido y varias fases/grupos. Todo el pool gratis; funciones de análisis mantienen premium. Respeta MI-TORNEO.md, sin puntos, porcentajes, imágenes o campos inventados ni pools de otras cuentas. Entrega README de contrato/estados y referencia visual; no portar support.js ni ejemplos a producción.
