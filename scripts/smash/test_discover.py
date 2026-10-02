import unittest
from unittest.mock import patch

from discover import discover


class CatalogClient:
    calls = 0

    def __init__(self, entrants=16):
        self.entrants = entrants

    def query(self, query, variables):
        self.calls += 1
        return {"tournaments": {"pageInfo": {"totalPages": 1, "total": 1}, "nodes": [{
            "id": 1, "name": "The Oven prueba", "countryCode": "GT", "isOnline": False,
            "events": [{"id": 2, "name": "Ultimate Singles", "numEntrants": self.entrants,
                        "isOnline": False, "state": "COMPLETED", "type": 1,
                        "startAt": 150, "videogame": {"id": 1386}}]}]}}


class DiscoveryTests(unittest.TestCase):
    def test_production_fetches_20_entrants_for_active_player_validation(self):
        for entrants in (19, 20, 21):
            with self.subTest(entrants=entrants), patch('discover.fetch_event', return_value=(
                    {'id': 2, 'entrantCountFetched': entrants, 'setsFetched': 20}, {}, {})) as fetch:
                data = discover(CatalogClient(entrants), 100, 200)
                self.assertEqual(len(data['events']), int(entrants >= 20))
                self.assertEqual(fetch.called, entrants >= 20)

    def test_small_events_are_only_fetched_for_opt_in_study(self):
        with patch("discover.fetch_event", return_value=({"id": 2, "entrantCountFetched": 16, "setsFetched": 20}, {}, {})) as fetch:
            normal = discover(CatalogClient(), 100, 200)
            self.assertEqual(normal["events"], [])
            self.assertEqual(normal["excludedEvents"], [{"id": "2", "reason": "under_20_entrants"}])
            fetch.assert_not_called()
            study = discover(CatalogClient(), 100, 200, include_small=True)
            self.assertEqual(len(study["events"]), 1)
            self.assertEqual(study["events"][0]["id"], 2)
            self.assertEqual(study["excludedEvents"], [])


if __name__ == "__main__":
    unittest.main()
