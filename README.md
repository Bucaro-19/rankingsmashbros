# Smash GT — rankingsmashbros.com

Ranking experimental de Smash Ultimate en Guatemala. No es oficial ni usa la fórmula exacta de UltRank.

- `ranking-smash-ultimate/`: sitio (HTML/CSS/JS vanilla, PHP para la encuesta y el panel de opiniones).
- `scripts/smash/`: captura desde start.gg, cálculo, exportación y despliegue por FTP. Ver `scripts/smash/README.md` y `METODOLOGIA.md`.
- `docs/smash/`: contexto, trabajo en curso y estado de la migración.
- `.github/workflows/`: verificación, publicación semanal y despliegues manuales.

Pruebas:

```sh
python3 -m unittest discover -s scripts/smash -q
node --test scripts/smash/test_app.cjs
```
