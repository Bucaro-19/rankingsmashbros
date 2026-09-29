import unittest
from unittest.mock import patch

from discover import discover


class CatalogClient:
    calls = 0

    def query(self, query, variables):
        self.calls += 1
        return {"tournaments": {"pageInfo": {"totalPages": 1, "total": 1}, "nodes": [{
            "id": 1, "name": "The Oven prueba", "countryCode": "GT", "isOnline": False,
            "events": [{"id": 2, "name": "Ultimate Singles", "numEntrants": 16,
                        "isOnline": False, "state": "COMPLETED", "type": 1,
                        "startAt": 150, "videogame": {"id": 1386}}]}]}}


class DiscoveryTests(unittest.TestCase):
    def test_small_events_are_only_fetched_for_opt_in_study(self):
        with patch("discover.fetch_event", return_value=({"id": 2, "entrantCountFetched": 16, "setsFetched": 20}, {}, {})) as fetch:
            normal = discover(CatalogClient(), 100, 200)
            self.assertEqual(normal["events"], [])
            self.assertEqual(normal["excludedEvents"], [{"id": "2", "reason": "under_32_entrants"}])
            fetch.assert_not_called()
            study = discover(CatalogClient(), 100, 200, include_small=True)
            self.assertEqual(len(study["events"]), 1)
            self.assertEqual(study["events"][0]["id"], 2)
            self.assertEqual(study["excludedEvents"], [])


if __name__ == "__main__":
    unittest.main()
