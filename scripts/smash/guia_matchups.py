"""Render the draft matchup guide for review and check it against the character catalog. Not published."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "docs/smash/guia/matchups-borrador.json"
TARGET = ROOT / "docs/smash/guia/MATCHUPS-BORRADOR.md"


def catalog():
    text = (ROOT / "ranking-smash-ultimate/characters.js").read_text(encoding="utf-8")
    return dict((slug, name) for name, slug in re.findall(r'"name":\s*"([^"]+)",\s*"slug":\s*"([^"]+)"', text))


def validate(guide, names):
    entries = guide["characters"]
    for slug, entry in entries.items():
        if slug not in names:
            raise ValueError(f"Personaje fuera del catálogo: {slug}")
        if "sameAs" in entry:
            if set(entry) != {"sameAs"} or "counters" not in entries.get(entry["sameAs"], {}):
                raise ValueError(f"Referencia inválida en {slug}")
            continue
        if set(entry) != {"weakness", "counters"} or not entry["weakness"].strip() or not 1 <= len(entry["counters"]) <= 3:
            raise ValueError(f"Ficha incompleta: {slug}")
        seen = set()
        for counter, reason in entry["counters"]:
            if counter not in names or counter == slug or counter in seen or not reason.strip() or len(reason) > 220:
                raise ValueError(f"Counter inválido en {slug}: {counter}")
            seen.add(counter)


def render(guide, names):
    entries = guide["characters"]
    lines = ["# Guía de matchups — BORRADOR SIN REVISAR", "",
             "Generado desde `matchups-borrador.json` con `python scripts/smash/guia_matchups.py`. No editar a mano.", "",
             "**No son datos del ranking.** Es conocimiento general del juego redactado por Claude Code, sin fuente verificable. "
             "No se publica hasta que el dueño o jugadores de la escena lo revisen. Para corregir: cambia el texto en el JSON, "
             "o marca aquí la línea y dile a Claude Code qué está mal.", "",
             f"Fichas: {len(entries)} de {len(names)} personajes (primero los más jugados en Guatemala).", ""]
    for slug, entry in sorted(entries.items(), key=lambda item: names[item[0]].casefold()):
        lines.append(f"## {names[slug]}")
        if "sameAs" in entry:
            lines += ["", f"Igual que **{names[entry['sameAs']]}** (personaje eco o muy parecido).", ""]
            continue
        lines += ["", f"**Le cuesta:** {entry['weakness']}", ""]
        lines += [f"- **{names[counter]}** — {reason}" for counter, reason in entry["counters"]]
        lines.append("")
    return "\n".join(lines)


def main():
    guide, names = json.loads(SOURCE.read_text(encoding="utf-8")), catalog()
    validate(guide, names)
    text = render(guide, names)
    if "--check" in sys.argv:
        if TARGET.read_text(encoding="utf-8") != text:
            sys.exit("MATCHUPS-BORRADOR.md no coincide con el JSON; vuelve a generarlo.")
        return
    TARGET.write_text(text, encoding="utf-8")
    print(f"{len(guide['characters'])} fichas escritas en {TARGET.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
