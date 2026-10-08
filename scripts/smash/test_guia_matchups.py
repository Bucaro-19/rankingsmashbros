import json
import unittest

import guia_matchups as guide


class MatchupGuideTests(unittest.TestCase):
    def test_draft_is_valid_and_the_review_copy_matches_it(self):
        data, names = json.loads(guide.SOURCE.read_text(encoding="utf-8")), guide.catalog()
        guide.validate(data, names)
        self.assertEqual(data["status"], "borrador_sin_revisar")
        self.assertEqual(guide.TARGET.read_text(encoding="utf-8"), guide.render(data, names))

    def test_draft_is_never_part_of_the_published_site(self):
        from deploy import FILES
        self.assertFalse([name for name in FILES if "matchup" in name.lower() or "guia" in name.lower()])

    def test_every_weakness_names_its_article_and_scene_rows_meet_the_sample(self):
        data, names = json.loads(guide.SOURCE.read_text(encoding="utf-8")), guide.catalog()
        self.assertTrue(all(guide.WIKI.fullmatch(entry["source"]) for entry in data["characters"].values()))
        self.assertIn("CC BY-SA", data["license"])
        ok = {"weaknesses": ["w"], "source": "https://www.ssbwiki.com/Mario_(SSBU)"}
        base = {"sceneMinimumGames": 8, "echoes": {}, "scene": {}}
        for bad in ({**base, "characters": {"mario": {**ok, "source": "https://example.com/x"}}},
                    {**base, "characters": {"mario": {**ok, "weaknesses": []}}},
                    {**base, "characters": {"nadie": ok}},
                    {**base, "characters": {"mario": ok}, "scene": {"mario": [["link", 3, 2]]}},
                    {**base, "characters": {"mario": ok}, "scene": {"mario": [["mario", 6, 4]]}},
                    {**base, "characters": {"mario": ok}, "echoes": {"link": "samus"}}):
            with self.assertRaises(ValueError):
                guide.validate(bad, names)
        guide.validate({**base, "characters": {"mario": ok}, "scene": {"mario": [["link", 6, 4]]}}, names)


if __name__ == "__main__":
    unittest.main()
