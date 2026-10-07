# Smash GT — rankingsmashbros.com

Ranking experimental de Smash Ultimate en Guatemala. No es oficial ni usa la fórmula exacta de UltRank.

- `ranking-smash-ultimate/`: sitio (HTML/CSS/JS vanilla, PHP para la encuesta y el panel de opiniones).
- `scripts/smash/`: captura desde start.gg, cálculo, exportación y despliegue por FTP. Ver `scripts/smash/README.md` y `METODOLOGIA.md`.
- `docs/smash/`: contexto, trabajo en curso y estado de la migración.
- `.github/workflows/`: verificación, publicación semanal y despliegues manuales.

La instalación SQL fue confirmada por el dueño en BanaHosting. Estado y siguiente entrega: [BASE-DE-DATOS.md](docs/smash/BASE-DE-DATOS.md) y [SIGUIENTE-FASE.md](docs/smash/SIGUIENTE-FASE.md). Para continuar con Claude Code, comenzar por `CLAUDE.md`. Las pantallas nuevas requieren primero handoff de Claude Design.

Pruebas:

```sh
python3 -m unittest discover -s scripts/smash -q
node --test scripts/smash/test_app.cjs
```
