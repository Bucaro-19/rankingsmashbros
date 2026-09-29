"""Reproducible coverage and sensitivity audit for the provisional ranking."""
import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from rank import competitive_set, compute, profile_country


def audit(snapshot, curation, points_table=None):
    excluded = set(curation.get("excludedEventIds", {})) | set(curation.get("excludedForeignEventIds", {}))
    overrides = curation.get("playerOverrides", {})

    def ranking(extra_excluded=()):
        return compute(snapshot, excluded | set(extra_excluded), overrides, points_table,
                       curation.get("playerAliases", {}))

    baseline = ranking()
    events = {str(event["id"]): event for event in snapshot["events"]}
    foreign = [eid for eid in baseline["eventIds"] if events[eid]["tournament"].get("countryCode") != "GT"]
    scenarios = {"Sin torneos extranjeros": ranking(foreign)} if foreign else {}
    for eid in foreign:
        scenarios[f"Sin {events[eid]['tournament']['name']} ({eid})"] = ranking([eid])

    valid_by_event = Counter()
    for match in snapshot["sets"].values():
        if competitive_set(match):
            valid_by_event[str(match["event"]["id"])] += 1
    ledger = []
    for eid, event in sorted(events.items(), key=lambda item: (item[1]["startAt"], item[0])):
        status = "incluido" if eid in baseline["eventIds"] else baseline["eventDecisions"].get(eid, "sin_decisión")
        slug = event.get("slug")
        ledger.append({"id": eid, "date": datetime.fromtimestamp(event["startAt"], timezone.utc).date().isoformat(),
                       "name": event["name"], "country": event["tournament"].get("countryCode"),
                       "entrants": event.get("numEntrants"), "validSets": valid_by_event[eid],
                       "status": status, "source": "https://www.start.gg/" + slug if slug else None})

    current = baseline["ranking"]
    scenario_maps = {name: {row["id"]: row for row in result["ranking"]} for name, result in scenarios.items()}
    top = [{"tag": row["tag"], "id": row["id"], "currentRank": row["rank"], "rating": row["rating"],
            "scenarios": {name: (rows[row["id"]]["rank"] if row["id"] in rows else None)
                          for name, rows in scenario_maps.items()}} for row in current[:10]]
    unverified = [{"rank": row["rank"], "tag": row["tag"], "id": row["id"],
                   "profileCountry": profile_country(snapshot["players"][row["id"]]) or "(vacío)",
                   "basis": row["countryBasis"]} for row in current
                  if profile_country(snapshot["players"][row["id"]]) not in {"gt", "guatemala"}]
    return {"snapshot": snapshot["generatedAt"], "counts": baseline["counts"],
            "coverage": {"localSeedPlayersForForeignSearch": snapshot.get("foreignSeedPlayers"),
                         "foreignEventsFound": snapshot.get("foreignEventsFound"),
                         "foreignEventsFetched": snapshot.get("foreignEventsFetched"),
                         "top100WithUnverifiedCountry": len(unverified),
                         "top100WithAtMostThreeEvents": sum(row["events"] <= 3 for row in current),
                         "top100WithFewerThanTenSets": sum(row["sets"] < 10 for row in current)},
            "unverifiedCountry": unverified, "top10Sensitivity": top, "eventLedger": ledger,
            "excludedForeignEvents": curation.get("excludedForeignEventIds", {}),
            "scenarioNote": "Cada escenario recalcula todo el modelo; un cambio de posición mide sensibilidad, no demuestra cuál orden es correcto."}


def markdown(result):
    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")

    lines = ["# Auditoría reproducible del piloto Smash GT", "",
             f"Captura: `{result['snapshot']}`. Este informe **no certifica** la elegibilidad ni convierte el piloto en ranking oficial.", "",
             "## Cobertura y pendientes", ""]
    for key, value in result["counts"].items():
        lines.append(f"- {key}: {value}")
    for key, value in result["coverage"].items():
        lines.append(f"- {key}: {value}")
    lines += ["", "La búsqueda extranjera parte de perfiles vistos en Guatemala; no prueba cobertura de quienes solo compiten fuera.",
              "El país del perfil y las excepciones son pistas de candidatura, no verificación de nacionalidad o residencia.", "",
              "## Sensibilidad del top 10", "",
              result["scenarioNote"], ""]
    scenarios = list(result["top10Sensitivity"][0]["scenarios"]) if result["top10Sensitivity"] else []
    lines += ["| Actual | Jugador | Puntos | " + " | ".join(scenarios) + " |",
              "|---:|---|---:|" + "---:|" * len(scenarios)]
    for row in result["top10Sensitivity"]:
        lines.append(f"| {row['currentRank']} | {cell(row['tag'])} | {row['rating']} | " +
                     " | ".join(str(row["scenarios"][name] or "fuera del top 100") for name in scenarios) + " |")
    lines += ["", "## Candidaturas del top 100 sin Guatemala en el perfil actual", "",
              "| Puesto | Jugador | País del perfil | Base provisional |", "|---:|---|---|---|"]
    for row in result["unverifiedCountry"]:
        lines.append(f"| {row['rank']} | {cell(row['tag'])} | {cell(row['profileCountry'])} | {cell(row['basis'])} |")
    lines += ["", "## Registro de eventos capturados", "",
              "| Fecha UTC | Evento | País | Inscritos | Sets válidos | Estado |", "|---|---|---|---:|---:|---|"]
    for row in result["eventLedger"]:
        name = f"[{cell(row['name'])}]({row['source']})" if row["source"] else cell(row["name"])
        lines.append(f"| {row['date']} | {name} | {cell(row['country'])} | {row['entrants']} | {row['validSets']} | {cell(row['status'])} |")
    if result["excludedForeignEvents"]:
        lines += ["", "## Eventos extranjeros descartados antes de descargar el cuadro", "",
                  "| ID start.gg | Motivo registrado |", "|---|---|"]
        for eid, reason in sorted(result["excludedForeignEvents"].items()):
            lines.append(f"| {cell(eid)} | {cell(reason)} |")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("curation", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--points-csv", type=Path)
    args = parser.parse_args()
    result = audit(json.loads(args.snapshot.read_text()), json.loads(args.curation.read_text()),
                   args.points_csv.read_text() if args.points_csv else None)
    args.output.write_text(markdown(result))
    print(f"Auditoría generada: {args.output}")


if __name__ == "__main__":
    main()
