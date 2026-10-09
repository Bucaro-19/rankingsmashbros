"""Public metadata, crawler boundaries and sitemap/cut publication behavior."""
import copy
import ftplib
from html.parser import HTMLParser
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from xml.etree import ElementTree as ET

from deploy import FILES, deploy
from seo import build_sitemap, timestamp, ORIGIN, PUBLIC_PAGES, SITEMAP_NS

SITE = Path(__file__).resolve().parents[2] / 'ranking-smash-ultimate'


class Head(HTMLParser):
    def __init__(self, text):
        super().__init__(); self.meta = {}; self.canonical = []; self.titles = []; self.scripts = []
        self.in_title = False; self.in_json = False; self.feed(text.split('</head>')[0])

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'meta':
            key = attrs.get('property', attrs.get('name'))
            if key in self.meta: raise AssertionError('Duplicate metadata: ' + key)
            self.meta[key] = attrs.get('content')
        if tag == 'link' and attrs.get('rel') == 'canonical': self.canonical.append(attrs['href'])
        if tag == 'title': self.in_title = True
        if tag == 'script' and attrs.get('type') == 'application/ld+json': self.in_json = True

    def handle_endtag(self, tag):
        if tag == 'title': self.in_title = False
        if tag == 'script': self.in_json = False

    def handle_data(self, text):
        if self.in_title: self.titles.append(text)
        if self.in_json: self.scripts.append(json.loads(text))


def locations(body):
    root = ET.fromstring(body)
    if root.tag != '{' + SITEMAP_NS + '}urlset': raise AssertionError('Wrong namespace')
    return {row.find('s:loc', {'s': SITEMAP_NS}).text: row.find('s:lastmod', {'s': SITEMAP_NS}).text for row in root}


def fixture(source):
    for name in FILES:
        path = source / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text('test')
    for name in ('public', 'analisis-top20', 'analisis-torneos'):
        (source / ('data/' + name + '.json')).write_bytes((SITE / ('data/' + name + '.json')).read_bytes())


class SEOTests(unittest.TestCase):
    def test_public_page_canonical_social_metadata_unique_and_share_image(self):
        titles, descriptions = set(), set()
        for page in PUBLIC_PAGES:
            name = page or 'index.html'; text = (SITE / name).read_text(); head = Head(text)
            with self.subTest(page=name):
                self.assertEqual(head.canonical, [ORIGIN + '/' + page])
                self.assertEqual(head.meta['og:url'], head.canonical[0])
                self.assertEqual(head.meta['og:title'], ''.join(head.titles))
                self.assertEqual(head.meta['og:description'], head.meta['description'])
                self.assertEqual(head.meta['twitter:title'], head.meta['og:title'])
                self.assertEqual(head.meta['twitter:description'], head.meta['description'])
                self.assertEqual(head.meta['og:type'], 'website'); self.assertEqual(head.meta['og:locale'], 'es_GT')
                self.assertEqual(head.meta['twitter:card'], 'summary_large_image')
                self.assertNotIn('noindex', head.meta.get('robots', ''))
                self.assertIn('piloto', head.meta['description'])
                # The approved 1200 x 630 image is published with the site, never a URL to a missing file.
                image = 'https://rankingsmashbros.com/assets/smash-gt-social.jpg'
                self.assertEqual((head.meta['og:image'], head.meta['twitter:image']), (image, image))
                self.assertEqual((head.meta['og:image:width'], head.meta['og:image:height']), ('1200', '630'))
                self.assertIn('assets/smash-gt-social.jpg', FILES)
                data = (SITE / 'assets/smash-gt-social.jpg').read_bytes()
                self.assertTrue(data.startswith(b'\xff\xd8') and len(data) < 300 * 1024)
                self.assertNotIn('SEO: imagen', text)
                titles.add(head.meta['og:title']); descriptions.add(head.meta['description'])
        self.assertEqual(len(titles), len(PUBLIC_PAGES)); self.assertEqual(len(descriptions), len(PUBLIC_PAGES))

    def test_private_pages_noindex_and_robots_exclusions(self):
        for page in ('cuenta.html', 'analisis.html'):
            self.assertIn('noindex', Head((SITE / page).read_text()).meta['robots'].split(','))
        robots = (SITE / 'robots.txt').read_text()
        self.assertIn('User-agent: *', robots)
        self.assertIn('Sitemap: ' + ORIGIN + '/sitemap.xml', robots)
        for path in ('panel.php', 'opiniones.php', 'cuenta.html', 'analisis.html', 'top/', 'top.php', '*-api.php',
                     'oauth.php', 'visita.php', 'recurrente-webhook.php', 'ranking-sync.php', 'ranking-worker.php', 'feedback-data/'):
            self.assertIn('Disallow: /' + path, robots)
        for page in PUBLIC_PAGES:
            if page: self.assertNotIn('Disallow: /' + page, robots)

    def test_structured_website_organization_resolve_without_invented_affiliation(self):
        graph = Head((SITE / 'index.html').read_text()).scripts
        self.assertEqual(len(graph), 1); self.assertEqual(graph[0]['@context'], 'https://schema.org')
        types = {node['@type']: node for node in graph[0]['@graph']}
        self.assertEqual(set(types), {'WebSite', 'Organization'})
        self.assertEqual(types['WebSite']['publisher']['@id'], types['Organization']['@id'])
        self.assertEqual(types['WebSite']['inLanguage'], 'es-GT')
        for node in types.values():
            self.assertEqual(node['url'], ORIGIN + '/'); self.assertIn('piloto', node['description'])
            self.assertNotIn('logo', node); self.assertNotIn('sameAs', node)

    def test_sitemap_only_indexable_public_pages_with_source_dates(self):
        public = json.loads((SITE / 'data/public.json').read_text())
        agenda = json.loads((SITE / 'data/agenda.json').read_text())
        before = copy.deepcopy(public); xml = build_sitemap(SITE, public, agenda=agenda); rows = locations(xml)
        self.assertEqual(public, before)
        self.assertEqual(set(rows), {ORIGIN + '/' + page for page in PUBLIC_PAGES})
        for url in (ORIGIN + '/', ORIGIN + '/metodologia.html'):
            self.assertEqual(timestamp(rows[url]), timestamp(public['generatedAt']))
        archive = json.loads((SITE / 'data/analisis-torneos.json').read_text())
        self.assertEqual(timestamp(rows[ORIGIN + '/analisis-torneos.html']), timestamp(archive['snapshotAt']))
        self.assertEqual(timestamp(rows[ORIGIN + '/torneos.html']), timestamp(agenda['generatedAt']))
        self.assertEqual((SITE / 'sitemap.xml').read_bytes(), xml)
        self.assertNotIn('encuesta', xml.decode())

    def test_deploy_full_and_assets_only_use_actual_cut_not_committed_sitemap(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder); fixture(source)
            newer = {'generatedAt': '2026-10-11T00:00:00-06:00'}
            live_agenda = {'generatedAt': '2026-10-12T07:17:00-06:00'}
            # Stale Git agenda must never date the deployed page (full or assets-only).
            (source / 'data/agenda.json').write_text('{"generatedAt":"2026-01-01T00:00:00Z"}')
            for assets_only in (False, True):
                with self.subTest(assets_only=assets_only):
                    ftp = Mock(); uploaded = {}
                    ftp.retrbinary.side_effect = lambda command, callback: callback(json.dumps(live_agenda if command == 'RETR data/agenda.json' else newer).encode())
                    ftp.storbinary.side_effect = lambda command, file: uploaded.update({command: file.read()})
                    with patch.dict('os.environ', {'SMASH_FTP_DIR': '.'}): deploy(ftp, source, assets_only=assets_only)
                    command = next(command for command in uploaded if command.startswith('STOR sitemap.xml.'))
                    current = newer if assets_only else json.loads((source / 'data/public.json').read_text())
                    self.assertEqual(timestamp(locations(uploaded[command])[ORIGIN + '/']), timestamp(current['generatedAt']))
                    self.assertEqual(timestamp(locations(uploaded[command])[ORIGIN + '/torneos.html']), timestamp(live_agenda['generatedAt']))
                    renamed = [call.args[1] for call in ftp.rename.call_args_list]
                    self.assertEqual(renamed[-1], 'sitemap.xml')
                    if assets_only:
                        self.assertEqual([call.args[0] for call in ftp.retrbinary.call_args_list], ['RETR data/public.json', 'RETR data/agenda.json'])
                        self.assertNotIn('data/public.json', renamed)
                    else:
                        self.assertEqual([call.args[0] for call in ftp.retrbinary.call_args_list], ['RETR data/agenda.json'])
                        self.assertEqual(renamed[-2], 'data/public.json')
                    self.assertNotIn('data/agenda.json', renamed)
                    self.assertEqual((source / 'sitemap.xml').read_text(), 'test')  # Source/artifact never silently reused.
                    self.assertIn('robots.txt', renamed)

    def test_agenda_unavailable_or_invalid_is_omitted_without_failing_deploy(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder); fixture(source)
            # An attractive local fallback must not be used if live agenda cannot be read.
            (source / 'data/agenda.json').write_text('{"generatedAt":"2026-10-01T00:00:00Z"}')
            for assets_only in (False, True):
                for kind in ('missing', 'permission', 'network', 'json', 'utf8', 'array', 'no_date', 'timezone', 'bad_date', 'oversize', 'nested'):
                    with self.subTest(assets_only=assets_only, kind=kind):
                        ftp = Mock(); uploaded = {}
                        def receive(command, callback):
                            if command == 'RETR data/public.json':
                                callback((source / 'data/public.json').read_bytes()); return
                            errors = {'missing': ftplib.error_perm('550 Not found'), 'permission': ftplib.error_perm('550 Permission denied'), 'network': OSError('test-only')}
                            if kind in errors: raise errors[kind]
                            body = {'json': b'not json', 'utf8': b'\xff', 'array': b'[]', 'no_date': b'{}',
                                    'timezone': b'{"generatedAt":"2026-10-11T00:00:00"}', 'bad_date': b'{"generatedAt":"2026-02-30T00:00:00Z"}',
                                    'oversize': b' ' * (512 * 1024 + 1), 'nested': b'['*2000 + b']'*2000}[kind]
                            callback(body)
                            # RETR must drain after hitting the buffer limit, not throw
                            # in the callback and leave a 226 reply for the next command.
                            if kind == 'oversize': callback(b'ignored tail')
                        ftp.retrbinary.side_effect = receive
                        ftp.storbinary.side_effect = lambda command, file: uploaded.update({command: file.read()})
                        deploy(ftp, source, assets_only=assets_only)
                        body = next(body for command, body in uploaded.items() if command.startswith('STOR sitemap.xml.'))
                        self.assertEqual(set(locations(body)), {ORIGIN+'/'+p for p in PUBLIC_PAGES if p != 'torneos.html'})
                        self.assertEqual(ftp.rename.call_args_list[-1].args[1], 'sitemap.xml')
                        ftp.delete.assert_not_called()

    def test_sitemap_agenda_is_optional_and_other_dates_remain_required(self):
        public = json.loads((SITE / 'data/public.json').read_text())
        for agenda in (None, {}, [], {'generatedAt': None}, {'generatedAt': 0}, {'generatedAt':'2026-10-08'}):
            self.assertNotIn(ORIGIN+'/torneos.html', locations(build_sitemap(SITE, public, agenda=agenda)))
        with self.assertRaises(ValueError): build_sitemap(SITE, {'generatedAt': None}, agenda={'generatedAt':'2026-10-08T00:00:00Z'})

    def test_remote_read_or_bad_dates_fail_before_upload_and_no_fake_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder); fixture(source)
            for kind in ('read', 'json', 'missing', 'timezone', 'invalid'):
                with self.subTest(kind=kind):
                    ftp = Mock()
                    if kind == 'read': ftp.retrbinary.side_effect = ftplib.error_perm('550 test-only')
                    else:
                        payload = {'generatedAt': {'missing': None, 'timezone': '2026-10-11T00:00:00', 'invalid': '2026-02-30T00:00:00Z'}.get(kind)}
                        body = b'bad json' if kind == 'json' else json.dumps(payload).encode()
                        ftp.retrbinary.side_effect = lambda command, callback: callback(body)
                    with self.assertRaises((ValueError, ftplib.error_perm)): deploy(ftp, source, assets_only=True)
                    ftp.storbinary.assert_not_called(); ftp.rename.assert_not_called()

    def test_data_failure_preserves_previous_sitemap_and_sitemap_failure_is_visible(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder); fixture(source)
            for target in ('data/public.json', 'sitemap.xml'):
                ftp = Mock()
                def fail(command, file):
                    if command.startswith('STOR ' + target + '.'):
                        raise ftplib.error_temp('450 test-only interruption')
                ftp.storbinary.side_effect = fail
                with self.subTest(target=target), self.assertRaises(ftplib.error_temp): deploy(ftp, source)
                self.assertNotIn('sitemap.xml', [call.args[1] for call in ftp.rename.call_args_list])
                if target == 'data/public.json': self.assertNotIn('data/public.json', [call.args[1] for call in ftp.rename.call_args_list])
                else: self.assertEqual(ftp.rename.call_args_list[-1].args[1], 'data/public.json')
                self.assertTrue(ftp.delete.call_args.args[0].endswith('.tmp'))


if __name__ == '__main__': unittest.main(verbosity=2)
