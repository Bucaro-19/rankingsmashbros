"""Export the provisional ranking and its event ledger for the static website."""
import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from rank import competitive_set, compute


def event_url(slug):
    return "https://www.start.gg/" + slug if re.fullmatch(r"tournament/[\w-]+/event/[\w-]+", slug or "") else None


def export(snapshot, ranking, curation=None, previous=None):
    curation = curation or {}
    if ranking.get("kind") != "smash_gt_provisional" or snapshot.get("kind") != "national_discovery":
        raise ValueError("Se requiere una captura nacional y su ranking provisional.")
    if snapshot["generatedAt"] != ranking["generatedAt"]:
        raise ValueError("La captura y el ranking no corresponden a la misma consulta.")
    all_players = ranking.get("fullRanking", ranking["ranking"])
    if "fullRanking" in ranking and (len(all_players) != ranking["counts"]["eligiblePlayers"]
            or all_players[:100] != ranking["ranking"]
            or [row.get("rank") for row in all_players] != list(range(1, len(all_players) + 1))
            or len({row["id"] for row in all_players}) != len(all_players)):
        raise ValueError("El ranking completo no coincide con sus clasificados y su top 100.")
    ranked = {row["id"] for row in all_players}
    accepted = set(ranking["eventIds"])
    results = []
    event_players = defaultdict(set)
    event_sets = Counter()
    activity = defaultdict(lambda: defaultdict(Counter))
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
        for pid, outcome in zip(pair, ('wins', 'losses')):
            if pid in ranked:
                activity[pid][eid][outcome] += 1
        slug = event.get("slug") or ""
        results.append({"id": str(sid), "eventId": eid, "playerIds": list(pair),
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
    season_start = datetime.fromtimestamp(snapshot["season"]["startInclusive"], timezone.utc)
    season_year = season_start.year
    start = season_start.strftime("%d/%m/%Y")
    # The UTC search bound can extend into the following local day. The public
    # label must not claim results from a day that had not begun at capture time.
    captured_at = datetime.fromisoformat(snapshot["generatedAt"]).timestamp()
    visible_end = min(captured_at, snapshot["season"]["endExclusive"] - 1)
    end = datetime.fromtimestamp(visible_end, ZoneInfo("America/Guatemala")).strftime("%d/%m/%Y")
    international = snapshot.get("internationalComplete") is True
    countries = {event["country"] for event in events}
    countries.discard(None)
    players = [dict(row) for row in all_players]
    event_dates = {e['id']: e['date'] for e in events}
    for row in players:
        ledger = [{'id': eid, 'wins': record['wins'], 'losses': record['losses']}
                  for eid, record in activity[row['id']].items()]
        ledger.sort(key=lambda e: (event_dates[e['id']], e['id']), reverse=True)
        row['activity'] = {'months': sorted({event_dates[e['id']][:7] for e in ledger}),
                           'events': ledger}
    scope_key = "combined" if international else "guatemala"
    previous_scope = (previous.get("rankingScope") or ("combined" if previous.get("status") == "international_pilot" else "guatemala" if previous.get("status") == "local_pilot" else scope_key)) if previous else None
    previous_cut = None
    previous_year = previous.get("seasonYear") if previous else None
    if previous and previous_year is None:
        previous_start = str(previous.get("seasonLabel", "")).split(" – ")[0]
        previous_year = int(previous_start[-4:]) if re.fullmatch(r"\d\d/\d\d/\d{4}", previous_start) else None
    if (previous and previous_scope == scope_key and previous_year == season_year
            and previous.get("methodVersion") == ranking.get("methodVersion", "BT-PILOTO-1")
            and isinstance(previous.get("generatedAt"), str)
            and previous["generatedAt"] < snapshot["generatedAt"]
            and isinstance(previous.get("players"), list)):
        old_ranks = {row.get("id"): row.get("rank") for row in previous["players"]
                     if isinstance(row, dict) and isinstance(row.get("rank"), int)}
        for row in players:
            row["previousRank"] = old_ranks.get(row["id"])
        previous_cut = previous["generatedAt"]
    return {"schemaVersion": 2, "status": "international_pilot" if international else "local_pilot", "rankingComputed": True,
            "generatedAt": snapshot["generatedAt"], "seasonYear": season_year,
            "seasonLabel": f"{start} – {end}", "previousCutAt": previous_cut,
            "scope": "Torneos presenciales en Guatemala y en el extranjero de jugadores descubiertos localmente." if international else "Solo torneos presenciales en Guatemala. Resultados del extranjero pendientes.",
            "rankingScope": scope_key,
            "rankingCoverage": "all_eligible" if "fullRanking" in ranking else "top_100",
            "players": players, "results": results, "events": events, "excludedEvents": excluded_events,
            "counts": {"players": len(players), "eligiblePlayers": ranking["counts"]["eligiblePlayers"],
                       "top100": min(100, len(players)), "events": ranking["counts"]["eligibleEvents"],
                       "sets": ranking["counts"]["competitiveSets"], "countries": len(countries)},
            "eligibilityRules": ranking.get("eligibilityRules"),
            "method": ranking["method"], "methodVersion": ranking.get("methodVersion", "BT-PILOTO-1"),
            "ttsSource": ranking.get("ttsSource"), "limitations": ranking["limitations"]}


def export_views(snapshot, ranking, curation, points_table, previous=None):
    """One atomic payload: combined default plus independently fitted GT-only view."""
    if not snapshot.get('internationalComplete'):
        raise ValueError('Las dos vistas requieren la captura internacional completa.')
    result = export(snapshot, ranking, curation, previous)
    local_events = [e for e in snapshot['events'] if e['tournament'].get('countryCode') == 'GT']
    local_ids = {str(e['id']) for e in local_events}
    local_snapshot = {**snapshot, 'internationalComplete': False, 'events': local_events,
                      'sets': {sid: m for sid, m in snapshot['sets'].items()
                               if str((m.get('event') or {}).get('id')) in local_ids}}
    local_curation = {**curation, 'excludedForeignEventIds': {}}
    local_rank = compute(local_snapshot, curation.get('excludedEventIds', {}),
                         curation.get('playerOverrides', {}), points_table, curation.get('playerAliases', {}))
    previous_local = previous.get('localRanking') if previous else None
    local = export(local_snapshot, local_rank, local_curation, previous_local)
    local['scope'] = 'Solo torneos presenciales de Guatemala; cálculo independiente del mismo corte.'
    local['limitations'] = ['Los resultados extranjeros se excluyen por la vista seleccionada; no están pendientes de descarga.'] + local['limitations'][1:]
    result['localRanking'] = local
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("ranking", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--curation", type=Path)
    parser.add_argument("--previous-public", type=Path, help="Corte público previo para mostrar cambio de puestos")
    parser.add_argument("--include-local", action="store_true", help="Publicar también la clasificación calculada solo con torneos GT")
    parser.add_argument("--points-csv", type=Path, help="Misma tabla TTS usada por el cálculo combinado")
    args = parser.parse_args()
    if args.include_local and not args.points_csv:
        parser.error("--include-local requiere --points-csv para mantener los mismos pesos de torneos")
    previous = json.loads(args.previous_public.read_text()) if args.previous_public and args.previous_public.is_file() else None
    snapshot = json.loads(args.snapshot.read_text())
    ranking = json.loads(args.ranking.read_text())
    curation = json.loads(args.curation.read_text()) if args.curation else {}
    result = (export_views(snapshot, ranking, curation, args.points_csv.read_text(), previous)
              if args.include_local else export(snapshot, ranking, curation, previous))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.output.with_suffix(".tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    tmp.replace(args.output)
    print(f"Vista piloto: {len(result['players'])} jugadores, {result['counts']['events']} eventos, {len(result['results'])} sets con clasificados.")


if __name__ == "__main__":
    main()
