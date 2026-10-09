"""SEO artifacts from published data only; no API, database or third-party calls."""
from datetime import datetime, timezone
import json
from xml.etree import ElementTree as ET

ORIGIN = 'https://rankingsmashbros.com'
SITEMAP_NS = 'http://www.sitemaps.org/schemas/sitemap/0.9'
PUBLIC_PAGES = ('', 'metodologia.html', 'analisis-top20.html', 'analisis-torneos.html', 'torneos.html', 'terminos.html', 'reembolsos.html')

# Actual editorial revision, fixed until these texts change; never the deploy clock or cut.
CONTENT_UPDATED_AT = {'terminos.html': '2026-10-09T21:53:35Z', 'reembolsos.html': '2026-10-09T21:53:35Z'}

def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('SEO: falta una fecha real del contenido.')
    date = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if date.tzinfo is None or date.year < 1970:
        raise ValueError('SEO: la fecha debe incluir zona horaria.')
    return date.astimezone(timezone.utc)


def build_sitemap(source, public, *, agenda=None):
    """Cut-based pages use the actual cut; historical studies keep their own date."""
    cut = timestamp(public['generatedAt'])
    top20 = json.loads((source / 'data/analisis-top20.json').read_text(encoding='utf-8'))
    tournaments = json.loads((source / 'data/analisis-torneos.json').read_text(encoding='utf-8'))
    # Top20 also reads public.json to warn when its archived cut is no longer current.
    dates = {'': cut, 'metodologia.html': cut,
             'analisis-top20.html': max(cut, timestamp(top20['cut'])),
             'analisis-torneos.html': timestamp(tournaments['snapshotAt'])}
    dates.update({page: timestamp(date) for page, date in CONTENT_UPDATED_AT.items()})
    # Agenda is independently published. Missing/unreadable metadata must not block a cut
    # or substitute its date with the ranking cut, a Git snapshot, or the deploy clock.
    if isinstance(agenda, dict):
        try:
            dates['torneos.html'] = timestamp(agenda.get('generatedAt'))
        except (ValueError, OverflowError):
            pass
    ET.register_namespace('', SITEMAP_NS)
    root = ET.Element('{' + SITEMAP_NS + '}urlset')
    for page in PUBLIC_PAGES:
        if page not in dates:
            continue
        date = dates[page]
        url = ET.SubElement(root, '{' + SITEMAP_NS + '}url')
        ET.SubElement(url, '{' + SITEMAP_NS + '}loc').text = ORIGIN + '/' + page
        ET.SubElement(url, '{' + SITEMAP_NS + '}lastmod').text = date.isoformat().replace('+00:00', 'Z')
    ET.indent(root, space='  ')
    return ET.tostring(root, encoding='utf-8', xml_declaration=True) + b'\n'
