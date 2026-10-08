# Tu opinión — rediseño y verificación, 7/oct/2026

## Alcance para Claude Code

Segunda tarea de ENCARGO-CODEX-OPINION-Y-CARGA-INICIAL.md. Rama `feat/opinion-redesign`, desde `main` `66f3004`, actualizada sobre `31f7b96`, independiente de la carga de games (#43). No se fusiona ni despliega sin orden del dueño. No necesita migración.

`encuesta.php`/`encuesta.css` implementan Página 2 del handoff local del dueño. Encabezado y pie de Método copiados exactamente, con aria-current movido a Tu opinión. Se reutilizan paginas.css/cabecera.js sin editar esas bases. No se porta support.js ni datos de ejemplo. No se rediseña opiniones.php ni se tocan los módulos de Claude.

Preguntas y opciones se agrupan en un array de presentación, preservando sus textos y name/value. Q3 conserva todos los párrafos: solo se trasladan las cuatro ayudas a details plegados. Q5/Q6 pasan de select a radios con los mismos valores 1–5 y etiquetas de los extremos. Se retira únicamente el placeholder del select sustituido, no una opción válida. Privacidad intacta y antes del submit. Recuadros amplios, foco amarillo, cero radios de borde, tipografías/tokens del handoff.

## Contrato del formulario (inalterado)

Método POST a ./encuesta.php, nonce privado y honeypot website sin cambios. Bloque original PHP previo al cierre de procesamiento de POST idéntico byte a byte: SHA-256 `dd3196bae5090d89c3a465312320de9ec1f56f5e30f09065aa99f10913940f82`. Persistencia única survey.php / survey_responses, sin fichero de respuestas ni fallback. Marcador smash-survey-storage=sql y require de survey.php conservados. No se guarda IP/correo/cuenta/navegador/id de sesión en respuestas ni se registra contenido en logs. No se leyó encuesta ni comentarios de producción en este encargo.

- Rechazo/CSRF/errores siguen con los mismos mensajes y nonce no consumido.
- Presentación del error repinta únicamente opciones válidas y escapa source/comment con `h` (ENT_QUOTES | ENT_SUBSTITUTE). POST con arrays/valores no admitidos no rompe el render; valores inválidos no se convierten en opciones válidas.
- Las reglas originales siguen siendo 12,000 bytes de request, 2,000 bytes de comentario, 250 bytes de URL y https a start.gg/www.start.gg. maxlength conserva 2,000/250 caracteres, tal como estaba; no redefine el límite real en bytes. El contador es solo informativo.
- Formulario y details funcionan sin JS. Radios required mantienen validación nativa; el servidor sigue validando todo. Progreso se pinta desde PHP tras POST, además de actualizarse en vivo si hay JS.
- Ya respondiste se muestra como panel informativo solo cuando el servidor devuelve el rechazo de cinco minutos; no se cambia el procesamiento ni se añade otro bloqueo a GET. Respuesta guardada reemplaza el formulario.

`encuesta.js` es una mejora opcional: progreso, contador, foco del resumen y botón Enviando. No tiene fetch, almacenamiento, analytics ni respuestas persistidas en el cliente. Restablece el botón al volver desde la caché atrás/adelante. cabecera.js conserva el comportamiento ya aprobado del encabezado. **No visita.js.** El JS nuevo está en deploy.py y su sintaxis se comprueba en CI; no se ejecutó ningún deploy.

## Pruebas y revisión

Local: MariaDB desechable 13.0.2, PHP 8.5.3, PyMySQL 1.1.2. `test_survey_http.py`: **14 pruebas correctas**, doce HTTP y dos estáticas. Se conservan todas las aserciones existentes de seguridad, almacenamiento, reintento y privacidad; solo cambian las de presentación del botón/escalas y se añaden checks de repintado/escape. 48 pruebas de scripts/smash, PHP/JS y diff correctos. MySQL 8.0/MariaDB 10.11 ejecutan estas pruebas en CI; runs completos correctos `37715216663` y `37715213097` sobre `0633176`, con los tres jobs verdes. Resultado final en EN-CURSO y PR. La aserción de presentación de test_survey_storage.php pasa a comprobar el GET renderizado en un proceso PHP con sesión temporal, en vez de buscar strings literales en el template; todas las aserciones de contratos, validación y almacenamiento de ese archivo permanecen intactas.

El contador Connections del servidor global era intermitente: un health check del contenedor podía incrementar el contador entre dos lecturas. El test ahora instrumenta **únicamente database.php copiado al directorio temporal**, justo antes del constructor PDO real. Registra solo una línea literal por intento en un fichero temporal externo al sitio, no SQL ni visitante. Exige exactamente los mismos cero/una conexión, sin usar >=, sleeps o ignorar el fallo. Una prueba nueva abre otra conexión SQL deliberadamente y comprueba que no contamina la cuenta de la app. database.php productivo permanece intacto; las demás aserciones de privacidad siguen activas.

Revisión en navegador Chrome mediante Playwright, sobre copia temporal de la app con SQL/sesiones/textos **inventados**. No se abre ni envía el formulario productivo. Viewports 1440×900 y 375×900:

| Estado | Qué se comprobó en ambos anchos |
|---|---|
| Inicial y parcial | Encabezado/pie, seis preguntas, radios reales, progreso 0→2/6 |
| Ayudas Q3 | Cuatro details cerrados y abiertos, todas las explicaciones legibles |
| Escalas | Cinco celdas táctiles, selección y etiquetas de los extremos |
| Validación servidor | Resumen, enlaces y errores por campo; conserva las dos respuestas |
| Enlace inválido | Mensaje original y asociación ARIA al campo |
| Enviando | Handler real de submit, botón deshabilitado y spinner; navegación detenida solo en fixture para fotografiar |
| Fallo/reintento | Configuración SQL deliberadamente incorrecta en fixture; seis radios y comentario conservados; posterior éxito |
| Guardado | Confirmación y ausencia de formulario |
| Ya respondiste | Panel informativo y rechazo original; no duplicación |
| Sin JS | Inicio, fallo con repintado y envío normal que termina en confirmación |

18 vistas y 28 capturas; todas las vistas verifican scrollWidth≤innerWidth; cero errores de JS. Capturas/reporte locales temporales en `/tmp/smash-initial-context/review/`, no se versionan ni contienen respuestas reales. Se inspeccionaron visualmente preguntas, escala, estados y pie en móvil/escritorio. Tras reiniciar pueden desaparecer: la evidencia durable es este registro y los tests HTTP.

Para repetir manualmente, usar una base desechable smash_schema_test* en localhost, instalar esquema/seed, copiar app+assets al fixture, configurar PHP y visitar encuesta.php a ambos anchos. Provocar fallos solo cambiando la configuración del fixture, nunca la privada productiva. Sin JS, enviar mediante el POST normal, comprobar repintado y corregir el fixture para reintentar. Nunca consultar comentarios reales para revisión visual.

## Pendiente

Revisión/orden de fusión y despliegue del dueño. La PR de la carga inicial es independiente y mantiene pendiente la simulación remota por acceso del router; no ejecutar escritura de producción desde este encargo.
