# Encargo para Codex — captura de próximos torneos de Guatemala

Fecha: 9 de octubre de 2026. Fase nueva pedida por el dueño: una agenda pública de torneos por venir. Esta tarea es **solo la captura y el archivo de datos**; la pantalla espera el diseño de Claude Design ([brief](BRIEF-CLAUDE-DESIGN-TORNEOS.md)) y la hará Claude Code.

## Qué hacer

1. **Captura** (`scripts/smash/agenda.py`, reutilizando `Client` de `collect.py`): torneos de Super Smash Bros. Ultimate (videojuego 1386) con `countryCode: "GT"` cuya fecha de inicio es futura, más los online organizados desde Guatemala si start.gg permite distinguirlos. Revisa el esquema vigente de start.gg antes de fijar la consulta; no asumas campos.
2. **Por torneo:** id, nombre, slug y URL, `startAt`, `endAt`, zona horaria, ciudad, estado o departamento, nombre y dirección del lugar, latitud y longitud, si es online, si la inscripción está abierta, `registrationClosesAt`, número de inscritos, y sus eventos de Ultimate (nombre, tipo singles/dobles, inscritos). Lo que start.gg no dé va en `null`, nunca en cero ni en texto inventado.
3. **Archivo público** `ranking-smash-ultimate/data/agenda.json`: versión de esquema, `generatedAt`, y la lista ordenada por fecha. Sin identificadores de personas, sin dueños ni contactos, sin lista de inscritos.
4. **Publicación:** un flujo programado propio (propón frecuencia; una vez al día parece suficiente) que capture, valide y suba **solo** `agenda.json` de forma atómica, sin tocar `public.json`, el ranking ni la carga SQL. Debe compartir el grupo de concurrencia de los flujos que usan FTP. Si la captura falla o sale vacía por un error, se conserva el archivo anterior.
5. **Validación** antes de subir: fechas con zona, URL solo de `start.gg`, coordenadas dentro de rango, tamaño acotado, y que un torneo ya empezado no aparezca como próximo.
6. **Cuota de start.gg:** mide cuántas consultas cuesta y déjalo en el informe. No consultes la API en cada visita.

## Límites

- No cambies `discover.py`, el cálculo, la elegibilidad ni `public.json`.
- Un torneo futuro no se excluye por las reglas de admisión del ranking: todavía no tiene asistencia. Solo marca en un campo si es presencial de singles (candidato a contar).
- Sin tabla SQL por ahora: la agenda es un archivo estático. Si ves una razón para guardarla en la base, déjala como propuesta.
- Nada de mapas ni geocodificación con servicios externos.

## Entrega

Una PR en rama propia desde `main`, con pruebas (captura con cliente simulado, validación, publicación con FTP simulado), una ejecución real de solo lectura que diga cuántos torneos próximos hay hoy, y `EN-CURSO.md` actualizado. No fusiones ni despliegues sin la orden del dueño.
