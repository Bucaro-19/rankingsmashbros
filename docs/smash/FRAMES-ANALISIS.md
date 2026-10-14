# Frames en «Tus herramientas contra él» (13/oct/2026)

## Fuente y alcance

Se revisaron repositorios primarios antes de capturar: [rubendal/ssbu](https://github.com/rubendal/ssbu) no declara licencia en raíz y su README anuncia datos de escenarios; [FrannHammer](https://github.com/Frannsoft/FrannHammer) licencia su software MIT, pero [atribuye los datos a Kurogane Hammer y dice que los obtiene con permiso](https://github.com/Frannsoft/FrannHammer/wiki/How-to-test-out-the-Ultimate-support-changes), sin licencia abierta verificable para ese conjunto de facts; [smash-ultimate-api](https://github.com/FelipeCarvalhoS/smash-ultimate-api) es MIT pero los datasets versionados son personajes/escenarios/items, no frames. No se identificó un dataset completo de frames con licencia abierta verificable en esa búsqueda; no se presenta esta conclusión como prueba de que no existe ninguno.

Se usa la alternativa **autorizada expresamente por el dueño**: valores numéricos de [Ultimate Frame Data](https://ultimateframedata.com/smash). Según lo comunicado por el dueño, **pidió permiso por correo y no recibió respuesta**; no se afirma haber obtenido una licencia o permiso de UFD. **Retirar si lo solicitan**, mediante el interruptor explicado abajo.

[robots.txt](https://ultimateframedata.com/robots.txt) comprobado HTTP 200: User-Agent `*`, Disallow vacío, sitemap indicado. Hash del texto capturado: `c6d4bbf5cc82a5275be357921f73bb949f56a4aac4e7bfd5451265e60e9adf78`. El capturador comprueba permiso antes de cada página incluso al reconstruir desde caché. User-Agent propio `SmashGT-FrameFacts/1.0 (+https://rankingsmashbros.com)`, separación mínima **1 s entre inicios de peticiones**, timeout 20 s, sin descargas de medios/subrecursos, sin reintento automático. Se retiene HTML temporal fuera del repo exclusivamente para comprobar/extraer hechos; **ningún HTML, nota, descripción, imagen, GIF o script de UFD se versiona/publica**. Las etiquetas españolas son nuestras categorías genéricas de movimientos; no se copian sus textos técnicos.

Captura de una vez: **83 páginas de personajes guardadas**; una página adicional, Palutena, agotó el tiempo de negociación TLS, quedó marcada y **no se reintentó**. También se consultaron robots y el índice (solo descubrir nombres de rutas), 86 intentos HTTP del sitio fuente en total contando Mario/robots de investigación. La segunda tanda descargó 31 páginas en **39,099 s**. Reconstrucción posterior con el parser ajustado: **0 consultas, 0,522 s**, todo desde la caché. No queda cron ni consulta de UFD desde el sitio vivo.

El archivo `data/frame-facts-v1.json` es privado por `.htaccess`, versionado y desplegado antes del lector. **65 666 bytes**, **7460 bytes gzip** medidos; no se descarga completo al navegador. Una llamada PHP local con tres fichas y un main: **862 bytes JSON, 0,426 ms, pico 2 MiB** (medición aislada, no promesa de rendimiento del hosting). Sin tablas ni migraciones nuevas; sin SQL productivo.

### Versión del juego: desconocida en la fuente

Las páginas capturadas **no declaran una versión del juego**. `source.gameVersion` y `deep.frameDataSource.gameVersion` quedan **null**, y el crédito visible dice «versión no declarada por la fuente». No se copia el 13.0.2 ficticio del handoff. [Nintendo](https://en-americas-support.nintendo.com/app/answers/detail/a_id/42809/p/1076) registra 13.0.1 como actualización con ajustes de balance y 13.0.5 como actualización de comportamiento online; eso no certifica la revisión de cada celda de UFD, por lo que no se inventa una versión de la captura. Si la fuente confirma una versión, el capturador/archivo se actualizan explícitamente con comprobación nueva.

## Selección conservadora de hechos

No se convierten rangos, variantes, múltiples impactos, punta/cerca/lejos, materiales, auras, formas ni valores condicionales en un único número supuesto.

- **fastest**: menor inicio numérico simple entre normales de tierra con daño base numérico simple. No incluye Jab 2/3, que requieren un golpe anterior; tampoco especiales, saltos o movimientos con valores ambiguos. Desempate por orden de la ficha. Se rotula el alcance en pantalla: «normales en tierra con dato inequívoco». No es una afirmación sobre todas las opciones posibles del luchador.
- **oos**: hasta tres opciones con tiempo único explícito en la tabla OOS de la fuente, ordenadas por frames. Empates se desglosan y se recortan a tres; las variantes aéreas reconocidas se nombran como tales. El dato **ya incluye** los costes de salto/salida del escudo que recoge la fuente: no se añaden otra vez. Opciones condicionadas a frente/bajo, armaduras o set de especiales de Mii no representable se omiten. Puede haber menos de tres, incluso cero, con su vacío.
- **punishable**: hasta tres normales/aéreos con valor negativo simple en escudo, más negativos primero; desempate por orden de fuente. Sin valores inequívocos, null. No se afirma una lista exhaustiva ni se estiman variantes. «Entra» si `frame <= abs(onShield)`, inclusivo. La pantalla avisa que tiempo no garantiza alcance/posición/invulnerabilidad/ejecución.
- **Pokémon Trainer y Pyra & Mythra**: el ID publicado agrupa formas diferentes; se omiten, sin atribuirles una forma concreta. **Palutena** se omite por el fallo de fuente anterior.
- 83 registros numéricos capturados, **75 fichas con fastest utilizable**. En esta primera selección conservadora no se entrega ficha completa de Ice Climbers, Joker, Ken, Lucario, Marth, Roy, Ryu y Steve: sus datos de inicio/daño requieren variantes no representadas por este contrato. Se muestra el vacío existente. Sus resultados del ranking/análisis no cambian. No hay castellano/inglés de notas de UFD oculto en el JSON.

Comprobación manual de celdas en cinco HTML guardados, sin otra descarga: [Mario](https://ultimateframedata.com/mario) Jab1 2/2.2 y OOS 3/6/7; [Fox](https://ultimateframedata.com/fox) Jab1 2/1.8 y OOS 6/7/8; [Link](https://ultimateframedata.com/link) Jab1 7/3 y OOS representables 9/10/10 (7 frontal se omite); [Bowser](https://ultimateframedata.com/bowser) Jab1 7/4 y OOS 6/9/11; [Captain Falcon](https://ultimateframedata.com/captain_falcon) Jab1 3/1.5 y OOS 10/10/13. Las pruebas fijan estos valores y los negativos seleccionados por personaje. No son datos del prototipo.

## Contrato para Claude Code

`analisis.php` requiere biblioteca privada `frame-facts.php`. El documento JSON se lee de disco solo tras el acceso completo; el cálculo gratis de teaser llama deep con `withFrames=false`. El HTTP gratis/vencido **no incluye deep** ni toolkit/punishable/crédito: solo su adelanto actual. Admin o premium propio vigente conservan las puertas de siempre. Sin peticiones extra a start.gg, UFD o Recurrente por visita.

Campos dentro de **deep**, sin alterar el resto de sus métricas:

```json
{
  "toolkit": {
    "mario": {
      "fastest": {"name":"Golpe normal 1","frame":2,"damage":2.2},
      "oos": [{"name":"Especial arriba","frame":3},{"name":"Aéreo neutral","frame":6},{"name":"Aéreo arriba","frame":7}]
    },
    "pokemon_trainer": null
  },
  "punishable": {"link":[{"name":"Smash arriba","onShield":-28}]},
  "frameDataSource": {"name":"Ultimate Frame Data","url":"https://ultimateframedata.com/smash","gameVersion":null}
}
```

Ejemplo parcial con datos comprobados, no toda la lista. `toolkit` solo contiene hasta tres slugs elegidos en la cuenta (nunca detectados supuestos); null si no hay elegidos o no hay documento. Cada valor puede ser null si no hay ficha completa. `punishable` solo tiene la clave del main utilizable del rival y hasta tres filas; null sin main/ficha/movimientos. Sin main **los golpes propios siguen disponibles**. `onShield` siempre negativo; `frame` entero positivo; `damage` numérico base, no texto ni cálculo de daño en combate.

`frame-tools.js` es un modelo/renderizador local pequeño, cargado antes de preparar.js; no hace red. Dibuja las fichas del handoff en la pantalla existente y escapa nombres. Las fuentes, colores y layout se conservan; se ajustó el margen de las anclas para que la cabecera no tape el título. Crédito visible solo cuando la API envía frameDataSource, enlace externo seguro y aviso fijo de que son datos del juego. Falta de documento/JSON inválido produce tres null sin romper el resto del análisis.

## Retirada y reproducción

**Un solo interruptor:** `const SMASH_FRAME_FACTS_ENABLED = false;` en `ranking-smash-ultimate/frame-facts.php`. En el próximo despliegue autorizado toolkit, punishable y frameDataSource serán null para todas las cuentas; el crédito desaparece y la pantalla conserva sus vacíos. El archivo ya está negado por Apache: no hay una vía pública de descarga que quede abierta. Si solicitan retirar también el archivo del repositorio, hacerlo aparte por orden del dueño; el interruptor basta para dejar de servir los datos.

Reconstrucción **sin red**, usando la caché local del trabajo (no versionada):

```sh
python3 scripts/smash/frame_facts.py --cache /tmp/smash-frame-facts-cache
```

`--capture` habilita descargas faltantes explícitamente, respeta robots y un segundo entre solicitudes; `failures.json` conserva las omitidas y no las reintenta. No borrar esa caché ni refrescar todas las páginas para regenerar etiquetas. Para una actualización posterior, revisar de nuevo fuente/robots/versión y autorizar una nueva captura pausada en otro directorio. El script solo escribe frame-facts-v1.json, nunca public.json.

## Pruebas y revisión

- **100 Python** del pipeline (seis nuevas de facts), **3 Node** del renderizador, contratos PHP de análisis y **14 HTTP** con MySQL/MariaDB desechable local correctos. Casos: muestra de cinco personajes, solo números/etiquetas propias, robots, pausa y caché sin red, interruptor, JSON ausente/dañado, premium/gratis/vencido, ficha ausente, sin main y servidor sin escrituras de competición.
- Navegador con cuenta y SQL inventados: ficha, tres opciones, castigables, crédito, sin ficha y sin main (golpes propios disponibles), luego revocación del rol admin de prueba para ver gratis sin fichas. **375 px: 360/360**, escritorio 1280: **1265/1265**, sin desborde; viewport restaurado y tabs de prueba cerradas. Un intento inicial de cambiar al usuario gratis chocó con el vínculo único del jugador en el helper de prueba; se verificó correctamente revocando el rol del mismo usuario inventado. No es un fallo del sitio productivo. Evidencia `/tmp/smash-legends-20261013/frames-{mobile,desktop}.png`.
- CI requerida en **MySQL 8.0 y MariaDB 10.11**, más PHP 7.4/8.1. Se agregó un fallback acotado de pull PHP ECR → imagen oficial de Docker Hub por throttling observado, sin omitir checks ni añadir credenciales. Esa corrección es común con PR #100.

Sin cálculo, elegibilidad, public.json, migraciones ni base de producción. SHA versionado: `1e681141bf4d043319593effc3153f44a7ec38531deef8a427f76c2573a24df1`. No fusionar ni desplegar sin orden del dueño.
