"""Public upcoming GT Ultimate agenda. Independent of ranking and SQL; env secrets only."""
import argparse
from datetime import datetime, timezone, timedelta
import ftplib
import io
import json
import math
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from collect import APIError, Client

SCHEMA_VERSION = 1
GAME_ID = '1386'
PER_PAGE = 5
MAX_PAGES = 40
EVENT_LIMIT = 50
MAX_BYTES = 512 * 1024
MAX_AGE = timedelta(hours=48)
DEFAULT_OUTPUT = Path(__file__).resolve().parents[2] / 'ranking-smash-ultimate/data/agenda.json'
# Checked by authenticated introspection on 8/oct/2026 (see AGENDA-TORNEOS.md).
QUERY = '''query Agenda($page:Int!,$after:Timestamp!){
 tournaments(query:{page:$page,perPage:5,sortBy:"startAt asc",filter:{
  countryCode:"GT",videogameIds:[1386],upcoming:true,afterDate:$after,
  published:true,publiclySearchable:true}}){
  pageInfo{total totalPages}
  nodes{id name slug url(relative:false) countryCode startAt endAt timezone
   city addrState venueName venueAddress lat lng isOnline isRegistrationOpen
   registrationClosesAt eventRegistrationClosesAt numAttendees
   events(limit:50,filter:{videogameId:[1386],published:true}){
    id name slug startAt type isOnline numEntrants videogame{id}
    teamRosterSize{minPlayers maxPlayers}
   }
  }
 }
}'''
ROOT_KEYS = {'schemaVersion','generatedAt','requests','coverage','tournaments'}
COVERAGE_KEYS = {'countryCode','videogameId','complete','pagesFetched','rawTournaments'}
TOURNAMENT_KEYS = {'id','name','slug','url','countryCode','startAt','endAt','timezone','city',
                   'department','venueName','venueAddress','latitude','longitude','isOnline',
                   'attendanceType','isRegistrationOpen','registrationClosesAt','eventRegistrationClosesAt',
                   'numAttendees','isOfflineSingles','events'}
EVENT_KEYS = {'id','name','slug','url','videogameId','startAt','type','competitionType','isOnline',
              'numEntrants','teamRosterSize','isOfflineSingles'}


def require(condition, message='Agenda inválida; se conserva el archivo anterior.'):
    if not condition: raise ValueError(message)


def utc_now(): return datetime.now(timezone.utc)


def aware(value):
    require(isinstance(value,str) and len(value)<64)
    try: at=datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError: raise ValueError('Fecha inválida en agenda.') from None
    require(at.tzinfo is not None,'Las fechas de agenda requieren zona horaria.')
    return at


def identifier(value):
    require(type(value) in (str,int) and re.fullmatch(r'[1-9][0-9]{0,19}',str(value)) is not None)
    return str(value)


def text(value, limit=500):
    if value is None: return None
    require(isinstance(value,str) and len(value)<=limit and not any(ord(c)<32 for c in value))
    return value.strip() or None


def zone(value):
    value=text(value,100)
    if value is None: return None
    try: ZoneInfo(value)
    except (ZoneInfoNotFoundError,ValueError): raise ValueError('Zona horaria no reconocida; no se inventa.') from None
    return value


def timestamp(value, tz):
    if value in (None,0) and type(value) is not bool: return None
    require(type(value) is int and value>0)
    try: return datetime.fromtimestamp(value,timezone.utc).astimezone(ZoneInfo(tz) if tz else timezone.utc).isoformat()
    except (ValueError,OverflowError,OSError): raise ValueError('Timestamp inválido en agenda.') from None


def count(value):
    require(value is None or (type(value) is int and value>=0))
    return value


def boolean(value):
    require(value is None or type(value) is bool)
    return value


def coordinate(value, maximum):
    require(value is None or (type(value) in (int,float) and math.isfinite(value) and -maximum<=value<=maximum))
    return value


def link(slug, supplied=None, *, event=False):
    if slug is not None:
        expression=r'tournament/[A-Za-z0-9_-]+'+(r'/event/[A-Za-z0-9_-]+' if event else '')
        require(re.fullmatch(expression,slug) is not None,'Slug de start.gg inválido.')
    url=supplied if supplied is not None else ('https://www.start.gg/'+slug if slug else None)
    if url is not None:
        require(isinstance(url,str) and len(url)<=1000)
        p=urlsplit(url)
        require(p.scheme=='https' and p.hostname in ('start.gg','www.start.gg') and p.port in (None,443)
                and not p.username and not p.password and not p.query and not p.fragment)
        require(slug is not None and p.path.rstrip('/')=='/'+slug,'URL ajena al slug del torneo/evento.')
    return url


def competition(event_type, roster):
    # Same singles value already used by discover.py; never infer from an event's name.
    if event_type==1: return 'singles'
    if roster and roster['minPlayers']==roster['maxPlayers'] and roster['minPlayers'] is not None:
        size=roster['minPlayers']
        if size==2: return 'doubles'
        if size>2: return 'teams'
    return None


def candidate(kind, online):
    if online is True or kind in ('doubles','teams'): return False
    if online is False and kind=='singles': return True
    return None


def aggregate_candidate(events):
    values=[e['isOfflineSingles'] for e in events]
    return True if True in values else None if None in values else False


def attendance(events):
    values={e['isOnline'] for e in events}
    if True in values and False in values: return 'mixed'
    if values=={True}: return 'online'
    if values=={False}: return 'offline'
    return None


def normalize(row):
    require(isinstance(row,dict) and row.get('countryCode')=='GT','Respuesta fuera del filtro Guatemala.')
    tz=zone(row.get('timezone')); start=timestamp(row.get('startAt'),tz)
    require(start is not None,'Sin inicio no se puede comprobar que un torneo sea futuro.')
    raw_events=row.get('events')
    require(isinstance(raw_events,list) and 0<len(raw_events)<EVENT_LIMIT,'Eventos incompletos o límite alcanzado; no publicar parcialmente.')
    events=[]
    for e in raw_events:
        require(isinstance(e,dict) and str((e.get('videogame') or {}).get('id'))==GAME_ID,'Evento ajeno a Ultimate.')
        roster=e.get('teamRosterSize')
        if roster is not None:
            require(isinstance(roster,dict))
            roster={key:count(roster.get(key)) for key in ('minPlayers','maxPlayers')}
            require(not all(v is not None for v in roster.values()) or roster['minPlayers']<=roster['maxPlayers'])
        event_type=count(e.get('type')); kind=competition(event_type,roster); online=boolean(e.get('isOnline'))
        slug=text(e.get('slug'))
        events.append(dict(id=identifier(e.get('id')),name=text(e.get('name')),slug=slug,
                           url=link(slug,event=True),videogameId=GAME_ID,startAt=timestamp(e.get('startAt'),tz),
                           type=event_type,competitionType=kind,isOnline=online,numEntrants=count(e.get('numEntrants')),
                           teamRosterSize=roster,isOfflineSingles=candidate(kind,online)))
    events.sort(key=lambda e:e['id'])
    slug=text(row.get('slug')); lat=coordinate(row.get('lat'),90); lng=coordinate(row.get('lng'),180)
    # (0,0) is not a Guatemala venue; the API sometimes uses it as an unset pair.
    if lat==0 and lng==0: lat=lng=None
    return dict(id=identifier(row.get('id')),name=text(row.get('name')),slug=slug,url=link(slug,row.get('url')),
                countryCode='GT',startAt=start,endAt=timestamp(row.get('endAt'),tz),timezone=tz,
                city=text(row.get('city')),department=text(row.get('addrState')),venueName=text(row.get('venueName')),
                venueAddress=text(row.get('venueAddress'),2000),latitude=lat,longitude=lng,
                isOnline=boolean(row.get('isOnline')),attendanceType=attendance(events),
                isRegistrationOpen=boolean(row.get('isRegistrationOpen')),
                registrationClosesAt=timestamp(row.get('registrationClosesAt'),tz),
                eventRegistrationClosesAt=timestamp(row.get('eventRegistrationClosesAt'),tz),
                numAttendees=count(row.get('numAttendees')),isOfflineSingles=aggregate_candidate(events),events=events)


def encode(data):
    return (json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf-8')


def validate(data, *, now=None, fresh=False):
    now=now or utc_now(); require(now.tzinfo is not None)
    require(isinstance(data,dict) and set(data)==ROOT_KEYS and type(data['schemaVersion']) is int and data['schemaVersion']==SCHEMA_VERSION)
    generated=aware(data['generatedAt']); require(generated<=now+timedelta(seconds=60))
    if fresh: require(now-generated<=MAX_AGE,'Agenda de más de 48 horas; capturar de nuevo antes de publicar.')
    require(type(data['requests']) is int and 1<=data['requests']<=MAX_PAGES*3)
    cov=data['coverage']; require(isinstance(cov,dict) and set(cov)==COVERAGE_KEYS and cov['complete'] is True
                                and cov['countryCode']=='GT' and cov['videogameId']==GAME_ID)
    require(type(cov['pagesFetched']) is int and 1<=cov['pagesFetched']<=MAX_PAGES)
    require(type(cov['rawTournaments']) is int and 0<=cov['rawTournaments']<=MAX_PAGES*PER_PAGE)
    tournaments=data['tournaments'];require(isinstance(tournaments,list) and len(tournaments)<=cov['rawTournaments'])
    tournament_ids=set();event_ids=set();order=[]
    for t in tournaments:
        require(isinstance(t,dict) and set(t)==TOURNAMENT_KEYS and t['countryCode']=='GT')
        require(t['id']==identifier(t['id']) and t['id'] not in tournament_ids);tournament_ids.add(t['id'])
        tz=zone(t['timezone']);start=aware(t['startAt']);require(start>now,'Un torneo ya empezado no puede publicarse como próximo.')
        if tz is not None: require(start.utcoffset()==start.astimezone(ZoneInfo(tz)).utcoffset())
        for key in ('endAt','registrationClosesAt','eventRegistrationClosesAt'):
            if t[key] is not None:
                value=aware(t[key])
                if tz is not None:require(value.utcoffset()==value.astimezone(ZoneInfo(tz)).utcoffset())
                if key=='endAt':require(value>=start,'El fin del torneo precede a su inicio.')
        for key in ('name','slug','city','department','venueName'):require(t[key]==text(t[key]))
        require(t['venueAddress']==text(t['venueAddress'],2000))
        link(t['slug'],t['url']);coordinate(t['latitude'],90);coordinate(t['longitude'],180)
        boolean(t['isOnline']);boolean(t['isRegistrationOpen']);count(t['numAttendees'])
        require(isinstance(t['events'],list) and 0<len(t['events'])<EVENT_LIMIT)
        for e in t['events']:
            require(isinstance(e,dict) and set(e)==EVENT_KEYS and e['videogameId']==GAME_ID)
            require(e['id']==identifier(e['id']) and e['id'] not in event_ids);event_ids.add(e['id'])
            require(e['name']==text(e['name']) and e['slug']==text(e['slug']))
            link(e['slug'],e['url'],event=True)
            if e['startAt'] is not None: aware(e['startAt'])
            count(e['type']);count(e['numEntrants']);boolean(e['isOnline'])
            roster=e['teamRosterSize']
            if roster is not None:
                require(isinstance(roster,dict) and set(roster)=={'minPlayers','maxPlayers'})
                for val in roster.values():count(val)
                require(not all(v is not None for v in roster.values()) or roster['minPlayers']<=roster['maxPlayers'])
            require(e['competitionType']==competition(e['type'],roster))
            require(e['isOfflineSingles'] is candidate(e['competitionType'],e['isOnline']))
        require(t['isOfflineSingles'] is aggregate_candidate(t['events']) and t['attendanceType']==attendance(t['events']))
        order.append((start,t['id']))
    require(order==sorted(order),'La agenda debe estar ordenada por inicio e ID.')
    require(len(encode(data))<=MAX_BYTES,'Agenda demasiado grande; se conserva la anterior.')
    return data


def capture(client, *, now=None, clock=utc_now):
    cutoff=now or clock();require(cutoff.tzinfo is not None)
    calls_before=client.calls;rows=[];expected=None;seen=set()
    for page in range(1,MAX_PAGES+1):
        data=client.query(QUERY,dict(page=page,after=int(cutoff.timestamp())))
        con=data.get('tournaments');require(isinstance(con,dict),'Conexión de torneos ausente; no equivale a agenda vacía.')
        info=con.get('pageInfo');require(isinstance(info,dict))
        total,pages=info.get('total'),info.get('totalPages')
        require(type(total) is int and total>=0 and type(pages) is int and pages>=0)
        require(pages<=MAX_PAGES and total<=MAX_PAGES*PER_PAGE,'Límite de captura alcanzado; no se publica parcialmente.')
        require((total,pages)==expected if expected else True,'La paginación cambió durante la captura.')
        expected=(total,pages)
        nodes=con.get('nodes');require(isinstance(nodes,list) and len(nodes)<=PER_PAGE)
        for row in nodes:
            require(isinstance(row,dict));tid=identifier(row.get('id'))
            require(tid not in seen,'Torneo duplicado entre páginas; no se publica parcialmente.')
            seen.add(tid);rows.append(row)
        if page>=pages:break
    require(len(rows)==expected[0] and (expected[0]!=0 or expected[1] in (0,1)), 'Conteo incompleto en agenda.')
    generated=now or clock();tournaments=[normalize(r) for r in rows]
    # Events may begin while pages are read; never publish them as upcoming.
    tournaments=[t for t in tournaments if aware(t['startAt'])>generated]
    tournaments.sort(key=lambda t:(aware(t['startAt']),t['id']))
    result=dict(schemaVersion=SCHEMA_VERSION,generatedAt=generated.isoformat(),requests=client.calls-calls_before,
                coverage=dict(countryCode='GT',videogameId=GAME_ID,complete=True,pagesFetched=page,rawTournaments=len(rows)),
                tournaments=tournaments)
    return validate(result,now=generated,fresh=True)


def load(path):
    with Path(path).open('rb') as stream: body=stream.read(MAX_BYTES+1)
    require(len(body)<=MAX_BYTES,'Agenda demasiado grande.')
    return json.loads(body)


def save(path,data):
    body=encode(data);require(len(body)<=MAX_BYTES)
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);name=None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent,prefix='.'+path.name+'-',suffix='.tmp',delete=False) as f:
            name=f.name;f.write(body)
        Path(name).replace(path)
    finally:
        if name:Path(name).unlink(missing_ok=True)


def publish(ftp,data, *, remote='.', clock=utc_now):
    validate(data,now=clock(),fresh=True)
    require(isinstance(remote,str) and re.fullmatch(r'\.|[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)*',remote) is not None
            and '..' not in remote.split('/'),'SMASH_FTP_DIR inválido.')
    if remote!='.':ftp.cwd(remote)
    try:ftp.cwd('data')
    except ftplib.error_perm as error:
        if not str(error).startswith('550'):raise
        ftp.mkd('data');ftp.cwd('data')
    if not data['tournaments']:
        # A complete empty response is valid, but must not silently erase future announcements.
        buffer=io.BytesIO()
        def receive(chunk):
            require(buffer.tell()+len(chunk)<=MAX_BYTES,'Agenda remota demasiado grande.')
            buffer.write(chunk)
        try:ftp.retrbinary('RETR agenda.json',receive)
        except ftplib.error_perm as error:
            if not str(error).startswith('550'):raise
        else:
            prior=json.loads(buffer.getvalue())
            require(isinstance(prior,dict) and isinstance(prior.get('tournaments'),list))
            require(not any(aware(t['startAt'])>clock() for t in prior['tournaments']),
                    'Captura vacía frente a anuncios futuros vigentes: conservar y revisar.')
    body=encode(data);temporary='agenda.json.'+uuid.uuid4().hex+'.tmp'
    try:
        ftp.storbinary('STOR '+temporary,io.BytesIO(body))
        validate(data,now=clock(),fresh=True)  # also protects a start reached during upload
        ftp.rename(temporary,'agenda.json')
    except Exception:
        try:ftp.delete(temporary)
        except ftplib.all_errors:pass
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    grab=commands.add_parser('capture');grab.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    check=commands.add_parser('validate');check.add_argument('path',type=Path)
    send=commands.add_parser('publish');send.add_argument('path',type=Path);send.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    try:
        if args.command=='capture':
            token=os.environ.get('STARTGG_TOKEN','').strip();require(bool(token),'Falta STARTGG_TOKEN en entorno privado.')
            data=capture(Client(token));save(args.output,data)
            print(json.dumps(dict(tournaments=len(data['tournaments']),requests=data['requests'],generatedAt=data['generatedAt'],bytes=len(encode(data)))))
        else:
            data=validate(load(args.path),fresh=True)
            if args.command=='publish' and args.apply:
                require(all(os.environ.get(k) for k in ('FTP_SERVER','FTP_USERNAME','FTP_PASSWORD')),'Faltan secretos FTP.')
                with ftplib.FTP(timeout=45) as ftp:
                    ftp.connect(os.environ['FTP_SERVER'],21);ftp.login(os.environ['FTP_USERNAME'],os.environ['FTP_PASSWORD'])
                    publish(ftp,data,remote=os.environ.get('SMASH_FTP_DIR') or 'ranking-smash-ultimate');ftp.quit()
                print('Solo data/agenda.json publicado; ranking y SQL intactos.')
            else:print('Agenda válida; sin publicación FTP (publish requiere --apply).')
    except (APIError,ValueError,TypeError,KeyError,OverflowError,OSError,ftplib.Error,EOFError) as error:
        # Never echo a server response, filename, token or FTP credential.
        parser.exit(1, ('Captura/publicación detenida: '+str(error) if isinstance(error,(APIError,ValueError)) else 'Captura/publicación detenida: '+type(error).__name__)+'. No se sustituye el archivo anterior.\n')


if __name__=='__main__':main()
