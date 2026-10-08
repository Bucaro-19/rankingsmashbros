"""Render the draft matchup guide for review and check it against the character catalog. Not published.

Two kinds of content, never mixed: weaknesses paraphrased from SmashWiki (each with its article), and the
real record of each matchup in the Guatemalan cut's games.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "docs/smash/guia/matchups-borrador.json"
TARGET = ROOT / "docs/smash/guia/MATCHUPS-BORRADOR.md"
WIKI = re.compile(r"https://www\.ssbwiki\.com/[A-Za-z0-9_.%&()-]+_\(SSBU\)")


def catalog():
    text = (ROOT / "ranking-smash-ultimate/characters.js").read_text(encoding="utf-8")
    return dict((slug, name) for name, slug in re.findall(r'"name":\s*"([^"]+)",\s*"slug":\s*"([^"]+)"', text))


def validate(guide, names):
    entries, minimum = guide["characters"], guide["sceneMinimumGames"]
    for slug, entry in entries.items():
        if slug not in names or set(entry) != {"weaknesses", "source"}:
            raise ValueError(f"Ficha inválida: {slug}")
        # A weakness without its article is an opinion, and opinions are what this file replaced.
        if not WIKI.fullmatch(entry["source"]) or not 1 <= len(entry["weaknesses"]) <= 3:
            raise ValueError(f"Ficha sin fuente o sin debilidades: {slug}")
        if any(not isinstance(text, str) or not text.strip() or len(text) > 200 for text in entry["weaknesses"]):
            raise ValueError(f"Debilidad vacía o demasiado larga: {slug}")
    for echo, original in guide["echoes"].items():
        if echo not in names or echo in entries or original not in entries:
            raise ValueError(f"Eco inválido: {echo}")
    for main, rows in guide["scene"].items():
        seen = set()
        for other, won, lost in rows:
            if main not in names or other not in names or other == main or other in seen:
                raise ValueError(f"Cruce inválido: {main} / {other}")
            if type(won) is not int or type(lost) is not int or won < 0 or lost < 0 or won + lost < minimum:
                raise ValueError(f"Cruce por debajo de la muestra mínima: {main} / {other}")
            seen.add(other)


def scene_lines(guide, names, slug):
    rows = [row for row in guide["scene"].get(slug, []) if row[1] > row[2]][:3]
    if not rows:
        return [f"- Ningún personaje le gana más de lo que pierde con {guide['sceneMinimumGames']} games o más."]
    return [f"- **{names[other]}** — le gana {won} de {won + lost} games" for other, won, lost in rows]


def render(guide, names):
    entries = guide["characters"]
    day = "/".join(reversed(guide["sceneCut"].split("-")))
    lines = ["# Guía de matchups — BORRADOR SIN REVISAR", "",
             "Generado desde `matchups-borrador.json` con `python scripts/smash/guia_matchups.py`. No editar a mano.", "",
             "Cada ficha tiene dos partes que no se mezclan:", "",
             "- **Le cuesta (SmashWiki):** debilidades del personaje, parafraseadas del artículo enlazado. " + guide["license"],
             f"- **En Guatemala le ganan:** récord real en los games del corte del {day}, solo cruces con "
             f"{guide['sceneMinimumGames']} games o más. Es un dato de la escena, no una regla del juego: "
             "refleja también quién juega cada personaje aquí.", "",
             "No se publica hasta que el dueño lo revise. Para corregir, dile a Claude Code qué línea está mal y por qué.", "",
             f"Fichas: {len(entries)} de {len(names)} personajes (los más jugados en Guatemala).", ""]
    for slug, entry in sorted(entries.items(), key=lambda item: names[item[0]].casefold()):
        lines += [f"## {names[slug]}", "", f"**Le cuesta** ([SmashWiki]({entry['source']})):", ""]
        lines += [f"- {text}" for text in entry["weaknesses"]]
        lines += ["", "**En Guatemala le ganan:**", ""] + scene_lines(guide, names, slug) + [""]
    for echo, original in sorted(guide["echoes"].items()):
        lines += [f"## {names[echo]}", "", f"Personaje eco: mismas debilidades que **{names[original]}**.", "",
                  "**En Guatemala le ganan:**", ""] + scene_lines(guide, names, echo) + [""]
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
