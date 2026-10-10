import copy
import ftplib
import json
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
    def test_seo_artifacts_in_publication_allowlist_and_shared_publication_lock(self):
        for name in ('robots.txt', 'sitemap.xml', 'torneos.html', 'tops.html', 'tops.css', 'tops.js', 'tops-api.php', 'terminos.html', 'reembolsos.html', 'visita.js'):
            self.assertIn(name, FILES)
        root = Path(__file__).resolve().parents[2]
        for name in ('smash-publish.yml', 'smash-deploy-snapshot.yml', 'smash-characters.yml'):
            workflow = (root / '.github/workflows' / name).read_text()
            self.assertIn('group: smash-gt-publication', workflow)
            self.assertIn('cancel-in-progress: false', workflow)

    def test_assets_only_preserves_live_agenda_bytes_in_success_and_failure(self):
        from test_seo import fixture, locations
        from seo import ORIGIN, timestamp
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder); fixture(source)
            (source / 'data/agenda.json').write_text('{"generatedAt":"2026-01-01T00:00:00Z"}')
            original = b'{"generatedAt":"2026-10-09T13:17:00Z","tournaments":[{"id":"test-only"}]}\n'
            self.assertNotIn('data/agenda.json', FILES)
            for failure in (False, True):
                with self.subTest(failure=failure):
                    files = {'data/agenda.json': original, 'data/public.json': (source / 'data/public.json').read_bytes()}
                    ftp = Mock()
                    ftp.retrbinary.side_effect = lambda command, callback: callback(files[command.removeprefix('RETR ')])
                    def store(command, stream):
                        name = command.removeprefix('STOR '); files[name] = stream.read()
                        if failure: raise ftplib.error_temp('450 test-only upload interruption')
                    ftp.storbinary.side_effect = store
                    ftp.rename.side_effect = lambda temporary, destination: files.update({destination: files.pop(temporary)})
                    ftp.delete.side_effect = lambda name: files.pop(name, None)
                    if failure:
                        with self.assertRaises(ftplib.error_temp): deploy(ftp, source, assets_only=True)
                    else:
                        deploy(ftp, source, assets_only=True)
                        self.assertEqual(timestamp(locations(files['sitemap.xml'])[ORIGIN+'/torneos.html']), timestamp('2026-10-09T13:17:00Z'))
                    self.assertEqual(files['data/agenda.json'], original)
                    self.assertEqual(files['data/public.json'], (source / 'data/public.json').read_bytes())
                    for call in ftp.storbinary.call_args_list:
                        self.assertNotIn('agenda.json', call.args[0])
                    for call in ftp.rename.call_args_list:
                        self.assertFalse(any('agenda.json' in name for name in call.args))
                    for call in ftp.delete.call_args_list:
                        self.assertNotIn('agenda.json', call.args[0])

    def test_tournaments_page_counts_one_view_with_its_own_stored_page(self):
        import re
        site = Path(__file__).resolve().parents[2] / 'ranking-smash-ultimate'
        page = (site / 'torneos.html').read_text()
        tags = re.findall(r'<script\b[^>]*visita\.js[^>]*>', page)
        self.assertEqual(len(tags), 1)
        self.assertIn('data-page="torneos"', tags[0])
        historical = (site / 'analisis-torneos.html').read_text()
        self.assertIn('data-page="analisis-torneos"', historical)

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
            public = {'generatedAt': '2026-10-04T11:43:18.348499+00:00'}
            for name, data in [('public', public), ('analisis-top20', {'cut': '2026-10-02T22:33:45Z'}),
                               ('analisis-torneos', {'snapshotAt': '2026-09-29T16:05:57Z'})]:
                (source / ('data/' + name + '.json')).write_text(json.dumps(data))
            with patch.dict("os.environ", {"SMASH_FTP_DIR": ""}):
                deploy(ftp, source)
            self.assertEqual(ftp.cwd.call_args_list[0].args, ("ranking-smash-ultimate",))
            root_ftp = Mock()
            with patch.dict("os.environ", {"SMASH_FTP_DIR": "."}):
                deploy(root_ftp, source)
            self.assertEqual(root_ftp.cwd.call_args_list[0].args, ("data",))
            with patch.dict("os.environ", {"SMASH_FTP_DIR": "../otro"}), self.assertRaises(ValueError):
                deploy(Mock(), source)
            self.assertEqual(ftp.rename.call_args_list[-2].args[1], "data/public.json")
            self.assertEqual(ftp.rename.call_args_list[-1].args[1], "sitemap.xml")
            ftp.delete.assert_not_called()
            assets_ftp = Mock()
            assets_ftp.retrbinary.side_effect = lambda command, callback: callback(json.dumps(public).encode())
            deploy(assets_ftp, source, assets_only=True)
            self.assertNotIn("data/public.json", [call.args[1] for call in assets_ftp.rename.call_args_list])
            secured_ftp = Mock()
            secured_ftp.retrbinary.side_effect = lambda command, callback: callback(json.dumps(public).encode())
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
        self.assertEqual(libraries, {"database.php", "survey.php", "accounts.php", "visits.php", "stats.php", "premium.php", "organizador.php", "organizer-slides.php", "tops.php", "analisis.php", "ranking-import.php", "ranking-sync-lib.php"})
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
