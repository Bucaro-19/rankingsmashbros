"""Offline phase-four study. Invented workloads, no API, cache or importer.

Request arithmetic excludes roster, hosting/cache traffic, retries, object-limit
validation and pagination changes. It is not a runtime policy or an ETA.
"""
import gzip
import json
from math import ceil

CURRENT_PAGE_SIZE=5
DETAIL_BATCH_SIZE=5  # Existing characters.py batches set lookups this way.


def request_model(histories,unique_season_sets,validated_cache_hits,*,light_page_size=50):
    if not isinstance(histories,list) or len(histories)>1000:
        raise ValueError('Invalid invented histories.')
    for value in histories+[unique_season_sets,validated_cache_hits,light_page_size]:
        if type(value) is not int or value<0:raise ValueError('Counts must be nonnegative integers.')
    if not 1<=light_page_size<=50 or not validated_cache_hits<=unique_season_sets<=sum(histories):
        raise ValueError('Inconsistent invented counts.')
    # A root with no sets still needs its first page to establish the empty list.
    current=sum(max(1,ceil(n/CURRENT_PAGE_SIZE)) for n in histories)
    listing=sum(max(1,ceil(n/light_page_size)) for n in histories)
    misses=unique_season_sets-validated_cache_hits
    details=ceil(misses/DETAIL_BATCH_SIZE)
    return dict(currentRequests=current,lightListRequests=listing,detailRequests=details,
                splitRequests=listing+details,extraRequests=listing+details-current,
                lightPageSize=light_page_size,detailCacheMisses=misses)


def invented_node(i):
    # No real users, event IDs, profiles, games or handoff sample data.
    return dict(id=i,state=3,winnerId=10,updatedAt=1770000000,completedAt=1770000000,
        displayScore='Inventado 2 - Ejemplo 0',
        event=dict(id=1,name='Evento inventado',slug='tournament/inventado/event/singles',
            numEntrants=20,startAt=1770000000,isOnline=False,type=1,videogame=dict(id=1386,name='Ultimate'),
            tournament=dict(id=2,name='Torneo inventado',slug='tournament/inventado',countryCode='GT')),
        slots=[dict(entrant=dict(id=en,name='Inventado',participants=[dict(player=dict(id=en,gamerTag='Inventado',
                    user=dict(slug='user/inventado',location=dict(country='Guatemala'))))])) for en in (10,20)],
        games=[dict(id=i*10+j,orderNum=j,winnerId=10,entrant1Score=2,entrant2Score=0,stage=dict(id=1),
                    selections=[dict(entrant=dict(id=en),character=dict(id=1,name='Personaje inventado')) for en in (10,20)]) for j in range(1,11)])


def manifest_node(node):
    # Proposed identity manifest; not a production GraphQL query or an importable set.
    event=node['event']
    return {**{k:node[k] for k in ('id','state','winnerId','updatedAt','completedAt','displayScore')},
        'event':{**{k:event[k] for k in ('id','startAt','type')},'videogame':{'id':event['videogame']['id']}},
        'slots':[dict(entrant=dict(id=s['entrant']['id'],participants=[dict(player=dict(id=p['player']['id']))
                  for p in s['entrant']['participants']])) for s in node['slots']]}


def dict_count(value):
    if isinstance(value,dict):return 1+sum(dict_count(v) for v in value.values())
    if isinstance(value,list):return sum(map(dict_count,value))
    return 0


def payload_model(count,*,manifest=False):
    nodes=[invented_node(i) for i in range(1,count+1)]
    if manifest:nodes=list(map(manifest_node,nodes))
    value=dict(player=dict(sets=dict(pageInfo=dict(total=count,totalPages=1),nodes=nodes)))
    body=json.dumps(value,ensure_ascii=False,separators=(',',':')).encode()
    return dict(nodes=count,jsonBytes=len(body),gzipBytes=len(gzip.compress(body,mtime=0)),
                jsonObjects=dict_count(value))


def study():
    workloads=[('long_history_50_current_cold',[1000],50,0,50),
               ('all_current_cold',[1000],1000,0,50),
               ('long_history_same_page_size',[1000],50,0,5),
               ('shared_sets_validated_cache',[250,250,250,250],500,400,50),
               ('many_short_histories',[5]*100,500,0,50)]
    return dict(status='offline_simulation_not_a_capture',modelVersion=1,
        baselineCommit='1119acc9c72f9ca9cf14211580fd71e025a95ffd',baselinePageSize=CURRENT_PAGE_SIZE,
        cases=[dict(name=name,**request_model(lengths,unique,hits,light_page_size=page))
               for name,lengths,unique,hits,page in workloads],
        payloads=dict(currentFiveDense=payload_model(5),proposedFiftyManifest=payload_model(50,manifest=True)),
        caveats=['Invented workloads, not measurements of Legends 7.',
                 'Fifty manifest nodes/request and five detail lookups/request still require real provider validation.',
                 'JSON dictionary counts are not the provider complexity score.',
                 'Only validated, fresh detail versions can count as cache hits.',
                 'No checkpoint, cache, SQL, ranking or production capture is modified.'])


if __name__=='__main__':print(json.dumps(study(),ensure_ascii=False))
