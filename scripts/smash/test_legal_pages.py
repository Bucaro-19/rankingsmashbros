"""Public service terms, editorial sitemap dates and navigable links; no database."""
from html.parser import HTMLParser
from pathlib import Path
import unittest
from urllib.parse import urlsplit
from deploy import FILES

SITE = Path(__file__).resolve().parents[2] / 'ranking-smash-ultimate'
SCREENS = ('index.html','metodologia.html','encuesta.php','analisis.html','preparar.html','torneos.html',
           'cuenta.html','analisis-top20.html','analisis-torneos.html','opiniones.php','panel.php','top.php',
           'terminos.html','reembolsos.html','tops.html')
LEGAL = ('terminos.html','reembolsos.html')

class Links(HTMLParser):
    def __init__(self,text):
        super().__init__();self.urls=[];self.ids=set();self.feed(text)
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.add(a['id'])
        if tag=='a' and 'href' in a:self.urls.append(a['href'])

class LegalPagesTests(unittest.TestCase):
    def test_every_screen_footer_links_to_published_legal_files(self):
        for page in LEGAL:self.assertIn(page,FILES)
        for page in SCREENS:
            with self.subTest(page=page):
                text=(SITE/page).read_text();footer=text[text.index('<footer'):text.index('</footer>')]
                for target in LEGAL:self.assertIn('/'+target,Links(footer).urls)

    def test_reading_pages_are_static_and_links_resolve(self):
        for page in LEGAL:
            text=(SITE/page).read_text();links=Links(text)
            self.assertIn('smash-redesign page-read',text)
            self.assertIn('./paginas.css',text);self.assertIn('./metodologia.css',text)
            self.assertNotIn('support.js',text);self.assertNotIn('visita.js',text)
            self.assertNotIn('<form',text)
            for href in links.urls:
                url=urlsplit(href)
                if url.scheme or url.netloc:continue
                name=url.path.lstrip('/')
                target=SITE/(name or 'index.html') if url.path else SITE/page
                self.assertTrue(target.exists(),f'{page}: missing {href}')
                if url.fragment and target.suffix=='.html':
                    if target.name=='cuenta.html' and url.fragment=='premium':
                        # Existing JS tab route, not an HTML anchor.
                        self.assertIn('id="tab-premium"',target.read_text())
                        self.assertIn("'premium'",(SITE/'cuenta.js').read_text())
                    else:self.assertIn(url.fragment,Links(target.read_text()).ids,f'{page}: missing anchor {href}')

    def test_prices_access_cancellation_and_approved_refunds_match_actual_contract(self):
        terms=(SITE/'terminos.html').read_text();refunds=(SITE/'reembolsos.html').read_text()
        for text in ('3 USD al mes','24 USD al año','Recurrente','Pagar no da puntos ni cambia puestos',
                     'José Aurelio Porras','Guatemala','hasta el final del periodo','Sí, cancelar',
                     'hash','luego se descartan','no cancela automáticamente una suscripción'):
            self.assertIn(text,terms)
        self.assertIn('smash-refund-policy-status" content="approved',refunds)
        for page in ('terminos.html','reembolsos.html','premium.js'):
            text=(SITE/page).read_text()
            for old in ('PROPUESTA','pendiente de aprobación','7 días'):
                self.assertNotIn(old,text)
            for required in ('Los pagos no son reembolsables','ni completo ni en proporción',
                             'error del sitio o del procesador','se devuelven completos','5 días hábiles',
                             'contacto@rankingsmashbros.com','Antes de cada renovación'):
                self.assertIn(required,text)
        self.assertIn('tag de tu cuenta y la fecha del cobro',refunds)
        self.assertIn('no tramita devoluciones automáticas',refunds)
        premium=(SITE/'premium.js').read_text()
        for page in LEGAL:self.assertIn('href="./'+page+'"',premium)

if __name__=='__main__':unittest.main()
