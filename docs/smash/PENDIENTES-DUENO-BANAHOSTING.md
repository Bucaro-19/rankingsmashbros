# Para cuando estés frente a la computadora — BanaHosting

Actualizado: 7 de octubre de 2026. Esta es tu lista práctica; el detalle técnico está en [CARGA-SEMANAL-SQL.md](CARGA-SEMANAL-SQL.md).

## Qué ya está hecho

El sitio, las cuentas OAuth, la base y el primer corte están funcionando. El código para recibir y cargar los cortes semanales ya está publicado. La clave de sincronización está preparada en tu Mac y guardada también en GitHub Secrets. **No necesitas crear otra clave ni ejecutar otra vez `install.sql`.**

La automatización SQL todavía está desactivada: el 7/oct se comprobó `SMASH_SQL_SYNC_ENABLED=false` y el servidor respondió `sync_not_configured`. Faltan el archivo privado en el hosting, la tarea de cPanel y la prueba completa. El ranking público sigue disponible.

## 1. Subir un archivo desde tu Mac

- [ ] Abre en Finder la carpeta del proyecto `rankingsmashbros`, luego `docs/smash/config/`.
- [ ] Localiza **`sync.local.php`**, sin `.example` al final. Ya contiene la clave correcta; no hace falta editarlo. Es un archivo local ignorado por Git, por eso no aparece al descargar el repositorio desde GitHub.
- [ ] En BanaHosting → cPanel → File Manager, entra a **`/home/ivcjgjlk/private-smash/`**. Es la carpeta privada que usamos para la base y OAuth, al mismo nivel que `rankingsmashbros.com`.
- [ ] Sube `sync.local.php` allí. La ruta final debe ser **`/home/ivcjgjlk/private-smash/sync.local.php`**. No lo subas dentro del dominio ni de `public_html`.
- [ ] En Permissions, pon **600**: lectura y escritura solo para el propietario. Si ya hay un archivo con ese nombre, comprueba antes si este paso ya se hizo; no reemplaces una configuración activa por rutina.

No copies la clave al chat, al archivo `.example` ni a comandos. Si el archivo local falta, avisa al agente para recuperarlo o coordinar una rotación en ambos destinos; no inventes una clave distinta solo en cPanel.

## 2. Comprobar PHP desde Terminal de cPanel

Estos comandos van en **cPanel → Terminal**, no en Terminal de la Mac. Ejecútalos uno por uno:

```sh
command -v php
```

```sh
php -v
```

```sh
php -r 'foreach (["mbstring", "pdo_mysql", "zlib"] as $extension) { echo $extension . ": " . (extension_loaded($extension) ? "OK" : "FALTA") . PHP_EOL; }'
```

Necesitamos PHP **8.1 o superior** y las tres extensiones en `OK`. Conserva la ruta que dé el primer comando. Antes se observó PHP 8.1.34 en cPanel, pero hay que confirmar el binario CLI que ejecutará el cron.

Si alguna extensión falta o PHP es anterior, comparte únicamente esta salida para corregir la ruta/configuración antes de seguir. No ejecutes `env`, ni muestres los archivos privados.

## 3. Ejecutar el procesador una vez

Si el paso anterior está correcto, ejecuta en la misma Terminal:

```sh
php -d memory_limit=512M /home/ivcjgjlk/rankingsmashbros.com/ranking-worker.php
```

Si aún no hay trabajos, esperamos algo parecido a:

```json
{"ok":true,"status":"idle","peakMemoryBytes":123456}
```

El número de memoria es ilustrativo y puede variar. `idle` significa que conectó y no tiene trabajos pendientes; **todavía no demuestra que una carga real funciona**. Si hay un trabajo pendiente puede procesarlo. Comparte la línea JSON de salida, que el script prepara sin credenciales. Si devuelve `ok:false`, detente antes de crear el cron y comparte solo el motivo.

## 4. Crear la tarea en cPanel

- [ ] Entra a **cPanel → Cron Jobs / Trabajos de cron**.
- [ ] Revisa si ya existe una tarea para `ranking-worker.php`; queremos una sola.
- [ ] Selecciona **cada cinco minutos**. Los campos son minuto `*/5`, hora `*`, día `*`, mes `*`, día de semana `*`.
- [ ] Si `command -v php` confirmó **`/usr/local/bin/php`**, usa este comando:

```sh
/usr/local/bin/php -d memory_limit=512M /home/ivcjgjlk/rankingsmashbros.com/ranking-worker.php >> /home/ivcjgjlk/private-smash/ranking-worker.log 2>&1
```

Si obtuviste otra ruta, usa **esa ruta comprobada** en lugar de `/usr/local/bin/php`. No pegues el ejemplo sin confirmar qué PHP ejecuta.

El cron revisa la cola de importación. **No consulta start.gg ni recalcula el ranking cada cinco minutos.** El cálculo y la publicación siguen previstos para cada domingo a las 00:00 de Guatemala; GitHub puede retrasar el disparo.

- [ ] Guarda la tarea y comparte su horario/comando y la salida del paso 3. Nada de claves.

## 5. Lo que hará Codex o Claude Code después

Puedes avisar: «Ya subí el archivo, PHP y extensiones están correctos y creé el cron», junto con las salidas anteriores. El agente puede hacer lo siguiente desde tu proyecto; **no necesitas ejecutar comandos con claves**:

1. Leer la clave local solo en memoria y ejecutar el diagnóstico autenticado con `scripts/database/publish_sql.py diagnostic`. Comprobar PHP web y que la carpeta privada se pueda escribir.
2. Enviar el paquete original del corte del 4/oct, ya importado, y esperar a que lo procese **el cron de BanaHosting**. La respuesta final debe ser `sql_synchronized`; la importación debe reconocer `already_imported`.
3. Verificar que el trabajo terminó correctamente y no se duplicaron cortes ni posiciones. Medir los recursos del worker en el servidor.
4. Solo tras esa prueba, activar la variable de GitHub **`SMASH_SQL_SYNC_ENABLED=true`**. El secreto `SMASH_SQL_SYNC_KEY` ya existe; no hace falta volver a pegarlo.
5. Documentar la evidencia y comprobar el próximo corte nuevo. El primer disparo semanal previsto es el domingo **11/oct/2026**; aún no está verificado.

No actives tú la variable antes de esa prueba. Web y SQL no se publican en una sola transacción: si falla la importación después de publicar, SQL conserva su último corte y el agente debe reparar/reintentar la carga. No se deben borrar cortes para arreglarlo.

## Relevo técnico para el agente

- Leer primero AGENTS.md, EN-CURSO.md y el bloque vigente de CARGA-SEMANAL-SQL.md. Las propuestas antiguas de `launchd` o del importador Python en hosting son antecedentes.
- Configuración privada local: `docs/smash/config/sync.local.php`, ignorada/600. No imprimir ni versionar su contenido. Debe coincidir con el secreto de GitHub.
- Paquete original: hash de fuente `ecb1d4a5cd44f87250537a85d0d166fa6f9824ff3408f0b55c98ac6102fd9e45`. Puede seguir en `/tmp/smash-ranking-package.json`; confirmar existencia y contrato. Si falta, recuperar el original; no recapturar mains para el mismo corte ni enviar una variante.
- Antes de escribir, comprobar que `public.json` sigue siendo el corte correspondiente. Si cambió mientras esperábamos, revisar la secuencia de cortes/paquetes antes de enviar nada.
- Diagnóstico HMAC y envío usando entorno del subproceso; nunca pasar la clave en argumentos, archivos versionados o salida. `publish_sql.py` ya limita los datos impresos.
- Verificar primero con el cron real y luego activar; ejecutar el worker manualmente no demuestra que el cron esté funcionando. No afirmar que el próximo disparo programado ya ocurrió.
- El despliegue FTP actual solo accede a la carpeta del sitio; no puede subir esta configuración privada ni crear el cron. No existe acceso SSH configurado. Estos son los pasos que requieren al dueño en cPanel.
- Ninguna pantalla nueva es necesaria para esta configuración.
