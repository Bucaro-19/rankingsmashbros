# Relevo vigente para Claude Code — 7 de octubre de 2026

El dueño pidió dejar documentada la continuidad y detener el trabajo de Codex por ahora. Está trabajando remotamente: no asumir que puede ejecutar comandos de cPanel inmediatamente. **Esta entrega es solo documentación; no inicia otro módulo.** Sustituye como punto de entrada el relevo anterior de encuesta/OAuth, ya completado.

## Prompt listo para pegar

> Lee AGENTS.md, CLAUDE.md y docs/smash/RELEVO-CLAUDE-CONTINUACION.md. Después revisa CONTEXTO.md, EN-CURSO.md, SIGUIENTE-FASE.md, CUENTAS-OAUTH.md y el bloque vigente de CARGA-SEMANAL-SQL.md. Confirma rama, cambios locales, remoto y Actions antes de editar; preserva esta documentación si hay commits locales pendientes de subir. El proyecto correcto es Bucaro-19/rankingsmashbros, no graduación. Encuesta SQL, cuentas OAuth y comparación pública con TrueSkill ya están publicadas. No reinstales tablas ni rehagas esas entregas. La automatización SQL en BanaHosting está implementada, pero falta configurar el archivo privado/cron y verificar el circuito real; los pasos del dueño están en PENDIENTES-DUENO-BANAHOSTING.md. Si no hay evidencia de esos pasos, conserva SMASH_SQL_SYNC_ENABLED=false y continúa con planificación o trabajo independiente. Como siguiente fase se recomienda historial disponible desde SQL y estadísticas de rivales, pero el dueño todavía no eligió módulo: confirma la prioridad antes de iniciar una implementación nueva. Toda pantalla nueva requiere primero un handoff de Claude Design. No cambies el cálculo, la elegibilidad ni public.json; no implantes TrueSkill por inferencia. Documenta alcance, contratos, pruebas, commits, publicación y pendientes, distinguiendo lo comprobado de lo propuesto. No necesitas publicar la web por esta entrega exclusivamente documental.

## Estado al recibir el relevo

- Repositorio local: `rankingsmashbros`, dentro de la carpeta de proyectos Git del dueño. Último main remoto comprobado: **`49240bd`**, PR #24. Confirmar el estado actual: este relevo puede estar en un commit local posterior todavía sin publicar.
- Web: **https://rankingsmashbros.com/**, BanaHosting, HTML/CSS/JS y PHP. El ranking público y el perfil actual leen el JSON del corte. La encuesta y cuentas utilizan SQL para sus propios datos.
- Base instalada: MariaDB 11.4.13, esquema `001_accounts_competition`, 31 tablas. Primera importación real: cutId=1, publicado; 188 posiciones por vista. No volver a ejecutar la instalación como siguiente paso.
- OAuth real de Bucaro19 comprobado: identidad por IDs del proveedor, no por alias. Alcance `user.identity`. Los tokens se descartan tras verificar identidad; no existen tokens persistidos para consultar torneos personales o enviar resultados.
- Intereses jugador/organizador no conceden permisos administrativos. Reportes, agenda, torneo en curso, notificaciones y top 15 por organizador siguen pendientes.
- Método **BT-PILOTO-3**: mínimo local 20 activos, extranjero 64 activos; jugador con 2 eventos/4 sets y participación local. Nacionalidad aún no verificada solo por país de perfil. Ambos rankings se calculan independientemente. No hay bono de constancia aprobado.
- Comparación conceptual publicada: **https://rankingsmashbros.com/metodologia.html#trueskill**. No se ejecutó un estudio empírico ni se publicaron posiciones TrueSkill. La liga Rankup enlazada es de 2024 y no detalla su configuración exacta.
- Publicación de metodología: PR #23/main `82858eb`, despliegue **37666259662**, `assets_only=true`, correcto. Página/CSS comprobados contra main y revisión visual en escritorio y ancho móvil de 390 px. PR #24 conserva la evidencia documental, sin redespliegue.
- JSON sin cambios después de publicar: SHA-256 **`1e681141bf4d043319593effc3153f44a7ec38531deef8a427f76c2573a24df1`**, corte Oct4. Este es el último resultado comprobado, no una garantía sobre futuras publicaciones; consultar el sitio antes de reemplazar datos.
- CI PR #23 completa/correcta: 37665496993 y 37665508275. CI PR #24 completa/correcta: 37666581028. Hubo jobs detenidos instalando dependencias; las ejecuciones duplicadas/reintentos están descritos en las PR. No confundir un entorno detenido con un fallo del cálculo.
- Se corrigió únicamente un test intermitente: al comparar importadores PHP/Python, `players.updated_at` es un reloj de SQL y puede diferir entre ejecuciones. El test sigue comparando fechas de fuente/paquete y resultados; los snapshots de rollback/conflicto conservan ese campo. No cambiaron los importadores productivos.

## Prioridad operativa: terminar BanaHosting cuando el dueño esté listo

Leer [PENDIENTES-DUENO-BANAHOSTING.md](PENDIENTES-DUENO-BANAHOSTING.md) y [CARGA-SEMANAL-SQL.md](CARGA-SEMANAL-SQL.md).

El receptor, cola, importador PHP y worker CLI están publicados. Última comprobación: receptor `sync_not_configured`, variable **`SMASH_SQL_SYNC_ENABLED=false`**. No se confirmó subida del archivo ni instalación del cron.

El dueño tiene que subir el archivo privado local existente, confirmar PHP CLI/extensiones, ejecutar el worker y crear el cron cada cinco minutos. El cron importa trabajos pendientes; no consulta start.gg ni recalcula cada cinco minutos. El cálculo sigue previsto para domingo 00:00 Guatemala, con posible demora de GitHub. Primer nuevo disparo previsto: 11/oct/2026, todavía no comprobado.

Tras recibir evidencia, el agente puede diagnosticar por HTTPS autenticado, enviar el **paquete original** del corte ya importado, comprobar que lo procesa el cron real sin duplicar cortes y activar la variable solo después. No recapturar un paquete distinto para el mismo corte. Web y SQL no se publican en una transacción conjunta; si SQL se atrasa, revisar/reintentar sin borrar historia.

Configuraciones locales privadas: `docs/smash/config/sync.local.php` y `oauth.local.php`, ignoradas/600. No imprimir, versionar ni pedir las claves por chat. La clave de sincronización ya está en GitHub Secrets. La cuenta FTP solo ve el sitio, no la carpeta privada; no hay SSH configurado. No abrir MySQL a las IP de Actions.

## Qué se puede avanzar mientras el dueño está remoto

Estas son **opciones recomendadas, no módulos ya elegidos**. En la última consulta el dueño prefirió detener el trabajo antes de seleccionar una opción.

### 1. Historial disponible desde SQL y estadísticas de rivales — recomendado

Permite aprovechar cortes/resultados ya importados sin una consulta API por visita. Antes de implementar, fijar contrato y cobertura:

- El perfil actual se arma con `smash_account_profile()` en `accounts.php`, a partir del JSON público. `account-api.php` verifica identidad/sesión. Preservar ese comportamiento hasta contar con un lector SQL validado.
- Historial de ranking: usar cortes publicados y tablas `rankings`, `cut_events`, `cut_set_results`, `player_characters`. Identificar temporada, método, vista y fecha. No rellenar semanas inexistentes ni inventar movimientos: actualmente solo se ha confirmado un corte en SQL.
- Para una vista del corte actual, comprobar correspondencia con el corte público. SQL automático aún no está activado: no mostrar un corte SQL viejo como si fuera el vigente. Documentar explícitamente cómo se informa la falta de sincronización, sin una sustitución silenciosa.
- Diferenciar resultados que entran al ranking de actividad adicional disponible en las tablas de contexto. Estas tablas no representan el historial completo de una persona en start.gg y conservan parte del contexto como se observó inicialmente.
- Rivales: enfrentamientos entre los dos jugadores, récord y torneos conocidos, personajes con cobertura y posición solo cuando exista en el corte/vista. Un extranjero o jugador sin puesto no equivale a rival débil. No mostrar ceros como sustitutos de datos ausentes.
- Usar IDs estables, consultas parametrizadas, paginación y límites. No permitir que parámetros de usuario cambien qué cuenta está autenticada. No conceder roles ni persistir tokens como efecto de leer estadísticas.
- Pruebas relevantes en bases desechables: paridad con ambas vistas, IDs/alias duplicados, jugador sin puesto, rival extranjero, historia incompleta, corte atrasado, falta de datos y sesiones revocadas. No crear cuentas de prueba en producción.

Puede prepararse el backend sin pantalla nueva. Para una nueva ficha del rival, gráfico de evolución o nueva vista de historial, entregar primero al dueño un brief de Claude Design con datos, estados vacíos/error/atrasados y comportamiento móvil. Reutilizar una pantalla existente no autoriza inventar otra.

### 2. Agenda de próximos torneos

Preparar captura compartida/caché y contrato de torneos Ultimate presenciales de Guatemala: fecha, zona horaria, ubicación disponible y enlace de inscripción. No usar la admisión al ranking de eventos terminados para excluir automáticamente un evento futuro sin asistencia conocida. El catálogo actual es histórico y no constituye una agenda.

Revisar documentación vigente de start.gg antes de fijar consultas/cuotas. No consultar la API en cada visita ni prometer cobertura completa. Pantalla nueva: brief y handoff de Claude Design primero.

### 3. Estudio Bradley–Terry frente a TrueSkill

Es un experimento separado del ranking publicado. Requiere decidir unidad de resultado, parámetros, orden temporal, reinicio por temporada y cómo tratar timestamps ausentes. Usar los mismos sets/periodo/cohorte y reportar diferencias, estabilidad y predicción fuera de muestra. Nunca elegir parámetros para producir un puesto deseado ni reemplazar el top por el estudio. Confirmar este encargo con el dueño; aún no fue seleccionado.

## Entrega y cierre para el siguiente agente

1. Confirmar Git/Actions y leer el estado vigente antes de seguir secciones históricas de los documentos.
2. Mantener pendientes los pasos de cPanel hasta tener evidencia; el dueño ya tiene los comandos por escrito.
3. Confirmar el módulo a iniciar y documentar alcance antes de implementarlo. Preparar el brief de Design cuando aplique.
4. Trabajar en rama propia, ejecutar los checks pertinentes y registrar lo efectivamente completado. Publicaciones de UI/backend usan el flujo de main y `assets_only=true` cuando se conserva el corte.
5. Actualizar EN-CURSO.md con pruebas, commits/PR/runs, límites y próximo paso. No afirmar que preparar un backend, un secreto o un cron implica que fue probado en producción.

No se enviaron mensajes a otra sesión de Claude ni se inició una implementación de estas opciones. El dueño trasladará este relevo.
