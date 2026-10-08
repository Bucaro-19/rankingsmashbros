import copy
import ftplib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from publish_data import export
from deploy import deploy, require_sql_survey, validate_public_data, validate_study_data, FILES


def snapshot():
    return {
        "kind": "coverage_probe", "rankingComputed": False, "generatedAt": "2026-09-28T12:00:00+00:00",
        "season": {"startInclusive": 1767225600, "endExclusive": 1790726400},
        "players": {"1": {"gamerTag": "Jugador de prueba", "countryStatus": "GT_candidate",
                            "user": {"slug": "user/test", "email": "private@example.com"}},
                    "2": {"gamerTag": "Rival extranjero", "countryStatus": "other_country"}},
        "coverage": {"1": {"historyComplete": False}},
        "sets": {"10": {"state": 3, "winnerId": 101, "displayScore": "Jugador de prueba 2 - Rival extranjero 1",
            "slots": [{"entrant": {"id": 101, "participants": [{"player": {"id": 1}}]}},
                      {"entrant": {"id": 102, "participants": [{"player": {"id": 2}}]}}],
            "event": {"id": 5, "startAt": 1788220800, "isOnline": False,
                "slug": "tournament/test/event/ultimate", "tournament": {"name": "Torneo de prueba", "countryCode": "MX"}}}}}


class ExportTests(unittest.TestCase):
    def test_foreign_opponents_are_context_not_national_roster(self):
        result = export(snapshot())
        self.assertEqual([p["id"] for p in result["players"]], ["1"])
        self.assertEqual(result["counts"], {"players": 1, "events": 1, "sets": 1, "countries": 1})
        self.assertEqual(result["results"][0]["country"], "MX")
        self.assertNotIn("email", str(result))
        self.assertNotIn("private@example.com", str(result))
        self.assertFalse(result["rankingComputed"])

    def test_pending_online_byes_dq_and_unknown_players_not_competitive_results(self):
        for change in ["online", "pending", "dq", "bye", "unknown", "wrong_winner"]:
            with self.subTest(change=change):
                data = snapshot()
                match = data["sets"]["10"]
                if change == "online": match["event"]["isOnline"] = True
                if change == "pending": match["state"] = 2
                if change == "dq": match["displayScore"] = "Jugador de prueba 2 - Rival DQ"
                if change == "bye": match["slots"].pop()
                if change == "unknown": match["slots"][0]["entrant"]["participants"][0]["player"] = None
                if change == "wrong_winner": match["winnerId"] = 999
                self.assertEqual(export(data)["counts"]["sets"], 0)

    def test_unvalidated_ranking_and_untrusted_links_not_published(self):
        data = snapshot()
        data["players"]["1"]["user"]["slug"] = "javascript:alert(1)"
        self.assertIsNone(export(data)["players"][0]["url"])
        data["rankingComputed"] = True
        with self.assertRaises(ValueError): export(data)

    def test_data_is_renamed_only_after_successful_upload(self):
        ftp = Mock()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            for name in FILES:
                (source / name).parent.mkdir(parents=True, exist_ok=True)
                (source / name).write_text("test")
            with patch.dict("os.environ", {"SMASH_FTP_DIR": ""}):
                deploy(ftp, source)
            self.assertEqual(ftp.cwd.call_args_list[0].args, ("ranking-smash-ultimate",))
            root_ftp = Mock()
            with patch.dict("os.environ", {"SMASH_FTP_DIR": "."}):
                deploy(root_ftp, source)
            self.assertEqual(root_ftp.cwd.call_args_list[0].args, ("data",))
            with patch.dict("os.environ", {"SMASH_FTP_DIR": "../otro"}), self.assertRaises(ValueError):
                deploy(Mock(), source)
            self.assertEqual(ftp.rename.call_args_list[-1].args[1], "data/public.json")
            ftp.delete.assert_not_called()
            assets_ftp = Mock()
            deploy(assets_ftp, source, assets_only=True)
            self.assertNotIn("data/public.json", [call.args[1] for call in assets_ftp.rename.call_args_list])
            secured_ftp = Mock()
            admin_hash = "$2y$12$" + "A" * 53
            deploy(secured_ftp, source, assets_only=True, admin_hash=admin_hash)
            self.assertIn("admin-auth.php", [call.args[1] for call in secured_ftp.rename.call_args_list])
            self.assertNotIn("data/public.json", [call.args[1] for call in secured_ftp.rename.call_args_list])
            self.assertEqual(secured_ftp.rename.call_args_list[0].args[1], "admin-auth.php")
            failed = Mock()
            failed.storbinary.side_effect = ftplib.error_temp("450 upload interrupted")
            with self.assertRaises(ftplib.error_temp): deploy(failed, source)
            failed.rename.assert_not_called()
            self.assertTrue(failed.delete.call_args.args[0].endswith(".tmp"))

    def test_deployment_requires_consistent_ranking_with_international_coverage(self):
        data = {"schemaVersion": 2, "status": "international_pilot", "rankingComputed": True,
                "players": [{"id": str(i), "rank": i} for i in range(1, 101)], "events": [{"name": "Prueba", "validSets": 6739, "activePlayers": 32}],
                "counts": {"players": 100, "events": 1, "sets": 6739}}
        validate_public_data(data)
        for change in ["coverage_only", "local_pilot", False, 99]:
            altered = copy.deepcopy(data)
            if isinstance(change, str): altered["status"] = change
            elif isinstance(change, bool): altered["rankingComputed"] = change
            else: altered["players"].pop()
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_public_data(altered)

        data['players'].extend({'id': str(i), 'rank': i} for i in range(101, 156))
        data['rankingCoverage'] = 'all_eligible'
        data['counts'].update(players=155, eligiblePlayers=155, top100=100)
        validate_public_data(data)
        for change in ('truncated', 'gap', 'duplicate'):
            altered = copy.deepcopy(data)
            if change == 'truncated':
                altered['players'].pop()
                altered['counts']['players'] -= 1
            elif change == 'gap': altered['players'][-1]['rank'] += 1
            else: altered['players'][-1]['id'] = '1'
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_public_data(altered)

    def test_study_must_be_a_separate_complete_simulation(self):
        valid = {"schemaVersion": 1, "status": "simulacion_sin_cambio_de_regla", "baselineVerifiedAsOf": "2026-09-29T00:00:00Z", "smallEvents": [],
                 "scenarios": {"pointsException": {}, "min24": {}, "min16": {}}}
        validate_study_data(valid)
        valid["status"] = "ranking_publicado"
        with self.assertRaisesRegex(ValueError, "estudio completo"):
            validate_study_data(valid)

    def test_php_libraries_are_published_denied_and_uploaded_before_their_callers(self):
        # The allowlist is independent of the file tree: a committed but unlisted PHP file would
        # deploy "successfully" and break the pages that require it. Files replace one by one,
        # so a library must already be in place (and denied by .htaccess) when its caller lands.
        import re
        site = Path(__file__).resolve().parents[2] / "ranking-smash-ultimate"
        pages = sorted(path.name for path in site.glob("*.php"))
        self.assertEqual(pages, sorted(name for name in FILES if name.endswith(".php")))
        htaccess = (site / ".htaccess").read_text()
        libraries = set()
        for page in pages:
            source = (site / page).read_text()
            required = re.findall(r"require(?:_once)?\s+__DIR__\s*\.\s*'/([A-Za-z0-9_.-]+\.php)'", source)
            self.assertEqual(len(required), len(re.findall(r"\brequire(?:_once)?\b[^;]*\.php'", source)), page)
            for library in required:
                libraries.add(library)
                self.assertIn(library, FILES, f"{page} requires {library}")
                self.assertLess(FILES.index(library), FILES.index(page), f"{library} must upload before {page}")
        self.assertEqual(libraries, {"database.php", "survey.php", "accounts.php", "visits.php", "stats.php", "premium.php", "organizador.php", "analisis.php", "ranking-import.php", "ranking-sync-lib.php"})
        for library in libraries:
            self.assertLess(FILES.index(".htaccess"), FILES.index(library))
            self.assertRegex(htaccess, r'<Files "%s">\s*Require all denied\s*</Files>' % re.escape(library))
        # The admin hash file is the only PHP loaded from the protected folder; it is written by deploy().
        self.assertEqual(FILES[-1], "data/public.json")

    def test_file_backed_survey_pages_are_never_published(self):
        site = Path(__file__).resolve().parents[2] / "ranking-smash-ultimate"
        require_sql_survey(site)  # the pages in this checkout
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            for page in ("encuesta.php", "opiniones.php"):
                (source / page).write_text((site / page).read_text())
            require_sql_survey(source)
            legacy = "<?php $path = __DIR__ . '/feedback-data/respuestas-2026.php'; ?><title>x</title>"
            for page, content in [("encuesta.php", legacy), ("opiniones.php", legacy),
                                  ("encuesta.php", (site / "encuesta.php").read_text().replace('content="sql"', 'content="file"')),
                                  ("opiniones.php", (site / "opiniones.php").read_text() + "<!-- respuestas-2026 -->")]:
                original = (source / page).read_text()
                (source / page).write_text(content)
                with self.subTest(page=page), self.assertRaises(ValueError):
                    require_sql_survey(source)
                (source / page).write_text(original)
        # Deploys only run from main: another ref could carry the pages of before the migration.
        workflows = Path(__file__).resolve().parents[2] / ".github/workflows"
        for name in ("smash-deploy-snapshot.yml", "smash-publish.yml"):
            self.assertIn("github.ref == 'refs/heads/main'", (workflows / name).read_text(), name)


if __name__ == "__main__":
    unittest.main()
