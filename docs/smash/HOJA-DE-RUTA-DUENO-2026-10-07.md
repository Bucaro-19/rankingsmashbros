# Hoja de ruta pedida por el dueño — 7 de octubre de 2026

Registro de lo que el dueño pidió en conversación con Claude Code después de activar la carga automática a SQL. **Nada de esto está implementado.** Son decisiones de producto y pedidos; el alcance técnico de cada uno se fija al iniciarlo. Complementa `scripts/smash/ACUERDOS-2026-10-01.md`.

## Lo que pidió

1. **Panel administrativo con estadísticas, solo para el dueño:** cuántas personas entran a la página y cuántas se registran, para conocer el tráfico.
2. **Sesión que se mantenga iniciada:** no tener que autorizar con start.gg en cada visita para ver su perfil.
3. **Gratis:** historial y estadísticas de rivales con los que el jugador ya se enfrentó (la opción 1 de RELEVO-CLAUDE-CONTINUACION.md).
4. **Premium:** análisis del contrincante durante un torneo —su main, si conviene o no usar los mains propios, qué matchup es bueno o malo, cómo le ha ido en torneos y qué posibilidad hay de ganarle— y el **top 15 por organizador**.
5. **Motivo del premium:** que la página se sostenga sola; la contribución debe ser pequeña. Sigue vigente el acuerdo del 1/oct: el puesto básico es gratis para todos y pagar no da puntos ni cambia el cálculo o el calendario.
6. **Fases futuras:** un ranking calculado por país (México, Estados Unidos, etc.); por eso el dominio no nombra un solo país. No iniciar ahora.

## Estado técnico al registrar esto (comprobado en el repo)

- El esquema `001_accounts_competition` no tiene tablas de visitas, de sesiones persistentes ni de pagos/suscripciones. Los tres pedidos de base necesitan una migración versionada `002`; no alterar tablas a mano.
- La sesión actual es la de PHP con máximo absoluto de ocho horas (`SMASH_ACCOUNT_MAX_AGE = 28800` en `accounts.php`) y los tokens de start.gg se descartan. Mantener la sesión no requiere guardar tokens del proveedor: basta un identificador propio, aleatorio, guardado como hash, revocable al cerrar sesión o desvincular.
- Estadísticas de visitas: contar en el propio hosting, con agregados diarios. Regla vigente del proyecto: no guardar IP, correo, user agent ni identificadores de sesión de visitantes; cualquier conteo de «personas distintas» debe diseñarse sin esos datos o con la aprobación explícita del dueño.
- Registros: ya se pueden contar hoy con `users` y `oauth_connections` (un usuario real al 7/oct).
- Análisis de matchup: las probabilidades entre dos jugadores salen del modelo ya calculado y el historial entre ambos está en SQL. Los personajes solo existen cuando start.gg los registró (175 de 188 clasificados tenían alguno en el corte del 4/oct) y la muestra por emparejamiento de personajes es pequeña: mostrar cobertura y no presentar una tabla de matchups como hecho cuando no hay datos suficientes.
- «Durante un torneo» necesita datos del torneo en curso, que hoy no se capturan (pendiente junto con la agenda).
- Cobros: falta elegir proveedor de pagos disponible para Guatemala, precio y modalidad. Ninguna credencial de pago va al repositorio ni al chat.

## Pantallas

Panel de estadísticas, ficha de rival/historial, análisis premium, top 15 por organizador y cualquier pantalla de pago son **pantallas nuevas**: requieren brief y handoff de Claude Design antes de implementarse. El backend, la migración y las pruebas pueden avanzar sin pantalla.

## Decisiones del dueño después de leer esto (7/oct)

- Aprobó el orden propuesto.
- Sesión: «lo normal, como Facebook» → 90 días renovables y varios dispositivos a la vez. Implementación en curso; ver EN-CURSO.md.
- Visitantes: prefiere el conteo **exacto**. Se hará con un identificador aleatorio en una cookie propia del sitio, del que se guarda solo el hash por día. Es exacto por navegador, no por persona: dos dispositivos cuentan como dos y borrar cookies cuenta como visitante nuevo. Sigue sin guardarse IP ni navegador. Esto modifica, con su autorización, la regla anterior de no guardar identificadores de visitantes; la encuesta sigue siendo anónima y no se cruza con este identificador.

## Orden propuesto por Claude Code (aprobado por el dueño el 7/oct)

1. Sesión persistente (sin pantalla nueva; es lo más corto y lo usa el dueño a diario).
2. Conteo de visitas y registros en el servidor, más el brief de Claude Design para el panel.
3. Backend de historial y rivales desde SQL, más su brief.
4. Premium: definir pagos y qué se desbloquea; después análisis de contrincante y top 15 por organizador.
5. Ranking por país, en una fase posterior.
