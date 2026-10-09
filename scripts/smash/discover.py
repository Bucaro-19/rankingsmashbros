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

from rules import LOCAL_MINIMUM_ACTIVE
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
# Separate from TOURNAMENTS on purpose: who created a tournament is optional context for the
# organizer tops, so a rejected or failed owner query must never block the weekly capture.
OWNERS = """query($page:Int!,$after:Timestamp!,$before:Timestamp!){
 tournaments(query:{page:$page,perPage:50,sortBy:"startAt desc",
  filter:{countryCode:"GT",afterDate:$after,beforeDate:$before,videogameIds:[1386]}}){
  pageInfo{total totalPages}
  nodes{id city owner{id}}
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


def tournament_owners(client, start, end):
    """Creator and city per tournament id, or None when start.gg does not answer the query."""
    found = {}
    try:
        for page in range(1, 101):
            data = client.query(OWNERS, {"page": page, "after": start, "before": end})["tournaments"]
            total_pages = (data.get("pageInfo") or {}).get("totalPages")
            if not isinstance(total_pages, int) or total_pages < 0 or total_pages > 100:
                return None
            for node in data.get("nodes") or []:
                owner = (node.get("owner") or {}).get("id")
                city = node.get("city")
                found[str(node["id"])] = {"ownerId": str(owner) if owner is not None else None,
                                          "city": city.strip() if isinstance(city, str) and city.strip() else None}
            if page >= total_pages:
                return found
    except (APIError, KeyError, TypeError, AttributeError):
        pass
    return None


def tournament_catalog(tournaments, reasons, owners):
    """Every Ultimate tournament of the catalog with its creator, including the ones the ranking excludes."""
    if owners is None:
        return None
    catalog = []
    for tournament in tournaments:
        events = [{"id": str(event.get("id")), "name": event.get("name"), "type": event.get("type"),
                   "numEntrants": event.get("numEntrants"), "startAt": event.get("startAt"),
                   "reason": reasons.get(str(event.get("id")))}
                  for event in tournament.get("events") or []
                  if str((event.get("videogame") or {}).get("id")) == str(GAME_ID)]
        if not events:
            continue
        extra = owners.get(str(tournament.get("id"))) or {}
        catalog.append({"id": str(tournament.get("id")), "name": tournament.get("name"), "slug": tournament.get("slug"),
                        "startAt": tournament.get("startAt"), "city": extra.get("city"),
                        "ownerId": extra.get("ownerId"), "events": events})
    return sorted(catalog, key=lambda row: row["id"])


def small_organizer_candidates(tournaments, start, end):
    """Private optional context, never merged with the national event/player/set collections."""
    return sorted([
        {**e, 'tournament': {k:t.get(k) for k in ('id','name','slug','countryCode')}}
        for t in tournaments for e in t.get('events') or []
        if t.get('countryCode') == 'GT' and t.get('isOnline') is False
        and e.get('isOnline') is False and e.get('state') == 'COMPLETED'
        and e.get('type') == 1 and str((e.get('videogame') or {}).get('id')) == str(GAME_ID)
        and type(e.get('numEntrants')) is int and 1 <= e['numEntrants'] < LOCAL_MINIMUM_ACTIVE
        and type(e.get('startAt')) is int and start <= e['startAt'] < end
    ], key=lambda e:(e['startAt'], str(e['id'])), reverse=True)


def discover(client, start, end, *, max_events=None, include_small=False, organizer_candidates=False):
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
    reasons = {}
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
            elif not isinstance(event.get("numEntrants"), int) or event["numEntrants"] < 1 or (not include_small and event["numEntrants"] < LOCAL_MINIMUM_ACTIVE):
                reason = f"under_{LOCAL_MINIMUM_ACTIVE}_entrants"
            elif not isinstance(event.get("startAt"), int) or not start <= event["startAt"] < end:
                reason = "outside_window"
            reasons[str(event.get("id"))] = reason
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
    # After the event captures: the ranking data is already complete if this optional query fails.
    catalog = tournament_catalog(tournaments, reasons, tournament_owners(client, start, end))
    countries = Counter((((p.get("user") or {}).get("location") or {}).get("country") or "unknown") for p in players.values())
    result = {"kind": "national_discovery", "generatedAt": datetime.now(timezone.utc).isoformat(),
            "season": {"startInclusive": start, "endExclusive": end},
            "catalogComplete": True, "eventsComplete": max_events is None,
            "tournamentsFound": len(tournaments), "candidateEventsFound": len([e for t in tournaments for e in t.get("events") or [] if str((e.get("videogame") or {}).get("id")) == str(GAME_ID)]),
            "excludedEvents": excluded, "events": event_records, "players": players, "sets": matches,
            "countryCounts": dict(countries), "requests": client.calls,
            "tournamentCatalog": catalog,
            "selectionNote": ("Estudio: todos los eventos presenciales singles con inscritos conocidos; aún requieren evaluación de DQ, puntos y exclusiones editoriales."
                              if include_small else "Provisional: eventos presenciales singles con al menos 20 inscritos; solo se admiten al cálculo los que tengan 20 jugadores activos; faltan DQ, excepciones por valor de jugadores y exclusiones editoriales de UltRank.")}
    if organizer_candidates:
        try:
            result['organizerCandidates'] = small_organizer_candidates(tournaments, start, end)
        except (KeyError, TypeError, ValueError):
            # An optional catalog defect must not invalidate the already captured national cut.
            result['organizerCandidates'] = None
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2026-01-01")
    parser.add_argument("--end", required=True)
    parser.add_argument("--max-events", type=int, help="Para una muestra reciente; la captura se marca incompleta")
    parser.add_argument("--include-small", action="store_true", help="Capturar también singles locales con menos de 20 inscritos para un estudio; no modifica el ranking publicado")
    parser.add_argument('--organizer-candidates', action='store_true', help='Guardar candidatos pequeños aparte, sin descargar ni incorporar sus sets al ranking')
    args = parser.parse_args()
    try:
        start, end = season_timestamp(args.start), season_timestamp(args.end)
        if start >= end or (args.max_events is not None and args.max_events < 1):
            raise ValueError("Fechas o límite inválidos.")
        token = os.environ.get("STARTGG_TOKEN") or getpass.getpass("Token start.gg (entrada oculta): ")
        if not token.strip():
            raise ValueError("Se requiere un token de start.gg.")
        result = discover(Client(token.strip()), start, end, max_events=args.max_events, include_small=args.include_small, organizer_candidates=args.organizer_candidates)
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
