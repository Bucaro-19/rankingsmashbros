# Encargo para Codex — que Google encuentre y muestre bien el sitio

Fecha: 8 de octubre de 2026. Una sola tarea, sin pantallas nuevas ni cambios de diseño. Claude Code sigue con el top por organizador (`organizador.*`, `top.php`, `top.css`, pestaña «Mis torneos» de `cuenta.*`): no toques esos archivos salvo lo que se indica abajo para `cuenta.html`.

## Estado comprobado en producción (8/oct)

- `https://rankingsmashbros.com/robots.txt` y `/sitemap.xml` responden 404.
- La portada tiene `<title>` y `<meta name="description">`, pero no `<link rel="canonical">`, ni etiquetas Open Graph/Twitter, ni datos estructurados.
- La portada pinta el ranking con JavaScript desde `data/public.json`; el HTML inicial casi no tiene texto que un buscador pueda leer.
- `www.rankingsmashbros.com` no respondió en la comprobación (pudo ser la red local): verifica si existe y, si responde, que redirija al dominio sin `www`.

## Qué hacer

1. **`robots.txt`**: permitir el sitio público; excluir lo privado o sin valor de búsqueda (`/panel.php`, `/opiniones.php`, `/cuenta.html`, `/analisis.html`, `/top/`, APIs `*-api.php`, `/oauth.php`, `/visita.php`, `/recurrente-webhook.php`, `/ranking-sync.php`, `/feedback-data/`). Declarar el sitemap.
2. **`sitemap.xml`**: solo páginas públicas e indexables (portada, `metodologia.html`, `analisis-top20.html`, `analisis-torneos.html`, `encuesta.php` si el dueño quiere que aparezca; pregúntalo en la PR). `lastmod` real: el del corte para las que dependen de `public.json`. Decide si es estático o lo genera `deploy.py`/la publicación semanal, y que no pueda quedar desfasado en silencio.
3. **En cada página pública**: `canonical` absoluto, `og:title`, `og:description`, `og:url`, `og:type`, `og:image`, `og:locale` (`es_GT`), `twitter:card`. Títulos y descripciones propios por página, en español de Guatemala, sin prometer lo que el sitio no es (es un ranking **piloto** de la comunidad, no oficial).
4. **Imagen para compartir** (1200 × 630): no inventes un diseño nuevo. Si no hay una imagen aprobada en el repo, deja el `og:image` listo para un archivo y pide al dueño la imagen por Claude Design en la PR.
5. **`noindex`** en las páginas privadas o personales que hoy no lo tengan (`cuenta.html`, `analisis.html`). `panel.php`, `opiniones.php` y `top.php` ya lo envían: no los cambies.
6. **Datos estructurados** (JSON-LD) en la portada: `WebSite` y `Organization` como mínimo. Si propones `ItemList` con el top, que salga de `public.json` en el paso de publicación, nunca escrito a mano.
7. **Texto legible sin JavaScript en la portada**: propón la opción de menor riesgo (por ejemplo, un bloque `<noscript>` o un resumen estático que la publicación semanal regenera con el top 10 y la fecha del corte). No cambies `app.js` ni el aspecto de la página con JavaScript activo. Si esto exige tocar el diseño, déjalo como propuesta y no lo implementes.
8. Añade los archivos nuevos a la lista `FILES` de `scripts/smash/deploy.py` y a las pruebas de `test_publish.py`.

## Límites

- No cambies el cálculo, `public.json`, la encuesta, las cuentas ni premium.
- Nada de servicios externos, scripts de terceros ni analítica nueva. No uses las herramientas «SEO and Marketing Tools» de cPanel.
- No registres el sitio en Google Search Console: eso lo hace el dueño con su cuenta. Deja en la PR los pasos exactos (verificación por registro DNS TXT o por archivo HTML, y envío del sitemap).
- El contador de visitas propio (`visita.js`) no debe cambiar.

## Entrega

Una PR en rama propia desde `main`, con pruebas (`test_publish.py` y las que añadas), revisión en navegador de que las páginas se ven igual, validación del sitemap y del JSON-LD, y `EN-CURSO.md` actualizado. No fusiones ni despliegues sin la orden del dueño.
