"""Find overseas Ultimate events of locally discovered Guatemala candidates."""
import argparse
import getpass
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from collect import APIError, Client
from discover import fetch_event
from rank import profile_country

USER_EVENTS = """query($id:ID!,$page:Int!){user(id:$id){
 events(query:{page:$page,perPage:100,sortBy:"startAt desc",
  filter:{videogameId:[1386],eventType:1,minEntrantCount:64}}){
  pageInfo{total totalPages}
  nodes{id name slug startAt numEntrants isOnline state type videogame{id name}
   tournament{id name slug countryCode isOnline}}
 }}}"""


def save(path, result):
    path.parent.mkdir(exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False))
    tmp.replace(path)


def seeds(snapshot, overrides):
    result = {}
    for pid, player in snapshot["players"].items():
        if profile_country(player) in {"gt", "guatemala"} or pid in overrides:
            uid = (player.get("user") or {}).get("id")
            result[pid] = str(uid) if uid is not None else None
    return result


def scan_user(client, user_id, start, end):
    selected = {}
    for page in range(1, 101):
        user = client.query(USER_EVENTS, {"id": user_id, "page": page}).get("user")
        connection = (user or {}).get("events")
        if not isinstance(connection, dict):
            raise APIError("Historial de eventos no disponible; no se registra como completo.")
        total_pages = (connection.get("pageInfo") or {}).get("totalPages")
        if not isinstance(total_pages, int) or total_pages < 0 or total_pages > 100:
            raise APIError("Paginación de eventos incompleta.")
        for event in connection.get("nodes") or []:
            started = event.get("startAt")
            if not isinstance(started, int):
                continue
            if started < start:
                continue
            if started >= end or event.get("isOnline") is not False or event.get("type") != 1 or event.get("state") != "COMPLETED":
                continue
            tournament = event.get("tournament") or {}
            country = tournament.get("countryCode")
            if country is None or country == "GT":
                continue
            if str((event.get("videogame") or {}).get("id")) != "1386":
                continue
            selected[str(event["id"])] = event
        if page >= total_pages:
            return selected
    raise APIError("Límite de páginas de historial alcanzado.")


def discover_abroad(client, national, overrides, path, *, max_users=None):
    roots = seeds(national, overrides)
    if path.exists():
        state = json.loads(path.read_text())
        if state.get("nationalGeneratedAt") != national["generatedAt"]:
            raise ValueError("La captura nacional cambió; el historial extranjero anterior no se puede reutilizar.")
    else:
        state = {"kind": "abroad_discovery", "nationalGeneratedAt": national["generatedAt"],
                 "season": national["season"], "seedPlayerIds": sorted(roots),
                 "scannedPlayerIds": [], "missingUserIds": [], "events": {},
                 "eventSources": {}, "discoveryComplete": False, "fetchedEvents": {},
                 "players": {}, "sets": {}, "eventsComplete": False}
    previous_roots = set(state["seedPlayerIds"])
    current_roots = set(roots)
    if not previous_roots.issubset(current_roots):
        raise ValueError("Se retiraron jugadores semilla; la captura extranjera debe reconstruirse.")
    if previous_roots != current_roots:
        # Documented eligibility additions should not discard completed API work.
        state["seedPlayerIds"] = sorted(current_roots)
        state["discoveryComplete"] = False
        state["eventsComplete"] = False
        save(path, state)
    remaining = [pid for pid in sorted(roots) if pid not in state["scannedPlayerIds"]]
    if max_users is not None:
        remaining = remaining[:max_users]
    for index, pid in enumerate(remaining, 1):
        uid = roots[pid]
        if uid is None:
            state["missingUserIds"].append(pid)
        else:
            found = scan_user(client, uid, national["season"]["startInclusive"], national["season"]["endExclusive"])
            for eid, event in found.items():
                state["events"][eid] = event
                sources = state["eventSources"].setdefault(eid, [])
                if pid not in sources:
                    sources.append(pid)
        state["scannedPlayerIds"].append(pid)
        if index % 10 == 0 or index == len(remaining):
            save(path, state)
            print(f"Jugadores consultados {len(state['scannedPlayerIds'])}/{len(roots)}; eventos extranjeros {len(state['events'])}; API {client.calls}", flush=True)
    state["discoveryComplete"] = len(state["scannedPlayerIds"]) == len(roots)
    save(path, state)
    return state


def fetch_abroad_events(client, state, path, excluded=(), *, max_events=None):
    if not state["discoveryComplete"]:
        raise ValueError("Primero se debe completar el descubrimiento de jugadores.")
    excluded = {str(eid) for eid in excluded}
    candidates = [event for eid, event in state["events"].items() if eid not in excluded]
    candidates.sort(key=lambda event: (event["startAt"], str(event["id"])))
    remaining = [event for event in candidates if str(event["id"]) not in state["fetchedEvents"]]
    if max_events is not None:
        remaining = remaining[:max_events]
    for index, event in enumerate(remaining, 1):
        record, players, matches = fetch_event(client, event)
        state["fetchedEvents"][str(event["id"])] = record
        state["players"].update(players)
        state["sets"].update(matches)
        save(path, state)
        print(f"Brackets extranjeros {len(state['fetchedEvents'])}/{len(candidates)}: {event['name']} ({record['setsFetched']} sets)", flush=True)
    state["excludedEventIds"] = sorted(excluded)
    state["eventsComplete"] = all(str(event["id"]) in state["fetchedEvents"] for event in candidates)
    save(path, state)
    return state


def require_reviewed_events(state, curation):
    excluded = set(curation.get("excludedForeignEventIds", {}))
    approved = set(curation.get("approvedForeignEventIds", {}))
    if excluded & approved:
        raise ValueError("Un evento extranjero está aprobado y excluido a la vez.")
    unreviewed = set(state["events"]) - excluded - approved
    if unreviewed:
        raise ValueError("Eventos extranjeros nuevos pendientes de revisión: " + ", ".join(sorted(unreviewed)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("national", type=Path)
    parser.add_argument("--curation", type=Path, required=True)
    parser.add_argument("--max-users", type=int, help="Muestra para pruebas; marca la cobertura incompleta")
    parser.add_argument("--fetch", action="store_true", help="Descargar brackets completos tras revisar candidatos")
    parser.add_argument("--max-events", type=int, help="Muestra de brackets; marca la cobertura incompleta")
    args = parser.parse_args()
    try:
        national = json.loads(args.national.read_text())
        curation = json.loads(args.curation.read_text())
        if national.get("kind") != "national_discovery" or not national.get("eventsComplete"):
            raise ValueError("Se necesita primero una captura nacional completa.")
        token = os.environ.get("STARTGG_TOKEN") or getpass.getpass("Token start.gg (entrada oculta): ")
        if not token.strip():
            raise ValueError("Se requiere un token de start.gg.")
        client = Client(token.strip())
        path = Path(__file__).parent / "data" / "abroad.json"
        state = discover_abroad(client, national, curation.get("playerOverrides", {}), path, max_users=args.max_users)
        if args.fetch:
            if state["discoveryComplete"]:
                require_reviewed_events(state, curation)
            fetch_abroad_events(client, state, path, curation.get("excludedForeignEventIds", {}), max_events=args.max_events)
        print(f"Descubrimiento completo: {state['discoveryComplete']}; brackets completos: {state['eventsComplete']}; API: {client.calls}.")
    except (ValueError, APIError) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
