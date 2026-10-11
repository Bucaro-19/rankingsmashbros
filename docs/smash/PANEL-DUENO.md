# Panel privado del dueño — visitas y registros

Pedido del dueño el 7 de octubre de 2026. Implementa el handoff de Claude Design `design_handoff_smash_gt_panel/` (carpeta local, sin versionar). Dirección: `https://rankingsmashbros.com/panel.php`. No tiene enlace desde el sitio.

## Quién entra

Solo una cuenta de start.gg con el rol **`admin`** en `user_roles`. Ese rol no se puede obtener desde la web: las preferencias de cuenta solo manejan `player` y `organizer`. Se concede con una escritura en la base, con el visto bueno explícito del dueño:

```sql
INSERT INTO user_roles (user_id, role) VALUES (<id del dueño en users>, 'admin');
```

- Sin sesión: `panel.php` responde 401 con «Tu sesión venció» y el botón para entrar con start.gg; al volver de la autorización, `cuenta.js` regresa al panel.
- Otra cuenta: 403 con «Sin acceso.», sin cifras, sin el script del panel y sin título revelador.
- La página y `panel-api.php` envían `no-store` y `noindex`. La sesión es la misma de las cuentas, incluida la cookie de sesión persistente.

## Qué muestra

Todo sale de las tablas del contador (VISITAS.md) y de `users` / `oauth_connections`. Visitantes y redes solo como agregados. Las cuentas tienen una lista privada para el dueño, con la proyección limitada indicada abajo.

- **De un vistazo:** visitantes de hoy (parcial) y de ayer, últimos 7 y 30 días, cuentas registradas y cuántas siguen vinculadas.
- **Periodo** (7, 30, 90 días o temporada; se recuerda en el navegador): visitantes distintos con comparación en palabras, redes distintas, visitantes con sesión, vistas, registros nuevos y su proporción.
- **Gráfica:** por día en 7 y 30 días, por semana en 90 días y temporada; alterna visitantes y vistas; franja de registros; lectura de la barra elegida; teclado con ← → Inicio Fin; lista de valores como alternativa completa.
- **Páginas más visitadas** del periodo.

## Reglas de cálculo (`stats.php`)

- Día = calendario de Guatemala (UTC−6), igual que el contador. Los registros usan `users.created_at` llevado a ese calendario.
- Los periodos son **días completos que terminan ayer**. Hoy solo aparece en su tarjeta y como barra rayada.
- Los visitantes distintos de un periodo o de una semana los cuenta la base sobre todo el rango; no son la suma de los días.
- Los días anteriores al inicio del contador son «sin datos», nunca cero. Un periodo más largo que la historia informa cuántos días tienen datos.
- La comparación solo aparece si los N días anteriores están completos y medidos. La temporada no se compara.
- Semanas: bloques de siete días contados hacia atrás desde ayer; el más antiguo, si queda recortado por el inicio del contador, se marca parcial.
- El primer día del contador (7/oct/2026) empezó por la tarde, así que ese día está medido solo en parte aunque cuente como día con datos.

## Archivos

`panel.php` (página y decisión de acceso), `panel-api.php` (cifras en JSON, solo GET), `stats.php` (biblioteca, denegada en `.htaccess`), `panel-model.js` (reglas de presentación puras), `panel.js`, `panel.css`. `accounts.php` ganó `smash_account_resume` y `smash_account_current`, compartidas con `account-api.php`.

## Pruebas

- `php scripts/database/test_stats.php`: periodos, distintos, redes, páginas, registros por día de Guatemala, semanas, comparación y rol.
- `python scripts/database/test_panel_http.py`: anónimo 401, otra cuenta 403 sin pistas, dueño 200 con agregados, sesión recordada, y pérdida de acceso al quitar el rol o revocar la conexión.
- `node --test scripts/smash/test_panel.cjs`: fechas, barras, teclado, comparación, aviso de historia corta, eje y páginas.
- Navegador contra copia local con base desechable y 45 días inventados: escritorio y 375 px, los cuatro periodos, gráfica, lista, estado del primer día y «Sin acceso»; sin errores de consola ni desbordamiento.

## Fuera de alcance

Exportaciones, alertas, metas, país, dispositivo, fuente de tráfico, tiempo en página y datos por visitante. No se recogen.

## Lista de registros (10/oct/2026)

Las cifras de registros de hoy, ayer, periodo, día/semana seleccionados y la lista de valores son botones. «Cuentas registradas» abre todas, incluso las anteriores al contador. La lista usa los componentes existentes, indica el total, muestra 50 por petición y ofrece «Ver más». Orden: `users.created_at DESC, users.id DESC` (el desempate es interno). Vacío: «Nadie se registró en este periodo». Enter/Espacio, `aria-expanded`, foco en el encabezado y cierre/Escape de vuelta al botón. Cambio de periodo/gráfica cancela la petición pendiente y cierra el detalle; un error conserva las filas y el total para reintentar el mismo lote.

Contrato privado de `panel-api.php`:

- GET normal conserva `report`/`csrf`; añade `registrationSnapshot`, token aleatorio de 32 caracteres, sin codificar IDs. `report.yesterday`, cuando existe, añade `registrations`.
- GET `?registrations=all|today|yesterday|7|30|90|season|YYYY-MM-DD_YYYY-MM-DD&snapshot=<token>&offset=0`. Los rangos por fecha se aceptan solo si pertenecen a un día/semana del reporte. `day` opcional ancla el calendario para consultas directas sin snapshot; no admite días futuros ni fechas inválidas. El panel siempre usa el snapshot del reporte.
- Respuesta: `{ok:true, registrations:{total, items:[{tag,registeredAt,linked}], nextOffset}}`. Tamaño fijo 50; `nextOffset` nulo al terminar. `registeredAt` ISO con segundos y `-06:00`; se presenta sin reinterpretarlo en la zona del navegador. `tag` sale de `players.tag`; sin jugador/tag: «Cuenta sin jugador vinculado». `linked` exige una conexión OAuth no revocada; se muestra vinculada/desvinculada.
- No envía IDs de cuenta/start.gg/jugador, display_name, correo, IP, sesión, token OAuth ni pagos. Solo `smash_stats_is_owner` después de revalidar la sesión; 401/403 idénticos a los actuales, también para peticiones con parámetros o si se revoca rol/conexión. GET de estadísticas con `no-store, private` y noindex; no es un endpoint público.
- Intervalos iguales a `smash_stats_registrations`: límite UTC desde las 06:00 del primer día, exclusivo a las 06:00 del día siguiente al último. Los periodos largos conservan el recorte al inicio del contador, terminan ayer; la tarjeta total no lo aplica. El reporte y las listas comparten `smash_stats_registration_scopes`.
- Reporte y cada página se leen en transacción **REPEATABLE READ / READ ONLY**. La sesión privada guarda solamente límites (máximo ID interno y rangos de calendario), nunca filas/listas: máximo cinco snapshots, 30 minutos. Nuevas cuentas no desplazan las páginas ni cambian las cifras de un reporte abierto, incluso al pasar medianoche. El estado de vinculación/tag se consulta al abrir cada lote. Al vencer o salir un reporte de esos cinco, 400 `registration_snapshot_expired`: la pantalla ofrece «Actualizar datos». Una consulta directa sin snapshot obtiene límites actuales; para paginar un reporte estable se usa su token. Una eliminación administrativa de cuentas/edición manual de fechas requiere refrescar el reporte; no existe esa operación en el flujo normal de la cuenta.
- Solo SELECT en este módulo; sin migraciones, escrituras del contador/cuentas, consultas a start.gg ni listas en localStorage/caché compartida. La reanudación de sesión mantiene su comportamiento previo.

Pruebas con filas inventadas: paridad cifra/lista en todos los periodos, días y semanas, medianoche GT 05:59:59/06:00 UTC, sin jugador, conexión revocada, vacío, 50+5, empate por fecha, proyección cerrada, parámetros inválidos, snapshot falsificado/vencido, y nueva cuenta posterior al reporte que no entra en su lista. Revisión local real PHP/SQL a 375 y 1280 px, lista completa/semanal/vacía, paginación, error/reintento y teclado.
