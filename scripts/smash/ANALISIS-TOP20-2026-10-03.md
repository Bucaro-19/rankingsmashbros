# Top 20 y constancia: estudio para revisión comunitaria

Elaborado el 3 de octubre de 2026. Corte del 2 de octubre de 2026, 16:33 Guatemala. Método BT-PILOTO-3. **No cambia el ranking ni adopta bonos.**

## Conclusión propuesta

Priorizar la comparabilidad entre rivales locales e internacionales antes de añadir un premio de asistencia. Mantener el piloto identificado como experimental y reconocer la constancia mediante meses y torneos visibles, separados de los puntos. Si se prefiere un bono, discutir y validar las dos simulaciones antes de aprobarlo.

## Hallazgos

- La base reproduce exactamente los 188 clasificados, 42 eventos y 7,526 sets del corte publicado.
- ShinyMark tiene 17–6 contra Schatzally. Con todos los resultados queda #2; al retirar juntos los tres eventos extranjeros pasa a #1 y Schatzally a #2. Ninguna retirada individual de un torneo invierte estos dos puestos. La estabilidad ante retiradas individuales no certifica que el modelo compare bien ambas escenas.
- Solo 2 clasificados tienen sets en los eventos extranjeros incluidos. La cobertura es parcial y el modelo se ajusta conjuntamente sobre sus rivales; no se debe inferir el nivel internacional a partir del puesto nacional ni borrar resultados válidos para obtener un orden esperado.
- El ajuste base alcanzó su tolerancia de 1e-7 en 585 iteraciones. No se detectó un agotamiento del límite numérico en ese ajuste; esto no valida pesos, elegibilidad ni capacidad predictiva.
- NONAME (#14, 3 eventos) oscila entre #9 y #30 al retirar un evento a la vez. Juafe (#16, 2 eventos) deja de cumplir actividad en dos escenarios. Son señales de muestra limitada, no sanciones ni intervalos de confianza.

## Veinte jugadores

Los rangos recalculan toda la red y la elegibilidad al retirar uno de los 42 eventos. Contra top 20 es una medida retrospectiva del mismo corte, no validación externa.

| Puesto | Jugador | Puntos | Torneos | Meses | V–D | V–D vs top 20 | Rango sin un evento | Escenarios sin elegibilidad |
|---:|---|---:|---:|---:|---|---|---|---:|
| 1 | Schatzally | 2518 | 15 | 8 | 88–19 | 50–18 | 1–1 | 0 |
| 2 | ShinyMark | 2460 | 15 | 9 | 95–12 | 48–6 | 2–2 | 0 |
| 3 | Crisam | 2356 | 15 | 9 | 77–24 | 40–21 | 3–3 | 0 |
| 4 | Eman | 2340 | 14 | 9 | 64–28 | 31–27 | 4–4 | 0 |
| 5 | Krlos04 | 2300 | 17 | 8 | 78–34 | 32–33 | 5–6 | 0 |
| 6 | Finn | 2285 | 4 | 3 | 25–0 | 8–0 | 5–7 | 0 |
| 7 | Delisaster. | 2236 | 10 | 8 | 45–14 | 12–13 | 6–7 | 0 |
| 8 | DragonSlayer | 2213 | 7 | 6 | 32–14 | 8–12 | 8–8 | 0 |
| 9 | Nepeta | 2112 | 16 | 9 | 55–30 | 12–24 | 9–12 | 0 |
| 10 | Hanma | 2095 | 13 | 8 | 47–25 | 9–18 | 9–16 | 0 |
| 11 | Daak.RD | 2092 | 16 | 8 | 60–33 | 5–29 | 10–15 | 0 |
| 12 | Saintts | 2092 | 4 | 4 | 18–8 | 5–5 | 9–16 | 0 |
| 13 | Mejia | 2090 | 3 | 3 | 12–6 | 2–6 | 10–17 | 0 |
| 14 | NONAME | 2088 | 3 | 2 | 10–6 | 2–5 | 9–30 | 0 |
| 15 | Bomber | 2063 | 8 | 8 | 30–15 | 6–10 | 9–17 | 0 |
| 16 | Juafe | 2063 | 2 | 2 | 12–4 | 0–4 | 14–17 | 2 |
| 17 | AnderWebos | 2032 | 14 | 8 | 45–28 | 7–21 | 15–19 | 0 |
| 18 | Rom | 2016 | 16 | 9 | 50–34 | 5–26 | 17–20 | 0 |
| 19 | CASSLER | 2012 | 5 | 3 | 26–9 | 3–5 | 17–27 | 0 |
| 20 | Isaac | 1991 | 4 | 4 | 22–7 | 1–3 | 18–28 | 0 |

## Opciones de constancia

Los bonos usan las puntuaciones publicadas, conservan desempates y reordenan a los 188 clasificados. No reentrenan el modelo. Sus coeficientes son hipótesis de sensibilidad, no valores calibrados.

| Opción | Regla | Cambian puesto | Máximo cambio | Entradas top 100 | Entradas top 20 |
|---|---|---:|---:|---|---|
| Sin bono | 0 puntos extra | 0 | 0 | Ninguna | Ninguna |
| Por torneos | 5 × torneos adicionales después del segundo; tope 30 | 114 | 10 | tilin | Praider |
| Por meses | 10 × meses activos adicionales después del segundo; tope 30 | 123 | 10 | tilin | Praider |

Un mes activo tiene al menos un set válido en un evento admitido, con fecha local de Guatemala. Ni el bono por torneos ni el bono por meses exige ganar: ambos pueden premiar solo asistencia. Los meses reducen la acumulación de eventos en una semana, pero siguen dependiendo de acceso, costo y fecha de entrada a la temporada. Un máximo de 30 limita puntos, no limita a un número fijo de puestos.

## Explicación de victorias y derrotas

Para una fuerza hipotética de 1800 puntos, un rival de 2000 da una probabilidad logística de victoria aproximada de 24%; uno de 1600, de 76%. Ganar al primero aporta más evidencia positiva y perder contra el segundo más evidencia negativa, a igual peso y repetición. No son puntos fijos ni probabilidades calibradas. El ajuste conjunto, el valor de eventos y los rivales repetidos impiden convertirlo en una tabla exacta de +X/−Y por set.

## Antes de cambiar reglas

1. Revisar cómo se conecta el contexto extranjero al local, sin excluir viajes o resultados por conveniencia.
2. Separar una evaluación temporal: ajustar con un corte anterior y evaluar resultados posteriores, evitando usar el mismo resultado para estimar al rival y medir acierto.
3. Revisar cobertura de torneos por región, perfiles de nacionalidad pendiente y participantes que compiten solo fuera.
4. Consultar si constancia significa asistencia, rendimiento sostenido o reconocimiento separado. El formulario público existente acepta comentarios sin cuenta.
5. Solo tras decidir, anunciar regla, versión y temporada; mantener cortes comparables.

## Reproducción y referencia

`study_top20.py` exige coincidencia exacta con el corte publicado antes de generar escenarios. Las fichas públicas incluyen el registro de torneos, rivales y escenarios con mayor cambio. Los cálculos se quedan en el repositorio privado; la página publica resultados y una explicación.

Referencia general: [Turner y Firth, Bradley-Terry Models in R (2012)](https://www.jstatsoft.org/article/view/v048i09). Los coeficientes del piloto y de estas propuestas son propios de Smash GT, no de ese artículo ni de UltRank.
