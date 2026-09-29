"""Exportación pública mínima de cobertura. Nunca fabrica un rating."""
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


def day(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y-%m-%d")


def export(snapshot):
    if snapshot.get("kind") != "coverage_probe" or snapshot.get("rankingComputed") is not False:
        raise ValueError("Se requiere una captura de cobertura; el cálculo aún no está validado.")
    datetime.fromisoformat(snapshot["generatedAt"])
    players = []
    for pid, player in snapshot["players"].items():
        if player.get("countryStatus") != "GT_candidate":
            continue
        slug = (player.get("user") or {}).get("slug", "") or ""
        players.append({"id": str(pid), "tag": player.get("gamerTag") or "Sin alias",
                        "url": "https://www.start.gg/" + slug if re.fullmatch(r"user/[\w-]+", slug) else None,
                        "sets": 0, "historyComplete": snapshot["coverage"].get(str(pid), {}).get("historyComplete", False)})
    candidate_ids = {player["id"] for player in players}
    results, events, countries = [], set(), set()
    for sid, match in snapshot["sets"].items():
        event = match.get("event") or {}
        # These are observed results, not a declaration of UltRank eligibility.
        if match.get("state") != 3 or match.get("winnerId") is None or event.get("isOnline") is not False:
            continue
        slots = match.get("slots") or []
        if len(slots) != 2:
            continue
        ids, entrant_ids = [], []
        for slot in slots:
            entrant = slot.get("entrant") or {}
            participants = entrant.get("participants") or []
            if len(participants) != 1 or not (participants[0].get("player") or {}).get("id"):
                break
            ids.append(str(participants[0]["player"]["id"]))
            entrant_ids.append(str(entrant.get("id")))
        score = match.get("displayScore")
        if len(ids) != 2 or not candidate_ids.intersection(ids) or str(match["winnerId"]) not in entrant_ids:
            continue
        # Obvious walkovers are not competitive results; other ambiguous scores await review.
        if not score or re.search(r"\b(?:DQ|BYE|W/?O)\b|(?<!\d)-1(?!\d)", score, re.I):
            continue
        if event.get("id") is None or event.get("startAt") is None:
            continue
        tournament = event.get("tournament") or {}
        country = tournament.get("countryCode")
        slug = event.get("slug") or ""
        url = "https://www.start.gg/" + slug if re.fullmatch(r"tournament/[\w-]+/event/[\w-]+", slug) else None
        results.append({"id": str(sid), "playerIds": ids, "score": score,
                        "tournament": tournament.get("name") or event.get("name") or "Torneo",
                        "country": country, "date": day(event["startAt"]), "url": url})
        events.add(str(event["id"]))
        if country:
            countries.add(country)
    results.sort(key=lambda row: (row["date"], row["id"]), reverse=True)
    for player in players:
        player["sets"] = sum(player["id"] in match["playerIds"] for match in results)
    players.sort(key=lambda player: (player["tag"].casefold(), player["id"]))
    return {"schemaVersion": 1, "status": "coverage_only", "rankingComputed": False,
            "generatedAt": snapshot["generatedAt"],
            "seasonLabel": f"Consulta: {day(snapshot['season']['startInclusive'])} → {day(snapshot['season']['endExclusive'] - 1)}",
            "players": players, "results": results,
            "counts": {"players": len(players), "events": len(events), "sets": len(results), "countries": len(countries)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = export(json.loads(args.snapshot.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    temporary.replace(args.output)
    print(f"Exportación pública: {len(result['players'])} candidatos; {len(result['results'])} resultados observados. Sin ranking.")


if __name__ == "__main__":
    main()
