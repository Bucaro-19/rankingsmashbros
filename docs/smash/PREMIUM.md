# Premium — suscripción con Recurrente

Decisiones del dueño (7/oct/2026): **3 USD al mes o 24 USD al año**, cobrados con **Recurrente** (cuenta comercial Ingporras), como apoyo para sostener el sitio. El ranking, el puesto, el perfil y el historial con rivales siguen gratis. **Pagar no cambia puntos, puestos ni elegibilidad.**

Esta entrega es solo la parte de servidor. Las pantallas (pestaña Premium, análisis de rival) esperan los handoffs de Claude Design: briefs en BRIEF-CLAUDE-DESIGN-ANALISIS-RIVAL.md y el prompt de la pantalla Premium entregado al dueño en la conversación del 7/oct.

## Cómo funciona

1. La cuenta con sesión pide un plan: `POST premium-api.php {action:"checkout", plan:"monthly"|"annual"}` con CSRF.
2. El servidor crea en Recurrente un checkout de suscripción (precio fijo en el código, USD) y guarda una fila `pending` en `premium_subscriptions`. Devuelve la dirección de la página de pago de Recurrente.
3. El pago ocurre en Recurrente. **Este sitio nunca ve la tarjeta.** Al volver, `GET premium-api.php` consulta a Recurrente si ese checkout se pagó y activa el premium.
4. Recurrente también avisa por webhook (`recurrente-webhook.php`). El aviso se verifica con la firma de Svix y solo sirve para saber qué suscripción consultar: **el estado siempre se lee de la API de Recurrente, nunca del aviso.**
5. Renovaciones y fallos: al vencer el periodo pagado se vuelve a consultar la suscripción, llegue o no un aviso.
6. Cancelar: `POST {action:"cancel"}` detiene los cobros en Recurrente; el acceso sigue hasta el final del periodo ya pagado.

Premium = existe una suscripción de la cuenta, en el mismo modo que la llave (prueba o real), con `current_period_end` en el futuro y estado `active`, `past_due` o `canceled`.

## Privacidad y seguridad

- Se guardan solo identificadores de Recurrente (checkout y suscripción), plan, estado y fin del periodo. **Nunca** tarjeta, nombre, correo, teléfono ni NIT del pagador, aunque Recurrente los envíe.
- `premium_events` recuerda el identificador y el tipo de cada aviso para no procesarlo dos veces; no guarda su contenido. Nada del aviso se escribe en logs.
- A Recurrente se envía como metadato únicamente el número interno de la cuenta de Smash GT y el plan.
- La única dirección a la que se redirige al navegador es `https://app.recurrente.com/...`, validada.
- Las suscripciones de prueba (llave `sk_test_`) no cuentan como premium cuando el sitio usa la llave real, y al revés.
- Suscripciones de la misma cuenta de Recurrente que este sitio no inició (por ejemplo, de otro proyecto de Ingporras) se ignoran.

## Configuración privada

`/home/ivcjgjlk/private-smash/recurrente.local.php` (fuera del sitio, permisos 600). Ejemplo sin llaves: `docs/smash/config/recurrente.local.php.example`. Contiene `enabled`, `secret_key` (`sk_test_...` o `sk_live_...`) y `webhook_secret` (`whsec_...`, lo entrega Recurrente al registrar el webhook `https://rankingsmashbros.com/recurrente-webhook.php`). Sin archivo o con `enabled=false`, premium está apagado y nada cambia para nadie.

La llave de prueba del dueño está en su Mac, en `docs/smash/config/recurrente.local.txt` (ignorado por Git). No imprimirla ni copiarla al chat.

## Tablas (migración 004)

`premium_subscriptions` y `premium_events`. Ver `docs/smash/migrations/004_premium.sql`.

## Panel del dueño

`accounts.premium` en el panel: cuentas con un periodo pagado vigente y cobro real. Las pruebas del sandbox no se cuentan.

## Pruebas

- `php scripts/database/test_premium.php`: configuración, firma del webhook, y con un Recurrente inventado: checkout, activación al volver sin webhook, avisos una sola vez, aviso falsificado que no cambia nada, suscripción ajena ignorada, proveedor caído, renovación, cancelación, pago vencido y privacidad.
- `python scripts/database/test_premium_http.py`: planes públicos, escrituras solo con cuenta y CSRF, webhook con firma inválida, repetido, mal formado, demasiado grande y con premium apagado.
- Cliente HTTP real comprobado contra el **sandbox** de Recurrente desde la Mac del dueño: listar suscripciones, crear y leer un checkout mensual de 3 USD y uno anual de 24 USD (ambos sin pagar), y 404 de una suscripción inexistente.

## Pendiente

- Registrar el webhook del sandbox y subir el archivo privado al servidor (pasos del dueño).
- Un pago de prueba completo en el sandbox (tarjeta de prueba de Recurrente), hecho por el dueño, para confirmar el circuito real: no se ha visto todavía una suscripción pagada real, así que los campos de una suscripción activa se tomaron de la documentación.
- Pantallas, con sus handoffs. Conectar el análisis de rival a la condición premium.
- Cambiar a la llave real cuando todo esté probado, y decidir cómo se informa la factura (Recurrente puede emitir FEL; no se configuró).
