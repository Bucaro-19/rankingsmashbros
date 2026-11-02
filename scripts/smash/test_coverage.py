"""Complementary discovery with an invented start.gg whose search hides some tournaments."""
import copy
import json
import unittest

from collect import APIError
from coverage import BY_IDS, MAX_ATTEMPTS, MAX_EVENT_DOWNLOADS, complement, known_event_ids, seed_players
from discover import discover
from organizer_small import capture
from rank import compute

START, END = 1767247200, 1793512800  # 2026 in Guatemala, as the weekly capture uses it
DAY = 86400
PINGUIS = "5551493"


def entrant(eid, pid):
    return int(f"{eid}{int(pid) % 100000:05d}")


def person(pid, country="Guatemala"):
    return {"id": int(pid), "gamerTag": f"P{pid}", "user": {"id": int(pid) + 900000, "slug": f"user/{pid}", "location": {"country": country}}}


class World:
    """Invented events: entrants, the players with a valid set, and extra DQ-only results."""

    def __init__(self):
        self.tournaments, self.events, self.hidden = {}, {}, set()

    def add(self, tid, eid, *, entrants, active, start, name="Singles", hidden=False, dq=(), extra_valid=(), country="GT"):
        players = [str(1000 + i) for i in range(entrants)]
        sets = []
        # A chain of valid sets gives exactly `active` players with a competitive set.
        for i in range(active - 1):
            sets.append((players[i], players[i + 1], "2 - 0"))
        for winner, loser, score in extra_valid:
            sets.append((winner, loser, score))
        for winner, loser in dq:
            sets.append((winner, loser, "DQ"))
        roster = sorted(set(players) | {p for s in sets for p in s[:2]}, key=int)
        event = {"id": eid, "name": name, "slug": f"tournament/t{tid}/event/{eid}", "numEntrants": len(roster) if entrants else 0,
                 "isOnline": False, "state": "COMPLETED", "startAt": start, "type": 1,
                 "videogame": {"id": 1386, "name": "Super Smash Bros. Ultimate"}}
        tournament = self.tournaments.setdefault(tid, {"id": tid, "name": f"Torneo {tid}", "slug": f"tournament/t{tid}", "startAt": start,
                                                     "endAt": start + DAY, "countryCode": country, "isOnline": False,
                                                     "city": "Ciudad de Guatemala", "owner": {"id": 2735916}, "events": []})
        tournament["events"].append(event)
        self.events[eid] = {"event": event, "tid": tid, "roster": roster, "sets": sets}
        if hidden:
            self.hidden.add(tid)

    def node(self, eid, sid, winner, loser, score):
        data = self.events[eid]
        moment = data["event"]["startAt"] + 3600
        return {"id": sid, "state": 3, "winnerId": entrant(eid, winner), "displayScore": f"P{winner} {score.split(' - ')[0]} - P{loser} {score.split(' - ')[1]}" if score != "DQ" else "DQ",
                "completedAt": moment, "updatedAt": moment,
                "slots": [{"entrant": {"id": entrant(eid, pid), "participants": [{"player": person(pid)}]}} for pid in (winner, loser)]}

    def history(self, pid):
        nodes = []
        for eid, data in self.events.items():
            for winner, loser, _ in data["sets"]:
                if pid in (winner, loser):
                    t = self.tournaments[data["tid"]]
                    nodes.append({"event": {"id": eid, "startAt": data["event"]["startAt"], "tournament": {"id": t["id"], "countryCode": t["countryCode"]}}})
        return nodes


class FakeClient:
    def __init__(self, world, fail_on=None, history_pages=1, history=True):
        self.world, self.calls, self.fail_on, self.history_pages, self.log = world, 0, fail_on, history_pages, []
        self.history = history

    def query(self, query, variables):
        self.calls += 1
        if self.fail_on and self.fail_on in query:
            raise APIError("fallo inventado")
        if "player(id" in query:
            self.log.append(("history", variables["id"], variables["page"]))
            if not self.history:
                return {"player": None}
            nodes = self.world.history(str(variables["id"]))
            return {"player": {"sets": {"pageInfo": {"total": len(nodes), "totalPages": self.history_pages}, "nodes": nodes if variables["page"] == 1 else []}}}
        if query == BY_IDS:
            self.log.append(("ids", tuple(variables["ids"])))
            found = [copy.deepcopy(self.world.tournaments[int(t)]) for t in variables["ids"] if int(t) in self.world.tournaments]
            return {"tournaments": {"pageInfo": {"total": len(found)}, "nodes": found}}
        if "tournaments(query" in query:
            # The filtered search, as observed: hidden tournaments never appear.
            visible = [copy.deepcopy(t) for tid, t in sorted(self.world.tournaments.items()) if tid not in self.world.hidden]
            if "owner{id}" in query:
                return {"tournaments": {"pageInfo": {"total": len(visible), "totalPages": 1},
                                        "nodes": [{"id": t["id"], "city": t["city"], "owner": t["owner"]} for t in visible]}}
            return {"tournaments": {"pageInfo": {"total": len(visible), "totalPages": 1}, "nodes": visible}}
        eid = int(variables["id"])
        data = self.world.events[eid]
        if "entrants(query" in query:
            nodes = [{"id": entrant(eid, pid), "name": f"P{pid}", "participants": [{"player": person(pid)}]} for pid in data["roster"]]
            key = "entrants"
        elif "standings(" in query:
            nodes, key = [], "standings"
        else:
            nodes = [self.world.node(eid, f"{eid}{i:04d}", w, l, s) for i, (w, l, s) in enumerate(data["sets"])]
            key = "sets"
        return {"event": {"id": eid, key: {"pageInfo": {"total": len(nodes), "totalPages": 1}, "nodes": nodes}}}


def pinguis_world():
    """A visible national event plus the three tournaments verified on 1/nov/2026, invented sizes."""
    w = World()
    regulars = [str(1000 + i) for i in range(30)]
    w.add(1, 101, entrants=30, active=30, start=START + 200 * DAY)
    # 947356: 42 registered, 38 active; pinguis 0-2 with one DQ.
    w.add(947356, 1697423, entrants=41, active=37, start=START + 240 * DAY, hidden=True,
          extra_valid=[(regulars[0], PINGUIS, "2 - 0"), (regulars[1], PINGUIS, "2 - 1")], dq=[(regulars[2], PINGUIS)])
    # 948197: 20 registered, 18 active; pinguis 0-1 and three DQ.
    w.add(948197, 1699110, entrants=19, active=17, start=START + 241 * DAY, hidden=True,
          extra_valid=[(regulars[3], PINGUIS, "2 - 0")], dq=[(regulars[4], PINGUIS), (regulars[5], PINGUIS), (regulars[6], PINGUIS)])
    # 957669: Clase A admissible with pinguis only DQ; Clase B with 13 registered.
    w.add(957669, 1719115, entrants=37, active=30, start=START + 268 * DAY, name="Clase A", hidden=True,
          dq=[(regulars[7], PINGUIS), (regulars[8], PINGUIS)])
    w.add(957669, 1719129, entrants=12, active=9, start=START + 268 * DAY + 3600, name="Clase B", hidden=True,
          extra_valid=[(PINGUIS, regulars[9], "2 - 1"), (PINGUIS, regulars[10], "2 - 0"), (regulars[11], PINGUIS, "2 - 0"), (regulars[9], PINGUIS, "2 - 1")])
    return w


def national_from(world, *, organizer=True):
    data = discover(FakeClient(world), START, END, organizer_candidates=organizer)
    data["generatedAt"] = "2026-11-01T12:37:58+00:00"
    return data


CURATION = {"recoveredTournamentIds": {"947356": "Verificado por ID", "948197": "Verificado por ID", "957669": "Verificado por ID"}}


class CoverageComplementTests(unittest.TestCase):
    def test_search_omits_the_tournaments_and_the_complement_recovers_them(self):
        world = pinguis_world()
        national = national_from(world)
        self.assertEqual([e["id"] for e in national["events"]], [101])
        self.assertNotIn(1697423, known_event_ids(national))
        result, summary = complement(FakeClient(world), national, CURATION)
        self.assertEqual(summary["status"], "complete")
        # 20 registered but 18 active is downloaded too: rank.py decides that it does not count.
        self.assertEqual(sorted(summary["recoveredEvents"]), ["1697423", "1699110", "1719115"])
        self.assertEqual(summary["excludedEvents"], {})
        self.assertEqual(summary["smallContextEvents"], ["1719129"])
        sizes = {e["id"]: e["numEntrants"] for e in result["events"]}
        self.assertEqual((sizes[1697423], sizes[1699110], sizes[1719115]), (42, 20, 38))
        ids = {str(e["id"]) for e in result["events"]}
        self.assertEqual(len(ids), len(result["events"]))
        self.assertTrue({"101", "1697423", "1719115"} <= ids)
        catalog = {row["id"]: row for row in result["tournamentCatalog"]}
        self.assertEqual(catalog["957669"]["ownerId"], "2735916")
        self.assertLessEqual(summary["requests"], MAX_ATTEMPTS)

    def test_twenty_registered_with_eighteen_active_does_not_count(self):
        world = pinguis_world()
        result, summary = complement(FakeClient(world, history=False), national_from(world), {"recoveredTournamentIds": {"948197": "x"}})
        self.assertEqual(summary["recoveredEvents"], ["1699110"])
        self.assertEqual(summary["seedsWithoutHistory"], summary["seedsScanned"])
        event = next(e for e in result["events"] if e["id"] == 1699110)
        self.assertEqual(event["numEntrants"], 20)
        ranking = compute(result)
        self.assertEqual(ranking["eventDecisions"]["1699110"], "under_minimum_active_players")
        self.assertEqual(ranking["eventQualifications"]["1699110"]["activePlayers"], 18)
        self.assertNotIn("1699110", ranking["eventIds"])

    def test_small_class_b_becomes_excluded_context_never_a_ranking_event(self):
        world = pinguis_world()
        result, summary = complement(FakeClient(world), national_from(world), CURATION)
        self.assertNotIn(1719129, [e["id"] for e in result["events"]])
        self.assertIn("1719129", [str(e["id"]) for e in result["organizerCandidates"]])
        context = capture(FakeClient(world), result, limit=6)
        self.assertIn(1719129, [e["id"] for e in context["events"]])
        self.assertNotIn("1719129", compute(result)["eventIds"])
        # Without the small-context circuit it is only recorded as excluded, with its reason.
        _, plain = complement(FakeClient(world), national_from(world, organizer=False), CURATION)
        self.assertEqual(plain["excludedEvents"], {"1719129": "under_20_entrants"})

    def test_dq_only_participation_is_no_activity_and_pinguis_stays_unranked(self):
        world = pinguis_world()
        result, _ = complement(FakeClient(world), national_from(world), CURATION)
        ranking = compute(result)
        self.assertIn("1719115", ranking["eventIds"])
        self.assertIn("1697423", ranking["eventIds"])
        self.assertNotIn(PINGUIS, [row["id"] for row in ranking["fullRanking"]])
        # His only valid sets in admissible events: two losses in 1697423. DQ in 1719115 adds nothing.
        sets = [m for m in result["sets"].values() if PINGUIS in [str(p["player"]["id"]) for s in m["slots"] for p in s["entrant"]["participants"]]]
        self.assertTrue(any(m["displayScore"] == "DQ" and m["event"]["id"] == 1719115 for m in sets))

    def test_the_same_event_found_by_search_history_and_list_is_kept_once(self):
        world = pinguis_world()
        world.hidden.discard(947356)  # The search now finds it too.
        national = national_from(world)
        self.assertIn(1697423, [e["id"] for e in national["events"]])
        result, summary = complement(FakeClient(world), national, CURATION)
        self.assertEqual([e["id"] for e in result["events"]].count(1697423), 1)
        self.assertNotIn("1697423", summary["recoveredEvents"])
        # Two seeds that both played the hidden event only add it once.
        world2 = pinguis_world()
        result2, summary2 = complement(FakeClient(world2), national_from(world2), {"recoveredTournamentIds": {}})
        self.assertEqual(len(summary2["recoveredEvents"]), len(set(summary2["recoveredEvents"])))
        self.assertEqual(len({str(e["id"]) for e in result2["events"]}), len(result2["events"]))

    def test_history_alone_finds_a_hidden_tournament_without_a_list(self):
        world = pinguis_world()
        national = national_from(world)
        client = FakeClient(world)
        result, summary = complement(client, national, {})
        self.assertGreater(summary["seedsScanned"], 0)
        self.assertIn("1697423", summary["recoveredEvents"])
        self.assertTrue(all(kind != "ids" or len(entry[0]) <= 25 for kind, *entry in client.log))

    def test_failure_or_exhausted_budget_never_blocks_the_national_cut(self):
        world = pinguis_world()
        national = national_from(world)
        before = json.dumps(national, sort_keys=True)
        for fail_on in ("player(id", "filter:{ids"):
            with self.subTest(fail_on=fail_on):
                result, summary = complement(FakeClient(world, fail_on=fail_on), copy.deepcopy(national), CURATION)
                if fail_on == "filter:{ids":
                    self.assertEqual(summary["status"], "failed")
                    stripped = {k: v for k, v in result.items() if k != "coverageComplement"}
                    self.assertEqual(json.dumps(stripped, sort_keys=True), before)
                compute(result)
        # An exhausted budget keeps fully downloaded events only and marks the rest as pending.
        import coverage
        original = coverage.MAX_ATTEMPTS
        try:
            coverage.MAX_ATTEMPTS = 8
            result, summary = complement(FakeClient(world), copy.deepcopy(national), CURATION)
        finally:
            coverage.MAX_ATTEMPTS = original
        self.assertEqual(summary["status"], "budget_exhausted")
        self.assertTrue(summary["pendingEvents"])
        for eid in summary["recoveredEvents"]:
            event = next(e for e in result["events"] if str(e["id"]) == eid)
            self.assertEqual(event["setsFetched"], len(world.events[int(eid)]["sets"]))
        compute(result)

    def test_without_additional_events_the_calculation_is_identical(self):
        world = World()
        world.add(1, 101, entrants=30, active=30, start=START + 200 * DAY)
        world.add(2, 102, entrants=25, active=25, start=START + 210 * DAY)
        national = national_from(world)
        result, summary = complement(FakeClient(world), copy.deepcopy(national), {})
        self.assertEqual(summary["recoveredEvents"], [])
        stripped = {k: v for k, v in result.items() if k != "coverageComplement"}
        self.assertEqual(json.dumps(stripped, sort_keys=True), json.dumps(national, sort_keys=True))
        self.assertEqual(json.dumps(compute(result), sort_keys=True), json.dumps(compute(national), sort_keys=True))

    def test_excluded_context_does_not_alter_the_ranking(self):
        world = World()
        world.add(1, 101, entrants=30, active=30, start=START + 200 * DAY)
        world.add(2, 102, entrants=26, active=26, start=START + 210 * DAY)
        world.add(948197, 1699110, entrants=20, active=18, start=START + 241 * DAY, hidden=True)
        national = national_from(world)
        result, summary = complement(FakeClient(world), national, {})
        self.assertEqual(summary["recoveredEvents"], ["1699110"])
        self.assertTrue(compute(national)["fullRanking"])
        # 1699110 joins the capture but not the calculation: every rating stays the same.
        base, extended = compute(national), compute(result)
        self.assertEqual([(r["id"], r["rating"], r["rank"]) for r in base["fullRanking"]],
                         [(r["id"], r["rating"], r["rank"]) for r in extended["fullRanking"]])
        self.assertEqual(base["eventIds"], extended["eventIds"])

    def test_seeds_are_guatemala_profiles_recent_first_with_weekly_rotation(self):
        world = pinguis_world()
        national = national_from(world)
        national["players"]["1001"]["user"]["location"]["country"] = "Mexico"
        seeds = seed_players(national)
        self.assertNotIn("1001", seeds)
        self.assertEqual(len(seeds), len(set(seeds)))
        later = {**national, "generatedAt": "2026-11-08T12:37:58+00:00"}
        self.assertNotEqual(seed_players(later)[4:], seeds[4:])
        self.assertEqual(seed_players(later)[:4], seeds[:4])

    def test_listed_tournaments_are_downloaded_before_newer_history_finds(self):
        # The search never sees them, so every week they must fit again: listed ones go first.
        import coverage
        world = pinguis_world()
        original = coverage.MAX_EVENT_DOWNLOADS
        try:
            coverage.MAX_EVENT_DOWNLOADS = 1
            _, summary = complement(FakeClient(world), national_from(world), {"recoveredTournamentIds": {"947356": "x"}})
        finally:
            coverage.MAX_EVENT_DOWNLOADS = original
        self.assertEqual(summary["recoveredEvents"], ["1697423"])
        self.assertEqual(sorted(summary["pendingEvents"]), ["1699110", "1719115"])
        self.assertEqual(summary["unlistedTournaments"], ["948197", "957669"])

    def test_audit_makes_the_complement_and_its_absence_visible(self):
        from audit import audit, markdown
        world = pinguis_world()
        world.add(2, 102, entrants=28, active=28, start=START + 230 * DAY)
        national = national_from(world)
        self.assertIn("No se ejecutó en esta captura", markdown(audit(national, {})))
        result, _ = complement(FakeClient(world, history=False), national, CURATION)
        report = markdown(audit(result, {}))
        self.assertIn("Recuperados para el cálculo normal: 1697423, 1699110, 1719115", report)
        self.assertIn("Contexto pequeño: 1719129", report)
        self.assertIn("no prueba que no falten otros torneos", report)

    def test_listed_ids_are_bounded(self):
        world = pinguis_world()
        _, summary = complement(FakeClient(world), national_from(world), {"recoveredTournamentIds": {str(i): "x" for i in range(41)}})
        self.assertEqual(summary["status"], "failed")


    def test_recovered_events_reach_sql_with_their_activity_counts(self):
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "database"))
        from ranking_package import normalize_capture_entities
        world = pinguis_world()
        result, _ = complement(FakeClient(world, history=False), national_from(world), CURATION)
        entities = normalize_capture_entities(result)[0]
        self.assertEqual((entities["events"][1699110]["registered_entrants"], entities["events"][1699110]["active_players"]), (20, 18))
        self.assertEqual(entities["events"][1719115]["active_players"], 30)
        outcomes = [s["outcome_type"] for s in entities["sets"].values() if s["event_id"] == 1719115]
        self.assertIn("dq", outcomes)

    def test_simulation_reports_the_next_cut_without_publishing(self):
        from simulate_coverage import compare
        world = pinguis_world()
        world.add(2, 102, entrants=28, active=28, start=START + 230 * DAY)
        national = national_from(world)
        extended, _ = complement(FakeClient(world, history=False), national, CURATION)
        abroad = {"kind": "abroad_discovery", "nationalGeneratedAt": national["generatedAt"], "season": national["season"],
                  "discoveryComplete": True, "eventsComplete": True, "fetchedEvents": {}, "players": {}, "sets": {},
                  "eventSources": {}, "seedPlayerIds": [], "events": {}}
        report = compare(national, extended, abroad, {}, None, [PINGUIS])
        decisions = {row["id"]: row["decision"] for row in report["newCapturedEvents"]}
        self.assertEqual(decisions, {"1697423": "included", "1699110": "under_minimum_active_players", "1719115": "included"})
        self.assertEqual(report["watch"][PINGUIS], {"before": None, "after": None, "eventsAfter": None, "setsAfter": None})
        self.assertEqual(report["after"]["eligibleEvents"], report["before"]["eligibleEvents"] + 2)

    def test_weekly_step_is_opt_in_skipped_on_resume_and_never_blocks(self):
        from pathlib import Path
        workflow = (Path(__file__).resolve().parents[2] / ".github/workflows/smash-publish.yml").read_text()
        step = workflow[workflow.index("Complemento de cobertura"):workflow.index("Descartar complemento reanudado")]
        self.assertIn("inputs.resume_run_id == ''", step)
        self.assertIn("vars.SMASH_COVERAGE_COMPLEMENT_ENABLED == 'true'", step)
        self.assertIn("|| echo", step)
        self.assertLess(workflow.index("discover.py --start"), workflow.index("coverage.py"))
        self.assertLess(workflow.index("coverage.py"), workflow.index("organizer_small.py scripts"))
        self.assertLess(workflow.index("coverage.py"), workflow.index("discover_abroad.py"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
