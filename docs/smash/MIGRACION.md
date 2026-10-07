# Migración a repo y dominio propios — 6 de octubre de 2026

## Hecho
- Repo `Bucaro-19/rankingsmashbros` creado con el historial de Smash filtrado desde `Bucaro-19/rsvp-graduacion` (solo `ranking-smash-ultimate/`, `scripts/smash/`, `docs/smash/` y los workflows `smash-*`). Los hashes de commit cambiaron; los números de PR de los mensajes (#1–#25) son del repo viejo.
- `deploy.py` y los workflows aceptan dos variables de Actions: `SMASH_FTP_DIR` (carpeta del sitio bajo la raíz del FTP; `.` publica en la raíz; por defecto `ranking-smash-ultimate`) y `SMASH_PUBLIC_URL` (URL base sin barra final; por defecto `https://ingporras.com/ranking-smash-ultimate`).
- El repo viejo sigue publicando en `https://ingporras.com/ranking-smash-ultimate/` cada domingo. Este repo todavía NO publica: no tiene secretos ni `SMASH_SYNC_ENABLED`.

## Falta, en orden
1. Dueño, en cPanel de BanaHosting: agregar `rankingsmashbros.com` como dominio adicional, apuntar el DNS y activar SSL. Anotar la carpeta raíz que cPanel le asigna.
2. Dueño, en este repo (Settings → Secrets and variables → Actions). GitHub no deja copiar secretos entre repos:
   - Secretos: `STARTGG_TOKEN` (aprovechar para rotarlo), `FTP_SERVER`, `FTP_USERNAME`, `FTP_PASSWORD`, `SMASH_FEEDBACK_ADMIN_HASH`.
   - Si la carpeta del dominio queda fuera de la raíz de la cuenta FTP actual, crear una cuenta FTP cuya raíz sea esa carpeta y usar `SMASH_FTP_DIR=.`. Si queda dentro, usar la ruta relativa.
   - Variables: `SMASH_FTP_DIR`, `SMASH_PUBLIC_URL=https://rankingsmashbros.com`. No activar `SMASH_SYNC_ENABLED` todavía.
3. Correr `smash-deploy-snapshot.yml` con `assets_only=false` y verificar `https://rankingsmashbros.com/`: schema 3, 188 clasificados, imágenes, panel, encuesta y `opiniones.php`.
4. Copiar a mano las respuestas de la encuesta del servidor: `ranking-smash-ultimate/feedback-data/` → la carpeta nueva. No están en Git y el despliegue nunca las toca.
5. Activar aquí `SMASH_SYNC_ENABLED=true` y `SMASH_RELEASE_MODE=weekly`; en el repo viejo poner `SMASH_SYNC_ENABLED=false` para que no publiquen los dos.
6. Redirigir `ingporras.com/ranking-smash-ultimate/` al dominio nuevo (`.htaccess`), actualizar enlaces del portafolio y los `ingporras.com` que quedan en pies de página y documentación de este repo.
7. Cuando todo esté verificado, quitar del repo viejo la carpeta, scripts, docs y workflows de Smash.
