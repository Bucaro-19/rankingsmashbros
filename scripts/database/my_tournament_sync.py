"""Bounded private tournament bracket. Stdlib only, no SQL and no ranking publisher."""
import argparse
from datetime import datetime,timezone
import json,os,re,sys,time
from pathlib import Path
from zoneinfo import ZoneInfo
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'smash'))
from collect import Client,APIError
from organizer_small import BudgetClient
from publish_sql import request,encode_transport,SyncStopped

VERSION=1
POLICIES={1687524:dict(tournamentId='942547',country='SV',start=1792857600,end=1792987200,timezone='America/El_Salvador')}
AUTH_UNTIL=1792994400 # 26/oct/2026 06:00 UTC, end of 25/oct GT.
MAX_BATCHES=2
MAX_RAW=8*1024*1024
PER_PAGE=24
ENTRANTS='entrants(query:{page:$page,perPage:50}){pageInfo{total totalPages}nodes{id name initialSeedNum participants{player{id gamerTag}}}}'
META='query($id:ID!,$page:Int!){event(id:$id){id name slug startAt type isOnline videogame{id} tournament{id name countryCode startAt endAt timezone} phases{id name phaseOrder} phaseGroups{id displayIdentifier state bracketType startAt firstRoundTime phase{id name phaseOrder} wave{startAt}} '+ENTRANTS+'}}'
ROSTER='query($id:ID!,$page:Int!){event(id:$id){id '+ENTRANTS+'}}'
GROUP='''id seeds(query:{page:$page,perPage:24}){pageInfo{total totalPages}nodes{id seedNum groupSeedNum isBye entrant{id}}} sets(page:$page,perPage:24,sortType:STANDARD){pageInfo{total totalPages}nodes{id round fullRoundText startAt state winnerId slots(includeByes:true){entrant{id} seed{id} prereqId prereqType prereqPlacement}}}'''


def require(value):
    if not value:raise ValueError('bracket_source_invalid')


def identifier(value,opaque=False):
    require(type(value) in (str,int))
    value=str(value);require(re.fullmatch(r'[A-Za-z0-9_-]{1,100}' if opaque else r'[1-9][0-9]{0,19}',value) is not None);return value


def text(value,limit=255,nullable=False):
    if value is None and nullable:return None
    require(isinstance(value,str) and len(value)<=limit and not any(ord(c)<32 for c in value));return value


def number(value,minimum=0,nullable=False):
    if value is None and nullable:return None
    require(type(value) is int and value>=minimum);return value


def seed_number(value):
    return None if value is None or (type(value) is int and value==0) else number(value,1)


def stamp(value):
    if value is None or value==0:return None
    return number(value,1)


def page(conn):
    if conn is None:return None
    require(isinstance(conn,dict));nodes=conn.get('nodes');info=conn.get('pageInfo')
    require(nodes is None or isinstance(nodes,list));require(info is None or isinstance(info,dict))
    if nodes is None or info is None or info.get('total') is None or info.get('totalPages') is None:return None
    total=number(info['total']);pages=number(info['totalPages'])
    require(total<=5000 and pages<=500)
    return nodes,total,pages


class Budget:
    def __init__(self,client,clock=time.monotonic):
        self.client=client;self.clock=clock;self.batches=1;self.current=BudgetClient(client,clock)
    def query(self,q,v):
        if self.client.calls-self.current.initial+3>30:
            require(self.batches<MAX_BATCHES);self.batches+=1;self.current=BudgetClient(self.client,self.clock)
        result=self.current.query(q,v)
        require(self.clock()-self.current.started<=120)
        return result


def schedule(event_id,now,manual):
    require(event_id in POLICIES);p=POLICIES[event_id]
    if now>=min(AUTH_UNTIL,p['end']):return 'ended'
    local=datetime.fromtimestamp(now,ZoneInfo(p['timezone']))
    start=datetime.fromtimestamp(p['start'],ZoneInfo(p['timezone'])).date()
    if manual or local.date()>=start:return 'due'
    return 'due' if local.hour%3==0 and local.minute==19 else 'not_due'


def capture(client,event_id,*,clock=time.monotonic):
    require(event_id in POLICIES);policy=POLICIES[event_id];b=Budget(client,clock);began=clock();initial=client.calls
    source=b.query(META,dict(id=event_id,page=1))['event'];t=source['tournament']
    require(identifier(source['id'])==str(event_id) and source['type']==1 and source['isOnline'] is False and identifier(source['videogame']['id'])=='1386')
    require(identifier(t['id'])==policy['tournamentId'] and t['countryCode']==policy['country'])
    tz=t.get('timezone')
    if tz is not None:ZoneInfo(tz)
    event=dict(id=str(event_id),tournamentId=identifier(t['id']),name=text(source['name']),tournamentName=text(t['name']),slug=text(source['slug']),country=text(t['countryCode'],2),startAt=stamp(source.get('startAt')),endAt=stamp(t.get('endAt')),timezone=tz)
    require(re.fullmatch(r'tournament/[A-Za-z0-9_-]+/event/[A-Za-z0-9_-]+',event['slug']) is not None)
    entrants={};registration='published';conn=source.get('entrants');expected=None
    for n in range(1,21):
        parsed=page(conn)
        if parsed is None or (n==1 and not parsed[0]):registration='unavailable';break
        nodes,total,pages=parsed;require(total<=1000 and pages<=20 and (expected is None or expected==(total,pages)));expected=(total,pages)
        for entry in nodes:
            eid=identifier(entry['id']);require(eid not in entrants)
            people=entry.get('participants');require(isinstance(people,list) and len(people)==1)
            player=people[0].get('player');pid=identifier(player['id']) if player else None
            tag=text(player['gamerTag'],100) if player else text(entry['name'],100)
            entrants[eid]=dict(id=eid,playerId=pid,tag=tag,initialSeed=seed_number(entry.get('initialSeedNum')))
        if n>=pages:break
        conn=b.query(ROSTER,dict(id=event_id,page=n+1))['event']['entrants']
    if registration=='published':require(len(entrants)==expected[0])
    else:entrants={}
    groups={}
    rawgroups=source.get('phaseGroups');require(rawgroups is None or isinstance(rawgroups,list))
    require(len(rawgroups or [])<=100)
    if registration=='published':
        for g in rawgroups or []:
            gid=identifier(g['id']);phase=g['phase'];require(gid not in groups)
            at=stamp(g.get('startAt'));time_source='pool' if at is not None else None
            if at is None:
                at=stamp((g.get('wave') or {}).get('startAt'));time_source='wave' if at is not None else None
            if at is None:
                at=stamp(g.get('firstRoundTime'));time_source='round' if at is not None else None
            groups[gid]=dict(id=gid,phaseId=identifier(phase['id']),phaseName=text(phase['name']),phaseOrder=number(phase.get('phaseOrder'),0,True),identifier=text(g.get('displayIdentifier'),100,True),state=number(g.get('state'),0,True),bracketType=text(g.get('bracketType'),100,True),startAt=at,timeSource=time_source,seeds=[],sets=[],dataAvailable=True,setsAvailable=True)
    tasks=[(gid,1) for gid in groups];counts={}
    while tasks:
        chunk=tasks[:3];tasks=tasks[3:];variables={};decl=[];parts=[]
        for i,(gid,n) in enumerate(chunk):
            decl+=['$id'+str(i)+':ID!','$page'+str(i)+':Int!'];variables.update({'id'+str(i):gid,'page'+str(i):n})
            parts.append('g'+str(i)+':phaseGroup(id:$id'+str(i)+'){'+GROUP.replace('$page','$page'+str(i))+'}')
        data=b.query('query('+','.join(decl)+'){'+''.join(parts)+'}',variables)
        for i,(gid,n) in enumerate(chunk):
            g=data.get('g'+str(i));require(isinstance(g,dict) and identifier(g['id'])==gid)
            seeds=page(g.get('seeds'));sets=page(g.get('sets'))
            if seeds is None:
                groups[gid].update(dataAvailable=False,seeds=[],sets=[],setsAvailable=False);continue
            if sets is None:groups[gid]['setsAvailable']=False;sets=([],0,0)
            seedrows,ns,np=seeds;setrows,ms,mp=sets
            if gid in counts:
                oldns,oldms,oldnp,oldmp=counts[gid]
                if n>oldnp:
                    require(not seedrows);ns,np=oldns,oldnp
                if n>oldmp:
                    require(not setrows);ms,mp=oldms,oldmp
                if counts[gid]!=(ns,ms,np,mp) and os.environ.get('GITHUB_EVENT_NAME')=='workflow_dispatch':
                    print(json.dumps(dict(status='pagination_changed',page=n,before=counts[gid],after=[ns,ms,np,mp])))
            require(gid not in counts or counts[gid]==(ns,ms,np,mp));counts[gid]=(ns,ms,np,mp)
            for seed in seedrows:
                en=identifier(seed['entrant']['id']) if seed.get('entrant') else None
                groups[gid]['seeds'].append(dict(id=identifier(seed['id']),entrantId=en,seed=seed_number(seed.get('seedNum')),groupSeed=seed_number(seed.get('groupSeedNum')),isBye=seed.get('isBye')))
            for match in setrows:
                slots=match.get('slots');require(isinstance(slots,list) and len(slots)<=2)
                groups[gid]['sets'].append(dict(id=identifier(match['id'],True),round=match.get('round'),roundText=text(match.get('fullRoundText'),255,True),startAt=stamp(match.get('startAt')),state=number(match.get('state'),0,True),winnerId=identifier(match['winnerId']) if type(match.get('winnerId')) is int and match['winnerId']>0 else None,
                    slots=[dict(index=j,entrantId=identifier(slot['entrant']['id']) if slot.get('entrant') else None,seedId=identifier(slot['seed']['id']) if slot.get('seed') else None,prereqId=identifier(slot['prereqId'],True) if slot.get('prereqId') else None,prereqType=text(slot.get('prereqType'),32,True),prereqPlacement=number(slot.get('prereqPlacement'),0,True)) for j,slot in enumerate(slots)]))
            if n<max(np,mp):tasks.append((gid,n+1))
    for gid,g in groups.items():
        if g['dataAvailable']:require(len(g['seeds'])==counts[gid][0] and len(g['sets'])==counts[gid][1])
    result=dict(schemaVersion=VERSION,kind='my_tournament_bracket',capturedAt=datetime.now(timezone.utc).isoformat(),event=event,registrationState=registration,entrants=list(entrants.values()),groups=list(groups.values()),audit=dict(requests=client.calls-initial,batches=b.batches,elapsedMilliseconds=round((clock()-began)*1000)))
    validate(result);return result


def keys(v,expected):
    require(isinstance(v,dict) and set(v)==set(expected.split()))


def validate(p):
    keys(p,'schemaVersion kind capturedAt event registrationState entrants groups audit')
    require(type(p['schemaVersion']) is int and p['schemaVersion']==1 and p['kind']=='my_tournament_bracket' and p['registrationState'] in ('published','unavailable'))
    require(isinstance(p['capturedAt'],str) and re.fullmatch(r'2026-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|\+00:00)',p['capturedAt']) is not None)
    when=datetime.fromisoformat(p['capturedAt'].replace('Z','+00:00'));require(when.tzinfo is not None)
    e=p['event'];keys(e,'id tournamentId name tournamentName slug country startAt endAt timezone');require(e['id']=='1687524' and e['tournamentId']=='942547' and e['country']=='SV' and e['slug']=='tournament/legends7/event/ultimate-singles')
    for k in ('name','tournamentName','slug'):text(e[k])
    for k in ('startAt','endAt'):number(e[k],1,True)
    text(e['timezone'],100,True)
    if e['timezone'] is not None:ZoneInfo(e['timezone'])
    require(isinstance(p['entrants'],list) and len(p['entrants'])<=1000 and isinstance(p['groups'],list) and len(p['groups'])<=100)
    if p['registrationState']=='unavailable':require(not p['entrants'] and not p['groups'])
    ens={};players=set();seeds=set();sets=set();groups=set()
    for en in p['entrants']:
        keys(en,'id playerId tag initialSeed');require(isinstance(en['id'],str) and identifier(en['id']) not in ens);ens[en['id']]=en;text(en['tag'],100);number(en['initialSeed'],1,True)
        if en['playerId'] is not None:require(isinstance(en['playerId'],str) and identifier(en['playerId']) not in players);players.add(en['playerId'])
    for g in p['groups']:
        keys(g,'id phaseId phaseName phaseOrder identifier state bracketType startAt timeSource seeds sets dataAvailable setsAvailable')
        require(identifier(g['id']) not in groups);groups.add(g['id']);identifier(g['phaseId']);text(g['phaseName']);text(g['identifier'],100,True);text(g['bracketType'],100,True)
        for k in ('phaseOrder','state'):number(g[k],0,True)
        number(g['startAt'],1,True);require(g['timeSource'] in (None,'pool','wave','round') and ((g['startAt'] is None)==(g['timeSource'] is None)))
        require(type(g['dataAvailable']) is bool and type(g['setsAvailable']) is bool and isinstance(g['seeds'],list) and isinstance(g['sets'],list))
        if not g['dataAvailable']:require(not g['seeds'] and not g['sets'])
        if not g['setsAvailable']:require(not g['sets'])
        members=set();local_seeds=set()
        for seed in g['seeds']:
            keys(seed,'id entrantId seed groupSeed isBye');require(identifier(seed['id']) not in seeds);seeds.add(seed['id']);local_seeds.add(seed['id'])
            require(seed['isBye'] is None or type(seed['isBye']) is bool)
            for k in ('seed','groupSeed'):number(seed[k],1,True)
            require(seed['entrantId'] is None or seed['entrantId'] in ens)
            if seed['entrantId'] is not None:members.add(seed['entrantId'])
        for match in g['sets']:
            keys(match,'id round roundText startAt state winnerId slots');require(identifier(match['id'],True) not in sets);sets.add(match['id']);require(match['winnerId'] is None or match['winnerId'] in members)
            number(match['round'],-2147483648,True);number(match['startAt'],1,True);number(match['state'],0,True);text(match['roundText'],255,True)
            require(isinstance(match['slots'],list) and len(match['slots'])<=2);indices=set()
            for slot in match['slots']:
                keys(slot,'index entrantId seedId prereqId prereqType prereqPlacement');require(type(slot['index']) is int and slot['index'] in (0,1) and slot['index'] not in indices);indices.add(slot['index'])
                require(slot['entrantId'] is None or slot['entrantId'] in members);require(slot['seedId'] is None or slot['seedId'] in local_seeds)
                if slot['prereqId'] is not None:identifier(slot['prereqId'],True)
                text(slot['prereqType'],32,True);number(slot['prereqPlacement'],0,True)
    keys(p['audit'],'requests batches elapsedMilliseconds')
    for v in p['audit'].values():number(v)
    require(p['audit']['requests']<=60 and 1<=p['audit']['batches']<=2 and p['audit']['elapsedMilliseconds']<=240000)
    require(len(seeds)<=5000 and len(sets)<=5000 and len(json.dumps(p,ensure_ascii=False).encode())<=MAX_RAW)


def main(argv=None):
    args=argparse.ArgumentParser(description=__doc__);args.add_argument('--publish',action='store_true');opts=args.parse_args(argv)
    began=time.monotonic();summary=dict(status='failed',queries=0,groups=None,entrants=None,sets=None,seconds=0);client=None
    try:
        event_id=int(os.environ.get('SMASH_MY_TOURNAMENT_EVENT_ID','1687524'));due=schedule(event_id,time.time(),os.environ.get('GITHUB_EVENT_NAME')=='workflow_dispatch' or not opts.publish)
        if due!='due':summary['status']=due;return 0
        client=Client(os.environ['STARTGG_TOKEN']);snap=capture(client,event_id)
        summary.update(status='validated_no_writes',groups=len(snap['groups']),entrants=len(snap['entrants']),sets=sum(len(g['sets']) for g in snap['groups']))
        if opts.publish:
            outcome=request(os.environ['SMASH_SQL_SYNC_KEY'],encode_transport(snap),'application/vnd.smash.bracket+gzip')
            require(outcome.get('status') in ('stored','already_stored'));summary['status']=outcome['status']
        return 0
    except Exception as error:
        summary['reason']='bracket_source_query_failed' if isinstance(error,APIError) else 'bracket_capture_stopped'
        if not opts.publish:
            import traceback
            summary['trace']=[dict(file=Path(x.filename).name,function=x.name,line=x.lineno) for x in traceback.extract_tb(error.__traceback__)]
        return 1
    finally:
        summary['queries']=client.calls if client else 0;summary['seconds']=round(time.monotonic()-began,3);print(json.dumps(summary))
        if os.environ.get('GITHUB_STEP_SUMMARY'):
            with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:f.write('## Mi torneo\n\n'+json.dumps(summary)+'\n')
if __name__=='__main__':raise SystemExit(main())
