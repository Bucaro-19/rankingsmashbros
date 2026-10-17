"""One schema query and event metadata; no player values, artifacts or writes."""
import json,os
from rival_automation import Client

TYPES=['Event','Phase','PhaseGroup','Seed','Set','SetSlot','Entrant']
SELECTED={'Event':{'phases','phaseGroups','entrants'},'Phase':{'phaseOrder','phaseGroups','startAt','isExhibition','state','seeds','isPublished'},'PhaseGroup':{'phase','startAt','firstRoundTime','seeds','sets','state','bracketType','displayIdentifier'},'Seed':{'seedNum','groupSeedNum','phaseGroup','entrant','phase'},'Set':{'slots','startAt','startedAt','round','fullRoundText','winnerId','phaseGroup','state'},'SetSlot':{'prereqId','prereqType','prereqPlacement','seed','entrant','standing'},'Entrant':{'initialSeedNum','participants'}}
INNER='kind name ofType{kind name ofType{kind name ofType{kind name}}}'
QUERY='query{'+''.join('t'+str(i)+':__type(name:"'+name+'"){fields{name description type{'+INNER+'} args{name defaultValue type{'+INNER+'}}}}' for i,name in enumerate(TYPES))+'}'
def main():
    client=Client(os.environ['STARTGG_TOKEN']);data=client.query(QUERY,{})
    for i,name in enumerate(TYPES):
        fields=data['t'+str(i)]['fields']
        print(json.dumps(dict(type=name,names=[f['name'] for f in fields],selected=[f for f in fields if f['name'] in SELECTED[name]])))
    meta=client.query('query{event(id:1687524){id startAt isOnline type videogame{id} tournament{id startAt endAt timezone countryCode} phases{id name phaseOrder} phaseGroups(query:{page:1,perPage:1}){pageInfo{total totalPages}nodes{id}}}}',{})['event']
    groups=meta.pop('phaseGroups');meta['groupCount']=(groups.get('pageInfo') or {}).get('total') if isinstance(groups,dict) else None
    print(json.dumps(dict(eventMetadata=meta,queries=client.calls)))
if __name__=='__main__':
    try:main()
    except Exception:print(json.dumps(dict(status='schema_probe_failed')));raise SystemExit(1)
