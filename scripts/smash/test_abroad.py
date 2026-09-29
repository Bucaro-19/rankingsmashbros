import unittest
import tempfile
from pathlib import Path

from combine import combine
from discover_abroad import discover_abroad, require_reviewed_events, scan_user, seeds


class StubClient:
    calls = 0

    def query(self, query, variables):
        self.calls += 1
        page = variables["page"]
        events = [
            {"id": 1, "startAt": 180, "isOnline": False, "type": 1, "state": "COMPLETED",
             "videogame": {"id": 1386}, "tournament": {"countryCode": "MX", "isOnline": False}},
            {"id": 2, "startAt": 90, "isOnline": False, "type": 1, "state": "COMPLETED",
             "videogame": {"id": 1386}, "tournament": {"countryCode": "US", "isOnline": False}},
        ] if page == 1 else [
            {"id": 3, "startAt": 170, "isOnline": False, "type": 1, "state": "COMPLETED",
             "videogame": {"id": 1386}, "tournament": {"countryCode": "US", "isOnline": False}},
            {"id": 4, "startAt": 160, "isOnline": True, "type": 1, "state": "COMPLETED",
             "videogame": {"id": 1386}, "tournament": {"countryCode": "MX", "isOnline": True}},
        ]
        return {"user": {"events": {"pageInfo": {"totalPages": 2}, "nodes": events}}}


class AbroadTests(unittest.TestCase):
    def test_unsorted_history_is_fully_paginated_and_online_excluded(self):
        found = scan_user(StubClient(), "u1", 100, 200)
        self.assertEqual(set(found), {"1", "3"})

    def test_profile_country_and_override_are_separate_seed_paths(self):
        snapshot = {"players": {
            "1": {"user": {"id": 10, "location": {"country": "Guatemala"}}},
            "2": {"user": {"id": 20, "location": {"country": "Mexico"}}},
            "3": {"user": {"id": 30, "location": {"country": "US"}}}}}
        self.assertEqual(seeds(snapshot, {"2": "2025 PR"}), {"1": "10", "2": "20"})

    def test_incomplete_foreign_capture_cannot_be_combined(self):
        national = {"kind": "national_discovery", "catalogComplete": True, "eventsComplete": True,
                    "generatedAt": "2026-01-01", "season": {}, "events": [], "players": {}, "sets": {}}
        abroad = {"kind": "abroad_discovery", "nationalGeneratedAt": "2026-01-01", "season": {},
                  "discoveryComplete": True, "eventsComplete": False}
        with self.assertRaisesRegex(ValueError, "no está completa"):
            combine(national, abroad)

    def test_documented_seed_addition_resumes_without_losing_previous_events(self):
        national = {"generatedAt": "2026-09-28", "season": {"startInclusive": 100, "endExclusive": 200},
                    "players": {"1": {"user": {"id": 10, "location": {"country": "Guatemala"}}},
                                "2": {"user": {"id": 20, "location": {"country": "US"}}}}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "abroad.json"
            first = discover_abroad(StubClient(), national, {}, path)
            self.assertEqual(first["seedPlayerIds"], ["1"])
            second = discover_abroad(StubClient(), national, {"2": "asiento regional"}, path)
            self.assertEqual(second["seedPlayerIds"], ["1", "2"])
            self.assertEqual(second["scannedPlayerIds"], ["1", "2"])
            self.assertEqual(len(second["events"]), 2)

    def test_new_foreign_event_requires_editorial_review_before_publication(self):
        state = {"events": {"10": {}, "20": {}}}
        with self.assertRaisesRegex(ValueError, "20"):
            require_reviewed_events(state, {"approvedForeignEventIds": {"10": "reviewed"}})
        require_reviewed_events(state, {"approvedForeignEventIds": {"10": "reviewed"},
                                        "excludedForeignEventIds": {"20": "non-standard"}})

    def test_foreign_event_with_only_seed_dq_is_not_included(self):
        national = {"kind": "national_discovery", "catalogComplete": True, "eventsComplete": True,
                    "generatedAt": "2026-01-01", "season": {}, "events": [], "players": {}, "sets": {}}
        abroad = {"kind": "abroad_discovery", "nationalGeneratedAt": "2026-01-01", "season": {},
                  "discoveryComplete": True, "eventsComplete": True, "eventSources": {"5": ["1"]},
                  "fetchedEvents": {"5": {"id": 5}}, "events": {"5": {}}, "players": {},
                  "sets": {"8": {"event": {"id": 5}, "state": 3, "winnerId": 20,
                                 "displayScore": "DQ", "slots": []}}, "seedPlayerIds": ["1"]}
        combined = combine(national, abroad)
        self.assertEqual(combined["foreignEventsFetched"], 0)
        self.assertEqual(combined["foreignEventsWithoutSeedSet"], ["5"])


if __name__ == "__main__":
    unittest.main()
