# Cobertura de torneos e historial del jugador — 1–2 de noviembre de 2026 (Claude Code)

Encargo del dueño: recuperar los torneos que la búsqueda de start.gg omite y que una cuenta vea sus participaciones verificadas aunque no cuenten. **No es un puesto manual para nadie**: el caso que lo destapó (pinguis, jugador 5551493) sirve de prueba y sigue sin puesto.

## Causa comprobada

| Evidencia | Run | Resultado |
|---|---|---|
| Historial público | [41392168416](https://github.com/Bucaro-19/rankingsmashbros/actions/runs/41392168416) | La interfaz dice «No Events», pero `player.sets` devuelve 13 sets en cuatro eventos de tres torneos |
| Metadatos por ID | [41392236930](https://github.com/Bucaro-19/rankingsmashbros/actions/runs/41392236930) | 947356, 948197 y 957669: GT, presenciales, Ultimate, terminados |
| Filtros de búsqueda | [41392406064](https://github.com/Bucaro-19/rankingsmashbros/actions/runs/41392406064) | `ids` solos: 3; con `countryCode:"GT"`: 0; con `videogameIds:[1386]`: 0; ambos: 0 |
| Activos y clasificación | [41392499626](https://github.com/Bucaro-19/rankingsmashbros/actions/runs/41392499626), [41392594117](https://github.com/Bucaro-19/rankingsmashbros/actions/runs/41392594117) | 38, 18 y 30 activos; sets de pinguis válidos y por DQ |
| Búsqueda por organizador (Claude Code) | [41393251710](https://github.com/Bucaro-19/rankingsmashbros/actions/runs/41393251710) | Los tres son del organizador 2735916, que ya está en el catálogo; `ownerId` solo, con juego o con país devuelve 4/3/4 torneos y **ninguno** de los tres |
| Lista del perfil del organizador | [41393303571](https://github.com/Bucaro-19/rankingsmashbros/actions/runs/41393303571) | `user.tournaments` devuelve 18 torneos y ninguno de los tres |

Conclusión: ninguna búsqueda ni lista probada los devuelve; sí lo hacen la consulta por ID y los historiales de sets de sus jugadores. **No se sabe por qué start.gg los oculta** y no se asume una causa interna. Las ramas `probe/…` son solo sondas de lectura y no se fusionan; la del dueño (`probe/pinguis-public-history-20261101`) tampoco.

## Solución

### 1. Complemento de cobertura (`scripts/smash/coverage.py`)

Corre en `smash-publish.yml` justo después de `discover.py`, antes del contexto pequeño y de la búsqueda extranjera. **Apagado por defecto**: variable `SMASH_COVERAGE_COMPLEMENT_ENABLED=true`. No corre al reanudar una captura.

1. **Candidatos:** los torneos de `recoveredTournamentIds` en `curation.json` (lista verificada, con motivo) más los que aparezcan en los historiales de una muestra de jugadores: los 4 con actividad más reciente y 4 rotando por semana, solo perfiles de Guatemala de la captura, 2 páginas de 50 sets cada uno. La consulta del historial pide solo IDs de evento y torneo y el país.
2. **Validación por ID** (`tournaments(filter:{ids})`, sin filtro de país ni juego): metadatos reales, organizador y ciudad. Cada evento pasa por **las mismas reglas de `discover.py`** (presencial, terminado, singles, Ultimate, temporada, 20 inscritos para descargar).
3. **Separación:**
   - Evento con 20 o más inscritos → se descarga completo con `fetch_event` y entra a la captura nacional. **`rank.py` decide** con los 20 activos: el de 20 inscritos y 18 activos queda fuera, como cualquier otro.
   - Menos de 20 inscritos → candidato del contexto pequeño (`organizer_small.py`, mismo límite de 6 por semana); nunca entra al cálculo.
   - Dobles, online, sin terminar, fuera de temporada → excluido con su motivo.
4. **Sin duplicados:** se omite todo evento ya conocido por la búsqueda, el catálogo, los excluidos o los candidatos pequeños; uno hallado por varios caminos se agrega una vez; un set repetido invalida ese evento.
5. **Fallos:** cualquier error de API, presupuesto agotado o dato inesperado deja la captura nacional como estaba (salvo el resumen) y el paso nunca detiene la publicación. Si se agota el presupuesto a mitad, se conservan solo eventos descargados completos y el resto queda en `pendingEvents`.

**Techos fijos** (no son argumentos): 210 intentos HTTP con 3 reservados por consulta (≈70 consultas), 240 s, historiales ≤48 intentos, 25 torneos validados, 12 descargas, 40 IDs listados; `Client` mantiene 1 petición por segundo. Como la búsqueda nunca ve estos torneos, **se vuelven a descargar cada semana**, igual que el resto de la captura nacional: los listados van primero (más antiguos primero) y luego los hallados por historial (más recientes primero).

**Mantenimiento:** un torneo hallado solo por historial aparece en `unlistedTournaments`. Hay que añadirlo a `recoveredTournamentIds` con su motivo, porque la rotación de la muestra puede no volver a encontrarlo.

### 2. Resumen operativo

`national.json` y `combined.json` llevan `coverageComplement`: estado, jugadores consultados y truncados, páginas, torneos no vistos, validados, no disponibles, recuperados, contexto pequeño, excluidos con motivo, pendientes, fallidos, hallados solo por historial, consultas y segundos. El paso lo escribe en el resumen del run de Actions y `auditoria.md` tiene la sección «Complemento de cobertura» (o avisa que no se ejecutó). Solo IDs públicos de torneos y eventos y conteos: ningún ID de jugador, token ni dato privado. Sin consultas a start.gg por visita.

### 3. Historial de la cuenta

`smash_account_small_events` (mismo nombre, alcance ampliado; sin migración) devuelve las participaciones registradas que el corte publicado no le cuenta al jugador, con su motivo concreto y sus sets:

- Solo eventos con **cuadro completo capturado**: `events.active_players` lo escriben el circuito nacional y el de torneos pequeños, nunca los historiales de análisis; las marcas de `organizer_event_context` anteriores a esa columna siguen valiendo. Un set suelto de un historial de análisis no aparece como participación.
- Motivos: menos activos que el mínimo («tuvo 18 jugadores activos (20 inscritos) y el ranking pide 20 o más…»), solo DQ/W.O./bye, también en un evento que sí cuenta para otros, exclusión editorial publicada, o «no está entre los torneos del corte publicado».
- La pantalla existente distingue: **sin datos** («No encontramos sets tuyos… eso no quiere decir que no hayas jugado»), **participación registrada que no cuenta** («Tus torneos aún no cuentan») y **actividad válida insuficiente** («Casi clasificas»). Se quitaron «Sin torneos en 2026» y «Cuando juegues uno… aparecerá aquí». Los sets por DQ se marcan como no válidos. El texto de cobertura dice que no es el historial completo de start.gg.

No cambia fórmula, puntos, mínimos, elegibilidad, puestos, `public.json` ni contratos de importación.

## Simulación de recuperación (solo lectura)

`scripts/smash/simulate_coverage.py` toma las capturas privadas de un run publicado, ejecuta el complemento sobre una copia, combina y calcula ambas versiones con la misma curación y tabla TTS, e imprime qué cambiaría el siguiente corte normal. No publica, no escribe SQL ni FTP y no reemplaza capturas.

```bash
python scripts/smash/simulate_coverage.py national.json abroad.json --curation scripts/smash/curation.json --points-csv scripts/smash/data/ultrank_players.csv --watch 5551493
```

Ejecutada en Actions sobre la captura del run semanal [41307127512](https://github.com/Bucaro-19/rankingsmashbros/actions/runs/41307127512) (1/nov): primer intento [41394539207](https://github.com/Bucaro-19/rankingsmashbros/actions/runs/41394539207), con un tope de 4 descargas que dejó pendiente el torneo del 30/ago (motivo del ajuste a 12 y de la prioridad de los listados); final [41394881853](https://github.com/Bucaro-19/rankingsmashbros/actions/runs/41394881853):

| Medida | Resultado |
|---|---|
| Consultas / tiempo | **32 / 31,7 s** (8 jugadores, 12 páginas de historial, 1 validación de 5 torneos, 5 eventos descargados) |
| Torneos no vistos por la búsqueda | 5: los 3 listados y **962666, 968395** hallados por historial (ya añadidos a la lista) |
| Recuperados para el cálculo | 1697423 (42 inscritos / 38 activos), 1719115 (38/30), 1719121 Clase S (28/23), 1729836 (30/30) → **entran**; 1699110 (20/18) → **no cuenta**: `under_minimum_active_players` |
| Contexto pequeño | 1719129 (Clase B, 13 inscritos) y 1741829 |
| Excluidos | 1746992: `not_singles` |
| Pendientes / fallidos | ninguno |
| Efecto en el siguiente corte | eventos admitidos 48 → 52; clasificados 202 → 210; 171 puestos se mueven y 186 puntajes cambian, **solo por el cálculo normal** |
| pinguis | sin puesto antes y después: con los datos recuperados tiene un evento que cuenta (1697423, 0–2) y no llega a 2 eventos / 4 sets |

Las cifras de «antes» salen de recalcular la captura de ese run en la simulación y pueden diferir en uno o dos clasificados del corte publicado; lo que importa es la diferencia con el mismo cálculo. **No se publicó nada.** Los cambios llegarán al ranking solo cuando el dueño active la variable y corra el semanal normal.

Para pinguis, en la cuenta se verán: 1697423 (cuenta, 0–2), 1719115 Clase A (no cuenta para él: solo DQ), 1699110 (18 activos de 20 inscritos) y, cuando el contexto pequeño lo capture, 1719129 Clase B (2–2, 13 inscritos). El contexto pequeño toma los 6 candidatos más recientes por semana, así que la Clase B del 26/sep puede tardar o no entrar; no se promete.

## Límites

- La muestra de historiales es acotada y el orden en que start.gg pagina `player.sets` no está documentado: un torneo oculto al que no asistió ningún jugador muestreado puede seguir faltando. No se promete cobertura completa.
- El complemento depende de que la consulta por ID siga devolviendo estos torneos.
- Jugadores nuevos que llegan por torneos recuperados amplían las semillas de la búsqueda extranjera (unas consultas más en `discover_abroad.py`).
- Recuperar torneos cambia legítimamente el siguiente corte; por eso la activación es decisión del dueño.

## Pruebas

`scripts/smash/test_coverage.py` (16, datos inventados): la búsqueda omite y el complemento recupera y valida; el mismo evento por búsqueda, historial y lista no se duplica; 20 inscritos/18 activos no cuenta; Clase B de 13 queda como contexto excluido; DQ solo no da actividad; pinguis sigue sin puesto; fallo, error de validación y presupuesto agotado no bloquean el corte; sin eventos adicionales el cálculo es idéntico; el contexto excluido no altera ningún puntaje; prioridad de los listados; entidades SQL con activos e inscritos; simulación; auditoría; paso semanal opcional, omitido al reanudar y no bloqueante. `scripts/database/test_accounts_http.py`: participación de 20/18 con sus sets y DQ, DQ en evento que cuenta, historial de análisis que no aparece y cifras del corte intactas, en MariaDB local desechable y CI con MySQL 8.0 y MariaDB 10.11. El importador y su paridad Python/PHP no cambian: un evento recuperado entra al paquete como cualquier evento nacional.
