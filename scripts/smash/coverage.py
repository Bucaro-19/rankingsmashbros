"""Complementary discovery of Guatemala events that the filtered tournament search omits.

Checked on 1/nov/2026: start.gg returns three Guatemala tournaments (947356, 948197, 957669)
when they are looked up by ID and in their players' set histories, but not in any search
tried: by country, by game, by both, by organizer, or in the organizer's profile list.
The cause inside start.gg is not known and is not assumed here.

This complement reads a small, fixed sample of national players' set histories plus the
tournament IDs listed in curation.json, validates every unseen tournament by ID with its real
metadata and applies the same event rules as discover.py. Admissible events join the national
capture and go through rank.py like any other event; smaller ones become private context.
It never assigns points or places. Ceilings are fixed; any failure or an exhausted budget
leaves the national capture exactly as it was, with a summary of what happened.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time

from collect import APIError, Client
from discover import GAME_ID, event_reason, fetch_event, small_organizer_candidates
from rank import competitive_set, profile_country
from rules import LOCAL_MINIMUM_ACTIVE

# Fixed ceilings, not arguments. Three attempts are reserved before every query (Client retries).
# The search never returns these tournaments, so every week they are downloaded again like any
# national event: the ceiling has to hold every known omitted event, measured at ~3.75 queries each.
MAX_ATTEMPTS = 210
MAX_SECONDS = 240
RECENT_SEEDS = 4
ROTATING_SEEDS = 4
HISTORY_PAGES = 2
# Histories never use more than this, and always leave the reserve to validation and downloads.
HISTORY_ATTEMPTS = 48
DOWNLOAD_RESERVE = 42
MAX_TOURNAMENTS = 25
MAX_EVENT_DOWNLOADS = 12
MAX_LISTED_IDS = 40

PLAYER_EVENTS = """query($id:ID!,$page:Int!){player(id:$id){
 sets(page:$page,perPage:50,filters:{entrantSize:[1]}){pageInfo{total totalPages}
  nodes{event{id startAt videogame{id} tournament{id countryCode}}}}
 }}"""
# The only lookup that returned the omitted tournaments: by ID, without country or game filters.
BY_IDS = """query($ids:[ID]){tournaments(query:{page:1,perPage:25,filter:{ids:$ids}}){
 pageInfo{total}
 nodes{id name slug startAt endAt countryCode isOnline city owner{id}
  events(limit:30){id name slug numEntrants isOnline state startAt type videogame{id name}}}
 }}"""


class BudgetExhausted(APIError):
    pass


class Budget:
    def __init__(self, client, clock=time.monotonic):
        self.client = client
        self.initial = client.calls
        self.clock = clock
        self.started = clock()

    @property
    def calls(self):
        return self.client.calls

    def used(self):
        return self.client.calls - self.initial

    def query(self, query, variables):
        if self.used() + 3 > MAX_ATTEMPTS or self.clock() - self.started >= MAX_SECONDS:
            raise BudgetExhausted("Presupuesto del complemento agotado.")
        return self.client.query(query, variables)


def history_limit():
    return min(HISTORY_ATTEMPTS, MAX_ATTEMPTS - DOWNLOAD_RESERVE)


def known_event_ids(national):
    """Events the national capture already has, admitted, excluded or kept as small candidates."""
    known = {str(e["id"]) for e in national.get("events") or []}
    known |= {str(e["id"]) for e in national.get("excludedEvents") or []}
    known |= {str(e["id"]) for e in national.get("organizerCandidates") or []}
    for tournament in national.get("tournamentCatalog") or []:
        known |= {str(e["id"]) for e in tournament.get("events") or []}
    return known


def week_index(generated_at):
    year, week, _ = datetime.fromisoformat(generated_at).isocalendar()
    return year * 53 + week


def seed_players(national):
    """Guatemala profiles active in the capture: the most recent ones plus a weekly rotation."""
    last = {}
    for match in (national.get("sets") or {}).values():
        pair = competitive_set(match)
        if pair is None:
            continue
        moment = match.get("completedAt") or match.get("updatedAt") or 0
        for pid in pair:
            player = (national.get("players") or {}).get(pid) or {}
            if profile_country(player) in {"gt", "guatemala"}:
                last[pid] = max(last.get(pid, 0), moment if isinstance(moment, int) else 0)
    ordered = sorted(last, key=lambda pid: (-last[pid], int(pid) if pid.isdigit() else 0, pid))
    recent, rest = ordered[:RECENT_SEEDS], ordered[RECENT_SEEDS:]
    if not rest:
        return recent
    offset = (week_index(national["generatedAt"]) * ROTATING_SEEDS) % len(rest)
    return recent + [rest[(offset + i) % len(rest)] for i in range(min(ROTATING_SEEDS, len(rest)))]


def listed_tournament_ids(curation):
    listed = curation.get("recoveredTournamentIds") or {}
    if not isinstance(listed, dict) or len(listed) > MAX_LISTED_IDS:
        raise ValueError("Lista de torneos a recuperar inválida.")
    ids = []
    for key, reason in listed.items():
        if not str(key).isdigit() or not isinstance(reason, str) or not reason.strip():
            raise ValueError("Lista de torneos a recuperar inválida.")
        ids.append(str(key))
    return sorted(ids, key=int)


def scan_histories(budget, seeds, start, end, known, summary):
    """Tournament IDs of unseen Guatemala events in the seeds' recent set histories."""
    found = {}
    for pid in seeds:
        if budget.used() + 3 > history_limit():
            break
        for page in range(1, HISTORY_PAGES + 1):
            if budget.used() + 3 > history_limit():
                summary["seedsTruncated"] += 1
                break
            player = budget.query(PLAYER_EVENTS, {"id": pid, "page": page}).get("player")
            connection = (player or {}).get("sets")
            if not isinstance(connection, dict):
                summary["seedsWithoutHistory"] += 1
                break
            summary["historyPages"] += 1
            for node in connection.get("nodes") or []:
                event = (node or {}).get("event") or {}
                tournament = event.get("tournament") or {}
                eid, tid = event.get("id"), tournament.get("id")
                if eid is None or tid is None or str(eid) in known or tournament.get("countryCode") != "GT":
                    continue
                # Other games' events would only spend validation queries.
                if str((event.get("videogame") or {}).get("id")) != str(GAME_ID):
                    continue
                if not isinstance(event.get("startAt"), int) or not start <= event["startAt"] < end:
                    continue
                found.setdefault(str(tid), set()).add(str(eid))
            total = (connection.get("pageInfo") or {}).get("totalPages")
            if not isinstance(total, int) or page >= total:
                break
            if page == HISTORY_PAGES:
                summary["seedsTruncated"] += 1
        summary["seedsScanned"] += 1
    return found


def validate(budget, tournament_ids):
    """Real metadata of each tournament, looked up by ID. Missing IDs come back as None."""
    nodes = {}
    for index in range(0, len(tournament_ids), 25):
        batch = tournament_ids[index:index + 25]
        data = budget.query(BY_IDS, {"ids": batch}).get("tournaments") or {}
        for node in data.get("nodes") or []:
            if str(node.get("id")) in batch:
                nodes[str(node["id"])] = node
    return {tid: nodes.get(tid) for tid in tournament_ids}


def classify(tournaments, start, end, known, small_enabled, listed=()):
    """Admissible downloads, small context candidates and exclusions, by the discover.py rules."""
    admissible, small, excluded, catalog = [], [], {}, []
    for tid, node in tournaments.items():
        if node is None:
            continue
        events = [e for e in node.get("events") or [] if str((e.get("videogame") or {}).get("id")) == str(GAME_ID)]
        rows = []
        for event in events:
            eid = str(event.get("id"))
            if node.get("countryCode") != "GT":
                reason = "not_guatemala"
            else:
                reason = event_reason(node, event, start, end)
            rows.append({"id": eid, "name": event.get("name"), "type": event.get("type"),
                         "numEntrants": event.get("numEntrants"), "startAt": event.get("startAt"), "reason": reason})
            if eid in known:
                continue
            record = {**event, "tournament": {k: node.get(k) for k in ("id", "name", "slug", "countryCode")}}
            if reason is None:
                admissible.append(record)
            elif (small_enabled and reason == f"under_{LOCAL_MINIMUM_ACTIVE}_entrants"
                  and small_organizer_candidates([{**node, "events": [event]}], start, end)):
                small.append(record)
            else:
                excluded[eid] = reason
        if rows:
            owner = (node.get("owner") or {}).get("id")
            city = node.get("city")
            catalog.append({"id": tid, "name": node.get("name"), "slug": node.get("slug"), "startAt": node.get("startAt"),
                            "city": city.strip() if isinstance(city, str) and city.strip() else None,
                            "ownerId": str(owner) if owner is not None else None, "events": rows})
    listed = {str(tid) for tid in listed}
    admissible.sort(key=lambda e: (0, e["startAt"], str(e["id"])) if str(e["tournament"]["id"]) in listed else (1, -e["startAt"], str(e["id"])))
    return admissible, small, excluded, catalog


def complement(client, national, curation, *, clock=time.monotonic):
    """Return (national with the recovered events, summary). Never raises for API problems."""
    started = clock()
    start, end = national["season"]["startInclusive"], national["season"]["endExclusive"]
    known = known_event_ids(national)
    small_enabled = isinstance(national.get("organizerCandidates"), list)
    summary = {"schemaVersion": 1, "status": "complete", "seedsPlanned": 0, "seedsScanned": 0, "seedsTruncated": 0,
               "seedsWithoutHistory": 0, "historyPages": 0, "listedTournaments": 0, "unseenTournaments": 0,
               "validatedTournaments": 0, "unavailableTournaments": [], "unlistedTournaments": [], "recoveredEvents": [], "smallContextEvents": [],
               "excludedEvents": {}, "pendingEvents": [], "failedEvents": [], "requests": 0, "seconds": 0,
               "limits": {"attempts": MAX_ATTEMPTS, "historyAttempts": history_limit(), "seconds": MAX_SECONDS, "historyPages": HISTORY_PAGES,
                          "seeds": RECENT_SEEDS + ROTATING_SEEDS, "tournaments": MAX_TOURNAMENTS,
                          "eventDownloads": MAX_EVENT_DOWNLOADS}}
    budget = Budget(client, clock)
    result = national
    try:
        listed = listed_tournament_ids(curation)
        summary["listedTournaments"] = len(listed)
        seeds = seed_players(national)
        summary["seedsPlanned"] = len(seeds)
        found = {tid: set() for tid in listed}
        try:
            for tid, events in scan_histories(budget, seeds, start, end, known, summary).items():
                found.setdefault(tid, set()).update(events)
        except BudgetExhausted:
            summary["status"] = "budget_exhausted"
        unseen = sorted(found, key=int)
        summary["unseenTournaments"] = len(unseen)
        if len(unseen) > MAX_TOURNAMENTS:
            # Listed IDs first, then the oldest IDs; the rest wait for a later week.
            unseen = (listed + [tid for tid in unseen if tid not in listed])[:MAX_TOURNAMENTS]
            summary["status"] = "budget_exhausted"
        tournaments = validate(budget, unseen) if unseen else {}
        summary["validatedTournaments"] = len([n for n in tournaments.values() if n is not None])
        summary["unavailableTournaments"] = sorted((tid for tid, n in tournaments.items() if n is None), key=int)
        admissible, small, excluded, catalog = classify(tournaments, start, end, known, small_enabled, listed)
        # Found only through histories this week: list them in curation.json so they are not lost.
        contributed = {str(e["tournament"]["id"]) for e in admissible + small} | {
            tid for tid, node in tournaments.items() if node is not None and any(str(e.get("id")) in excluded for e in node.get("events") or [])}
        summary["unlistedTournaments"] = sorted((tid for tid in contributed if tid not in listed), key=int)
        summary["excludedEvents"] = dict(sorted(excluded.items(), key=lambda kv: int(kv[0])))
        summary["smallContextEvents"] = sorted((str(e["id"]) for e in small), key=int)
        records, players, sets = [], {}, {}
        for event in admissible:
            if len(records) >= MAX_EVENT_DOWNLOADS:
                summary["pendingEvents"].append(str(event["id"]))
                continue
            try:
                record, event_players, event_sets = fetch_event(budget, event)
            except BudgetExhausted:
                summary["status"] = "budget_exhausted"
                summary["pendingEvents"].append(str(event["id"]))
                continue
            except APIError:
                summary["failedEvents"].append(str(event["id"]))
                continue
            if set(event_sets) & (set(national.get("sets") or {}) | set(sets)):
                summary["failedEvents"].append(str(event["id"]))
                continue
            records.append(record)
            players.update(event_players)
            sets.update(event_sets)
        summary["recoveredEvents"] = [str(r["id"]) for r in records]
        result = merge(national, records, players, sets, small, excluded, catalog)
    except (APIError, KeyError, TypeError, ValueError, AttributeError):
        # The national capture stays exactly as discover.py left it.
        summary["status"] = "failed"
        result = national
    summary["requests"] = budget.used()
    summary["seconds"] = round(clock() - started, 3)
    return {**result, "coverageComplement": summary}, summary


def merge(national, records, players, sets, small, excluded, catalog):
    result = dict(national)
    known = known_event_ids(national)
    if any(str(r["id"]) in known for r in records) or len({str(r["id"]) for r in records}) != len(records):
        raise ValueError("Evento repetido entre la búsqueda y el complemento.")
    result["events"] = list(national["events"]) + records
    result["players"] = {**national["players"], **{pid: p for pid, p in players.items() if pid not in national["players"]}}
    result["sets"] = {**national["sets"], **sets}
    result["excludedEvents"] = list(national.get("excludedEvents") or []) + [
        {"id": eid, "reason": reason} for eid, reason in sorted(excluded.items(), key=lambda kv: int(kv[0]))]
    if isinstance(national.get("organizerCandidates"), list):
        result["organizerCandidates"] = sorted(list(national["organizerCandidates"]) + small,
                                               key=lambda e: (e["startAt"], str(e["id"])), reverse=True)
    if isinstance(national.get("tournamentCatalog"), list):
        present = {row["id"] for row in national["tournamentCatalog"]}
        result["tournamentCatalog"] = sorted(list(national["tournamentCatalog"]) + [row for row in catalog if row["id"] not in present],
                                             key=lambda row: row["id"])
    return result


def report(summary):
    line = json.dumps({k: summary[k] for k in ("status", "seedsScanned", "seedsTruncated", "historyPages", "listedTournaments",
                                                 "unseenTournaments", "validatedTournaments", "unavailableTournaments", "unlistedTournaments",
                                                 "recoveredEvents", "smallContextEvents", "excludedEvents", "pendingEvents",
                                                 "failedEvents", "requests", "seconds")}, ensure_ascii=False)
    print("Complemento de cobertura:", line, flush=True)
    target = os.environ.get("GITHUB_STEP_SUMMARY")
    if target:
        with open(target, "a", encoding="utf-8") as handle:
            handle.write("### Complemento de cobertura\n\n")
            for label, key in (("Estado", "status"), ("Jugadores consultados", "seedsScanned"), ("Historiales truncados", "seedsTruncated"),
                               ("Torneos no vistos por la búsqueda", "unseenTournaments"), ("Validados por ID", "validatedTournaments"),
                               ("Consultas", "requests"), ("Segundos", "seconds")):
                handle.write(f"- {label}: {summary[key]}\n")
            for label, key in (("Recuperados (entran al cálculo normal)", "recoveredEvents"), ("Contexto pequeño", "smallContextEvents"),
                               ("Pendientes", "pendingEvents"), ("Fallidos", "failedEvents"), ("No disponibles", "unavailableTournaments"),
                               ("Hallados solo por historial: añadir a curation.json", "unlistedTournaments")):
                handle.write(f"- {label}: {', '.join(summary[key]) or 'ninguno'}\n")
            for eid, reason in summary["excludedEvents"].items():
                handle.write(f"- Excluido {eid}: {reason}\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("national", type=Path)
    parser.add_argument("--curation", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="Escribir en otro archivo (simulación); por defecto reemplaza la captura")
    args = parser.parse_args()
    try:
        national = json.loads(args.national.read_text())
        curation = json.loads(args.curation.read_text())
        if national.get("kind") != "national_discovery" or not national.get("eventsComplete") or "coverageComplement" in national:
            raise ValueError("Se necesita una captura nacional completa sin complemento previo.")
    except (OSError, ValueError) as error:
        parser.exit(1, str(error) + "\n")
    token = os.environ.get("STARTGG_TOKEN", "").strip()
    if not token:
        print("::warning::Complemento de cobertura omitido: falta el token; captura nacional intacta.")
        return
    result, summary = complement(Client(token), national, curation)
    target = args.output or args.national
    tmp = target.with_suffix(".coverage.tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False))
    tmp.replace(target)
    report(summary)
    if summary["status"] != "complete":
        print(f"::warning::Complemento de cobertura: {summary['status']}; el corte nacional no se bloquea.")


if __name__ == "__main__":
    main()
