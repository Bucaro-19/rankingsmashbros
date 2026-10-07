# Relevo a Claude Code — siguiente entrega, 7 de octubre de 2026

El dueño encargó a Claude Code continuar el backend y pidió el prompt de Claude Design para ingreso/perfil. Codex no inició estas funciones ni envió mensajes a otra sesión de Claude. Este documento sustituye el encargo limitado de TRABAJO-PARALELO-2026-10-07.md, ya completado.

## Prompt listo para pegar en Claude Code

> Lee AGENTS.md, CLAUDE.md y docs/smash/{CONTEXTO,EN-CURSO,BASE-DE-DATOS,SIGUIENTE-FASE,MIGRACION-ENCUESTA,RELEVO-CLAUDE-CODE-2026-10-07}. Continúa desde main actualizado de Bucaro-19/rankingsmashbros, en una rama propia. PR #10 ya fue revisada y fusionada por Codex: commit 972225d. La siguiente entrega es completar la migración de la encuesta y el panel existentes a SQL, con respaldo, comparación y transición segura. No rehagas el importador ni reinstales tablas. Antes de activar SQL, prepara código, pruebas, protocolo de pausa de envíos, recuperación y documentación; luego ejecuta/publica siguiendo las autorizaciones vigentes del dueño y verifica producción. Si necesitas la Terminal web de cPanel y no puedes operarla, entrega al dueño los comandos exactos sin pedirle contraseñas ni descargar respuestas por una URL pública. Mantén cálculo, public.json, UI actual, autenticación administrativa, CSRF y límite de cinco minutos. No introduzcas doble escritura ni fallback silencioso al archivo cuando SQL falle. Toda pantalla nueva espera el handoff de Claude Design; el brief de ingreso/perfil está en BRIEF-CLAUDE-DESIGN-CUENTAS.md. Al terminar la encuesta, continúa con la preparación del transporte privado para cargar semanalmente el ranking en SQL. No abras MySQL a todas las IP de Actions ni inventes permisos/cuotas de start.gg. Documenta resultados reales, commits, runs, límites y siguiente paso para otro agente.

## Estado confirmado al entregar

- Main `972225d`: PR #10 fusionada. Checks finales de la rama correctos: runs `37582899820` (PR) y `37582895363` (push). Suite nueva confirmada en los logs de `37582761629`: MySQL 8.0.46 y MariaDB 10.11.19, además de SQLite. Codex corrigió el rollback indebido de una transacción previa del llamador.
- Hosting: MariaDB 11.4.13, esquema `001_accounts_competition`, 31 tablas, 87 personajes/selecciones. No reinstalar.
- Ranking ya importado: cutId 1 publicado, corte 2026-10-04T11:43:18.348499Z; 188 puestos por vista, 3435 jugadores de contexto, 43 torneos, 47 eventos, 4498 entrants y 8985 sets. No confundir contexto con guatemaltecos clasificados. Repetición y paridad comprobadas; importador en IMPORTACION-RANKING.md.
- Encuesta: primera copia ejecutada por el dueño con el importador inicial en cPanel. Codex confirmó con SELECT únicamente agregados: 13 filas, 13 hashes distintos, 1 prueba interna (12 respuestas de comunidad). Sin lectura de comentarios durante esa revisión. Reconsultar conteos: pueden llegar respuestas nuevas.
- Encuesta y panel **siguen usando el archivo** `feedback-data/respuestas-2026.php`. SQL es copia; falta repetición real con versión revisada, registrar tamaño/hash del respaldo y verificar valores contra el archivo. Nunca afirmar paridad campo por campo por haber comparado solo conteos.
- Sitio lee JSON. Publicación web semanal activa; carga semanal SQL aún no automática. Actions genera paquete privado pero no tiene acceso remoto a la base. Users=0 al último corte; no existe OAuth ni cuentas reales.

## Entrega inmediata: encuesta y panel en SQL

1. Revisar el escritor actual en encuesta.php, el lector en opiniones.php, database.php, import_survey.php, allowlist/orden del despliegue y las pruebas HTTP. Preparar servicio compartido de encuesta si mejora la separación, con consultas parametrizadas, UTC/utf8mb4, errores saneados y tratamiento de NULL como texto vacío.
2. Conservar opciones, validación, honeypot, nonce, cookies seguras y límite de cinco minutos. Marcar sesión guardada/rotar nonce solo después de confirmar la escritura. Si falla SQL, mostrar error y permitir reintento; no registrar éxito ni escribir en una segunda fuente. Evitar duplicados por reintentos según un contrato documentado, sin guardar IP/correo.
3. El panel conserva contraseña/sesión administrativa vigente, exclusión de is_test, orden, agregados y escape HTML de comentarios/enlaces. No exponer respuestas mediante un endpoint público. Contemplar errores de lectura sin simular una encuesta vacía.
4. Pruebas con datos inventados: envío y lectura reales sobre motores desechables, privacidad anónima, CSRF, límite de sesión, fallo de DB sin éxito falso, repetición/reintento sin duplicar y preservación de la UI/datos actuales. Mantener CI existente, no conectar pruebas a producción.
5. Protocolo de transición: pausa controlada y breve de envíos, esperar escrituras en curso, respaldo fechado con tamaño/hash, importación final con herramienta revisada y repetición, comparación fila por fila sin imprimir respuestas, cambio de fuente de escritura/lectura, verificación y reapertura. FTP no cambia dos PHP de forma atómica; el mecanismo de pausa debe cubrir todo el intervalo. No eliminar archivo/respaldo.
6. Recuperación: si falla antes de aceptar respuestas SQL, conservar el archivo como fuente y resolver; si ya hubo respuestas nuevas SQL, no volver al archivo sin reconciliarlas. Definir el procedimiento antes de desplegar.
7. PR/checks/merge, despliegue solo de archivos permitidos y QA del panel existente. Si se crea una respuesta de prueba real, acordar su identificación is_test para que no altere las opiniones de comunidad. Actualizar EN-CURSO, SIGUIENTE-FASE y MIGRACION-ENCUESTA con evidencia y pendientes.

## Accesos existentes y límites

- Mac: `/opt/homebrew/opt/mysql-client/bin/mysql` usa la configuración privada ya provista en `~/.my.cnf`. No leer/imprimir/copiar ese archivo ni pasar contraseñas como argumentos. Producción: usar SELECT para verificar; escrituras solo dentro del alcance autorizado y con transacción. Detalle en BASE-DE-DATOS.md.
- Servidor: `/home/ivcjgjlk/private-smash/config.local.php`, fuera del sitio; no abrir ni publicar. Importador inicial y respaldo están en private-smash según MIGRACION-ENCUESTA.md. Actualizar el importador privado antes de repetir; no desplegar scripts/docs al document root.
- No hay SSH. El dueño ya usó Terminal web de cPanel. Una sesión puede vencer; no reutilizar contraseñas del chat ni extraer cookies.
- Claude puede actualizar ahora encuesta.php, opiniones.php, servicio/CI/docs necesarios: la restricción de tres archivos del encargo paralelo anterior correspondía solo a la primera entrega.

## Después: carga semanal SQL y cuentas

- Diseñar transporte privado/autenticado compatible con BanaHosting, validación de tamaño/hash, prevención de replay, ejecución idempotente y conservación del último corte ante fallo. No aceptar destinos arbitrarios, secretos en query strings o paquetes accesibles públicamente. Evitar que la sincronización de torneos en vivo reescriba cortes publicados.
- Concretar las pruebas/operación antes de activar el automatismo. El calendario sigue domingo 00:00 Guatemala; consultar variables y ejecuciones actuales.
- El dueño recibe el brief de Claude Design para ingreso/perfil/edición de mains. Esperar su handoff para pantallas nuevas. OAuth se implementará con IDs verificados, state/CSRF, sesiones, tokens protegidos y permisos reales; una selección de rol no otorga permisos de organizador en start.gg.
- Historial/rank desde base/caché, sin consultas API por cada visita. Pendientes posteriores: top 15 por organizador con atribución definida, agenda/torneo activo, propuestas de resultados y avisos. No prometerlos como ya implementados.

