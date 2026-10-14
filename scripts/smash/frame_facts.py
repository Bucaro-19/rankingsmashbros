"""One-off numeric Ultimate Frame Data snapshot. Offline by default; never run by the site.

Only numeric facts and our generic move labels are emitted. No notes, media or prose.
Downloaded HTML stays in an owner-selected private cache, outside the repository.
"""
import argparse
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser

ROOT=Path(__file__).resolve().parents[2]
ORIGIN='https://ultimateframedata.com'
AGENT='SmashGT-FrameFacts/1.0 (+https://rankingsmashbros.com)'
# These are our own generic labels, not the source's attack descriptions/notes.
LABELS={
 'Jab':'Golpe normal', 'Jab 1':'Golpe normal 1','Jab 2':'Golpe normal 2','Jab 3':'Golpe normal 3',
 'Forward Tilt':'Tilt lateral','Up Tilt':'Tilt arriba','Down Tilt':'Tilt abajo','Dash Attack':'Ataque en carrera',
 'Forward Smash':'Smash lateral','Up Smash':'Smash arriba','Down Smash':'Smash abajo',
 'Neutral Air':'Aéreo neutral','Forward Air':'Aéreo frontal','Back Air':'Aéreo atrás','Up Air':'Aéreo arriba','Down Air':'Aéreo abajo',
 'Up B':'Especial arriba','Neutral B':'Especial neutral','Side B':'Especial lateral','Down B':'Especial abajo',
 'Grab':'Agarre',
}
GROUND=set(list(LABELS)[:11]) - {'Jab 2','Jab 3'} # Follow-ups cannot start from neutral.
# Composite start.gg identities cannot be assigned a single form's technical facts.
OMITTED={'pokemon_trainer':'Tres luchadores; la selección no distingue la forma.',
         'pyra':'Pyra/Mythra comparten ID; la selección no distingue la forma.'}


class NumericParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.stack=[];self.rows=[];self.oos=[];self.row=None
    def handle_starttag(self,tag,attrs):
        if tag!='div':return
        cls=dict(attrs).get('class','').split();self.stack.append((cls,[]))
        if 'movecontainer' in cls:self.row={}
    def handle_data(self,data):
        # Only collect the requested factual cells. Never collect source notes/prose.
        for classes,parts in self.stack:
            if set(classes)&{'movename','startup','basedamage','advantage','oos1','oos2','oos3'}:parts.append(data)
    def handle_endtag(self,tag):
        if tag!='div' or not self.stack:return
        cls,parts=self.stack.pop();value=' '.join(' '.join(parts).split())
        for key in ('movename','startup','basedamage','advantage'):
            if key in cls and self.row is not None:self.row[key]=value
        if any(c in cls for c in ('oos1','oos2','oos3')):self.oos.append(value)
        if 'movecontainer' in cls:
            if self.row:self.rows.append(self.row)
            self.row=None


def single(value, *, decimal=False, negative=False):
    pattern=r'-[0-9]+' if negative else r'[0-9]+(?:\.[0-9]+)?' if decimal else r'[0-9]+'
    value=str(value or '').strip().replace('−','-')
    if not re.fullmatch(pattern,value):return None
    n=float(value) if decimal else int(value)
    return n if (-200<=n<0 if negative else 0<n<=200) else None


def parse(html):
    p=NumericParser();p.feed(html)
    fastest=[];unsafe=[]
    for index,row in enumerate(p.rows):
        key=row.get('movename');label=LABELS.get(key)
        if not label:continue # Conditional, charged, multistate or bespoke moves not guessed.
        frame=single(row.get('startup'));damage=single(row.get('basedamage'),decimal=True)
        if key in GROUND and frame is not None and damage is not None:
            fastest.append((frame,index,dict(name=label,frame=frame,damage=damage)))
        adv=single(row.get('advantage'),negative=True)
        if adv is not None and key!='Grab':unsafe.append((adv,index,dict(name=label,onShield=adv)))
    oos=[]
    for row in p.oos:
        m=re.fullmatch(r'Out of Shield, (.+?)\s*[—–]\s*(\d+) frames?',row)
        if not m:continue
        frame=single(m[2]); names=re.split(r' or |, (?!Air$)',m[1])
        if frame is None:continue
        # A tied rank can name several independent options with the same timing.
        for key in names:
            air=bool(re.search(r'(?:, Air|\s*\(Air\))$',key,re.I))
            key=re.sub(r'(?:, Air|\s*\(Air\))$','',key,flags=re.I)
            key=next((candidate for candidate in LABELS if candidate.lower()==key.lower()),None)
            if key is None:continue
            label=LABELS[key]+(' aéreo' if air else '')
            if not any(x['name']==label for x in oos):oos.append(dict(name=label,frame=frame))
    oos.sort(key=lambda x:(x['frame'],x['name']))
    fastest.sort(key=lambda x:(x[0],x[1]));unsafe.sort(key=lambda x:(x[0],x[1]))
    return dict(fastest=fastest[0][2] if fastest else None,oos=oos[:3],punishable=[r[2] for r in unsafe[:3]])


class Snapshot:
    def __init__(self,cache,*,capture=False,clock=time.monotonic,sleep=time.sleep,opener=urllib.request.urlopen):
        self.cache=Path(cache).resolve();self.capture=capture;self.clock=clock;self.sleep=sleep;self.opener=opener;self.last=None;self.requests=0
        if self.cache==ROOT or ROOT in self.cache.parents:raise ValueError('HTML cache must stay outside the repository.')
        self.cache.mkdir(parents=True,exist_ok=True)
        self.robot=None
    def get(self,path,cache_name):
        target=self.cache/cache_name
        if target.exists():return target.read_bytes()
        if not self.capture:raise ValueError('Missing cached page. Capture must be explicitly enabled.')
        if path!='/robots.txt' and (self.robot is None or not self.robot.can_fetch(AGENT,ORIGIN+path)):raise ValueError('robots.txt disallows capture.')
        if self.last is not None:self.sleep(max(0,1-(self.clock()-self.last)))
        self.last=self.clock();self.requests+=1
        req=urllib.request.Request(ORIGIN+path,headers={'User-Agent':AGENT})
        with self.opener(req,timeout=20) as response:
            if urllib.parse.urlsplit(response.geturl()).hostname!='ultimateframedata.com':raise ValueError('Unexpected redirect.')
            body=response.read(2*1024*1024+1)
        if len(body)>2*1024*1024:raise ValueError('Page ceiling.')
        # Private scratch only; no source HTML is committed or deployed.
        import os
        fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as out:out.write(body)
        return body
    def run(self,slugs):
        robots=self.get('/robots.txt','robots.txt').decode();self.robot=urllib.robotparser.RobotFileParser();self.robot.parse(robots.splitlines())
        facts={};sources={};failed=self.cache/'failures.json';failures=json.loads(failed.read_text()) if failed.exists() else {}
        omissions=dict(OMITTED)
        for slug in sorted(slugs):
            if slug in OMITTED:continue
            if slug in failures:omissions[slug]='Página no disponible durante la captura; sin reintento automático.';continue
            if not re.fullmatch('[a-z_]+',slug):raise ValueError('Unexpected character slug.')
            path='/'+('hero' if slug=='dq_hero' else slug)
            if not self.robot.can_fetch(AGENT,ORIGIN+path):raise ValueError('robots.txt disallows cached source.')
            try:body=self.get(path,slug+'.html')
            except (urllib.error.URLError,TimeoutError):
                failures[slug]='unavailable_at_capture';failed.write_text(json.dumps(failures))
                omissions[slug]='Página no disponible durante la captura; sin reintento automático.'
                if len(failures)>=3:raise ValueError('Three source failures: capture stopped, private cache retained.')
                continue
            sheet=parse(body.decode('utf-8'));facts[slug]=sheet
            sources[slug]=dict(url=ORIGIN+path,sha256=hashlib.sha256(body).hexdigest())
        return dict(schemaVersion=1,source=dict(name='Ultimate Frame Data',url=ORIGIN+'/smash',gameVersion=None,
                    capturedAt=datetime.fromtimestamp(max((self.cache/(slug+'.html')).stat().st_mtime for slug in facts),timezone.utc).isoformat(),robotsSha256=hashlib.sha256(robots.encode()).hexdigest()),
                    policy='unambiguous-default-numerics-v1',characters=facts,sources=sources,omitted=omissions)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cache',type=Path,required=True);p.add_argument('--capture',action='store_true');a=p.parse_args()
    text=(ROOT/'ranking-smash-ultimate/characters.js').read_text();slugs=re.findall(r'"slug": "([a-z_]+)"',text)
    if not 80<=len(slugs)<=100:raise ValueError('Unexpected catalog size.')
    snapshot=Snapshot(a.cache,capture=a.capture);start=time.monotonic();data=snapshot.run(slugs)
    out=ROOT/'ranking-smash-ultimate/data/frame-facts-v1.json'
    import tempfile,os
    fd,temp=tempfile.mkstemp(prefix='.frame-facts-',dir=out.parent)
    try:
        with os.fdopen(fd,'w') as stream:stream.write(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
        os.replace(temp,out)
    finally:Path(temp).unlink(missing_ok=True)
    print(json.dumps(dict(characters=len(data['characters']),omitted=len(data['omitted']),requests=snapshot.requests,seconds=round(time.monotonic()-start,3),bytes=out.stat().st_size)))
if __name__=='__main__':main()
