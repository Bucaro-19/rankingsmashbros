"""Offline facts and capture policy. No tests contact the source."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from frame_facts import parse,Snapshot,LABELS,ORIGIN
ROOT=Path(__file__).resolve().parents[2]
SITE=ROOT/'ranking-smash-ultimate'


class FrameFactsTests(unittest.TestCase):
    def test_numeric_only_ambiguous_values_and_followups(self):
        def move(name,frame,damage,adv):
            return f'<div class="movecontainer"><div class="movename">{name}</div><div class="startup">{frame}</div><div class="basedamage">{damage}</div><div class="advantage">{adv}</div><div class="notes">DO NOT COPY THIS SOURCE PROSE<img src="private.gif"></div></div>'
        html=move('Jab 1',5,'2.0','-14')+move('Jab 2',2,'3.0','-19')+move('Forward Tilt',1,'5.0/8.0','-12/-16')
        html+='<div class="oos1">Out of Shield, Neutral Air or Up Smash — 6 frames</div><div class="oos2">Out of Shield, Up B — 3 frames (front only)</div>'
        facts=parse(html)
        self.assertEqual(facts['fastest'],dict(name='Golpe normal 1',frame=5,damage=2.0))
        self.assertEqual([r['frame'] for r in facts['oos']],[6,6]);self.assertEqual(len(facts['punishable']),2)
        self.assertNotIn('PROSE',json.dumps(facts));self.assertNotIn('gif',json.dumps(facts))

    def test_stored_samples_checked_against_five_source_pages(self):
        # Manually checked cells in cached source HTML, 13/oct GT. No source prose/media in fixture.
        samples={
         'mario':(2,2.2,[3,6,7],[-25,-20,-18]),
         'fox':(2,1.8,[6,7,8],[-36,-36,-22]),
         'link':(7,3.0,[9,10,10],[-28,-23,-19]),
         'bowser':(7,4.0,[6,9,11],[-33,-32,-30]),
         'captain_falcon':(3,1.5,[10,10,13],[-27,-20,-13]),
        }
        data=json.loads((SITE/'data/frame-facts-v1.json').read_text())
        self.assertEqual(data['schemaVersion'],1);self.assertIsNone(data['source']['gameVersion'])
        for slug,(frame,damage,oos,adv) in samples.items():
            with self.subTest(slug=slug):
                sheet=data['characters'][slug]
                self.assertEqual((sheet['fastest']['frame'],sheet['fastest']['damage']),(frame,damage))
                self.assertEqual([r['frame'] for r in sheet['oos']],oos)
                self.assertEqual([r['onShield'] for r in sheet['punishable']],adv)
                self.assertEqual(data['sources'][slug]['url'],ORIGIN+'/'+slug)
                self.assertEqual(len(data['sources'][slug]['sha256']),64)
        self.assertNotIn('pokemon_trainer',data['characters']);self.assertNotIn('pyra',data['characters'])

    def test_dataset_has_only_numeric_facts_and_our_labels(self):
        data=json.loads((SITE/'data/frame-facts-v1.json').read_text())
        labels=set(LABELS.values())|{x+' aéreo' for x in LABELS.values()}
        for slug,sheet in data['characters'].items():
            self.assertEqual(set(sheet),{'fastest','oos','punishable'})
            rows=([sheet['fastest']] if sheet['fastest'] else [])+sheet['oos']+sheet['punishable']
            self.assertLessEqual(len(sheet['oos']),3);self.assertLessEqual(len(sheet['punishable']),3)
            for row in rows:
                self.assertIn(row['name'],labels)
                self.assertTrue(all(type(v) in (float,int) for k,v in row.items() if k!='name'))
                self.assertLessEqual(set(row),{'name','frame','damage','onShield'})

    def test_polite_capture_cache_and_robots(self):
        now=[0.0];times=[];urls=[]
        def sleep(seconds):now[0]+=seconds
        class Response(io.BytesIO):
            def geturl(self):return urls[-1]
        def open_page(request,timeout):
            urls.append(request.full_url);times.append(now[0])
            return Response(b'User-agent: *\nDisallow:\n' if request.full_url.endswith('robots.txt') else b'<html></html>')
        with tempfile.TemporaryDirectory() as folder:
            source=Snapshot(folder,capture=True,clock=lambda:now[0],sleep=sleep,opener=open_page)
            source.run(['mario','fox']);self.assertEqual(source.requests,3)
            self.assertEqual(times,[0,1,2]);self.assertTrue(all(u.startswith(ORIGIN+'/') for u in urls))
            cached=Snapshot(folder,opener=lambda *a,**k:self.fail('Offline cache must not request anything'))
            cached.run(['fox','mario']);self.assertEqual(cached.requests,0)
            (Path(folder)/'robots.txt').write_text('User-agent: *\nDisallow: /mario\n')
            with self.assertRaisesRegex(ValueError,'robots'):cached.run(['mario'])

    def test_one_removal_switch_and_missing_or_bad_snapshot(self):
        import subprocess
        with tempfile.TemporaryDirectory() as folder:
            site=Path(folder);(site/'data').mkdir()
            source=(SITE/'frame-facts.php').read_text()
            lib=site/'frame-facts.php';lib.write_text(source)
            def read():
                code='require '+json.dumps(str(lib))+";echo json_encode(smash_frame_facts(['mario'],'link',true));"
                return json.loads(subprocess.check_output(['php','-r',code]))
            empty=dict(toolkit=None,punishable=None,frameDataSource=None)
            self.assertEqual(read(),empty)
            snapshot=site/'data/frame-facts-v1.json';snapshot.write_text('{bad')
            self.assertEqual(read(),empty)
            snapshot.write_bytes((SITE/'data/frame-facts-v1.json').read_bytes())
            self.assertEqual(read()['toolkit']['mario']['fastest']['frame'],2)
            lib.write_text(source.replace('const SMASH_FRAME_FACTS_ENABLED = true;','const SMASH_FRAME_FACTS_ENABLED = false;'))
            self.assertEqual(read(),empty)

    def test_private_dataset_is_denied_and_deployed_before_reader(self):
        import deploy
        rules=(SITE/'.htaccess').read_text()
        for name in ('frame-facts.php','frame-facts-v1.json'):self.assertIn(f'<Files "{name}">\n  Require all denied',rules)
        self.assertLess(deploy.FILES.index('.htaccess'),deploy.FILES.index('data/frame-facts-v1.json'))
        self.assertLess(deploy.FILES.index('data/frame-facts-v1.json'),deploy.FILES.index('frame-facts.php'))
        self.assertLess(deploy.FILES.index('frame-facts.php'),deploy.FILES.index('analisis.php'))
        for name in ('preparar.js','frame-tools.js','frame-facts.php'):
            self.assertNotIn('fetch(\'https://ultimateframedata',(SITE/name).read_text())
