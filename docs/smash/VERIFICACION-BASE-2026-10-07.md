# Verificación directa de la base de producción — 7 de octubre de 2026 (Claude Code)

Archivo aparte para no chocar con el PR #4 abierto de Codex. Integrar estos datos en `BASE-DE-DATOS.md` y `EN-CURSO.md` cuando ese PR se fusione.

## Qué se consultó (solo lectura, desde la Mac del dueño)
- Motor: `11.4.13-MariaDB-cll-lve-log`. Base `ivcjgjlk_smash`.
- 31 tablas, todas InnoDB y `utf8mb4_unicode_ci`. El charset por defecto de la base es `latin1_swedish_ci`: una tabla nueva creada sin `DEFAULT CHARSET` saldría en latin1; declararlo siempre en las migraciones.
- `schema_migrations`: `001_accounts_competition`, instalada 2026-10-07 05:15:05 UTC.
- `characters`: 87 filas; acentos guardados en UTF-8 correcto (comprobado por HEX en "Pokémon Trainer"). Las otras 29 tablas están vacías.
- Usuario `ivcjgjlk_admin`: `ALL PRIVILEGES` sobre `ivcjgjlk_smash.*`, nada más.

Esto confirma lo que `SIGUIENTE-FASE.md` daba como "esperado, no verificado en producción" (31 tablas / 87 selecciones). No verifica la conexión de PHP desde el hosting: eso es el PR #4.

## Cómo quedó el acceso
- SSH no disponible: el puerto 21098 sugerido no responde, tampoco 22/2222/2200/1157/7822; la Terminal de cPanel es una jaula sin `sshd_config` ni `ss`. No se hizo escaneo de puertos. Sin túnel.
- MySQL remoto directo: puerto 3306 de `bh8932.banahosting.com` abierto. El dueño autorizó en cPanel → Remote MySQL la IP `190.14.141.191` (su Mac; es IP residencial y puede cambiar; no usar `%`).
- En la Mac del dueño: `~/.my.cnf` (permisos 600, contraseña escrita por él, no está en ningún repo ni chat) y cliente en `/opt/homebrew/opt/mysql-client/bin/mysql` (no está en el PATH). Un agente en esa Mac puede ejecutar ese binario sin argumentos de conexión.
- GitHub Actions NO tiene acceso a la base (IP no autorizada) y debe seguir así; el importador de cortes necesita la vía que define `SIGUIENTE-FASE.md`.

## Cuidado
Esa conexión tiene permisos de escritura sobre producción. Usarla para lectura y diagnóstico; cualquier cambio de esquema va por migración versionada en el repo, y cualquier escritura de datos necesita visto bueno del dueño.
