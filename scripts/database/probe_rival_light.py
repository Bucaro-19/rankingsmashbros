"""Read-only comparison of equivalent windows of start.gg history. Outputs aggregates."""
import hashlib
import json
import math
import os
import time

from rival_automation import event_roster
from collect import Client
from discover import season_timestamp
from organizer_small import BudgetClient
from rival_history import HISTORY, connection, linked_to_player

LIGHT_PAGE = 50
CURRENT_PAGE = 5
DETAIL_GROUP = 5
MAX_CANDIDATES = 30
MAX_REQUESTS = 84
MAX_SECONDS = 180
EVENT_ID = 1687524
START = season_timestamp('2026-01-01')
END = season_timestamp('2027-01-01')
LIGHT = '''query($id:ID!,$page:Int!){
  player(id:$id){sets(page:$page,perPage:50,filters:{entrantSize:[1],state:[3]}){
    pageInfo{total totalPages}
    nodes{id state updatedAt event{id startAt type videogame{id}}}
  }}
}'''


class ProbeStopped(ValueError):
    pass


class ProbeClient(Client):
    def __init__(self, token):
        super().__init__(token)
        self.started = time.monotonic()

    def query(self, query, variables):
        if self.calls + 3 > MAX_REQUESTS or time.monotonic() - self.started >= MAX_SECONDS:
            raise ProbeStopped('probe_budget')
        return super().query(query, variables)


def query_aliases(query, entity, ids, fields):
    params = {f'id{i}':str(id_) for i,id_ in enumerate(ids)}
    declarations = ','.join(f'${key}:ID!' for key in params)
    nodes = ' '.join(f'{key}:{entity}(id:${key}){{{fields}}}' for key in params)
    result = query(f'query({declarations}){{{nodes}}}', params)
    return [result.get(key) for key in params]


def candidate_totals(client, roster):
    ids = sorted(roster['players'], key=lambda pid:hashlib.sha256(('legends7-pilot-v1:'+pid).encode()).digest())
    query = BudgetClient(client).query
    ids = ids[:MAX_CANDIDATES]
    candidates = []
    for offset in range(0, len(ids), 10):
        chunk = ids[offset:offset+10]
        rows = query_aliases(query, 'player', chunk,
                             'id sets(page:1,perPage:1,filters:{entrantSize:[1],state:[3]}){pageInfo{total}}')
        for pid, row in zip(chunk, rows):
            if not row or str(row.get('id')) != pid:
                continue
            total = (((row.get('sets') or {}).get('pageInfo') or {}).get('total'))
            if type(total) is int and total > 0:
                candidates.append((pid,total))
    return candidates


def sample_plan(candidates):
    short = [item for item in candidates if item[1] <= 20]
    short += [item for item in candidates if 20 < item[1] <= 30]
    long = [item for item in candidates if item[1] >= 100]
    plan = [('short_complete',pid,total,1) for pid,total in short[:2]]
    if long:
        pid,total = long[0]
        plan.append(('long_first_window',pid,total,1))
    if len(long) > 1:
        pid,total = long[1]
        plan.append(('long_later_window',pid,total,total//LIGHT_PAGE))
    return plan


def page_nodes(query, document, pid, page, page_size, total):
    result = query(document, {'id':pid,'page':page})
    conn = (result.get('player') or {}).get('sets')
    info = connection(conn)
    size = max(0,min(page_size,total-(page-1)*page_size))
    if info['total'] != total or info['totalPages'] != math.ceil(total/page_size) or len(conn['nodes']) != size:
        raise ProbeStopped('unstable_pagination')
    return conn['nodes']


def by_id(nodes):
    result = {}
    for node in nodes:
        id_ = str(node.get('id'))
        if not id_.isdigit() or id_ in result:
            raise ProbeStopped('invalid_set_ids')
        result[id_] = node
    return result


def in_season(match):
    event = match.get('event') or {}
    at = event.get('startAt')
    return (match.get('state') == 3 and event.get('type') == 1
            and str((event.get('videogame') or {}).get('id')) == '1386'
            and type(at) is int and START <= at < END)


def normalized(match):
    # Compare the complete current query projection, with identity/content fields
    # intact in memory. Array order for picks, slots and games has no semantic effect.
    def stable(value):
        if isinstance(value, list):
            return sorted((stable(item) for item in value),key=lambda item:json.dumps(item,sort_keys=True))
        if isinstance(value, dict):
            return {key:stable(item) for key,item in value.items()}
        return value
    return stable(match)


def compare_window(client, label, pid, total, page, *, clock=time.monotonic):
    budget = BudgetClient(client,clock)
    first = (page-1)*(LIGHT_PAGE//CURRENT_PAGE)+1
    size = min(LIGHT_PAGE,total-(page-1)*LIGHT_PAGE)
    started = clock()
    before = client.calls
    current = by_id(node for index in range(first,first+math.ceil(size/CURRENT_PAGE))
                    for node in page_nodes(budget.query,HISTORY,pid,index,CURRENT_PAGE,total))
    current_metrics = {'requests':client.calls-before,'seconds':round(clock()-started,3)}
    if len(current) != size:
        raise ProbeStopped('incomplete_current_window')

    before = client.calls
    started = clock()
    manifest = by_id(page_nodes(budget.query,LIGHT,pid,page,LIGHT_PAGE,total))
    listed = client.calls-before
    expected = {id_:match for id_,match in current.items() if in_season(match) and linked_to_player(match,pid)}
    report = {'sample':label,'historySets':total,'windowSets':size,'current':current_metrics,'seasonSets':len(expected)}
    if set(current) != set(manifest):
        return report | {'status':'window_mismatch','commonSourceSets':len(set(current) & set(manifest)),
                         'light':{'requests':listed,'listRequests':listed,'detailRequests':0,'seconds':round(clock()-started,3)}}

    ids = [id_ for id_,match in manifest.items() if in_season(match)]
    # Use the same selection as the baseline. The history query wraps the fields in nodes{...}.
    fields = HISTORY.split('nodes{',1)[1].removesuffix('}}}}')
    details = {}
    for offset in range(0,len(ids),DETAIL_GROUP):
        group = ids[offset:offset+DETAIL_GROUP]
        rows = query_aliases(budget.query,'set',group,fields)
        if any(not row or str(row.get('id')) != id_ for id_,row in zip(group,rows)):
            raise ProbeStopped('detail_unavailable')
        for id_,row in zip(group,rows):
            if row.get('updatedAt') != manifest[id_].get('updatedAt') or not in_season(row):
                raise ProbeStopped('set_changed_during_probe')
            if linked_to_player(row,pid):
                details[id_] = row
    matched = expected.keys() == details.keys()
    differing = sum(normalized(expected[id_]) != normalized(details[id_]) for id_ in expected.keys() & details.keys())
    if clock()-budget.started > 120:
        raise ProbeStopped('batch_time_ceiling')
    return report | {
        'status':'matched' if matched and not differing else 'detail_mismatch',
        'games':sum(len(match.get('games') or []) for match in expected.values()),
        'selections':sum(len(game.get('selections') or []) for match in expected.values() for game in (match.get('games') or [])),
        'differentDetailSets':differing,'lightSeasonSets':len(details),
        'light':{'requests':client.calls-before,'listRequests':listed,'detailRequests':client.calls-before-listed,
                 'seconds':round(clock()-started,3)},
    }


def main():
    started = time.monotonic()
    client = ProbeClient(os.environ['STARTGG_TOKEN'])
    stage = 'roster'
    try:
        roster = event_roster(client,EVENT_ID)
        if roster is None:
            raise ProbeStopped('registrations_unavailable')
        stage = 'sample_selection'
        plan = sample_plan(candidate_totals(client,roster))
        print(json.dumps({'status':'selected','sampleSize':len(plan),'setupRequests':client.calls}),flush=True)
        if not plan:
            raise ProbeStopped('no_eligible_sample')
        reports = []
        for label,pid,total,page in plan:
            stage = label
            report = compare_window(client,label,pid,total,page)
            reports.append(report)
            print(json.dumps(report),flush=True)
        if time.monotonic()-started > MAX_SECONDS:
            raise ProbeStopped('probe_time_ceiling')
        outcome = 'matched' if all(r['status']=='matched' for r in reports) else 'partial'
        print(json.dumps({'status':outcome,'queries':client.calls,'seconds':round(time.monotonic()-started,3),
                          'windowsCompared':len(reports),'windowsMatched':sum(r['status']=='matched' for r in reports)}))
    except Exception as error:
        reason = str(error) if isinstance(error,ProbeStopped) else type(error).__name__
        print(json.dumps({'status':'probe_stopped','stage':stage,'reason':reason,'queries':client.calls,
                          'seconds':round(time.monotonic()-started,3)}),flush=True)
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
