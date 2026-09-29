"""Compare local-event thresholds without changing the published ranking."""
import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from publish_ranking import event_url
from rank import competitive_set, compute


def comparison_snapshot(national, previous):
    if (national.get("kind") != "national_discovery" or not national.get("catalogComplete")
            or not national.get("eventsComplete") or "todos los eventos" not in national.get("selectionNote", "")):
        raise ValueError("Se requiere la captura completa del estudio con torneos pequeños.")
    if (previous.get("kind") != "national_discovery" or not previous.get("internationalComplete")
            or abs(national["season"]["startInclusive"] - previous["season"]["startInclusive"]) > 24 * 3600):
        raise ValueError("Se requiere un corte previo completo con torneos extranjeros de la misma temporada.")
    foreign = {str(event["id"]): event for event in previous["events"]
               if (event.get("tournament") or {}).get("countryCode") != "GT"}
    local = {str(event["id"]): event for event in national["events"]}
    if set(local) & set(foreign):
        raise ValueError("Un evento se repite entre los datos locales y extranjeros.")
    foreign_sets = {sid: match for sid, match in previous["sets"].items()
                    if str((match.get("event") or {}).get("id")) in foreign}
    if set(foreign_sets) & set(national["sets"]):
        raise ValueError("Un set se repite entre los datos locales y extranjeros.")
    return {**national, "events": national["events"] + list(foreign.values()),
            "players": {**previous["players"], **national["players"]},
            "sets": {**foreign_sets, **national["sets"]},
            "internationalComplete": True, "foreignAsOf": previous["generatedAt"]}


def scenario_summary(baseline, variant):
    original = {row["id"]: row for row in baseline["ranking"]}
    updated = {row["id"]: row for row in variant["ranking"]}
    moved = [abs(row["rank"] - updated[pid]["rank"]) for pid, row in original.items() if pid in updated]
    return {"events": variant["counts"]["eligibleEvents"],
            "sets": variant["counts"]["competitiveSets"],
            "players": variant["counts"]["rankedPlayers"],
            "addedEvents": len(set(variant["eventIds"]) - set(baseline["eventIds"])),
            "newTop100": [{"tag": row["tag"], "rank": row["rank"]} for row in variant["ranking"] if row["id"] not in original],
            "leftTop100": [{"tag": row["tag"], "rank": row["rank"]} for row in baseline["ranking"] if row["id"] not in updated],
            "commonPlayersMoved": sum(change > 0 for change in moved),
            "largestMove": max(moved, default=0),
            "top10": [{"tag": row["tag"], "oldRank": original.get(row["id"], {}).get("rank"),
                       "rank": row["rank"], "rating": row["rating"]} for row in variant["ranking"][:10]]}


def study(national, previous, curation, points_table, published=None):
    snapshot = comparison_snapshot(national, previous)
    exclusions = set(curation.get("excludedEventIds", {})) | set(curation.get("excludedForeignEventIds", {}))
    kwargs = {"excluded_event_ids": exclusions, "player_overrides": curation.get("playerOverrides", {}),
              "points_table": points_table, "player_aliases": curation.get("playerAliases", {})}
    baseline = compute(snapshot, **kwargs)
    if published is not None:
        expected = [(row["id"], row["rank"], row["rating"]) for row in published.get("players", [])]
        actual = [(row["id"], row["rank"], row["rating"]) for row in baseline["ranking"]]
        if (expected != actual or published.get("counts", {}).get("events") != baseline["counts"]["eligibleEvents"]
                or published.get("counts", {}).get("sets") != baseline["counts"]["competitiveSets"]):
            raise ValueError("La base de la simulación no reproduce el ranking público usado como referencia.")
    exception = compute(snapshot, **kwargs, allow_points_exception=True)
    min24 = compute(snapshot, **kwargs, local_minimum=24)
    min16 = compute(snapshot, **kwargs, local_minimum=16)
    valid_sets = Counter()
    for match in national["sets"].values():
        if competitive_set(match):
            valid_sets[str(match["event"]["id"])] += 1
    small = []
    for event in national["events"]:
        eid = str(event["id"])
        if event.get("numEntrants", 0) >= 32:
            continue
        evidence = exception["eventQualifications"][eid]
        small.append({"id": eid, "name": (event.get("tournament") or {}).get("name") or event["name"],
                      "eventName": event["name"],
                      "date": datetime.fromtimestamp(event["startAt"], ZoneInfo("America/Guatemala")).date().isoformat(),
                      "url": event_url(event.get("slug")), "entrants": event["numEntrants"],
                      "activePlayers": evidence["activePlayers"], "validSets": valid_sets[eid],
                      "estimatedPoints": evidence["estimatedPoints"], "valuedPlayers": evidence["valuedPlayers"],
                      "qualifiesByException": evidence["path"] == "points", "decision": evidence["decision"],
                      "exclusionReason": curation.get("excludedEventIds", {}).get(eid)})
    small.sort(key=lambda row: (row["date"], row["name"].casefold(), row["id"]))
    return {"schemaVersion": 1, "snapshotAt": national["generatedAt"],
            "foreignResultsAsOf": snapshot["foreignAsOf"],
            "baselineVerifiedAsOf": published.get("generatedAt") if published is not None else None,
            "status": "simulacion_sin_cambio_de_regla",
            "baseline": {"events": baseline["counts"]["eligibleEvents"],
                         "sets": baseline["counts"]["competitiveSets"],
                         "players": baseline["counts"]["rankedPlayers"],
                         "top10": [{"tag": row["tag"], "rank": row["rank"], "rating": row["rating"]}
                                   for row in baseline["ranking"][:10]]},
            "scenarios": {"pointsException": scenario_summary(baseline, exception),
                          "min24": scenario_summary(baseline, min24),
                          "min16": scenario_summary(baseline, min16)},
            "smallEvents": small,
            "source": "https://docs.google.com/document/d/1dC5oJaRfXITqlVMG8w6uZ1KGVjWxshbNqQzRD6zSXE8/edit"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("national", type=Path, help="Captura completa hecha con --include-small")
    parser.add_argument("previous", type=Path, help="Corte combinado anterior, usado solo para mantener rivales extranjeros fijos")
    parser.add_argument("curation", type=Path)
    parser.add_argument("points_csv", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--published-public", type=Path, help="Verificar que el escenario base reproduce el ranking publicado")
    args = parser.parse_args()
    result = study(json.loads(args.national.read_text()), json.loads(args.previous.read_text()),
                   json.loads(args.curation.read_text()), args.points_csv.read_text(),
                   json.loads(args.published_public.read_text()) if args.published_public else None)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    temporary.replace(args.output)
    print(f"Estudio: {len(result['smallEvents'])} eventos pequeños; "
          f"{result['scenarios']['pointsException']['addedEvents']} califican por excepción TTS estimada.")


if __name__ == "__main__":
    main()
