import unittest
from collect import collect, country_candidate, profile_slug, APIError


def player(pid, country=None):
    return {"id": pid, "gamerTag": f"Prueba {pid}",
            "user": {"location": {"country": country}} if country else None}


def match(sid, p1, p2, country="MX", game="Super Smash Bros. Ultimate", started=150):
    return {"id": sid, "state": 3, "winnerId": p1["id"],
            "event": {"startAt": started, "videogame": {"name": game},
                      "tournament": {"countryCode": country}},
            "slots": [{"entrant": {"participants": [{"player": p}]}} for p in (p1, p2)]}


class FakeClient:
    def __init__(self, root, pages):
        self.root, self.pages, self.calls = root, pages, 0

    def query(self, query, variables):
        self.calls += 1
        if "slug" in variables:
            return {"user": {"player": self.root}}
        pages = self.pages[variables["id"]]
        return {"player": {"sets": {"nodes": pages[variables["page"] - 1],
                                    "pageInfo": {"totalPages": len(pages)}}}}


class CoverageTests(unittest.TestCase):
    def test_public_country_is_candidate_not_citizenship(self):
        self.assertEqual(country_candidate(player(1, "Guatemala")), "GT_candidate")
        self.assertEqual(country_candidate(player(1, " GT ")), "GT_candidate")
        self.assertEqual(country_candidate(player(1)), "unknown")
        self.assertEqual(country_candidate(player(1, "México")), "other_country")

    def test_foreign_results_deduplicate_and_expand_only_one_hop(self):
        gt, mx, jp = player(1, "Guatemala"), player(2, "Mexico"), player(3, "Japan")
        shared = match(11, gt, mx)
        client = FakeClient(gt, {"1": [[shared], [match(12, gt, mx, "GT")]],
                                "2": [[shared, match(13, mx, jp)]]})
        result = collect(client, ["user/example"], 100, 200)
        self.assertEqual(set(result["sets"]), {"11", "12", "13"})
        self.assertEqual(set(result["coverage"]), {"1", "2"})
        self.assertEqual(result["contextPlayerIdsWithoutHistory"], ["3"])
        self.assertFalse(result["rankingComputed"])
        self.assertTrue(result["coverage"]["1"]["historyComplete"])

    def test_caps_are_reported_without_claiming_complete_data(self):
        gt, mx = player(1, "GT"), player(2, "MX")
        client = FakeClient(gt, {"1": [[match(11, gt, mx)], []]})
        result = collect(client, ["user/example"], 100, 200, max_pages=1, max_opponents=0)
        self.assertFalse(result["coverage"]["1"]["historyComplete"])
        self.assertEqual(result["unfetchedDirectOpponents"], ["2"])

    def test_season_bounds_and_game_filter(self):
        gt, mx = player(1), player(2)
        client = FakeClient(gt, {"1": [[match(1, gt, mx, started=99),
            match(2, gt, mx, started=100), match(3, gt, mx, started=200),
            match(4, gt, mx, game="Super Smash Bros. Melee")]]})
        result = collect(client, ["user/example"], 100, 200, max_opponents=0)
        self.assertEqual(set(result["sets"]), {"2"})

    def test_bad_profile_and_missing_data_fail_explicitly(self):
        self.assertEqual(profile_slug("https://www.start.gg/user/7a6063d8/"), "user/7a6063d8")
        with self.assertRaises(ValueError):
            profile_slug("https://untrusted.example/user/test")
        with self.assertRaises(APIError):
            collect(FakeClient(None, {}), ["user/example"], 100, 200)


if __name__ == "__main__":
    unittest.main()
