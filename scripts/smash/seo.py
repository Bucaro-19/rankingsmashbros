"""SEO artifacts from published data only; no API, database or third-party calls."""
from datetime import datetime, timezone
import json
from xml.etree import ElementTree as ET

ORIGIN = 'https://rankingsmashbros.com'
SITEMAP_NS = 'http://www.sitemaps.org/schemas/sitemap/0.9'
PUBLIC_PAGES = ('', 'metodologia.html', 'analisis-top20.html', 'analisis-torneos.html')


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('SEO: falta una fecha real del contenido.')
    date = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if date.tzinfo is None or date.year < 1970:
        raise ValueError('SEO: la fecha debe incluir zona horaria.')
    return date.astimezone(timezone.utc)


def build_sitemap(source, public):
    """Cut-based pages use the actual cut; historical studies keep their own date."""
    cut = timestamp(public['generatedAt'])
    top20 = json.loads((source / 'data/analisis-top20.json').read_text(encoding='utf-8'))
    tournaments = json.loads((source / 'data/analisis-torneos.json').read_text(encoding='utf-8'))
    # Top20 also reads public.json to warn when its archived cut is no longer current.
    dates = (cut, cut, max(cut, timestamp(top20['cut'])), timestamp(tournaments['snapshotAt']))
    ET.register_namespace('', SITEMAP_NS)
    root = ET.Element('{' + SITEMAP_NS + '}urlset')
    for page, date in zip(PUBLIC_PAGES, dates):
        url = ET.SubElement(root, '{' + SITEMAP_NS + '}url')
        ET.SubElement(url, '{' + SITEMAP_NS + '}loc').text = ORIGIN + '/' + page
        ET.SubElement(url, '{' + SITEMAP_NS + '}lastmod').text = date.isoformat().replace('+00:00', 'Z')
    ET.indent(root, space='  ')
    return ET.tostring(root, encoding='utf-8', xml_declaration=True) + b'\n'
