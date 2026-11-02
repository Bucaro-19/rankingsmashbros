"""Read-only simulation of the coverage complement over a published run's private captures.

Runs coverage.py on a copy of national.json (or reads a copy it already produced), then
combines and ranks both versions with the same curation and TTS table, and prints what the
next normal cut would change. It publishes nothing, writes nothing to SQL or FTP, and never
replaces the original captures. Player IDs are only printed for the ones passed with --watch.
"""
import argparse
import json
import os
from pathlib import Path

from collect import Client
from combine import combine
from coverage import complement
from rank import compute


def ranked(snapshot, curation, points):
    excluded = list(curation.get("excludedEventIds", {})) + list(curation.get("excludedForeignEventIds", {}))
    return compute(snapshot, excluded, curation.get("playerOverrides", {}), points, curation.get("playerAliases", {}))


def compare(national, extended, abroad, curation, points, watch=()):
    before = ranked(combine(national, abroad), curation, points)
    after = ranked(combine(extended, abroad), curation, points)
    old = {row["id"]: row for row in before["fullRanking"]}
    new = {row["id"]: row for row in after["fullRanking"]}
    added = sorted(set(after["eventQualifications"]) - set(before["eventQualifications"]), key=int)
    return {
        "complement": extended.get("coverageComplement"),
        "before": {"eligibleEvents": before["counts"]["eligibleEvents"], "classified": len(old)},
        "after": {"eligibleEvents": after["counts"]["eligibleEvents"], "classified": len(new)},
        "newCapturedEvents": [{"id": eid, **{k: after["eventQualifications"][eid].get(k) for k in ("entrants", "activePlayers", "decision")}}
                              for eid in added],
        "rankingChanges": {"entered": len(set(new) - set(old)), "left": len(set(old) - set(new)),
                           "moved": sum(1 for pid in set(old) & set(new) if old[pid]["rank"] != new[pid]["rank"]),
                           "ratingChanged": sum(1 for pid in set(old) & set(new) if old[pid]["rating"] != new[pid]["rating"])},
        "watch": {pid: {"before": old.get(pid, {}).get("rank"), "after": new.get(pid, {}).get("rank"),
                        "eventsAfter": new.get(pid, {}).get("events"), "setsAfter": new.get(pid, {}).get("sets")} for pid in watch},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("national", type=Path)
    parser.add_argument("abroad", type=Path)
    parser.add_argument("--curation", type=Path, required=True)
    parser.add_argument("--points-csv", type=Path, help="Tabla TTS fijada, la misma del semanal")
    parser.add_argument("--extended", type=Path, help="Copia ya complementada; sin ella se ejecuta el complemento con STARTGG_TOKEN")
    parser.add_argument("--watch", action="append", default=[], help="ID público de jugador a seguir, repetible")
    args = parser.parse_args()
    national = json.loads(args.national.read_text())
    curation = json.loads(args.curation.read_text())
    if args.extended:
        extended = json.loads(args.extended.read_text())
    else:
        token = os.environ.get("STARTGG_TOKEN", "").strip()
        if not token:
            parser.exit(1, "Falta STARTGG_TOKEN o --extended.\n")
        extended, _ = complement(Client(token), national, curation)
    result = compare(national, extended, json.loads(args.abroad.read_text()), curation, args.points_csv.read_text() if args.points_csv else None, args.watch)
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
