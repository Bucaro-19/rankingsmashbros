"""Export a clearly labeled, local-only pilot ranking for the static website."""
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from rank import competitive_set


def export(snapshot, ranking):
    if ranking.get("kind") != "smash_gt_provisional" or snapshot.get("kind") != "national_discovery":
        raise ValueError("Se requiere una captura nacional y su ranking provisional.")
    if snapshot["generatedAt"] != ranking["generatedAt"]:
        raise ValueError("La captura y el ranking no corresponden a la misma consulta.")
    ranked = {row["id"] for row in ranking["ranking"]}
    accepted = set(ranking["eventIds"])
    results = []
    for sid, match in snapshot["sets"].items():
        event = match.get("event") or {}
        if str(event.get("id")) not in accepted:
            continue
        pair = competitive_set(match)
        if not pair or not ranked.intersection(pair):
            continue
        slug = event.get("slug") or ""
        results.append({"id": str(sid), "playerIds": list(pair),
                        "score": match["displayScore"],
                        "tournament": (match.get("tournament") or {}).get("name") or event.get("name") or "Torneo",
                        "country": (match.get("tournament") or {}).get("countryCode") or "GT",
                        "date": datetime.fromtimestamp(event["startAt"], timezone.utc).strftime("%Y-%m-%d"),
                        "url": "https://www.start.gg/" + slug if re.fullmatch(r"tournament/[\w-]+/event/[\w-]+", slug) else None})
    results.sort(key=lambda row: (row["date"], row["id"]), reverse=True)
    start = datetime.fromtimestamp(snapshot["season"]["startInclusive"], timezone.utc).strftime("%d/%m/%Y")
    end = datetime.fromtimestamp(snapshot["season"]["endExclusive"] - 1, timezone.utc).strftime("%d/%m/%Y")
    international = snapshot.get("internationalComplete") is True
    countries = {(event.get("tournament") or {}).get("countryCode") for event in snapshot["events"] if str(event["id"]) in accepted}
    countries.discard(None)
    return {"schemaVersion": 2, "status": "international_pilot" if international else "local_pilot", "rankingComputed": True,
            "generatedAt": snapshot["generatedAt"], "seasonLabel": f"{start} – {end}",
            "scope": "Torneos presenciales en Guatemala y en el extranjero de jugadores descubiertos localmente." if international else "Solo torneos presenciales en Guatemala. Resultados del extranjero pendientes.",
            "players": ranking["ranking"], "results": results,
            "counts": {"players": len(ranking["ranking"]), "events": ranking["counts"]["eligibleEvents"],
                       "sets": ranking["counts"]["competitiveSets"], "countries": len(countries)},
            "method": ranking["method"], "limitations": ranking["limitations"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("ranking", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = export(json.loads(args.snapshot.read_text()), json.loads(args.ranking.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.output.with_suffix(".tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    tmp.replace(args.output)
    print(f"Vista piloto: {len(result['players'])} jugadores, {result['counts']['events']} eventos, {len(result['results'])} sets con clasificados.")


if __name__ == "__main__":
    main()
