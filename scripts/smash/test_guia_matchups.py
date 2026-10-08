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

    def test_unknown_characters_and_self_counters_are_rejected(self):
        names = {"a": "A", "b": "B"}
        for bad in ({"x": {"weakness": "w", "counters": [["a", "r"]]}}, {"a": {"weakness": "w", "counters": [["a", "r"]]}},
                    {"a": {"weakness": "w", "counters": []}}, {"a": {"sameAs": "b"}}):
            with self.assertRaises(ValueError):
                guide.validate({"characters": bad}, names)


if __name__ == "__main__":
    unittest.main()
