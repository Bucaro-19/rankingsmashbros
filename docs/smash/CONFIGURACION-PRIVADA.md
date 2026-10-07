# Ingresar el usuario MySQL desde cPanel

El dueño confirmó que creó el usuario MySQL. Falta completar la configuración privada y verificar conexión; todavía no existe código desplegado que cargue este archivo. Base confirmada: `ivcjgjlk_smash`.

## Archivo que debe completar el dueño

1. cPanel → Administrador de archivos → directorio Inicio de su cuenta (arriba de public_html y de la carpeta rankingsmashbros.com).
2. Crear carpeta `private-smash` **fuera de public_html y de todos los directorios de sitios/dominios**. Si no se reconoce la carpeta Inicio, mostrar solo la estructura de carpetas antes de ingresar la contraseña.
3. Subir la plantilla `docs/smash/config/config.local.php.example` a private-smash y renombrarla **`config.local.php`**. También se puede crear ese archivo y copiar la plantilla desde el editor de cPanel.
4. Editar SOLO `user` y `password` con el usuario MySQL completo (incluido prefijo de cPanel) y su contraseña. Conservar base `ivcjgjlk_smash`; host `localhost` es el valor inicial para conexión en el mismo hosting, pendiente de prueba. Si BanaHosting indicó otro host, usarlo.
5. Guardar. Los valores son cadenas PHP entre comillas simples: si un valor contiene `'`, escribir `\'`; una contrabarra literal se escribe `\\`. No añadir etiquetas HTML ni cierre `?>`.
6. Permisos sugeridos: archivo **600**, carpeta **700**, siempre que PHP ejecute como el mismo usuario de la cuenta. Si no puede leerlo, revisar usuario/permisos del hosting; no cambiar a escritura pública.
7. En cPanel → MySQL Databases / Manage My Databases, comprobar que ese usuario esté asociado a `ivcjgjlk_smash` con los permisos necesarios. Haber creado usuario y base por separado no crea esa relación.

Estructura esperada (ejemplo; no afirmar la ruta /home sin verla):

```text
Inicio de la cuenta/
├── public_html/
├── rankingsmashbros.com/      ← sitio público
└── private-smash/
    └── config.local.php      ← aquí se ingresan usuario y contraseña
```

**No cargar este archivo en GitHub Secrets, la carpeta pública, el SQL, un .js o el chat.** Las credenciales MySQL son independientes de FTP, start.gg y la clave del panel de opiniones. PHP las leerá desde el servidor; el visitante no recibe el archivo.

## Qué comunicar al agente después

Decir «ya guardé el archivo» y la ruta completa que muestra cPanel (sin contraseña y sin captura del contenido). Esta ruta permite preparar el conector PDO/diagnóstico. Si la cuenta Inicio resulta distinta de lo previsto, ajustar el loader a su ruta real; no inventarla desde el prefijo de la base.

La ruta de ejemplo `/home/<cuenta>/private-smash/config.local.php` no está verificada. No confundir el host `localhost` dentro de BanaHosting con el Mac local: la prueba de producción debe ejecutarse en el hosting.

## Continuidad para Claude Code

- Dueño ya instaló SQL y creó usuario; no solicitar esas acciones de nuevo salvo fallo verificado.
- Plantilla en Git contiene únicamente placeholders. `config.local.php` real está ignorado y el despliegue no lo incluye.
- Conector y diagnóstico PDO todavía pendientes. Pedir solo ubicación y confirmación, no contraseña. No exponer un diagnóstico público ni leer/imprimir secretos con herramientas.
- Implementar validación de config, prepared statements nativos, utf8mb4 y UTC; tratar excepciones con mensajes saneados. Separar verificación de conexión de importación/cuentas.
- No es una pantalla nueva: instrucciones para el Administrador de archivos existente. Cualquier UI nueva sigue requiriendo Claude Design.

Referencias: [PDO y credenciales](https://www.php.net/manual/en/pdo.construct.php), [conexión MySQL](https://www.php.net/manual/en/ref.pdo-mysql.connection.php), [asociar usuario/base en cPanel](https://docs.cpanel.net/cpanel/databases/mysql-databases/).
