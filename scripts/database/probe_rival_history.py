"""Read-only diagnosis: aggregate/form/stack metadata only, no person values or raw errors."""
import copy,json,os,re,time,traceback,urllib.request
from pathlib import Path
from rival_automation import event_roster,Hosting,merge_state
from rival_context import package
from rival_history import HISTORY,connection
from collect import Client,ENDPOINT
from publish_sql import NoRedirect
from probe_rival_roster import field


def main():
    client=Client(os.environ['STARTGG_TOKEN'])
    roster=event_roster(client,1687524)
    if roster is None:print(json.dumps(dict(status='registrations_unavailable',queries=client.calls)));return
    inv=Hosting(os.environ['SMASH_SQL_SYNC_KEY']).inventory(roster)
    state=merge_state(roster,inv['checkpoint'],inv['knownIds'])
    pid=next((pid for pid,cov in state['coverage'].items() if not cov['complete']),None)
    if pid is None:print(json.dumps(dict(status='no_missing_roots',queries=client.calls)));return
    time.sleep(max(0,1-(time.monotonic()-client.last_call)));client.calls+=1
    req=urllib.request.Request(ENDPOINT,data=json.dumps(dict(query=HISTORY,variables=dict(id=pid,page=state['coverage'][pid]['nextPage']))).encode(),headers={'Authorization':'Bearer '+client.token,'Content-Type':'application/json'})
    with urllib.request.build_opener(NoRedirect()).open(req,timeout=30) as response:
        raw=response.read(8*1024*1024+1)
        if len(raw)>8*1024*1024:raise ValueError()
        payload=json.loads(raw)
    errors=[];querywords=set(re.findall(r'[A-Za-z_][A-Za-z0-9_]*',HISTORY))
    for error in payload.get('errors') or []:
        message=error.get('message','');kind='other';fields=[]
        for pattern in (r'Cannot query field "([A-Za-z_][A-Za-z0-9_]*)"',r'Unknown argument "([A-Za-z_][A-Za-z0-9_]*)"',r'Field "([A-Za-z_][A-Za-z0-9_]*)" is not defined'):
            match=re.search(pattern,message)
            if match:kind='schema_validation';fields=[match[1]] if match[1] in querywords else []
        if 'complexity' in message.lower():kind='complexity'
        if 'Syntax Error' in message:kind='syntax'
        errors.append(dict(kind=kind,fields=fields))
    player=(payload.get('data') or {}).get('player');conn=player.get('sets') if isinstance(player,dict) else None
    info=conn.get('pageInfo') if isinstance(conn,dict) else None;nodes=conn.get('nodes') if isinstance(conn,dict) else None
    report=dict(queries=client.calls,registered=roster['registrations'],known=len(inv['knownIds']),errors=errors,player=field(payload.get('data'),'player'),sets=field(player,'sets'),pageInfo=field(conn,'pageInfo'),total=field(info,'total'),totalPages=field(info,'totalPages'),nodes=field(conn,'nodes'))
    if isinstance(nodes,list):
        report['setCount']=len(nodes);report['setForms']=[{k:field(m,k) for k in ('id','state','winnerId','event','slots','games')} for m in nodes]
    print(json.dumps(report))
    if errors:return
    stage='connection'
    try:
        connection(conn);stage='normalize'
        selected={str(m['id']):m for m in nodes if isinstance(m.get('event'),dict) and (m['event'].get('videogame') or {}).get('id') in (1386,'1386') and m['event'].get('type')==1 and type(m['event'].get('startAt')) is int and 1767247200<=m['event']['startAt']<1798783200}
        data=dict(kind='analysis_history',schemaVersion=1,capturedAt=roster['capturedAt'],seasonYear=2026,roster=copy.deepcopy(roster),sets=selected,coverage={pid:dict(nextPage=2,totalPages=1,complete=True)},audit=dict(requests=1,seconds=1))
        data['roster']['players']={pid:roster['players'][pid]}
        p=package(data)
        print(json.dumps(dict(stage='normalized_no_writes',sets=len(p['content']['entities']['sets']),games=len(p['content']['entities']['games']))))
    except Exception as error:
        trace=[dict(file=Path(x.filename).name,function=x.name,line=x.lineno) for x in traceback.extract_tb(error.__traceback__)]
        print(json.dumps(dict(stage=stage,errorType=type(error).__name__,trace=trace)))

if __name__=='__main__':
    try:main()
    except Exception:print(json.dumps(dict(status='probe_stopped_no_writes')));raise SystemExit(1)
