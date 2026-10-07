# Migración a repo y dominio propios — 6 de octubre de 2026

## Estado vigente — 7/oct

El dominio nuevo está publicado, la encuesta escribe/lee en SQL y la URL anterior ya redirige al nuevo sitio (cierre documentado en MIGRACION-ENCUESTA.md). Conteo final: 13 respuestas de comunidad y 3 de prueba. El primer corte está en SQL; el cargador semanal desde la Mac está preparado, sin tarea automática instalada. Primer semanal del repo nuevo pendiente de verificar el domingo 11/oct. Las secciones del 6/oct siguientes son antecedentes; no repetir hash/FTP/migración ni instalar tablas. Cuentas: CUENTAS-OAUTH.md.

## Hecho
- Repo `Bucaro-19/rankingsmashbros` creado con el historial de Smash filtrado desde `Bucaro-19/rsvp-graduacion` (solo `ranking-smash-ultimate/`, `scripts/smash/`, `docs/smash/` y los workflows `smash-*`). Los hashes de commit cambiaron; los números de PR de los mensajes (#1–#25) son del repo viejo.
- `deploy.py` y los workflows aceptan dos variables de Actions: `SMASH_FTP_DIR` (carpeta del sitio bajo la raíz del FTP; `.` publica en la raíz; por defecto `ranking-smash-ultimate`) y `SMASH_PUBLIC_URL` (URL base sin barra final; por defecto `https://ingporras.com/ranking-smash-ultimate`).
- El repo viejo sigue publicando en `https://ingporras.com/ranking-smash-ultimate/` cada domingo. Este repo todavía NO publica: no tiene secretos ni `SMASH_SYNC_ENABLED`.

## Estado al cierre del 6 de octubre
- Dueño ya hizo: dominio adicional en cPanel (carpeta `/rankingsmashbros.com`, fuera de `public_html`), SSL activo (`https://rankingsmashbros.com` responde 404 con certificado válido: carpeta vacía), cuenta FTP nueva, los 5 secretos, `SMASH_FTP_DIR=.` y `SMASH_PUBLIC_URL=https://rankingsmashbros.com`. Dijo haber copiado `feedback-data/`; comprobarlo tras el primer despliegue.
- Primer intento de despliegue, run `37562021146` de `smash-deploy-snapshot.yml`: falló antes de conectarse al FTP con "Falta el hash de acceso al panel de opiniones o tiene un formato inválido". No se subió nada. El secreto `SMASH_FEEDBACK_ADMIN_HASH` debe ser bcrypt `$2y$` con costo 10–14 (60 caracteres, sin espacios ni salto de línea). Se le dio al dueño: `htpasswd -nBC 12 "" | tr -d ':\n' | pbcopy`. **Pendiente: que lo corrija y relanzar.** El FTP nuevo aún no se ha probado.
- `SMASH_SYNC_ENABLED` no existe en este repo a propósito. El repo viejo sigue publicando en ingporras.com.
- Base de datos para cuentas, agenda y mains: propuesta en `BASE-DE-DATOS.md` y `schema.sql`.

## Publicado en el dominio nuevo (6 de octubre, 20:49 Guatemala)
- Run `37563770354` de `smash-deploy-snapshot.yml` correcto, tras corregir el hash (se había copiado con el `%` que zsh añade al final) y el usuario/contraseña FTP (530).
- Verificado en https://rankingsmashbros.com/: schema 3, corte 2026-10-04T11:43:18, 188 clasificados en ambas vistas, 175 con personaje, imágenes y panel sin errores, `metodologia.html`, `encuesta.php` y `opiniones.php` responden 200, `feedback-data/` responde 403 (protegida, correcto).
- Activadas aquí `SMASH_SYNC_ENABLED=true` y `SMASH_RELEASE_MODE=weekly`. El repo viejo sigue con las suyas: publican a dominios distintos y no chocan. El domingo 11 de octubre es la primera actualización semanal de este repo y la primera prueba real del `STARTGG_TOKEN` nuevo; si falla, se conserva el corte actual.

## Pendientes históricos del 6/oct (consultar el estado vigente arriba)
1. Hecho: panel privado consultado en el dominio nuevo; 12 respuestas reales antes y después de publicar el conector PHP. Encuesta sigue usando su archivo protegido, todavía no SQL.
2. Lunes 12 de octubre: comprobar que el semanal de este repo publicó. Si sí: `SMASH_SYNC_ENABLED=false` en el repo viejo, redirección de `ingporras.com/ranking-smash-ultimate/` al dominio nuevo, actualizar enlaces del portafolio y los `ingporras.com` de pies de página y documentación, y después quitar Smash del repo viejo.
3. Base instalada/conectada y primer corte importado por Codex el 7/oct/2026 (PR #9): MariaDB 11.4.13, 31 tablas, 87 selecciones, cutId=1 publicado y 188 rankings por vista. Encuesta y automatización SQL semanal pendientes; ver BASE-DE-DATOS.md y SIGUIENTE-FASE.md. No reinstalar ni pedir credenciales por rutina.

## Lista original (referencia)
1. (Hecho) Dueño, en cPanel de BanaHosting: agregar `rankingsmashbros.com` como dominio adicional, apuntar el DNS y activar SSL. Anotar la carpeta raíz que cPanel le asigna.
2. (Hecho, salvo el hash) Dueño, en este repo (Settings → Secrets and variables → Actions). GitHub no deja copiar secretos entre repos:
   - Secretos: `STARTGG_TOKEN` (aprovechar para rotarlo), `FTP_SERVER`, `FTP_USERNAME`, `FTP_PASSWORD`, `SMASH_FEEDBACK_ADMIN_HASH`.
   - Si la carpeta del dominio queda fuera de la raíz de la cuenta FTP actual, crear una cuenta FTP cuya raíz sea esa carpeta y usar `SMASH_FTP_DIR=.`. Si queda dentro, usar la ruta relativa.
   - Variables: `SMASH_FTP_DIR`, `SMASH_PUBLIC_URL=https://rankingsmashbros.com`. No activar `SMASH_SYNC_ENABLED` todavía.
3. Correr `smash-deploy-snapshot.yml` con `assets_only=false` y verificar `https://rankingsmashbros.com/`: schema 3, 188 clasificados, imágenes, panel, encuesta y `opiniones.php`.
4. Copiar a mano las respuestas de la encuesta del servidor: `ranking-smash-ultimate/feedback-data/` → la carpeta nueva. No están en Git y el despliegue nunca las toca.
5. Activar aquí `SMASH_SYNC_ENABLED=true` y `SMASH_RELEASE_MODE=weekly`; en el repo viejo poner `SMASH_SYNC_ENABLED=false` para que no publiquen los dos.
6. Redirigir `ingporras.com/ranking-smash-ultimate/` al dominio nuevo (`.htaccess`), actualizar enlaces del portafolio y los `ingporras.com` que quedan en pies de página y documentación de este repo.
7. Cuando todo esté verificado, quitar del repo viejo la carpeta, scripts, docs y workflows de Smash.
