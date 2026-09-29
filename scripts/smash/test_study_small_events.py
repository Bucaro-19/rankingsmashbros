import unittest

from study_small_events import study
from test_rank import fixture


class SmallEventStudyTests(unittest.TestCase):
    def test_study_keeps_baseline_and_reports_exception_separately(self):
        national = fixture()
        national["selectionNote"] = "Estudio: todos los eventos presenciales singles con inscritos conocidos"
        national["events"][1]["numEntrants"] = 8
        national["sets"] = {sid: row for sid, row in national["sets"].items()
                            if str(row["event"]["id"]) == "10" or int(sid) % 100 <= 8}
        previous = {**national, "events": [], "players": {}, "sets": {}, "internationalComplete": True}
        points = ("Category,Note,Player,Start.gg Hex ID,Start.gg Num ID,Points,Start Date,End Date,Midpt Date,Source\n"
                  "rank,test,P1,hex,1,100,2026-01-01,2027-01-01,,test\n"
                  "rank,test,P2,hex,2,100,2026-01-01,2027-01-01,,test\n")
        result = study(national, previous, {}, points)
        self.assertEqual(result["baseline"]["events"], 1)
        self.assertEqual(result["scenarios"]["pointsException"]["events"], 2)
        self.assertEqual(result["smallEvents"][0]["estimatedPoints"], 224)
        self.assertTrue(result["smallEvents"][0]["qualifiesByException"])
        self.assertEqual(result["status"], "simulacion_sin_cambio_de_regla")
        with self.assertRaisesRegex(ValueError, "no reproduce"):
            study(national, previous, {}, points, {"players": [{"id": "fake", "rank": 1, "rating": 1500}],
                                                   "counts": {"events": 1, "sets": 31}})


if __name__ == "__main__":
    unittest.main()
