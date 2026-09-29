import unittest

from publish_ranking import export
from discover import season_timestamp
from rank import competitive_set, compute
from tiering import guatemala_points, parse_values, value_at


def player(pid, country="Guatemala"):
    return {"id": pid, "gamerTag": f"P{pid}", "user": {"slug": f"user/{pid}", "location": {"country": country}}}


def match(sid, event_id, winner, loser, score=None):
    score = score if score is not None else f"P{winner} 2 - P{loser} 0"
    return {"id": sid, "event": {"id": event_id, "slug": f"tournament/test/event/{event_id}", "startAt": 1768000000},
            "tournament": {"name": "Prueba", "countryCode": "GT"},
            "state": 3, "winnerId": f"e{winner}", "displayScore": score,
            "slots": [{"entrant": {"id": f"e{pid}", "participants": [{"player": {"id": pid}}]}} for pid in (winner, loser)]}


def fixture():
    players = {str(pid): player(str(pid), "Mexico" if pid == 1 else "Guatemala") for pid in range(1, 33)}
    events = [{"id": eid, "name": "Ultimate Singles", "numEntrants": 32, "startAt": 1768000000,
               "placements": {"1": 1}, "tournament": {"name": "Prueba", "countryCode": "GT"}} for eid in (10, 11)]
    sets = {str(eid * 100 + pid): match(str(eid * 100 + pid), eid, "1", str(pid))
            for eid in (10, 11) for pid in range(2, 33)}
    return {"kind": "national_discovery", "catalogComplete": True, "eventsComplete": True,
            "generatedAt": "2026-09-28T12:00:00+00:00",
            "season": {"startInclusive": 1767225600, "endExclusive": 1790640000},
            "events": events, "players": players, "sets": sets}


class PilotRankingTests(unittest.TestCase):
    def test_annual_boundaries_use_guatemala_midnight(self):
        self.assertEqual(season_timestamp("2026-01-01"), 1767247200)
        self.assertEqual(season_timestamp("2027-01-01"), 1798783200)

    def test_tts_values_respect_dates_midpoint_and_guatemala_multiplier(self):
        csv_text = ("Category,Note,Player,Start.gg Hex ID,Start.gg Num ID,Points,Start Date,End Date,Midpt Date,Source\n"
                    "rank,test,P1,hex,1,100,2026-01-01,2026-12-31,2026-07-01,test\n")
        values = parse_values(csv_text)
        self.assertEqual(value_at(values["1"], 1768000000), 100)
        self.assertEqual(value_at(values["1"], 1783000000), 50)
        self.assertEqual(guatemala_points({"1", "2"}, 1768000000, values), 106)

    def test_dq_and_unknown_winner_are_not_competitive(self):
        row = match("1", 10, "1", "2")
        self.assertEqual(competitive_set(row), ("1", "2"))
        row["displayScore"] = "DQ"
        self.assertIsNone(competitive_set(row))
        row["displayScore"] = "P1 2 - P2 0"
        row["winnerId"] = "other"
        self.assertIsNone(competitive_set(row))

    def test_complete_events_and_documented_override_produce_rank(self):
        snapshot = fixture()
        result = compute(snapshot, player_overrides={"1": "2025 PR"})
        self.assertEqual(result["counts"]["eligibleEvents"], 2)
        self.assertEqual(result["counts"]["competitiveSets"], 62)
        self.assertEqual(result["ranking"][0]["tag"], "P1")
        self.assertEqual(result["ranking"][0]["rank"], 1)
        self.assertEqual(result["ranking"][0]["events"], 2)
        self.assertEqual(result["ranking"][0]["localEvents"], 2)
        self.assertEqual(result["ranking"][0]["countryBasis"], "2025 PR")
        public = export(snapshot, result)
        self.assertEqual(public["counts"]["players"], 1)
        self.assertEqual(len(public["results"]), 62)
        self.assertEqual(public["status"], "local_pilot")
        self.assertEqual(public["methodVersion"], "BT-PILOTO-1")
        self.assertEqual(public["seasonYear"], 2026)
        self.assertTrue(public["seasonLabel"].endswith("28/09/2026"))
        self.assertEqual(len(public["events"]), 2)
        self.assertEqual([event["validSets"] for event in public["events"]], [31, 31])
        self.assertEqual(public["events"][0]["activePlayers"], 32)

    def test_previous_cut_is_only_compared_with_same_season_and_method(self):
        snapshot = fixture()
        ranking = compute(snapshot, player_overrides={"1": "2025 PR"})
        previous = {"seasonLabel": "01/01/2026 – 27/09/2026", "methodVersion": "BT-PILOTO-1",
                    "generatedAt": "2026-09-27T12:00:00+00:00",
                    "players": [{"id": "1", "rank": 3}]}
        public = export(snapshot, ranking, previous=previous)
        self.assertEqual(public["previousCutAt"], previous["generatedAt"])
        self.assertEqual(public["players"][0]["previousRank"], 3)
        previous["seasonYear"] = 2025
        self.assertIsNone(export(snapshot, ranking, previous=previous)["previousCutAt"])
        previous["seasonYear"] = 2026
        previous["methodVersion"] = "otro"
        self.assertIsNone(export(snapshot, ranking, previous=previous)["previousCutAt"])

    def test_export_rejects_event_set_count_mismatch(self):
        snapshot = fixture()
        result = compute(snapshot, player_overrides={"1": "2025 PR"})
        result["counts"]["competitiveSets"] += 1
        with self.assertRaisesRegex(ValueError, "no coinciden"):
            export(snapshot, result)

    def test_partial_capture_never_gets_positions(self):
        snapshot = fixture()
        snapshot["eventsComplete"] = False
        with self.assertRaisesRegex(ValueError, "completa"):
            compute(snapshot)


if __name__ == "__main__":
    unittest.main()
