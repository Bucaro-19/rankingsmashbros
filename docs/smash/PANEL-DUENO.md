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

Todo sale de las tablas del contador (VISITAS.md) y de `users` / `oauth_connections`. Solo agregados: nunca una lista de visitantes, redes o cuentas.

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

Exportaciones, alertas, metas, país, dispositivo, fuente de tráfico, tiempo en página y datos por persona. No se recogen.
