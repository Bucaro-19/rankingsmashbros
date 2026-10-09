# Encargo para Codex — torneos pequeños para el top del organizador

Fecha: 8 de octubre de 2026, noche. Una sola tarea, de datos. Claude Code mantiene `organizador.php`, `organizador-api.php`, `organizador.js`, `top.php` y la pestaña «Mis torneos»: no los toques.

## Problema

El top por organizador (ver [TOP-ORGANIZADOR.md](TOP-ORGANIZADOR.md)) se calcula solo con los sets de los torneos de cada organizador. Hoy **solo cuentan los torneos que también entran al ranking nacional**, porque `discover.py` únicamente descarga sets de eventos con 20 inscritos o más. El dueño quiere que los organizadores con torneos chicos también tengan su top: «no todos los torneos tendrán una muestra grande».

En la comprobación del 7/oct, un organizador tenía 15 torneos del año y solo 8 entraban al corte.

## Qué hacer

1. **Capturar los sets de los eventos presenciales de singles con menos de 20 inscritos**, sin que entren al ranking nacional. `discover.py` ya tiene `--include-small` para estudios; decide si se reutiliza o si conviene una captura aparte. Lo que importa:
   - el cálculo nacional, la elegibilidad (20 activos), `public.json` y sus hashes **no cambian en nada** con o sin estos eventos; demuéstralo con una prueba que compare el resultado con y sin la captura ampliada;
   - mide el costo en consultas a start.gg y en tiempo de la captura semanal, y dilo en el informe. Si el costo es alto, propón un límite (por ejemplo, solo eventos con al menos N inscritos, o solo de creadores que ya tienen cuenta en Smash GT) en vez de implementarlo a ciegas.
2. **Llevar esos sets a SQL** por el circuito existente (paquete → receptor → importador PHP, paridad con Python), de modo que `organizador.php` pueda leerlos igual que los demás: hoy lee `sets`, `set_slots`, `entrant_players` y `events`, y decide qué torneo cuenta con `cut_events`. Propón cómo se distingue en SQL «evento del corte nacional» de «evento solo para tops de organizador» sin tocar `cut_events`, `cut_set_results` ni `rankings`, y sin romper `already_imported` ni los hashes de los paquetes V1–V3. Si hace falta una migración, escríbela (006) pero **no la apliques**.
3. **Tolerancia**, como en el catálogo: si la captura ampliada falla, el corte nacional se publica y se importa igual.
4. Deja documentado el contrato para que Claude Code cambie `organizador.php` después: qué tabla o marca indica que un evento pequeño está disponible, y qué mínimo razonable de jugadores o sets propones para que un torneo pequeño cuente en un top (el dueño decide el número final).

## Fuera de alcance

- No cambies el método, la elegibilidad ni el mínimo de 20 del ranking nacional.
- No toques la pantalla ni la API del organizador.
- No escribas en producción ni apliques migraciones.
- Dobles, online y eventos sin terminar siguen fuera.

## Entrega

Una PR en rama propia desde `main`, con pruebas en MySQL 8.0 y MariaDB 10.11, el informe de costo y `EN-CURSO.md` actualizado. Di en la PR si es seguro fusionarla antes del corte del domingo 11/oct o si conviene esperar al lunes. No fusiones ni despliegues sin la orden del dueño.
