# Plan para extender Smash GT a El Salvador, México y Estados Unidos

Estado: **propuesta, 8 de octubre de 2026**. Nada de esto está programado. El dueño pidió un plan para ejecutar próximamente. Las cifras marcadas como «por medir» no se conocen todavía: no se inventan.

## Lo que ya sirve tal cual

- La fuente es start.gg, que cubre los tres países con la misma API.
- El método (Bradley–Terry con reglas públicas), las cuentas con start.gg, premium, el análisis de rival, el top por organizador y la agenda no dependen de Guatemala en su lógica.

## Lo que hoy está atado a Guatemala

| Pieza | Dónde está fijo | Qué hay que cambiar |
| --- | --- | --- |
| País de la captura | `discover.py` y `agenda.py` filtran `countryCode: "GT"` | Recibir el país (o la región) como parámetro |
| Quién es «local» | El ranking incluye a quien declara Guatemala en su perfil, más las excepciones de `curation.json` | Una regla y una lista de excepciones por país |
| Mínimos | 20 activos en torneos locales, 64 en torneos de fuera | Decidir mínimos por país: una escena grande pide más, una chica menos |
| Un solo corte | `public.json`, `cuts`, `rankings` suponen un ranking (con dos vistas) | Un corte por país, con su archivo y su fila en SQL |
| Direcciones | Todo vive en la raíz del dominio | Una ruta por país (`/gt/`, `/sv/`, `/mx/`…) y un selector |
| Hora y fechas | Guatemala, UTC−6 fija | Zona por país; México y EE. UU. tienen varias y horario de verano |
| Idioma | Español de Guatemala | EE. UU. necesita inglés |
| Marca | «Smash GT», «los que mandan en el 502» | Nombre paraguas o una marca por país |
| Hosting | Un plan compartido; hoy usa una fracción mínima | Volver a medir con el tamaño real de México o un estado de EE. UU. |

## El problema de tamaño

Es lo que decide el orden. Guatemala tiene 63 torneos de Ultimate en el año y la captura completa cuesta unos cientos de consultas a start.gg, con un límite de 80 por minuto.

- **El Salvador:** escena de tamaño parecido o menor. **Por medir.**
- **México:** bastante más grande y repartida por estados. **Por medir**; lo probable es que un solo ranking nacional no sea ni viable de capturar cada semana ni justo entre regiones.
- **Estados Unidos:** miles de torneos al año. Un ranking nacional propio no es realista ni aporta: ya existen rankings establecidos. Lo que sí puede servir es **un estado o una ciudad** a la vez.

## Orden propuesto

### Fase 0 — Terminar Guatemala (octubre)

Antes de abrir otro país: primer corte automático verificado (lunes 12/oct), torneos pequeños para organizadores, un pago real de premium, guía de matchups revisada y la medición de capacidad del hosting. Abrir un segundo país con esto a medias multiplica los problemas por dos.

### Fase 1 — Medir (una semana, solo lectura)

Encargo de datos, sin tocar el sitio: contar por país y por estado los torneos presenciales de singles del año, sus inscritos, cuántos pasan de 20 y de 64, cuántos jugadores distintos hay y cuántas consultas costaría la captura semanal. Con eso se decide si México va entero o por región y qué estado de EE. UU. tiene sentido.

### Fase 2 — El Salvador (piloto del «segundo país»)

Es el mejor primer paso: mismo idioma, misma zona horaria, escena pequeña y jugadores que ya cruzan a torneos de Guatemala. Sirve para construir lo que hoy está fijo (país como parámetro, corte por país, rutas, selector) con el menor riesgo. Entregas:

1. Captura y cálculo parametrizados por país, con Guatemala dando exactamente el mismo resultado que hoy (prueba de no regresión con el hash del corte).
2. Esquema SQL con país en los cortes (migración) y paquete por país.
3. Sitio: selector de país, rutas por país, agenda y top por organizador por país.
4. Reglas de El Salvador decididas con gente de esa escena: mínimos, quién es local, torneos que no cuentan.
5. Un organizador o jugador de confianza allá que revise el primer corte antes de publicarlo.

### Fase 3 — México, por región

Según la medición: empezar por la región o el estado con escena más activa y contacto local, con sus propios mínimos. El ranking «México» completo solo si la captura y la comparación entre regiones lo permiten.

### Fase 4 — Estados Unidos, un estado o ciudad

Solo con un socio local y en inglés. Antes de programar, comprobar qué rankings ya existen ahí y qué aportaría este: probablemente el análisis de rival y la agenda, más que el ranking.

## Decisiones del dueño que hacen falta

1. **Marca:** ¿un nombre paraguas para todos los países o una marca por país?
2. **Reglas por país:** ¿las mismas de Guatemala o las decide cada escena?
3. **Quién responde por cada país:** hace falta alguien local que conozca los torneos y atienda reclamos.
4. **Premium:** ¿un solo premium para todo o por país? Recurrente cobra desde Guatemala; para EE. UU. y México conviene comprobar qué métodos de pago acepta.
5. **Hosting:** si se pasa a un plan con base de datos y tareas propias antes de México.

## Riesgos

- Publicar un ranking de una escena ajena sin gente de esa escena: lo más probable es que lo rechacen.
- Costo de captura: superar el límite de start.gg tumbaría también la captura de Guatemala si comparten horario y token.
- Protección de datos: México y EE. UU. tienen reglas propias sobre datos personales; hoy solo se usan datos públicos de torneos y el contador no guarda la IP, pero conviene revisarlo antes de abrir.
- Mantenimiento: cada país añade un corte semanal que vigilar.
