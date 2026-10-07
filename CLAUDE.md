# Continuidad del proyecto

Repositorio del ranking Smash GT (Smash Ultimate Guatemala). Dominio: `rankingsmashbros.com`. Se separó de `Bucaro-19/rsvp-graduacion` el 6 de octubre de 2026 conservando el historial de Smash.

Leer primero `docs/smash/CONTEXTO.md`, `docs/smash/EN-CURSO.md`, `docs/smash/MIGRACION.md` y `docs/smash/BASE-DE-DATOS.md`. El estado de ejecución cambia: confirmar rama, diff y GitHub Actions antes de continuar.

El diseño entregado por el propietario (`design_handoff_smash_gt_ranking/`) es referencia, no código productivo, y no se versiona. No portar `support.js` ni el dataset de ejemplo.

## Diseño de pantallas (instrucción del dueño)

Cualquier pantalla nueva debe pedirse primero a **Claude Design**. No diseñarla ni implementarla sin ese handoff. Preparar el brief de funciones, estados, datos disponibles y comportamiento móvil, entregárselo al dueño para solicitar el diseño, y luego implementar la referencia recibida. El trabajo de backend, importación y conexión puede continuar sin pantalla nueva.

Para continuidad en Claude Code, leer también `docs/smash/SIGUIENTE-FASE.md`. Mantener el estado de instalación, pruebas, commits y pendientes actualizado; distinguir confirmación del dueño de verificación directa.
