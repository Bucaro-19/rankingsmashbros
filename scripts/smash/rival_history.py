"""Public tournament roster/history for analysis only. Never a national capture.

Thirty API attempts / 120 s per batch, including retries, one request/second via Client.
State resumes completed pages; missing/unpublished registrations are never called zero.
"""
from datetime import datetime, timezone
from pathlib import Path
import copy
import json
import re
import time

from collect import APIError, Client
from discover import season_timestamp
from organizer_small import BudgetClient, MAX_ATTEMPTS, MAX_SECONDS

META = '''query($slug:String!){tournament(slug:$slug){id name slug countryCode startAt endAt timezone events{id name slug type numEntrants startAt isOnline videogame{id name}}}}'''
ENTRANTS = '''query($id:ID!,$page:Int!){event(id:$id){entrants(query:{page:$page,perPage:50}){pageInfo{total totalPages}nodes{participants{player{id gamerTag user{slug location{country}}}}}}}}'''
REGISTRATIONS = '''query($slug:String!,$page:Int!){tournament(slug:$slug){participants(query:{page:$page,perPage:50}){pageInfo{total totalPages}nodes{events{id}player{id gamerTag user{slug location{country}}}}}}}'''
HISTORY = '''query($id:ID!,$page:Int!){player(id:$id){sets(page:$page,perPage:5,filters:{entrantSize:[1],state:[3]}){pageInfo{total totalPages}nodes{
 id state winnerId updatedAt completedAt displayScore
 event{id name slug numEntrants startAt isOnline type videogame{id name} tournament{id name slug countryCode}}
 slots{entrant{id name participants{player{id gamerTag user{slug location{country}}}}} stats{score{value}}}
 games{id orderNum winnerId entrant1Score entrant2Score stage{id} selections{entrant{id} character{id name}}}
}}}}'''
MAX_PLAYERS = 1000
MAX_BYTES = 32*1024*1024


def connection(conn):
    if not isinstance(conn, dict) or not isinstance(conn.get('nodes'), list):
        raise APIError('Roster/history unavailable; not a zero.')
    info = conn.get('pageInfo') or {}
    if any(type(info.get(k)) is not int or info[k] < 0 for k in ('total','totalPages')):
        raise APIError('Pagination unavailable.')
    return info


def roster(client, slug):
    if not re.fullmatch('[a-zA-Z0-9_-]+', slug): raise ValueError('Invalid tournament slug.')
    b = BudgetClient(client)
    t = b.query(META, {'slug':slug}).get('tournament')
    if not t or t['slug'] != 'tournament/'+slug: raise APIError('Tournament not found.')
    candidates = [e for e in t['events'] if str((e.get('videogame') or {}).get('id'))=='1386' and e['type']==1]
    if len(candidates)!=1: raise APIError('Ambiguous Ultimate singles events: owner must choose.')
    e=candidates[0]; players={}; count=0
    for page in range(1,MAX_PLAYERS//50+1):
        conn=b.query(ENTRANTS,dict(id=e['id'],page=page))['event']['entrants']; info=connection(conn)
        for en in conn['nodes']:
            people=en.get('participants') or []
            if len(people)!=1 or not people[0].get('player'): raise APIError('Singles registration without unique player.')
            p=people[0]['player']; players[str(p['id'])]=p;count+=1
        if page>=info['totalPages']: break
    if count!=info['total'] or count>MAX_PLAYERS: raise APIError('Incomplete roster or ceiling.')
    source='entrants'
    if not count:
        source='participants.events'; total=0; selected=0
        for page in range(1,MAX_PLAYERS//50+1):
            conn=b.query(REGISTRATIONS,dict(slug=slug,page=page))['tournament']['participants']; info=connection(conn)
            total+=len(conn['nodes'])
            for en in conn['nodes']:
                if not any(str(x['id'])==str(e['id']) for x in en.get('events') or []): continue
                p=en.get('player')
                if not p: raise APIError('Registration without player.')
                selected+=1;players[str(p['id'])]=p
            if page>=info['totalPages']: break
        if total!=info['total'] or total>MAX_PLAYERS: raise APIError('Incomplete registrations.')
        count=selected
    if not count or count!=len(players): raise APIError('registrations_unavailable: no verifiable public singles roster; not zero registrants.')
    return dict(schemaVersion=1,kind='analysis_roster',capturedAt=datetime.now(timezone.utc).isoformat(),
                tournament=t,event=e,source=source,players=players,registrations=count)


def new_state(roster_data, known, year):
    if roster_data.get('kind')!='analysis_roster' or not roster_data.get('players'): raise ValueError('Missing verified roster.')
    ids=set(roster_data['players']); known=sorted(ids & set(map(str,known)),key=int)
    return dict(stateVersion=1,roster=copy.deepcopy(roster_data),seasonYear=year,knownPlayerIds=known,
                coverage={pid:dict(nextPage=1,totalPages=None,complete=False) for pid in sorted(ids-set(known),key=int)},pages={})


def capture_batch(client, state, *, clock=time.monotonic):
    state=copy.deepcopy(state)
    if state.get('stateVersion')!=1 or not 2000<=state['seasonYear']<=2100: raise ValueError('Invalid state.')
    start=season_timestamp(f"{state['seasonYear']}-01-01");end=season_timestamp(f"{state['seasonYear']+1}-01-01")
    b=BudgetClient(client,clock);started=clock();before=client.calls; chosen={str(m['id']):m for page in state['pages'].values() for m in page['sets']}; touched=[]
    for pid,cov in state['coverage'].items():
        while not cov['complete']:
            if client.calls-before+3>MAX_ATTEMPTS or clock()-started>=MAX_SECONDS: break
            page=cov['nextPage']; key=f'{pid}:{page}'
            conn=(b.query(HISTORY,dict(id=pid,page=page)).get('player') or {}).get('sets'); info=connection(conn)
            rows=[]
            for m in conn['nodes']:
                ev=m.get('event') or {}; at=ev.get('startAt')
                if str((ev.get('videogame') or {}).get('id'))!='1386' or ev.get('type')!=1 or type(at) is not int or not start<=at<end: continue
                if m.get('state')!=3: raise APIError('Completed history changed.')
                rows.append(m);chosen[str(m['id'])]=m
            state['pages'][key]=dict(sets=rows,totalPages=info['totalPages'])
            cov.update(nextPage=page+1,totalPages=info['totalPages'],complete=page>=info['totalPages'])
            touched.append(pid)
        if client.calls-before+3>MAX_ATTEMPTS or clock()-started>=MAX_SECONDS: break
    if clock()-started>MAX_SECONDS: raise APIError('Capture time ceiling; retain previous state.')
    captured=datetime.now(timezone.utc).isoformat()
    data=dict(kind='analysis_history',schemaVersion=1,capturedAt=captured,seasonYear=state['seasonYear'],
        roster=state['roster'],sets=chosen,coverage=state['coverage'],
        audit=dict(requests=client.calls-before,seconds=round(clock()-started,3),playersQueried=len(set(touched)),
                   registered=len(state['roster']['players']),known=len(state['knownPlayerIds']),missing=len(state['coverage']),
                   complete=sum(x['complete'] for x in state['coverage'].values()),sets=len(chosen)))
    if len(json.dumps(state).encode())>MAX_BYTES: raise APIError('State ceiling; retain previous checkpoint.')
    return data,state


def save(path, value, *, replace=False):
    path=Path(path)
    root=Path(__file__).resolve().parents[2]
    if path.suffix!='.json' or path.is_symlink() or (path.exists() and not replace): raise ValueError('Private JSON output required; refusing overwrite.')
    if path.resolve()==root or root in path.resolve().parents: raise ValueError('Analysis captures must stay outside the repository/publication tree.')
    path.parent.mkdir(parents=True,exist_ok=True)
    body=json.dumps(value,ensure_ascii=False).encode()
    if len(body)>MAX_BYTES: raise ValueError('File ceiling.')
    import tempfile,os
    fd,name=tempfile.mkstemp(prefix='.analysis-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as out:out.write(body)
        Path(name).replace(path)
    finally:Path(name).unlink(missing_ok=True)
