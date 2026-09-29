"""Combine complete domestic and foreign event captures without losing provenance."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from rank import competitive_set


def combine(national, abroad):
    if national.get("kind") != "national_discovery" or not national.get("catalogComplete") or not national.get("eventsComplete"):
        raise ValueError("La captura nacional está incompleta.")
    if abroad.get("kind") != "abroad_discovery" or abroad.get("nationalGeneratedAt") != national.get("generatedAt"):
        raise ValueError("Las capturas no corresponden a la misma consulta nacional.")
    if abroad.get("season") != national.get("season") or not abroad.get("discoveryComplete") or not abroad.get("eventsComplete"):
        raise ValueError("La cobertura extranjera no está completa.")
    event_ids = {str(event["id"]) for event in national["events"]}
    excluded = set(abroad.get("excludedEventIds", []))
    seed_ids = {eid: set(player_ids) for eid, player_ids in abroad.get("eventSources", {}).items()}
    played_by_seed = set()
    for match in abroad["sets"].values():
        eid = str((match.get("event") or {}).get("id"))
        pair = competitive_set(match)
        if pair and seed_ids.get(eid, set()).intersection(pair):
            played_by_seed.add(eid)
    accepted_foreign = {eid: event for eid, event in abroad["fetchedEvents"].items()
                        if eid not in excluded and eid in played_by_seed}
    for eid in accepted_foreign:
        if eid in event_ids:
            raise ValueError("Evento repetido entre capturas.")
    result = {**national}
    result["events"] = national["events"] + list(accepted_foreign.values())
    result["players"] = {**national["players"], **abroad["players"]}
    result["sets"] = {**national["sets"], **{sid: match for sid, match in abroad["sets"].items()
                                                  if str((match.get("event") or {}).get("id")) in accepted_foreign}}
    result["internationalComplete"] = True
    result["nationalGeneratedAt"] = national["generatedAt"]
    result["generatedAt"] = datetime.now(timezone.utc).isoformat()
    result["foreignSeedPlayers"] = len(abroad["seedPlayerIds"])
    result["foreignEventsFound"] = len(abroad["events"])
    result["foreignEventsFetched"] = len(accepted_foreign)
    result["foreignEventsWithoutSeedSet"] = sorted(set(abroad["fetchedEvents"]) - played_by_seed)
    result["excludedForeignEventIds"] = abroad.get("excludedEventIds", [])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("national", type=Path)
    parser.add_argument("abroad", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = combine(json.loads(args.national.read_text()), json.loads(args.abroad.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.output.with_suffix(".tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False))
    tmp.replace(args.output)
    print(f"Capturas unidas: {result['foreignEventsFetched']} eventos extranjeros, {len(result['events'])} en total.")


if __name__ == "__main__":
    main()
