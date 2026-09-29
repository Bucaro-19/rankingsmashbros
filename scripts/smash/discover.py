"""Discover Guatemala Ultimate events and keep a complete, auditable local snapshot."""
import argparse
import getpass
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from collect import APIError, Client

GAME_ID = 1386
SEASON_ZONE = ZoneInfo("America/Guatemala")


def season_timestamp(value):
    """Interpret calendar-season boundaries at midnight in Guatemala."""
    return int(datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=SEASON_ZONE).timestamp())
PLAYER = "id gamerTag user { id slug location { country } }"
TOURNAMENTS = """query($page:Int!,$after:Timestamp!,$before:Timestamp!){
 tournaments(query:{page:$page,perPage:50,sortBy:"startAt desc",
  filter:{countryCode:"GT",afterDate:$after,beforeDate:$before,videogameIds:[1386]}}){
  pageInfo{total totalPages}
  nodes{id name slug startAt endAt countryCode isOnline
   events(limit:30){id name slug numEntrants isOnline state startAt type videogame{id name}}}
 }}"""
ENTRANTS = """query($id:ID!,$page:Int!){event(id:$id){id
 entrants(query:{page:$page,perPage:100}){pageInfo{total totalPages}
  nodes{id name participants{player{PLAYER}}}}
 }}""".replace("PLAYER", PLAYER)
STANDINGS = """query($id:ID!,$page:Int!){event(id:$id){id
 standings(query:{page:$page,perPage:100}){pageInfo{total totalPages}
  nodes{placement isFinal entrant{id}}}
 }}"""
SETS = """query($id:ID!,$page:Int!){event(id:$id){id
 sets(page:$page,perPage:50){pageInfo{total totalPages}
  nodes{id state winnerId displayScore completedAt updatedAt
   slots{entrant{id participants{player{PLAYER}}}}}}
 }}""".replace("PLAYER", PLAYER)


def pages(client, query, key, event_id, *, max_pages=100):
    nodes = []
    total_pages = None
    for page in range(1, max_pages + 1):
        event = client.query(query, {"id": event_id, "page": page}).get("event")
        if not event or str(event.get("id")) != str(event_id):
            raise APIError("Evento no disponible; se conserva la captura anterior.")
        connection = event.get(key)
        if not isinstance(connection, dict):
            raise APIError(f"{key} no disponible; se conserva la captura anterior.")
        info = connection.get("pageInfo") or {}
        reported = info.get("totalPages")
        if not isinstance(reported, int) or reported < 0:
            raise APIError(f"Paginación inválida en {key}.")
        if total_pages is None:
            total_pages = reported
        elif reported != total_pages:
            raise APIError(f"La paginación de {key} cambió durante la importación.")
        nodes.extend(connection.get("nodes") or [])
        if page >= total_pages:
            break
    if total_pages is None or total_pages > max_pages:
        raise APIError(f"Límite de páginas de {key} alcanzado; no se guardó una captura parcial.")
    if len(nodes) != info.get("total"):
        raise APIError(f"Conteo inconsistente en {key}; no se guardó una captura parcial.")
    return nodes


def fetch_event(client, event):
    event_id = event["id"]
    entrants = pages(client, ENTRANTS, "entrants", event_id)
    standings = pages(client, STANDINGS, "standings", event_id)
    sets = pages(client, SETS, "sets", event_id)
    entrant_to_player = {}
    players = {}
    for entrant in entrants:
        participants = entrant.get("participants") or []
        if len(participants) != 1:
            continue
        player = participants[0].get("player") or {}
        if player.get("id") is None:
            continue
        pid = str(player["id"])
        entrant_to_player[str(entrant["id"])] = pid
        players[pid] = player
    placements = {}
    for standing in standings:
        entrant = standing.get("entrant") or {}
        pid = entrant_to_player.get(str(entrant.get("id")))
        if pid and isinstance(standing.get("placement"), int) and standing.get("isFinal") is True:
            placements[pid] = standing["placement"]
    matches = {}
    for match in sets:
        if match.get("id") is not None:
            matches[str(match["id"])] = {**match, "event": {k: event.get(k) for k in ("id", "name", "slug", "numEntrants", "startAt")},
                                         "tournament": event["tournament"]}
    record = {**event, "entrantCountFetched": len(entrants),
              "standingsFetched": len(standings), "setsFetched": len(sets),
              "entrantsWithoutPlayer": len(entrants) - len(entrant_to_player),
              "placements": placements}
    return record, players, matches


def discover(client, start, end, *, max_events=None):
    tournaments = []
    for page in range(1, 101):
        data = client.query(TOURNAMENTS, {"page": page, "after": start, "before": end})["tournaments"]
        info = data.get("pageInfo") or {}
        total_pages = info.get("totalPages")
        if not isinstance(total_pages, int) or total_pages < 0 or total_pages > 100:
            raise APIError("No se pudo cubrir el catálogo de torneos.")
        tournaments.extend(data.get("nodes") or [])
        if page >= total_pages:
            break
    if len(tournaments) != info.get("total"):
        raise APIError("Conteo inconsistente de torneos.")

    eligible = []
    excluded = []
    for tournament in tournaments:
        for event in tournament.get("events") or []:
            if str((event.get("videogame") or {}).get("id")) != str(GAME_ID):
                continue
            reason = None
            if event.get("isOnline") is not False or tournament.get("isOnline") is True:
                reason = "online_or_unknown"
            elif event.get("state") != "COMPLETED":
                reason = "unfinished_event"
            elif event.get("type") != 1:
                reason = "not_singles"
            elif not isinstance(event.get("numEntrants"), int) or event["numEntrants"] < 32:
                reason = "under_32_entrants"
            elif not isinstance(event.get("startAt"), int) or not start <= event["startAt"] < end:
                reason = "outside_window"
            if reason:
                excluded.append({"id": str(event.get("id")), "reason": reason})
            else:
                eligible.append({**event, "tournament": {k: tournament.get(k) for k in ("id", "name", "slug", "countryCode")}})
    eligible.sort(key=lambda e: (e["startAt"], str(e["id"])))
    if max_events is not None:
        eligible = eligible[-max_events:]

    players = {}
    event_records = []
    matches = {}
    for index, event in enumerate(eligible, 1):
        record, event_players, event_matches = fetch_event(client, event)
        players.update(event_players)
        matches.update(event_matches)
        event_records.append(record)
        print(f"{index}/{len(eligible)} {event['name']}: {record['entrantCountFetched']} participantes, {record['setsFetched']} sets", flush=True)
    countries = Counter((((p.get("user") or {}).get("location") or {}).get("country") or "unknown") for p in players.values())
    return {"kind": "national_discovery", "generatedAt": datetime.now(timezone.utc).isoformat(),
            "season": {"startInclusive": start, "endExclusive": end},
            "catalogComplete": True, "eventsComplete": max_events is None,
            "tournamentsFound": len(tournaments), "candidateEventsFound": len([e for t in tournaments for e in t.get("events") or [] if str((e.get("videogame") or {}).get("id")) == str(GAME_ID)]),
            "excludedEvents": excluded, "events": event_records, "players": players, "sets": matches,
            "countryCounts": dict(countries), "requests": client.calls,
            "selectionNote": "Provisional: eventos presenciales singles con al menos 32 inscritos; faltan DQ, excepciones por valor de jugadores y exclusiones editoriales de UltRank."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2026-01-01")
    parser.add_argument("--end", required=True)
    parser.add_argument("--max-events", type=int, help="Para una muestra reciente; la captura se marca incompleta")
    args = parser.parse_args()
    try:
        start, end = season_timestamp(args.start), season_timestamp(args.end)
        if start >= end or (args.max_events is not None and args.max_events < 1):
            raise ValueError("Fechas o límite inválidos.")
        token = os.environ.get("STARTGG_TOKEN") or getpass.getpass("Token start.gg (entrada oculta): ")
        if not token.strip():
            raise ValueError("Se requiere un token de start.gg.")
        result = discover(Client(token.strip()), start, end, max_events=args.max_events)
        target = Path(__file__).parent / "data" / "national.json"
        target.parent.mkdir(exist_ok=True)
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps(result, ensure_ascii=False))
        tmp.replace(target)
        print(f"Guardado {target}: {len(result['events'])} eventos, {len(result['players'])} jugadores, {len(result['sets'])} sets, {result['requests']} consultas.")
        print("Perfiles por país:", result["countryCounts"])
    except (APIError, ValueError) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
