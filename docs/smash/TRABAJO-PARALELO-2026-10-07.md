# Trabajo paralelo — 7 de octubre de 2026

## Reparto

Codex completó el paquete privado y el importador transaccional de ranking/historial en PR #9/main e685fb2, con primera carga real y repetición verificadas. Mantiene un checkout separado en `/tmp/smash-ranking-db-import`. No modificar el cálculo ni cambiar el frontend de JSON a SQL todavía. Automatización de la carga SQL semanal sigue pendiente.

Claude Code puede preparar la migración de la encuesta en **otra rama y otro worktree** desde main. No cambiar de rama en el checkout de Codex. Archivos propios: `scripts/database/import_survey.php`, `scripts/database/test_import_survey.php` y `docs/smash/MIGRACION-ENCUESTA.md`. Usar el conector existente sin editar `database.php`. No tocar `schema.sql`, `install.sql`, `opiniones.php`, `encuesta.php`, workflows, importador de ranking ni documentos compartidos de estado en esta primera entrega. Codex actualizará EN-CURSO y SIGUIENTE-FASE; Claude documentará su avance en MIGRACION-ENCUESTA.

## Prompt para Claude Code

> Lee AGENTS.md, CLAUDE.md, docs/smash/{CONTEXTO,BASE-DE-DATOS,SIGUIENTE-FASE,TRABAJO-PARALELO-2026-10-07}. La conexión del hosting ya funciona: MariaDB 11.4.13, 31 tablas, 87 selecciones y schemaReady=true. Codex implementa ranking/historial en otro worktree. En una rama/worktree propios prepara SOLO el importador CLI y las pruebas de la encuesta hacia survey_responses. Fuente: feedback-data/respuestas-2026.php, primera línea guarda PHP y luego líneas JSON. Hash por bytes originales de cada línea, fechas UTC, is_test conservado, validación estricta de opciones/comentarios y repetición sin duplicados. Archivo inválido provoca rollback y un error que indique la línea sin imprimir comentarios privados. Verifica que la misma importación no cambia conteos. No ejecutes migración en producción ni cambies lectura/escritura de la encuesta en esta entrega: entrega PR, prueba con fixtures y documento de respaldo/comparación/transición para revisarlos juntos. No crear pantallas; no imprimir credenciales ni copiar respuestas reales a Git. Archivos asignados: scripts/database/import_survey.php, scripts/database/test_import_survey.php y docs/smash/MIGRACION-ENCUESTA.md. No tocar archivos compartidos ni workflows; deja los comandos para incorporar sus pruebas después.

## Integración

- Claude entrega PR y pruebas con datos inventados; Codex integra los comandos CI al cerrar el importador de ranking. No ejecutar dos migraciones productivas al mismo tiempo.
- La primera fase de Claude prepara código reversible, sin mover respuestas reales ni cambiar la web. Respaldar y comparar el archivo original antes de activar SQL; mantener diseño actual.
- Mains elegidos, OAuth, premium y pantallas nuevas esperan su brief/handoff de Claude Design.
