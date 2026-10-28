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

## Mi torneo: handoff final recibido (18/oct)

Referencia `design_handoff_rsb_mi_torneo/README.md`, `MiTorneo.dc.html` y lienzo de estados. Implementación en rama `feat/my-tournament-design`; seguimiento en EN-CURSO.md. La pantalla ya no necesita un diseño provisional ni otro prompt.

El contrato real difiere de la tabla orientativa del handoff: no hay ciudad, reglas de avance, fases futuras no asignadas ni marcadores en la captura. Se omiten. Los personajes detectados cuentan **games**, no sets: no se porta el texto ficticio «N de M sets». Tampoco se porta support.js ni los ejemplos. El bracket visual sale únicamente del grafo ya capturado del pool propio; los personajes del versus son históricos o elegidos en perfiles, nunca una selección confirmada para el set futuro. PR #110 fusionado y publicado por orden del dueño el 18/oct, despliegue assets-only 39141959105 correcto y hash público preservado. No hay migración, carga SQL ni aprobación de diseño pendientes para esta entrega.

## Desde Instagram — publicado y activo (27/oct)

**Ya conectado, publicado y activado por orden del dueño.** Primera captura real correcta, cron único cada dos horas y monitor de Actions verde. Se conservan solo las últimas 12 publicaciones. Los pasos siguientes quedan como referencia para reautorización o recuperación: no repetir el instalador ni crear otro cron por rutina. La captura corre en BanaHosting y no necesita la Mac ni otro servicio de pago. Detalles técnicos y retirada: [INSTAGRAM.md](INSTAGRAM.md).

1. En Instagram, entra a la cuenta de Ranking Smash Bros. Configuración → tipo de cuenta/herramientas → cambiar a cuenta profesional; Business o Creator sirven. Los nombres exactos de los menús pueden variar. No necesitas convertir tu cuenta personal si la del proyecto es otra.
2. En [Meta for Developers](https://developers.facebook.com/apps/), crea una app y añade la configuración de **Instagram API with Instagram Login**. Usa la ruta con Instagram Login, no la API antigua Basic Display ni el flujo de Facebook Login. Si Meta pide completar verificaciones o revisión, hazlo en su panel; este PR no obtiene esas aprobaciones.
3. Dentro de esa configuración, añade la cuenta profesional propia como cuenta autorizada/de prueba, acepta la invitación con esa cuenta si aparece y usa el botón de generar token/autorizar. Para esta galería basta **instagram_business_basic** (lectura propia). No concedas permisos para mensajes, comentarios o publicación si solo configuras esta función.
4. Obtén el **Instagram user_id de esa cuenta** y una llave **de larga duración, 60 días**. No uses el ID de la app ni el de una página de Facebook. Confirma en Meta la duración: si el generador solo entrega una llave corta, hay que intercambiarla por una larga siguiendo Business Login antes de continuar; no la pongas como si durara 60 días. Esa operación usa el secreto de la app solo en un servidor privado; pide ayuda si el panel no ofrece la llave larga, sin pegar ninguna llave en el chat.
5. En cPanel → administrador de archivos → /home/TU_USUARIO/private-smash (fuera de rankingsmashbros.com y public_html), crea **instagram.local.php**, usando la plantilla docs/smash/instagram-config.example.php como referencia. No edites la plantilla del repositorio con la llave verdadera. Pon enabled=true, account_id=user_id, access_token=llave larga nueva e issued_at=su fecha real de emisión UTC. Justo después de generarla, el comando `php -r 'echo gmdate("Y-m-d\TH:i:s\Z"),PHP_EOL;'` ayuda a obtener la hora actual; no sirve para rejuvenecer una llave antigua. Permisos del archivo **600**; el directorio debe permitir escribir al PHP del cron. El proceso creará ahí su estado renovado privado; no lo publiques ni lo copies a Git.
6. Usa el mismo ejecutable PHP CLI que ya utiliza el cron ranking-worker.php del sitio. Debe tener curl, GD y mbstring. En Terminal cPanel puedes comprobarlo con `RUTA_PHP -r 'echo PHP_VERSION, " curl=", (int)extension_loaded("curl"), " gd=", (int)extension_loaded("gd"), " mbstring=", (int)extension_loaded("mbstring"), PHP_EOL;'` (sustituye RUTA_PHP por el ejecutable real). Los tres indicadores deben ser 1. No hace falta entrar a la base.
7. Tras el despliegue autorizado, ejecuta una vez `RUTA_PHP /home/TU_USUARIO/rankingsmashbros.com/instagram-sync.php` (ajusta la raíz real del dominio). No pases la llave como argumento. Si dice ready, abre /instagram.html y revisa tus publicaciones y /data/instagram-status.json. Si falla, comparte solo el código seguro que imprime, nunca el archivo privado ni respuestas crudas de Meta. Si falta la configuración, no debe mostrar contenido de ejemplo.
8. cPanel → Cron Jobs: cada dos horas, minuto 7, calendario de Guatemala: **`7 */2 * * * RUTA_PHP /home/TU_USUARIO/rankingsmashbros.com/instagram-sync.php`**. Comprueba la zona del servidor y ajusta si no es Guatemala. Configura Cron Email para recibir fallos. No redirijas el resultado a un archivo público. La salida solo contiene estado y conteos, no llaves.
9. Cuando la captura funcione, en GitHub → Settings → Secrets and variables → Actions → Variables crea **SMASH_INSTAGRAM_ENABLED=true**. No necesita ningún secreto Instagram en GitHub: se guarda y renueva en el hosting. Ejecuta una vez «Instagram · comprobar captura del hosting». Debe quedar verde. Si Meta falla, la ejecución se pone roja y queda visible la última copia buena; activa las notificaciones de Actions para los fallos que quieras recibir. Ese control funciona cada dos horas y puede retrasarse por la cola de GitHub.
10. La renovación automática semanal guarda su estado en private-smash/instagram-token.json (600). No hay que copiar cada llave nueva a cPanel. Si Meta la revoca o vence, autoriza otra llave larga y reemplaza la semilla/fecha en el archivo privado. Para pausar, enabled=false y variable del monitor=false; conserva el último feed. Para ocultarlo, mueve el JSON público a una copia privada recuperable, como explica INSTAGRAM.md.

**Pantalla provisional, pendiente Claude Design.** El dueño autorizó avanzar con componentes existentes. Prompt para entregar:

> Diseña «Desde Instagram» para Ranking Smash Bros usando la identidad ya publicada: colores, Archivo/Big Shoulders Display, cortes inclinados y logo actual del podio. Dos superficies: sección debajo del ranking (6 tarjetas y enlace Ver publicaciones) y página /instagram.html (máximo 12). Mostrar imagen local, tipo Foto / Video · portada / Carrusel · primera imagen, fecha y caption breve. Al pulsar, modal accesible con imagen completa, caption original con saltos de línea y Ver en Instagram ↗. Solo fotos y miniaturas: sin videos reproducibles, embeds, SDK o cookies de Meta. Diseña escritorio y 375 px, caption largo/sin caption, foto ausente con logo, galería vacía, carga diferida y foco de teclado. Si falla la fuente, la portada queda oculta o conserva su copia anterior; no mostrar errores técnicos. No hay seguidores, likes, comentarios, avatares, nombres de usuarios, estadísticas ni archivo histórico. Últimas 12 exclusivamente. Conserva encabezado y pie actuales y reduced-motion. Entrega README con contratos/estados y HTML/CSS de referencia; sin support.js ni datos de ejemplo productivos.


### Asistente de Terminal para Instagram (27/oct)

La invitación rankingsmashbros está aceptada, comprobada en Roles y en la tabla del paso 2; ID de cuenta 17841423954542472. El error anterior de añadir era un duplicado: DeveloperAppInlineValidation decía «ya figuran como instagram testers». El dueño confirmó que guardó INSTAGRAM_ACCESS_TOKEN con gh; no se ha leído su valor. El secreto de GitHub no se transmite al hosting en el diseño actual.

Para guardar la configuración desde cPanel sin editar PHP, usar [configurar-instagram-cpanel.sh](configurar-instagram-cpanel.sh) de este PR, descargado desde el commit verificado, y ejecutarlo con bash en Terminal cPanel. Primero pregunta si la llave es larga (60 días) y generada hace menos de 24 h: contestar SI solo si ambas cosas son ciertas. Luego copiar el token desde Meta y pegarlo en el prompt oculto. No pegarlo en el comando, chat o captura. Guarda solo la configuración privada con enabled=false y 600; no crea cron ni consulta Meta. Si ya existe el archivo, se detiene y lo conserva. No usar la hora actual para dar vida nueva a una llave vieja; el margen de 24 h del asistente se explica en INSTAGRAM.md.

Al terminar, compartir únicamente la salida saneada. Orden recibida y #121 fusionado/publicado; captura real, permisos privados y tarea cada dos horas comprobados directamente, monitor verde. No falta otra autorización para la operación normal ya configurada. La renovación real se verificará cuando le corresponda; no renovar una llave recién creada para probarla.
