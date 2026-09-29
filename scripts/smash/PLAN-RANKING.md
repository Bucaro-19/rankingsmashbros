# De piloto a ranking nacional verificable

El top 100 publicado es un **piloto**, no un ranking oficial de la comunidad. Su cálculo es reproducible, pero la [auditoría de la captura del 28 de septiembre de 2026](AUDITORIA-PILOTO-2026-09-28.md) encontró cobertura y criterios pendientes. El puesto de una persona no debe corregirse manualmente para que coincida con una expectativa: se corrigen datos y reglas generales, se vuelve a calcular y se muestra qué cambió.

## Decisiones que deben quedar públicas antes de la primera lista definitiva

1. **Pertenencia a Guatemala.** Propuesta para consulta: nacionalidad guatemalteca y al menos un set válido en un evento presencial de Guatemala durante la temporada. El segundo requisito ya se comprueba automáticamente. Registrar para cada persona aceptada una fuente y fecha de verificación de nacionalidad, una categoría aplicable y un mecanismo de apelación. El país editable del perfil start.gg solo propone candidaturas. Las cuatro excepciones actuales tienen antecedentes documentados, pero no equivalen a una verificación bajo una regla aún no aprobada. Hasta verificar, la lista continúa como piloto.
2. **Periodo y frecuencia.** Primera temporada: año calendario 2026, desde el 1 de enero hasta el corte local indicado en cada publicación. Recalcular los domingos a medianoche de Guatemala. Congelar un corte final de 2026 después del 31 de diciembre y conservarlo al abrir 2027; definir plazo de correcciones y política de cambios retroactivos.
3. **Eventos válidos.** Publicar mínimos por asistencia *activa* o puntos, reglas para semanales, invitacionales, dobles, Squad Strike, online, eventos de exhibición y DQ. Cada inclusión/exclusión debe tener ID de evento, fuente, motivo y fecha. Revisar especialmente los 23 eventos locales y los tres extranjeros actuales; no asumir que todo singles presencial de 32 personas sirve.
4. **Muestra mínima por jugador.** Determinar eventos y sets exigidos, y cómo representar la incertidumbre por poca actividad. El corte actual de dos eventos y cuatro sets deja a 54 del top 100 con tres eventos o menos y a 17 con menos de diez sets. La regla debe fijarse antes de mirar a quién beneficia. Si no hay 100 personas que cumplan, publicar menos puestos en lugar de completar la lista con candidaturas débiles.
5. **Método de puntuación.** Publicar versión, fórmulas, pesos y fuente de valores; decidir si se quiere un ranking de rendimiento de temporada o una estimación de fuerza actual. No llamarlo “fórmula de UltRank”: el [documento de UltRank](https://docs.google.com/document/d/1dC5oJaRfXITqlVMG8w6uZ1KGVjWxshbNqQzRD6zSXE8/edit) describe componentes, pero no todos los coeficientes, y el [repositorio público](https://github.com/kenniky/ultrank-scoring) calcula principalmente el valor de eventos.
6. **Gobernanza.** Definir quién puede revisar perfiles y torneos, cómo se registran cambios, cuánto dura el plazo de objeciones y quién resuelve discrepancias. Una persona puede mantener el código, pero las decisiones editoriales que afectan a jugadores necesitan un registro visible.

## Trabajo técnico para cumplirlas

- Completar el padrón de candidatos con ID estable de jugador y alias históricos. Permitir que se propongan personas que solo juegan en el extranjero y verificar que sus torneos entren por el mismo criterio. Comparar el catálogo con listas de organizadores y torneos públicos para detectar eventos sin país o mal etiquetados.
- Crear un registro de eventos candidatos y decisiones. Guardar capturas originales, resultados válidos, DQ, motivo de descarte y versión de la tabla TTS. No publicar una actualización si la importación es parcial.
- Comparar variantes del método con pruebas fuera de muestra por fecha y sensibilidad al quitar un evento, cambiar ponderaciones y revisar enfrentamientos repetidos. Evaluar con métricas predictivas y estabilidad del top, no escogiendo el orden que favorezca a un jugador. El [informe de auditoría](AUDITORIA-PILOTO-2026-09-28.md) ya permite repetir la prueba de quitar los eventos extranjeros.
- Mostrar en la web, para cada edición, periodo, fecha de datos, reglas, torneos incluidos, sets válidos, mínimo de actividad, base de elegibilidad y cambios desde la edición anterior. Conservar ediciones congeladas y un formulario o canal para correcciones.
- Repetir periódicamente la verificación del flujo de importación, cálculo y despliegue. La ejecución completa del 29 de septiembre de 2026 terminó correctamente: 26 eventos, 6,739 sets válidos y archivo público actualizado por FTP. Esto valida el transporte y la captura de ese corte, no la política editorial de un ranking definitivo.

## Criterio de salida

La primera edición definitiva requiere: política de pertenencia y periodo aprobados; lista de eventos revisada; candidatos del extranjero buscados; método documentado y evaluado; cada puesto trazable hasta resultados; y correcciones y apelaciones definidas. La publicación completa ya fue verificada para el piloto. Hasta cumplir lo demás, la etiqueta **piloto** debe permanecer visible.

Para reproducir la auditoría con la captura privada ya descargada:

```sh
python3 scripts/smash/audit.py scripts/smash/data/combined.json scripts/smash/curation.json scripts/smash/AUDITORIA-PILOTO-2026-09-28.md --points-csv scripts/smash/data/ultrank_players.csv
```

Las capturas y la tabla TTS descargada están en `scripts/smash/data/` (ignorado por Git). El informe versionado corresponde exactamente al corte que indica su título; una captura nueva exige regenerarlo y revisar las diferencias.
