# SEO técnico — 8 de octubre de 2026

Entrega de Codex: [PR #58](https://github.com/Bucaro-19/rankingsmashbros/pull/58), rama `feat/technical-seo`. Sin fusión, despliegue, registro en Search Console, consultas a start.gg, conexión SQL o escritura en producción. El sitio continúa siendo un **ranking piloto independiente**, no oficial. No hay cambios de diseño ni scripts externos nuevos.

## Lo implementado

- `robots.txt` con el sitemap y exclusiones explícitas: panel/opiniones, cuenta/análisis personal, tops por organizador y sus rutas, APIs `*-api.php`, OAuth, visitas, webhook, receptor/worker y feedback-data. CSS, JavaScript, imágenes y datos públicos siguen accesibles para renderizar las páginas. Robots es una instrucción de rastreo, no control de acceso. Las protecciones PHP y `.htaccess` existentes permanecen.
- Cuatro URLs canónicas indexables: `/`, `/metodologia.html`, `/analisis-top20.html`, `/analisis-torneos.html`. Cada una tiene título/descripción propios con el carácter de piloto, canonical HTTPS absoluto, Open Graph (título, descripción, URL, tipo website, locale es_GT y site_name) y Twitter summary/título/descripción. Portada con JSON-LD `WebSite` + `Organization`, sin entidades oficiales, afiliaciones, dirección, logo o búsqueda inventados. No ItemList escrito a mano.
- `cuenta.html`: solo se añade meta robots `noindex`, excepción prevista por el encargo. `analisis.html` **ya lo tenía** y permanece intacta. Panel, opiniones y top no se editan.
- `og:image` queda **preparado en comentarios**, con destino `https://rankingsmashbros.com/assets/smash-gt-social.jpg` y 1200 × 630. No existe imagen de marca aprobada en el repo (solo assets de personajes), así que no se anuncia una URL activa que devolvería 404. Ver decisión pendiente más abajo. Twitter conserva `summary` hasta recibir la imagen.
- `.htaccess`: redirección permanente **308** de www y HTTP al origen `https://rankingsmashbros.com`, con ruta y consulta preservadas y sin cambiar método/cuerpo de POST. Host destino fijo; localhost y otros hosts no se redirigen. Excepción para `.well-known/acme-challenge/` y `.well-known/pki-validation/` (validación de certificados). La ruta de tops y las denegaciones existentes se conservan.

Google necesita poder rastrear una URL para procesar su noindex; un bloqueo de robots no elimina por sí mismo una URL que ya estuviera indexada. El encargo pide ambas medidas en las páginas personales: se conservan, y el dueño puede usar Retiradas de Search Console si ya aparecieran. No se cambian autenticación ni permisos. [Documentación oficial sobre noindex](https://developers.google.com/search/docs/crawling-indexing/block-indexing).

## Sitemap con fechas comprobadas

`scripts/smash/seo.py` genera XML UTF-8 con namespace 0.9, URLs absolutas y lastmod UTC. La copia versionada de `sitemap.xml` sirve como muestra reproducible para la vista local; **deploy.py nunca reutiliza sus fechas para publicar**: genera su cuerpo en memoria en cada despliegue.

| Página | Fuente real de lastmod |
| --- | --- |
| Portada | `public.json.generatedAt`, fecha del corte servido. |
| Método | `public.json.generatedAt`, porque su tabla de torneos/alcances depende del corte. |
| Estudio top 20 | Mayor de `analisis-top20.json.cut` y el corte publicado; el estudio también lee public.json para advertir si ya existe un corte distinto. |
| Estudio torneos pequeños | `analisis-torneos.json.snapshotAt`; conserva la fecha de ese estudio histórico y no se rejuvenece cada domingo. |

Las fechas representan **el corte de datos/contenido del estudio**, no la hora de subir los archivos ni un mtime de checkout. No se inventan fechas con «ahora». Según Google, lastmod debe reflejar una actualización significativa real. [Guía oficial de sitemaps](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap).

En publicación normal, usa el JSON que se va a publicar. En `assets_only=true`, lee **solo el JSON público vigente por la conexión FTP ya autenticada** (`RETR data/public.json`, límite 32 MiB); no usa el snapshot viejo de Git ni consulta SQL. Si no puede leer/parsear/comprobar fechas reales, falla **antes de subir cualquier archivo**. Es un cambio operativo intencionado: no publicar un sitemap engañoso como si nada hubiera pasado. Si se necesita arreglar assets cuando el JSON del sitio falta/corrompe, el dueño debe resolver ese caso explícitamente; no hay bypass silencioso.

Se sube `sitemap.xml` temporalmente y se renombra **después** de la carga exitosa del corte. `public.json` sigue siendo el último **archivo de datos** de FILES; el sitemap es metadata posterior. Si falla public.json, no se toca el sitemap anterior. Si falla el sitemap después del corte, el workflow falla explícitamente: FTP no hace una transacción de todo el sitio; reintentar el despliegue autorizado, que lo regenerará con el corte correcto. La publicación de assets, ranking y personajes comparte `concurrency.group=smash-gt-publication`, sin cancelación, para no competir entre sí.

Encuesta **fuera del sitemap por ahora**, pendiente de decisión del dueño en la PR; no se cambian su PHP ni preguntas/metadatos. No estar en el sitemap no es noindex: sigue siendo una página pública enlazada. Si el dueño quiere promoverla en buscadores, habrá que añadir su canonical/social y una fecha de modificación fiable del formulario en un encargo autorizado aparte.

## Propuesta para leer la portada sin JavaScript (no implementada)

La opción de menor riesgo es ampliar **el noscript que ya existe**, sin tocar app.js ni el DOM que usa el ranking cuando JS está activo:

1. En publicación, generar desde el mismo corte público un resumen con fecha, vista «Guatemala + internacionales», top 10 en su orden original, tags y puntos; enlaces a Método y a los estudios. No recalcular ni renumerar la vista local.
2. Escapar textos como HTML; solo URLs locales/versionadas. No cuentas, APIs, start.gg ni datos privados. En assets-only, usar el corte vigente del FTP, igual que el sitemap. Probar cortes nuevos, replay y falla de publicación; no escribir nombres/puestos a mano.
3. Mantenerlo dentro de noscript y reutilizar estilos aprobados. Con JS activo no cambia el aspecto; la lectura sin JS sí cambia, por eso se deja como **propuesta para aprobar**. Si necesita presentación nueva, pedir primero handoff a Claude Design.

Este fallback mejora lectura/accesibilidad sin JS; no se promete que Google lo use como contenido principal, porque normalmente renderiza JS. Para que el ranking esté en el HTML inicial también con JS activo, se necesitaría una propuesta de renderizado/progressive enhancement, revisión del diseño y el pipeline: fuera de este encargo. No ocultar texto para SEO ni ofrecer datos diferentes al buscador.

## Imagen para compartir — pendiente del dueño / Claude Design

Solicitar una imagen de marca aprobada **1200 × 630**, JPG, para `assets/smash-gt-social.jpg`: Smash GT / Smash Ultimate Guatemala, con la palabra «piloto» y sin insinuar afiliación oficial. No reutilizar automáticamente los retratos de Nintendo como imagen de la organización ni crear un diseño nuevo por Codex. Después de aprobarla:

1. Añadir el archivo explícitamente a FILES (antes de las páginas HTML; no entra en el glob de assets/characters).
2. Activar og:image, dimensiones y alt + twitter:image en las cuatro páginas; cambiar twitter:card a `summary_large_image`.
3. Probar 200/MIME/dimensiones y su vista previa, después del despliegue autorizado. No definir logo estructurado sin logo aprobado.

Referencias: [Open Graph](https://ogp.me/) y la revisión de metadatos de `test_seo.py`. Mientras tanto, el preview tiene título/descripción y la imagen es una limitación explícita, no una entrega supuestamente completa.

## Search Console — acciones exactas del dueño (no ejecutadas)

Después de aprobar/fusionar y desplegar esta PR, comprobar que `https://rankingsmashbros.com/robots.txt` y `/sitemap.xml` responden 200; el sitemap tiene las cuatro URLs y el corte real; https sin www no redirige sobre sí mismo y www/http redirigen al origen correcto. Validación en hosting pendiente del despliegue: lo verificado por Codex fue local.

**Opción A, propiedad Dominio (DNS):**

1. Abrir https://search.google.com/search-console/ con la cuenta Google del dueño → selector de propiedad → «Añadir propiedad» → «Dominio» → escribir `rankingsmashbros.com` sin protocolo/ruta → continuar.
2. Copiar el TXT exacto que genera Google (`google-site-verification=...`). No inventar ni reutilizar el token de otro dominio.
3. En el proveedor que gestiona el DNS autoritativo del dominio. Si es cPanel/BanaHosting: Domains → Zone Editor → Manage para rankingsmashbros.com → Add Record → TXT; nombre `rankingsmashbros.com.` (o `@` si ese editor lo pide), TTL por defecto, valor el TXT exacto. No cambiar A, CNAME, MX ni nameservers existentes. Guardar.
4. Volver a Google y pulsar «Verificar» cuando el TXT haya propagado. Conservar el TXT después; si aún no lo ve, esperar y reintentar, no crear otro valor por rutina.

**Opción B, propiedad Prefijo de URL (archivo HTML), si prefiere evitar DNS:**

1. Añadir propiedad → «Prefijo de URL» → `https://rankingsmashbros.com/` (incluida la barra final).
2. Elegir «Archivo HTML» y descargar el archivo exacto `google….html` que entrega Google.
3. Subirlo al document root `/home/ivcjgjlk/rankingsmashbros.com/` mediante File Manager, sin renombrarlo ni cambiar su contenido; su URL exacta debe responder 200 sin sesión. Alternativa por Git: entregar el archivo a un agente y añadir **ese nombre específico** a FILES en una entrega autorizada. La allowlist actual no publica archivos arbitrarios.
4. Pulsar «Verificar» en Google y conservar el archivo. Este método cubre el prefijo elegido; Dominio cubre también protocolos y subdominios. [Instrucciones oficiales de verificación](https://support.google.com/webmasters/answer/9008080).

**Envío del sitemap y comprobación:** en la propiedad verificada → Indexación → Sitemaps → añadir `https://rankingsmashbros.com/sitemap.xml` (si el prefijo está prellenado, escribir solo `sitemap.xml`) → Enviar. Después usar Inspección de URLs sobre la portada y las tres páginas públicas: probar URL publicada, verificar canonical/no bloqueos y pedir indexación si corresponde. No solicitar indexación de cuenta, análisis de rival, panel, opiniones, tops o APIs. Si la encuesta se aprueba, añadirla en su entrega correspondiente. Ningún paso asegura una fecha o posición de aparición en Google.

## Validación comprobada

- 59 pruebas de pipeline/exportación/publicación/SEO y 12 del ranking JS correctas localmente. Validación XML/JSON-LD/canonical/metadatos y fronteras de robots/noindex; publicación de sitemap con corte local/live FTP simulado, falla previa, falla del corte y falla de metadata; mismo bloqueo entre workflows.
- Chrome local: seis páginas (portada, Método, dos estudios, cuenta y análisis personal), antes/después en **1440 × 900 y 375 × 812**. Doce comparaciones: texto visible y geometría iguales, sin overflow horizontal. 24 capturas temporales y `comparison.json` en `/tmp/smash-seo-review/`; los body HTML son idénticos byte a byte a main. Tras actualizar a main `01babf6`, la portada se volvió a comparar en ambos tamaños: texto y geometría iguales, sin overflow; cuatro capturas adicionales `latest-*`. No interacción con cuentas de producción ni envío de encuestas. El servidor de prueba es estático, por lo que los endpoints PHP no se ejecutan.
- Apache 2.4.67 local HTTP y TLS, certificado desechable confiado expresamente por el cliente: www HTTP/HTTPS y dominio HTTP → 308 con ruta/query, dominio HTTPS y hosts de preview → 200 sin bucle, POST → 308, validaciones de certificado exentas, robots text/plain y sitemap application/xml → 200. Sin cambios en configuración del hosting. Resultados temporales en `/tmp/smash-seo-review/apache/results.json`.
- Antes de editar: árbol limpio en la rama anterior, origin `Bucaro-19/rankingsmashbros`; main `a6cec03` y Actions `37828965177` correctos. Rama propia; se conservan después los cambios de Claude #57 (portada tolerante a fallos y caché). CI de `6b96631` correcta en check + MySQL 8.0 + MariaDB 10.11: [37832700934](https://github.com/Bucaro-19/rankingsmashbros/actions/runs/37832700934); consultar también los checks actuales de la PR tras el relevo documental.
- No se editan datos/rank.py/app.js, encuesta, premium, visita.js, panel u organizador/top. En cuentas solo el noindex de cuenta.html. Canonical/social/JSON-LD están en head; no estilos, body, navegación o scripts de presentación nuevos.
