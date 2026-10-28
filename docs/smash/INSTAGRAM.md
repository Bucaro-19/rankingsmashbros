# Desde Instagram — captura propia, últimas 12

Publicado y activado el 27/oct/2026 por orden expresa del dueño; PR #121 fusionado y despliegue assets-only 40623868271. Pantalla provisional autorizada, pendiente revisión de Claude Design. No utiliza SQL, start.gg, el cálculo, public.json ni el circuito del corte. La elección del dueño es conservar **solo las últimas 12 publicaciones**, no un archivo histórico.

## Circuito y límites

1. Cron de BanaHosting cada dos horas, minuto 7, ejecuta `instagram-sync.php` con PHP CLI. Solo biblioteca `instagram.php`, curl, GD y mbstring; memoria 256M, ejecución CLI 300 s. Presupuesto 70 solicitudes, sin iniciar otra después de 240 s (una petición ya iniciada puede tardar hasta 15 s); cada respuesta API como máximo 512 KiB, cada imagen 12 MiB y 12 millones de píxeles. No requiere otro servicio de pago.
2. Confirma que `/me?fields=user_id` corresponde a la cuenta configurada. Lee `/me/media` con `instagram_business_basic`, API fijada a v25.0: id, media_type, caption cuando esté disponible, permalink, media_url, thumbnail_url y timestamp. Máximo tres páginas acotadas por cursor y 12 resultados; se ordenan por fecha. Si Meta rechaza específicamente caption con código 100, repite una vez sin ese campo y deja el texto vacío. No se inventa.
3. Carrusel: primer elemento de `/children`, limit=1. Video: solo thumbnail_url; no descarga ni reproduce el video. Imágenes: descarga HTTPS desde cdninstagram.com/fbcdn.net, máximo dos redirecciones a esos mismos dominios. Nunca envía el bearer al CDN. Sin SDK, embeds, cookies o peticiones del visitante a Meta; el enlace a Instagram requiere que la persona lo pulse.
4. GD reencoda y elimina metadatos: lado mayor de 1080 px y miniatura de 360 px, sin ampliar originales pequeños. WebP calidad 82 o JPG 85. Nombres SHA256 del contenido, cabecera immutable un año únicamente en assets/instagram. Los archivos referenciados se conservan; huérfanos propios mayores a siete días se eliminan después de una captura correcta. No elimina otros assets.
5. Publica data/instagram.json por rename atómico **después** de validar toda la respuesta. Error de API/esquema/renovación conserva la última copia buena. Una imagen que falla usa su copia local anterior o queda image:null: tarjeta legible con logo/texto/enlace, sin romper el resto. Las eliminaciones salen de la lista en la próxima captura correcta; sus archivos dejan de referenciarse y se limpian tras siete días. No es una eliminación instantánea de todos los caches de terceros.
6. Escribe data/instagram-status.json con estado reducido sin respuesta de Meta ni credenciales. Actions `smash-instagram-health.yml` lo comprueba cada dos horas en el minuto 29 UTC (22 minutos después del cron GT), solo en main y con SMASH_INSTAGRAM_ENABLED=true. Falla en rojo si no está ready o tiene más de tres horas. No captura ni usa FTP, SQL o llaves. GitHub puede retrasar sus horarios; configurar también Cron Email para enterarse de fallos del hosting. No modifica ninguna automatización existente.

El token se renueva semanalmente, o al quedar menos de siete días, nunca con menos de 24 horas de antigüedad ni después de caducar. `expires_in` de Meta determina el vencimiento real. Se persiste la renovación **antes** de capturar las publicaciones, para no perderla si después falla la API. Token revocado/caducado requiere autorización nueva; no se promete renovación indefinida si Meta retira el permiso.

## Archivos privados y despliegue

`/home/<usuario>/private-smash/instagram.local.php` (600), al lado y fuera de la raíz pública, contiene enabled, account_id, access_token e issued_at. Plantilla **sin secretos**: [instagram-config.example.php](instagram-config.example.php). El directorio privado debe existir y ser escribible por el PHP del cron. El proceso crea allí instagram-token.json (600) y instagram.lock (600). El token original identifica la configuración; no sobrescribe uno ya renovado. Cambiar el token semilla permite una nueva autorización. No copiar el estado al repositorio, a una carpeta web ni a un artefacto de Actions.

Ambos PHP son solo CLI: defensa PHP 403 más denegación en .htaccess. No incluyen accounts.php/database.php ni hacen consultas SQL. El CLI desactiva mensajes crudos de PHP y solo imprime conteos/códigos permitidos, nunca excepciones, URLs firmadas, bodies, tokens o cabeceras de Meta. Los archivos públicos rechazan credenciales conocidas incluso si aparecieran en contenido fuente.

FILES publica HTML/CSS/JS, las dos piezas PHP y assets/instagram/.htaccess. **Nunca** incluye JSON de ejecución ni imágenes generadas, y el despliegue no borra archivos remotos. Prueba FTP simulada cubre tanto assets_only como despliegue completo. El sitemap incorpora instagram.html con fecha editorial real; no lee el feed para inventar lastmod ni cambia public.json. El feed usa no-cache; salud usa no-store; esto no cambia el caché del ranking ni de las páginas.

## Contrato público v1

```json
{
  "schemaVersion": 1,
  "generatedAt": "2026-10-27T23:05:59Z",
  "posts": [
    {
      "id": "10001",
      "type": "IMAGE",
      "caption": "Texto público de la publicación",
      "permalink": "https://www.instagram.com/p/EJEMPLO/",
      "timestamp": "2026-10-27T18:00:00Z",
      "image": null
    }
  ]
}
```

Ejemplo inventado de contrato, no dataset instalado. type: IMAGE, VIDEO o CAROUSEL_ALBUM. image es null o `{src, thumbnail, width, height, thumbnailWidth, thumbnailHeight}`; rutas locales `assets/instagram/{sha256}-full.webp|jpg` y `...-thumb.webp|jpg`, nunca URL temporal. Máximo 12 posts, caption 2200 caracteres Unicode, JSON máximo 128 KiB. No account_id, nombre de usuario, seguidores, comentarios, personas etiquetadas ni estadísticas. El ID de media y su caption/permalink son contenido público solicitado por el dueño.

Salud: `{schemaVersion:1,checkedAt,ok,status,code}`; valores controlados, sin detalles de la respuesta fuente. Ausencia de configuración deja el feed intacto; el monitor no se debe activar antes de configurar y comprobar una captura.

## Interfaz

Portada: seis tarjetas después del ranking, inicialmente oculta; consulta el JSON al aproximarse a esa zona (IntersectionObserver) y solo entonces crea miniaturas lazy. Galería: hasta 12 tarjetas; vacío neutral si falta el archivo, no hay posts o la lectura falla. Ambos leen únicamente su snapshot local; no hay exposición de fallos de la API al visitante. La sección propia tiene enlace en la portada y su pie.

Modal nativo: imagen completa bajo demanda, caption en textContent con saltos de línea, fecha GT, tipo y Ver en Instagram. Escape/cerrar devuelve el foco, bloqueo de scroll, foco visible y prefers-reduced-motion. Sin dialog compatible, abre el permalink de forma segura. Un error HTTP de imagen conserva el bloque del logo y el enlace. No carga videos ni llamadas de análisis nuevas.

## Configuración y comprobación por el dueño

Guía de configuración/reautorización en [PENDIENTES-DUENO.md](PENDIENTES-DUENO.md), sección Desde Instagram. **Ya está instalado**: no volver a ejecutar el asistente ni añadir otro cron por rutina. Estado y evidencia en EN-CURSO.md.

Asistente manual para el dueño en Terminal cPanel: [configurar-instagram-cpanel.sh](configurar-instagram-cpanel.sh). Comprueba /usr/local/bin/php CLI 8.1+, curl/GD/mbstring; confirma token largo recién generado (<24 h), lo pide sin eco por /dev/tty y lo pasa a PHP solo por stdin. Crea exclusivamente /home/ivcjgjlk/private-smash/instagram.local.php, modo 600, cuenta 17841423954542472 comprobada en la pantalla de Meta. Se detiene antes de pedir la llave si el archivo ya existe; no lo reemplaza. Captura **desactivada**, sin API, SQL, cron, FTP, publicación o activación. Después del despliegue autorizado hay que habilitar la captura y hacer la primera prueba antes de programarla.

Excepción conservadora del asistente para la semilla recién creada y confirmada: no conoce el instante de emisión de Meta. Usa `issued_at = hora de configuración − 24 h` como **cota inferior**, nunca como una afirmación del instante real. Así no sobreestima los 60 días de vida, y su primera renovación se intenta seis días después de configurar, cuando ya supera el mínimo de 24 h. Tras renovar, el estado guarda el instante y expires_in de la respuesta real. Un token antiguo o de duración desconocida no debe configurarse con este asistente. El archivo editable manual sigue requiriendo una fecha de emisión válida; no rejuvenecer tokens antiguos.

El dueño confirmó guardado de INSTAGRAM_ACCESS_TOKEN mediante gh secret set. GitHub no permite volver a leerlo por API; el cron actual **no consume ese secreto**. El asistente necesita pegar el original desde Meta en Terminal cPanel. No se creó un canal para transportar secretos de Actions a hosting ni permisos para escribirlos desde un workflow. No hay ninguna escritura remota ejecutada por Codex en esta preparación.
 El dueño registró/autoriza la app y aceptó la invitación de tester; luego se verificó la captura real y se activó el cron. El token no fue pegado en chat, Git o argumentos de consola por esta integración.

Prueba manual después del despliegue autorizado: ejecutar el PHP CLI sin argumentos secretos. Debe imprimir status ready; comprobar ambos JSON estáticos y las rutas de imagen. Activar monitor después. En fallo, inspeccionar solo el código seguro y los permisos/versión PHP; **no habilitar curl verbose ni pegar el token en comandos o chat**. Para reautorizar, editar el archivo privado en cPanel con una llave larga nueva y su fecha real. Eliminar/rotar el token anterior en Meta cuando corresponda.

Apagar captura: enabled=false y desactivar variable del monitor; conserva el último feed. Para ocultar inmediatamente la sección, mover data/instagram.json fuera del sitio con el administrador de archivos (copia recuperable). Al no tener fuente, la portada se oculta y la galería muestra su vacío. No hace falta desplegar ni tocar SQL.

## Pruebas y límites de lo comprobado

- PHP con transporte inventado y GD real: paginación/12, primera imagen del carrusel/video, dimensiones y hash, persistencia de la renovación incluso si falla media, refresh fallido/expiración, API caída preserva feed, imagen fallida/reutilización/null, secreto no publicado, cuenta ajena, CDN no permitido, permisos y lock, eliminación de posts y limpieza de huérfanos. Nunca llama a Meta ni SQL.
- Node: validación, rutas locales, límites, feed diferido, seis tarjetas, vacío silencioso, modal/escape/foco, textContent y fallback de imagen, sin SDK/embeds.
- Python: salud fresca/obsoleta/malformada y errores sanitizados; HTTP 403 de ambos PHP; CLI sin configuración no llama a API; FTP simulado conserva feed/fotos tanto full como assets-only; SEO y publicación.
- CI ejecuta las pruebas PHP con GD en **MySQL 8.0 y MariaDB 10.11**, además de pipeline/Node. La funcionalidad Instagram no utiliza ninguna base.
- QA local con datos inventados: escritorio y 375 px, galería 12/preview 6, caption largo y vacío, logo al faltar foto, detalle/escape/foco, vacío/API caída. Ningún dato de ejemplo se versiona o se despliega.

Prueba autenticada completada: **dos posts reales, seis solicitudes, cero imágenes faltantes**, API v25.0 y captions/carouseles funcionando con la cuenta del dueño. **La primera renovación real todavía no ocurre**; solo está cubierta con transporte inventado y estado privado programado, sin forzar la renovación antes de 24 h. El portal de documentación respondió 429 durante la implementación; no se afirmó una lectura completa de esa web bloqueada. Si la API rechaza un campo distinto de caption, conserva el snapshot y marca error; no amplía permisos a ciegas. No se solicita publicar, leer mensajes, comentarios, contactos ni cuentas ajenas.

Referencias primarias para el operador:
- [Instagram API with Instagram Login](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/).
- [Business Login](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/business-login/).
- [Renovar token](https://developers.facebook.com/docs/instagram-platform/reference/refresh_access_token/).
- [Colección oficial Meta en Postman](https://www.postman.com/meta/instagram/folder/1z5vxzu/instagram-api-with-instagram-login).


## Estado productivo (27/oct)

- PHP 8.1.34; enabled=true; configuración, instagram-token.json y log privados 600 comprobados por metadatos.
- Cron único `7 */2 * * * /usr/local/bin/php /home/ivcjgjlk/rankingsmashbros.com/instagram-sync.php >> /home/ivcjgjlk/private-smash/instagram-sync.log 2>&1`. Usa calendario del servidor (EDT −0400 al instalar); no se alteró la zona global. Los cambios de horario del servidor pueden desplazar la hora equivalente de Guatemala; la tarea sigue siendo cada dos horas de ese calendario.
- Monitor habilitado, SMASH_INSTAGRAM_ENABLED=true; prueba manual 40629915272 verde. No necesita credenciales IG en Actions.
- Primera captura manual 27/oct 21:06:31 GT: dos carruseles, seis solicitudes incluyendo descargas, feed 2,484 B, todo servido desde el dominio. Bibliotecas denegadas por HTTP. public.json intacto.
- Primer disparo automático comprobado: ready y generatedAt **2026-10-28T04:07:02Z / 27/oct 22:07:02 GT**, después de la captura manual y sin reenviarla. Cierre: EN-CURSO.md. No volver a generar llaves o duplicar el cron para una actualización normal.
