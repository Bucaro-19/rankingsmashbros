"""Export the provisional ranking and its event ledger for the static website."""
import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from rank import competitive_set


def event_url(slug):
    return "https://www.start.gg/" + slug if re.fullmatch(r"tournament/[\w-]+/event/[\w-]+", slug or "") else None


def export(snapshot, ranking, curation=None):
    curation = curation or {}
    if ranking.get("kind") != "smash_gt_provisional" or snapshot.get("kind") != "national_discovery":
        raise ValueError("Se requiere una captura nacional y su ranking provisional.")
    if snapshot["generatedAt"] != ranking["generatedAt"]:
        raise ValueError("La captura y el ranking no corresponden a la misma consulta.")
    ranked = {row["id"] for row in ranking["ranking"]}
    accepted = set(ranking["eventIds"])
    results = []
    event_players = defaultdict(set)
    event_sets = Counter()
    for sid, match in snapshot["sets"].items():
        event = match.get("event") or {}
        eid = str(event.get("id"))
        if eid not in accepted:
            continue
        pair = competitive_set(match)
        if not pair:
            continue
        event_sets[eid] += 1
        event_players[eid].update(pair)
        if not ranked.intersection(pair):
            continue
        slug = event.get("slug") or ""
        results.append({"id": str(sid), "playerIds": list(pair),
                        "score": match["displayScore"],
                        "tournament": (match.get("tournament") or {}).get("name") or event.get("name") or "Torneo",
                        "country": (match.get("tournament") or {}).get("countryCode") or "GT",
                        "date": datetime.fromtimestamp(event["startAt"], timezone.utc).strftime("%Y-%m-%d"),
                        "url": event_url(slug)})
    results.sort(key=lambda row: (row["date"], row["id"]), reverse=True)
    events = []
    for event in snapshot["events"]:
        eid = str(event["id"])
        if eid not in accepted:
            continue
        tournament = event.get("tournament") or {}
        events.append({"id": eid, "name": tournament.get("name") or event.get("name") or "Torneo",
                       "eventName": event.get("name") or "Ultimate singles", "country": tournament.get("countryCode"),
                       "date": datetime.fromtimestamp(event["startAt"], ZoneInfo("America/Guatemala")).date().isoformat(),
                       "entrants": event.get("numEntrants"), "activePlayers": len(event_players[eid]),
                       "validSets": event_sets[eid], "ttsPointsEstimate": ranking.get("ttsPointsEstimate", {}).get(eid),
                       "url": event_url(event.get("slug"))})
    events.sort(key=lambda row: (row["date"], row["name"].casefold(), row["id"]))
    if sum(row["validSets"] for row in events) != ranking["counts"]["competitiveSets"]:
        raise ValueError("Los sets de eventos no coinciden con el cálculo del ranking.")
    excluded_events = []
    for event in snapshot["events"]:
        eid = str(event["id"])
        if eid in accepted or eid not in ranking.get("eventDecisions", {}):
            continue
        reason = curation.get("excludedEventIds", {}).get(eid) or curation.get("excludedForeignEventIds", {}).get(eid)
        if reason is None and ranking["eventDecisions"][eid] == "under_minimum_active_players":
            reason = "No llegó al mínimo de jugadores con un set competitivo."
        if reason:
            excluded_events.append({"id": eid, "name": (event.get("tournament") or {}).get("name") or event.get("name") or "Torneo",
                                    "reason": reason, "url": event_url(event.get("slug"))})
    for eid, reason in curation.get("excludedForeignEventIds", {}).items():
        if eid not in {row["id"] for row in excluded_events}:
            excluded_events.append({"id": eid, "name": f"Evento {eid}", "reason": reason, "url": None})
    excluded_events.sort(key=lambda row: row["id"])
    start = datetime.fromtimestamp(snapshot["season"]["startInclusive"], timezone.utc).strftime("%d/%m/%Y")
    end = datetime.fromtimestamp(snapshot["season"]["endExclusive"] - 1, timezone.utc).strftime("%d/%m/%Y")
    international = snapshot.get("internationalComplete") is True
    countries = {event["country"] for event in events}
    countries.discard(None)
    return {"schemaVersion": 2, "status": "international_pilot" if international else "local_pilot", "rankingComputed": True,
            "generatedAt": snapshot["generatedAt"], "seasonLabel": f"{start} – {end}",
            "scope": "Torneos presenciales en Guatemala y en el extranjero de jugadores descubiertos localmente." if international else "Solo torneos presenciales en Guatemala. Resultados del extranjero pendientes.",
            "players": ranking["ranking"], "results": results, "events": events, "excludedEvents": excluded_events,
            "counts": {"players": len(ranking["ranking"]), "events": ranking["counts"]["eligibleEvents"],
                       "sets": ranking["counts"]["competitiveSets"], "countries": len(countries)},
            "method": ranking["method"], "methodVersion": ranking.get("methodVersion", "BT-PILOTO-1"),
            "ttsSource": ranking.get("ttsSource"), "limitations": ranking["limitations"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("ranking", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--curation", type=Path)
    args = parser.parse_args()
    result = export(json.loads(args.snapshot.read_text()), json.loads(args.ranking.read_text()),
                    json.loads(args.curation.read_text()) if args.curation else None)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.output.with_suffix(".tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    tmp.replace(args.output)
    print(f"Vista piloto: {len(result['players'])} jugadores, {result['counts']['events']} eventos, {len(result['results'])} sets con clasificados.")


if __name__ == "__main__":
    main()
