# Cuentas y vinculación con start.gg

## Implementación — 7 de octubre de 2026

Código integrado: PR #18, `main` en `4229d26`. CI `37654934247` y `37654969407` correctas, incluyendo MySQL 8.0, MariaDB 10.11 y lint PHP 7.4/8.1. Beta publicada mediante `assets_only=true`, run `37655240917` correcto. Al publicar, el API devolvía `oauthReady=false` y producción tenía cero usuarios. Después el dueño registró/configuró la app y se verificó la vinculación real de Bucaro19, con un usuario y una conexión activa sin tokens persistidos; el cálculo sigue sin cambios. Evidencia detallada en EN-CURSO.md.

`cuenta.html`, `cuenta.css` y `cuenta.js` implementan el handoff local de Claude Design (`SmashRankingGT/design_handoff_smash_gt_cuentas/`), sin copiar su runtime ni sus usuarios de demostración. Backend: `accounts.php`, `account-api.php` y `oauth.php`. `account-model.js` contiene comportamiento puro del editor y movimientos.

No reinstalar las tablas: se usa el esquema `001_accounts_competition` existente. No cambiar el cálculo, la validación o la versión de `data/public.json`.

Actualización del dueño: **aplicación registrada y archivo privado habilitado**. Codex comprobó `oauthReady=true` mediante el API público. Después se comprobó la autorización real en Chrome: identidad Bucaro19, enlace al perfil esperado, foto, ranking e historial disponibles. El intercambio de código y la consulta GraphQL de identidad funcionaron con el proveedor real.

## Qué funciona en esta fase

- Autorización `user.identity` y asociación por `currentUser.id` / `currentUser.player.id`, obtenidos por el servidor después del intercambio de código. No usar alias, país o IDs enviados por el navegador para autenticar.
- Primera elección de intereses: jugador, organizador o ambos. **No concede permisos de torneo**, no crea `tournament_staff` y no permite autoconcederse `admin`.
- Perfil: puesto, puntos, movimiento cuando existe corte anterior, récord y torneos de ambas vistas, incluidos puestos posteriores al 100. Un usuario que no aparece muestra «sin puesto», sin atribuir una causa no verificada.
- Historial limitado a los resultados disponibles en el JSON publicado. La vista local conserva asistencia internacional conocida, marcada como excluida. No captura todavía todos los torneos pequeños, dobles o inscripciones sin sets.
- Personajes detectados y elegidos diferenciados. Guardado de main + hasta dos secundarios en `user_characters`, búsqueda, intercambio sin duplicados, descarte y aviso al salir sin guardar. Los elegidos personalizan la cuenta; **no reemplazan los detectados del ranking ni cambian puntos**.
- Cerrar sesión y desvincular. Desvincular cierra las sesiones de Smash GT y preserva preferencias e historial público. La revocación de la autorización en start.gg es independiente, desde ese proveedor.

Agenda, torneo en curso, reportes, notificaciones, top 15 por organizador y verificación de organizadores siguen pendientes. Pantallas nuevas requieren nuevo handoff de Claude Design.

## Registrar la aplicación (dueño)

1. Abrir [Developer Settings de start.gg](https://www.start.gg/admin/profile/developer/applications) con su cuenta y crear una **OAuth Application** (no un Personal Access Token).
2. Nombre sugerido: **Smash GT**. Sitio: `https://rankingsmashbros.com/`. Descripción: perfil y ranking de Smash Ultimate Guatemala con personajes elegidos e historial disponible.
3. Registrar exactamente esta URL de retorno HTTPS, sin barra final ni carpeta extra: **`https://rankingsmashbros.com/oauth.php`**.
4. La aplicación solicita únicamente **`user.identity`**. No requiere `user.email`, `tournament.manager` ni `tournament.reporter` para esta entrega.
5. Guardar el client ID y el client secret en el servidor, sin pegarlos en chat. Copiar `docs/smash/config/oauth.local.php.example` a **`/home/ivcjgjlk/private-smash/oauth.local.php`**, hermano del document root. Completar ambos valores y cambiar `enabled` a `true` cuando el backend esté publicado. No editar `config.local.php` de la base para esto.
6. Permisos del archivo: lectura para el proceso PHP, sin acceso público. No subir el archivo completado a GitHub, FTP público ni a un artefacto. El despliegue no lo incluye ni lo modifica.

Referencia oficial: [flujo de autorización](https://developer.start.gg/docs/oauth/oauth-overview/) y [alcance user.identity](https://developer.start.gg/docs/oauth/scopes/). Los nombres exactos de campos del formulario pueden variar; si pide una política o campos adicionales, revisar esos requisitos antes de completar con URLs inventadas.

## Archivo local con credenciales

La copia local editable es `docs/smash/config/oauth.local.php`, ignorada por Git y con permisos 600. **Editar esta copia, no `oauth.local.php.example`**. El ejemplo versionado debe contener exclusivamente placeholders. `.gitignore` no oculta cambios en un archivo que Git ya sigue; por eso se restauró el ejemplo y se preservó la llave en la copia privada.

El despliegue tampoco incluye la copia local. El archivo de producción sigue siendo `/home/ivcjgjlk/private-smash/oauth.local.php`, fuera del sitio público. No subir ninguna copia a una carpeta pública.

## Activación y comprobación real

Tras publicar el backend y completar la configuración privada:

1. Abrir `/cuenta.html`; el botón debe estar activo. Autorizar en start.gg y comprobar el alias y el ID de jugador esperado. No solicitar ni leer cookies/contraseñas para comprobarlo.
2. Confirmar perfil y ambos rankings contra el corte público, elegir intereses, guardar personajes y recargar.
3. Probar cancelación, cerrar sesión y nueva autorización; desvincular y verificar que otra pestaña/sesión ya no pueda guardar preferencias.
4. Comprobar conteos desde el diagnóstico privado. Solo este paso crea un usuario real; las pruebas automatizadas usan bases desechables. No declarar OAuth productivo hasta terminar esta prueba.

Verificado con el proveedor real: autorización básica, intercambio de código, identidad y perfil del propietario. Las pruebas desechables cubren cancelación, cierre, desvinculación y guardado; estos cambios no se ejercitaron arbitrariamente sobre las preferencias o sesión real del dueño.

## Sesiones, credenciales y consumo

- PHP: cookie HttpOnly, SameSite=Lax, Secure con HTTPS y regeneración tras ingreso/salida. Máximo absoluto de sesión: ocho horas; la limpieza de sesiones del hosting puede cerrarla antes.
- `state` aleatorio de un uso, válido por diez minutos. Inicio mediante POST con CSRF; callback consume el intento incluso al cancelar/fallar. URL del proveedor y callback fijas.
- API de cuenta: respuestas privadas `no-store`, escritura con CSRF, identidad desde sesión; valida roles, catálogo y duplicados. Revalida estado/version de vinculación bajo bloqueo antes de escribir, para impedir cambios después de revocación o de otra autorización.
- `oauth_connections.updated_at` actúa como versión de sesión. Una nueva autorización invalida sesiones anteriores; no es un sistema de sesiones múltiples permanente.
- Esta versión **descarta los tokens** tras verificar identidad. La fila de vinculación guarda el alcance y estado; columnas de tokens permanecen vacías. No implementar refresco/reportes usando tokens inexistentes. Una fase con sincronización por usuario necesitará persistencia cifrada y llave privada externa.
- Normalmente hay un intercambio de token y una consulta GraphQL por ingreso. Consultar perfil, alternar vistas y guardar mains usa hosting/datos compartidos, no vuelve a start.gg. OAuth no prueba que exista una cuota independiente o tarifa por jugador.
- El código de aplicación no registra secretos, códigos o cuerpos de error. Los logs de acceso del hosting pueden registrar la URL de callback; tratarlos como privados. No afirmar que un comentario del código desactiva los logs del servidor.

## Perfil v2 — 7 de octubre (Claude Code)

`cuenta.html`, `cuenta.css`, `cuenta.js` y `account-model.js` siguen ahora el handoff `design_handoff_smash_gt_cuentas_v2/`. Alcance, datos y límites en EN-CURSO.md, «Perfil v2». Contrato nuevo de `account-api.php`: `profile.rivals[playerId] = {tag, url, main, combined:{rank,points}|null, guatemala:{rank,points}|null}`, calculado del corte publicado para los oponentes del usuario autenticado; no acepta parámetros del navegador.

## Mantener la sesión iniciada — 7 de octubre (Claude Code)

Pedido del dueño: no autorizar con start.gg en cada visita, «lo normal, como Facebook». Requiere la migración `002_sessions_visits`.

- Al terminar una autorización correcta, `oauth.php` crea un identificador aleatorio de 32 bytes y lo entrega en la cookie **`smash_recordar`**: HttpOnly, Secure con HTTPS, SameSite=Lax, ruta `/`, 90 días. En `user_sessions` se guarda únicamente su SHA-256, con la versión de la conexión, el enlace de perfil y el avatar que antes solo vivían en la sesión PHP.
- `account-api.php` restablece la sesión con esa cookie cuando la sesión PHP no existe o superó sus ocho horas. Solo es válida si el usuario sigue activo y la conexión es la misma, sin revocar, que existía al emitirla. Al usarla en un día nuevo se renuevan los 90 días (una escritura diaria como máximo).
- Una cookie desconocida, mal formada, vencida o de una conexión revocada se borra del navegador. Un fallo de la base **no** la consume: responde 503 y la conserva.
- «Cerrar sesión» borra la fila de ese navegador y la cookie. «Desvincular» borra todas las filas de la cuenta; además la conexión queda revocada y, al volver a vincular, cambia de versión, por lo que ninguna cookie o sesión anterior revive.
- **Varios dispositivos:** un ingreso nuevo ya no cambia `oauth_connections.updated_at` si la conexión está vigente, así que el teléfono y la computadora pueden estar abiertos a la vez. Antes cada ingreso cerraba los demás; ese comportamiento se sustituyó a propósito.
- Las escrituras siguen exigiendo el token CSRF de la sesión: copiar la cookie no basta para guardar cambios desde otro sitio.
- Sigue sin guardarse ningún token de start.gg. Tampoco IP, navegador ni identificador de la sesión PHP. Quien use un equipo compartido debe cerrar sesión.
- Sin la migración instalada, el ingreso funciona igual que antes y no emite la cookie.

Pruebas: `test_accounts.php` (hash, renovación, vencimiento, segundo dispositivo, usuario desactivado, tabla ausente, desvincular y revincular) y `test_accounts_http.py` (reanudar sin sesión PHP y con sesión vencida, escritura tras reanudar, cookies falsas o vencidas, cierre de sesión, dos navegadores y desvinculación).

## Verificación reproducible

- `node --test scripts/smash/test_accounts.cjs`: movimientos con cortes reales, búsqueda normalizada, intercambio/compactación de personajes y filtros de historial.
- `php scripts/database/test_accounts.php`: state/replay/TTL, identidad y URLs, configuración privada/supresión de salida, paridad con clasificados del JSON; con base local desechable agrega vinculación, roles, guardado/rollback, revocación/reautorización, bloqueo de usuarios y transacciones.
- `python scripts/database/test_accounts_http.py`: HTTP real contra PHP temporal, CSRF, métodos, sesiones vencidas/rotación, límites, escritura ligada al usuario de sesión, paridad de vistas, cancelación y replay. Nunca contacta start.gg.
- Los helpers sintéticos se generan exclusivamente en un directorio temporal de prueba; no son endpoints publicados ni bypass de OAuth.
- Integración en CI con MySQL 8.0 y MariaDB 10.11. Lint del código servido en PHP 7.4 y 8.1. Verificación visual de ingreso/perfil/editor y guardado real en base local desechable; no confundirla con autorización real del proveedor.

## Continuidad para Claude Code

Leer este archivo y `EN-CURSO.md`. No rehacer migración de encuesta/carga inicial, no activar OAuth con placeholders, no agregar usuarios a producción para pruebas. Mantener `deploy.py` con bibliotecas antes de sus callers y `public.json` al final. Para publicar solamente estas pantallas usar `smash-deploy-snapshot.yml`, `assets_only=true`, desde `main` después de CI. No subir SQL, ejemplos privados, handoff o helpers de prueba.
