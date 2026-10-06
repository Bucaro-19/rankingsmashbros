# Fuentes de personajes

Los personajes cubiertos usan URLs de marcrd/smash-ultimate-assets según lo solicitado. Los huecos (DLC y variantes Mii) se guardan localmente desde los recursos usados por ThumbnailGenerator.

- https://github.com/marcrd/smash-ultimate-assets (Apache-2.0; el arte pertenece a sus titulares).
- Íconos: https://github.com/jonborg/ThumbnailGenerator/tree/90664e1febc8f012927d7a3c4eae2fe260e5453e/src/main/resources/icons/ssbu
- Retratos: https://github.com/jonborg/ThumbnailGeneratorCharacterImageRepository/tree/a1e6d93567edb5be7d40e9a791862f4ff2755bcb/ssbu/render
- Origen de los renders descrito por el proyecto: sitio oficial de Smash Ultimate.

La interfaz acredita las fuentes y conserva fallback `?` ante nombres desconocidos o errores de carga. `characters.js` tiene el catálogo explícito. No representa permisos editoriales ni datos de jugadores.

Los retratos locales se redujeron a 900 px de lado mayor con `sips -Z 900` (sin recortar ni retocar) para bajar la carpeta de 31 MB a 6 MB. Los íconos locales no se tocaron. Como estos renders vienen sin margen, `app.js` les pone la clase `is-tight` y `arena.css` los escala distinto a los de marcrd.
