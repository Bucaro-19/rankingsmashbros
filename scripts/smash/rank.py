"""Transparent, provisional Smash GT rating; it is not the UltRank algorithm."""
import argparse
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from tiering import guatemala_points, parse_values, value_at, SOURCE_URL

BAD_SCORE = re.compile(r"\b(?:DQ|BYE|W/?O|FORFEIT|DESCALIFICAD[OA])\b|(?<!\d)-1(?!\d)", re.I)


def profile_country(player):
    return ((((player.get("user") or {}).get("location") or {}).get("country") or "").strip().casefold())


def player_url(player):
    slug = (player.get("user") or {}).get("slug") or ""
    return "https://www.start.gg/" + slug if re.fullmatch(r"user/[\w-]+", slug) else None


def competitive_set(match):
    if match.get("state") != 3 or match.get("winnerId") is None:
        return None
    score = match.get("displayScore")
    if not isinstance(score, str) or not score.strip() or BAD_SCORE.search(score):
        return None
    slots = match.get("slots") or []
    if len(slots) != 2:
        return None
    entrants = []
    for slot in slots:
        entrant = slot.get("entrant") or {}
        participants = entrant.get("participants") or []
        if entrant.get("id") is None or len(participants) != 1:
            return None
        player = participants[0].get("player") or {}
        if player.get("id") is None:
            return None
        entrants.append((str(entrant["id"]), str(player["id"])))
    if entrants[0][1] == entrants[1][1]:
        return None
    winners = [pid for eid, pid in entrants if eid == str(match["winnerId"])]
    return (winners[0], next(pid for _, pid in entrants if pid != winners[0])) if len(winners) == 1 else None


def local_event_evidence(active_player_ids, timestamp, values):
    """Conservative TTS estimate: only people with a competitive set count."""
    if values is None:
        return {"estimatedPoints": None, "valuedPlayers": 0}
    return {"estimatedPoints": guatemala_points(active_player_ids, timestamp, values),
            "valuedPlayers": sum(value_at(values.get(pid, ()), timestamp) > 0 for pid in active_player_ids)}


def compute(snapshot, excluded_event_ids=(), player_overrides=None, points_table=None, player_aliases=None,
            *, local_minimum=32, allow_points_exception=False):
    if snapshot.get("kind") != "national_discovery" or not snapshot.get("catalogComplete") or not snapshot.get("eventsComplete"):
        raise ValueError("Solo se calcula una captura nacional completa.")
    excluded = {str(id_) for id_ in excluded_event_ids}
    player_overrides = player_overrides or {}
    player_aliases = player_aliases or {}
    values = parse_values(points_table) if points_table is not None else None
    if not isinstance(local_minimum, int) or local_minimum < 2:
        raise ValueError("El mínimo local debe ser al menos dos jugadores activos.")
    if allow_points_exception and values is None:
        raise ValueError("La excepción por puntos requiere la tabla TTS fijada.")
    events = {str(e["id"]): e for e in snapshot["events"]}
    by_event = defaultdict(list)
    rejected = Counter()
    for sid, match in snapshot["sets"].items():
        event_id = str((match.get("event") or {}).get("id"))
        pair = competitive_set(match)
        if event_id not in events or pair is None:
            rejected["invalid_or_unscored"] += 1
            continue
        by_event[event_id].append((sid, pair[0], pair[1]))

    eligible_events = {}
    event_reasons = {}
    event_qualifications = {}
    for eid, event in events.items():
        active = {pid for _, winner, loser in by_event[eid] for pid in (winner, loser)}
        country = (event.get("tournament") or {}).get("countryCode")
        evidence = local_event_evidence(active, event["startAt"], values) if country == "GT" else {"estimatedPoints": None, "valuedPlayers": 0}
        qualifies_by_points = (country == "GT" and allow_points_exception
                               and evidence["estimatedPoints"] >= 200 and evidence["valuedPlayers"] >= 2)
        minimum = local_minimum if country == "GT" else 64
        if eid in excluded:
            event_reasons[eid] = "manual_exclusion"
        elif len(active) < minimum and not qualifies_by_points:
            event_reasons[eid] = "under_minimum_active_players"
        elif not by_event[eid]:
            event_reasons[eid] = "no_valid_sets"
        else:
            eligible_events[eid] = {**event, "activePlayers": len(active),
                                    "ttsPointsEstimate": evidence["estimatedPoints"]}
        if country == "GT":
            event_qualifications[eid] = {"entrants": event.get("numEntrants"), "activePlayers": len(active),
                                         **evidence, "path": ("excluded" if eid not in eligible_events else
                                                               "players" if len(active) >= minimum else "points"),
                                         "decision": "included" if eid in eligible_events else event_reasons[eid]}

    edge_counts = Counter()
    for eid in eligible_events:
        for _, winner, loser in by_event[eid]:
            edge_counts[tuple(sorted((winner, loser)))] += 1
    games = []
    player_events = defaultdict(set)
    local_player_events = defaultdict(set)
    wins = Counter()
    losses = Counter()
    event_results = defaultdict(list)
    for eid, event in eligible_events.items():
        if event["ttsPointsEstimate"] is not None:
            size_weight = min(2.5, math.sqrt(event["ttsPointsEstimate"] / 96))
        elif (event.get("tournament") or {}).get("countryCode") != "GT":
            size_weight = min(2.5, math.sqrt(event["activePlayers"] / 64))
        else:
            size_weight = min(2.0, math.sqrt(event["activePlayers"] / 32))
        for sid, winner, loser in by_event[eid]:
            repetitions = edge_counts[tuple(sorted((winner, loser)))]
            weight = size_weight / math.sqrt(repetitions)
            games.append((winner, loser, weight))
            for pid in (winner, loser):
                player_events[pid].add(eid)
                if (event.get("tournament") or {}).get("countryCode") == "GT":
                    local_player_events[pid].add(eid)
            wins[winner] += 1
            losses[loser] += 1
            event_results[eid].append(sid)
    if not games:
        raise ValueError("No hay sets competitivos suficientes para calcular posiciones.")

    # Regularized Bradley-Terry fit. A shared zero prior stabilizes sparse and
    # disconnected brackets. All constants are ours and are deliberately public.
    players = set(pid for winner, loser, _ in games for pid in (winner, loser))
    logits = {pid: 0.0 for pid in players}
    degrees = defaultdict(float)
    for winner, loser, weight in games:
        degrees[winner] += weight
        degrees[loser] += weight
    prior = 0.5
    for _ in range(700):
        gradient = {pid: -prior * logits[pid] for pid in players}
        for winner, loser, weight in games:
            difference = max(-30, min(30, logits[winner] - logits[loser]))
            surprise = weight / (1 + math.exp(difference))
            gradient[winner] += surprise
            gradient[loser] -= surprise
        maximum = 0.0
        for pid in players:
            change = 1.2 * gradient[pid] / (degrees[pid] + 2 * prior)
            logits[pid] += change
            maximum = max(maximum, abs(change))
        if maximum < 1e-7:
            break

    rows = []
    for pid, player in snapshot["players"].items():
        profile_gt = profile_country(player) in {"guatemala", "gt"}
        if not profile_gt and pid not in player_overrides:
            continue
        if not local_player_events[pid] or len(player_events[pid]) < 2 or wins[pid] + losses[pid] < 4:
            continue
        standings = [event["placements"].get(pid) for eid, event in eligible_events.items() if eid in player_events[pid]]
        standings = [place for place in standings if place is not None]
        rows.append({"id": pid, "tag": player.get("gamerTag") or "Sin alias", "knownAs": player_aliases.get(pid), "url": player_url(player),
                     "rating": round(1500 + 400 / math.log(10) * logits[pid]),
                     "wins": wins[pid], "losses": losses[pid], "sets": wins[pid] + losses[pid],
                     "events": len(player_events[pid]), "localEvents": len(local_player_events[pid]),
                     "bestPlacement": min(standings) if standings else None,
                     "countryBasis": player_overrides[pid] if pid in player_overrides else "país del perfil start.gg; sin verificar"})
    rows.sort(key=lambda row: (-row["rating"], -row["wins"], -row["events"], row["tag"].casefold(), row["id"]))
    for index, row in enumerate(rows, 1):
        row["rank"] = index
    return {"kind": "smash_gt_provisional", "methodVersion": "BT-PILOTO-2" if allow_points_exception else "BT-PILOTO-1", "generatedAt": snapshot["generatedAt"],
            "season": snapshot["season"], "ranking": rows[:100], "fullRanking": rows,
            "counts": {"eligiblePlayers": len(rows), "rankedPlayers": min(100, len(rows)),
                       "eligibleEvents": len(eligible_events), "competitiveSets": len(games),
                       "eventsUnderMinimumActive": sum(reason == "under_minimum_active_players" for reason in event_reasons.values()),
                       "internationalEvents": sum((event.get("tournament") or {}).get("countryCode") != "GT" for event in eligible_events.values()),
                       "excludedDQOrUnknown": rejected["invalid_or_unscored"]},
            "eventDecisions": event_reasons,
            "eventQualifications": event_qualifications,
            "ttsPointsEstimate": {eid: event["ttsPointsEstimate"] for eid, event in eligible_events.items() if event["ttsPointsEstimate"] is not None},
            "eventIds": sorted(eligible_events),
            "method": "Bradley-Terry regularizado: prior 0.5; peso de evento GT min(2.5,sqrt(puntos_TTS_estimados/96)) con tabla TTS, o min(2,sqrt(jugadores_activos/32)) sin tabla; peso extranjero min(2.5,sqrt(jugadores_activos/64)); enfrentamientos repetidos divididos por sqrt(repeticiones); rating=1500+400/ln(10)*logit. Mínimo 2 eventos, 4 sets válidos y un evento GT con set válido. No equivale a UltRank.",
            "ttsSource": SOURCE_URL if values is not None else None,
            "limitations": (["La captura internacional parte de participantes localmente descubiertos; jugadores que compiten solo fuera del país pueden faltar."] if snapshot.get("internationalComplete") else ["Solo eventos presenciales de Guatemala en esta captura; resultados en el extranjero pendientes de integrar."]) + [
                            "La ubicación pública del perfil indica candidatura, no ciudadanía ni residencia verificada.",
                            "La exclusión de eventos no convencionales, DQ ambiguos y torneos semanales requiere revisión comunitaria."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--exclude", action="append", default=[], help="ID de evento no competitivo, repetible")
    parser.add_argument("--curation", type=Path, help="Archivo con exclusiones y candidaturas documentadas")
    parser.add_argument("--points-csv", type=Path, help="Tabla TTS de jugadores descargada de la fuente oficial")
    args = parser.parse_args()
    curation = json.loads(args.curation.read_text()) if args.curation else {}
    result = compute(json.loads(args.snapshot.read_text()), args.exclude + list(curation.get("excludedEventIds", {})) + list(curation.get("excludedForeignEventIds", {})),
                     curation.get("playerOverrides", {}), args.points_csv.read_text() if args.points_csv else None,
                     curation.get("playerAliases", {}))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.output.with_suffix(".tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    tmp.replace(args.output)
    print(f"{result['counts']['eligiblePlayers']} posiciones provisionales, con top 100 destacado; {result['counts']['eligibleEvents']} eventos y {result['counts']['competitiveSets']} sets válidos.")


if __name__ == "__main__":
    main()
