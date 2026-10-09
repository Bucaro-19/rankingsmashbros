"""One-off context for missing small events. Capture is read-only; load simulates by default.

No endpoint, migration, automatic schedule, ranking package or national cut writes.
Inventory contains event IDs and an existing-cut anchor, never a roster or credentials.
"""
import argparse
import copy
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import re
import sys
import time

from ranking_package import (canonical, digest, identifier, instant, integer, require,
                             normalize_capture_entities)
from import_ranking import LOCK, sql, verify_schema
from organizer_context import TABLES, validate_context
from organizer_sql import organizer_plan, import_organizer_context
from weekly_ranking_load import connect
from collect import Client, APIError
from discover import season_timestamp
from organizer_small import BudgetClient, capture, probe_catalog, MAX_EVENTS, MAX_ATTEMPTS, MAX_SECONDS

MAX_BYTES = 32 * 1024 * 1024


def begin(db, apply=False):
    require(not (db.server_status & 1), 'Foreign transaction.')
    sql(db, 'SET TRANSACTION ISOLATION LEVEL ' + ('SERIALIZABLE' if apply else 'REPEATABLE READ'))
    sql(db, 'SET TRANSACTION ' + ('READ WRITE' if apply else 'READ ONLY'))
    db.begin()


def validate_anchor(a):
    require(set(a) == {'cutId','generatedAt','seasonYear','methodVersion','sourceHash'}, 'Anchor fields.')
    identifier(a['cutId']); instant(a['generatedAt']); integer(a['seasonYear'], minimum=2000, maximum=2100)
    require(isinstance(a['methodVersion'], str) and 0 < len(a['methodVersion']) <= 100, 'Anchor method.')
    require(isinstance(a['sourceHash'], str) and re.fullmatch('[0-9a-f]{64}', a['sourceHash']), 'Anchor hash.')


def inventory(db, year):
    begin(db)
    try:
        verify_schema(db)
        require(organizer_plan(db, dict(entities={'events':[]}))['status'] == 'ready', '006 required.')
        rows = sql(db, "SELECT id,generated_at,season_year,method_version,source_hash FROM cuts WHERE season_year=%s AND status='published' ORDER BY generated_at DESC LIMIT 1", (year,))
        require(len(rows) == 1, 'No published anchor.')
        r = rows[0]
        anchor = dict(cutId=r[0],generatedAt=r[1].replace(tzinfo=timezone.utc).isoformat(),seasonYear=r[2],methodVersion=r[3],sourceHash=r[4])
        result = dict(inventoryVersion=1,anchor=anchor,
            markedEventIds=sorted(r[0] for r in sql(db, 'SELECT event_id FROM organizer_event_context')),
            protectedEventIds=sorted(r[0] for r in sql(db, 'SELECT id FROM events')))
        validate_inventory(result)
        return result
    finally:
        db.rollback()


def validate_inventory(data):
    require(set(data) == {'inventoryVersion','anchor','markedEventIds','protectedEventIds'} and type(data['inventoryVersion']) is int and data['inventoryVersion'] == 1, 'Inventory format.')
    validate_anchor(data['anchor'])
    for key in ('markedEventIds','protectedEventIds'):
        require(isinstance(data[key], list) and all(type(v) is int for v in data[key])
            and len(data[key]) == len({identifier(v) for v in data[key]}), 'Inventory IDs.')


def normalize_small(raw):
    # A completed start.gg event can still contain unplayed bracket slots. Do not turn
    # those pending sets into history/results, or discard its completed played sets.
    for m in raw['sets'].values():
        state = integer(m.get('state'), maximum=255)
        require(state == 3 or (state in (1,2) and m.get('winnerId') is None), 'Unfinished set has winner or unknown state.')
    completed = {sid:m for sid,m in raw['sets'].items() if m['state'] == 3}
    events = [dict(e,setsFetched=sum(identifier(m['event']['id']) == identifier(e['id']) for m in completed.values())) for e in raw['events']]
    indexed, ep, slots, _, _, _ = normalize_capture_entities(dict(generatedAt=raw['capturedAt'], events=events, players=raw['players'], sets=completed))
    entities = {name:[rows[k] for k in sorted(rows)] for name,rows in indexed.items()}
    entities['entrant_players'] = [ep[k] for k in sorted(ep)]
    entities['set_slots'] = [slots[k] for k in sorted(slots)]
    linked = {r['player_id'] for r in entities['entrant_players']}
    entities['players'] = [r for r in entities['players'] if r['id'] in linked]
    context = dict(schemaVersion=1,capturedAt=raw['capturedAt'],entities=entities,
        eligibility=[dict(event_id=e['id'],is_online=False,state='COMPLETED',entrant_size=1) for e in entities['events']])
    validate_context(context)
    return context


def capture_batch(client, inv, start, end, *, limit=6, catalog=None, clock=time.monotonic):
    validate_inventory(inv)
    require(type(limit) is int and 1 <= limit <= MAX_EVENTS, 'Event ceiling.')
    require(start >= season_timestamp(f"{inv['anchor']['seasonYear']}-01-01")
        and end <= season_timestamp(f"{inv['anchor']['seasonYear']+1}-01-01") and start < end, 'Season window.')
    started = clock(); before = client.calls
    budget = BudgetClient(client, clock)
    source = probe_catalog(budget, start, end) if catalog is None else copy.deepcopy(catalog)
    require(source['season'] == dict(startInclusive=start,endExclusive=end), 'Catalog window.')
    catalog_requests = client.calls-before
    candidates = source['organizerCandidates']
    require(isinstance(candidates,list) and len(candidates) == len({identifier(e['id']) for e in candidates}), 'Catalog IDs.')
    # Oldest first drains historical omissions. A fresh inventory avoids querying marked events.
    marked = set(inv['markedEventIds']); protected = set(inv['protectedEventIds'])
    missing = sorted((e for e in candidates if identifier(e['id']) not in marked|protected), key=lambda e:(e['startAt'],identifier(e['id'])))
    summary = dict(candidateEvents=len(candidates),markedCandidates=sum(identifier(e['id']) in marked for e in candidates),
        protectedCandidates=sum(identifier(e['id']) in protected-marked for e in candidates),missingEvents=len(missing),
        selectedEvents=min(limit,len(missing)),remainingEvents=max(0,len(missing)-limit),catalogRequests=catalog_requests)
    if not missing:
        return None,dict(summary,status='nothing_missing',apiRequests=client.calls-before,seconds=round(clock()-started,3))
    source['organizerCandidates'] = missing[:limit]
    # capture() sorts most recent first inside this selected OLDEST batch; membership stays fixed.
    raw = capture(budget, source, limit=limit, clock=clock)
    elapsed = round((clock()-started)*1000)
    require(elapsed <= MAX_SECONDS*1000 and client.calls-before <= MAX_ATTEMPTS, 'Capture budget.')
    context = normalize_small(raw)
    audit = dict(summary,apiRequests=client.calls-before,contextRequests=raw['requests'],elapsedMilliseconds=elapsed,
        ignoredUnfinishedSets=len(raw['sets'])-len(context['entities']['sets']))
    c = dict(backfillVersion=1,kind='small_events_backfill',anchor=inv['anchor'],season=source['season'],context=context,audit=audit)
    package = dict(content=c,sha256=digest(c)); validate_batch(package)
    body = canonical(package).encode()
    require(len(body) <= MAX_BYTES and len(gzip.compress(body,mtime=0)) <= 4*1024*1024, 'Batch size.')
    return package,dict(audit,status='captured_no_sql_writes',sets=len(context['entities']['sets']),seconds=elapsed/1000)


def validate_batch(package):
    require(set(package) == {'content','sha256'} and package['sha256'] == digest(package['content']), 'Batch hash.')
    c = package['content']
    require(set(c) == {'backfillVersion','kind','anchor','season','context','audit'} and type(c['backfillVersion']) is int
        and c['backfillVersion'] == 1 and c['kind'] == 'small_events_backfill', 'Batch format.')
    validate_anchor(c['anchor']); validate_context(c['context'])
    a = c['audit']; require(set(a) == {'candidateEvents','markedCandidates','protectedCandidates','missingEvents','selectedEvents','remainingEvents','catalogRequests','contextRequests','apiRequests','elapsedMilliseconds','ignoredUnfinishedSets'}, 'Audit format.')
    for n in a.values(): integer(n)
    require(a['selectedEvents'] == len(c['context']['entities']['events']) and a['selectedEvents'] <= MAX_EVENTS
        and a['catalogRequests']+a['contextRequests'] == a['apiRequests'] <= MAX_ATTEMPTS
        and a['elapsedMilliseconds'] <= MAX_SECONDS*1000 and a['remainingEvents']+a['selectedEvents'] == a['missingEvents']
        and a['candidateEvents'] == a['markedCandidates']+a['protectedCandidates']+a['missingEvents'], 'Audit budget/counts.')
    season = c['season']; year = c['anchor']['seasonYear']
    require(set(season) == {'startInclusive','endExclusive'} and season_timestamp(f'{year}-01-01') <= season['startInclusive'] < season['endExclusive'] <= season_timestamp(f'{year+1}-01-01'), 'Season format.')
    require(instant(c['context']['capturedAt']) >= instant(c['anchor']['generatedAt']), 'Capture predates anchor.')
    for event in c['context']['entities']['events']:
        require(instant(datetime.fromtimestamp(season['startInclusive'],timezone.utc).isoformat()) <= event['starts_at'] < instant(datetime.fromtimestamp(season['endExclusive'],timezone.utc).isoformat()), 'Event outside window.')
    return c


def subset(context, selected):
    t = context['entities']; result = dict(schemaVersion=1,capturedAt=context['capturedAt'],entities={},
        eligibility=[r for r in context['eligibility'] if r['event_id'] in selected])
    out = result['entities']
    out['events'] = [r for r in t['events'] if r['id'] in selected]
    for name in ('sets','entrants'): out[name] = [r for r in t[name] if r['event_id'] in selected]
    sids = {r['id'] for r in out['sets']}; eids = {r['id'] for r in out['entrants']}
    out['set_slots'] = [r for r in t['set_slots'] if r['set_id'] in sids]
    out['entrant_players'] = [r for r in t['entrant_players'] if r['entrant_id'] in eids]
    pids = {r['player_id'] for r in out['entrant_players']}; tids = {r['tournament_id'] for r in out['events']}
    out['players'] = [r for r in t['players'] if r['id'] in pids]; out['tournaments'] = [r for r in t['tournaments'] if r['id'] in tids]
    validate_context(result)
    return result


def load_batch(db, package, *, apply=False):
    c = validate_batch(package)
    require(not (db.server_status & 1), 'Foreign transaction.')
    require(sql(db,'SELECT GET_LOCK(%s,0)',(LOCK,))[0][0] == 1, 'Importer busy.')
    db.rollback()
    try:
        begin(db,apply)
        verify_schema(db)
        require(organizer_plan(db,c['context'])['status'] == 'ready', '006 required.')
        a = c['anchor']
        found = sql(db,'SELECT generated_at,season_year,method_version,source_hash,status FROM cuts WHERE id=%s',(a['cutId'],))
        require(len(found) == 1 and (instant(found[0][0].replace(tzinfo=timezone.utc).isoformat()),*found[0][1:]) ==
            (instant(a['generatedAt']),a['seasonYear'],a['methodVersion'],a['sourceHash'],'published'), 'Anchor changed.')
        marked = {r[0] for r in sql(db,'SELECT event_id FROM organizer_event_context')}
        selected = {r['id'] for r in c['context']['entities']['events']} - marked
        report = dict(readOnly=not apply,selectedEvents=len(selected),alreadyMarkedEvents=len(c['context']['entities']['events'])-len(selected),
                      capture=c['audit'],batchHash=package['sha256'])
        if not selected:
            db.rollback(); return dict(report,status='already_imported')
        context = subset(c['context'],selected)
        # Never refresh ANY existing unmarked live event: it may be national context even
        # if excluded from cut_events. The weekly loader retains its separate refresh policy.
        for eid in selected:
            require(not sql(db,'SELECT 1 FROM events WHERE id=%s',(eid,))
                and not sql(db,'SELECT 1 FROM cut_events WHERE event_id=%s',(eid,)), 'Protected live event.')
        for name in ('sets','entrants'):
            for row in context['entities'][name]:
                require(not sql(db,'SELECT 1 FROM '+name+' WHERE id=%s',(row['id'],)), 'Existing live identity.')
        if not apply:
            db.rollback(); return dict(report,status='validated_no_writes')
        outcome = import_organizer_context(db,context,a['cutId'],dict(status='ready',events=len(selected)),marker_subset=True)
        require(outcome['status'] == 'imported', 'Context transaction/parity failed.')
        db.commit()
        return dict(report,status='context_imported')
    except Exception:
        db.rollback(); raise
    finally:
        sql(db,'SELECT RELEASE_LOCK(%s)',(LOCK,))


def read_json(path):
    require(not path.is_symlink() and path.stat().st_size <= MAX_BYTES, 'Unsafe input.')
    return json.loads(path.read_text())


def write_private(path, data):
    require(not path.is_symlink() and not path.exists(), 'Output already exists.')
    path.parent.mkdir(parents=True,exist_ok=True)
    body = canonical(data).encode(); require(len(body) <= MAX_BYTES, 'Output too large.')
    import os
    fd = os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as out: out.write(body)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command',required=True)
    inv = sub.add_parser('inventory'); inv.add_argument('--year',type=int,default=2026); inv.add_argument('--output',type=Path,required=True)
    cap = sub.add_parser('capture'); cap.add_argument('--inventory',type=Path,required=True); cap.add_argument('--output',type=Path,required=True)
    cap.add_argument('--start',default='2026-01-01'); cap.add_argument('--end',required=True); cap.add_argument('--limit',type=int,default=6); cap.add_argument('--catalog',type=Path)
    load = sub.add_parser('load'); load.add_argument('package',type=Path); load.add_argument('--apply',action='store_true')
    for command in (inv,load):
        command.add_argument('--defaults-file',type=Path,default=Path.home()/'.my.cnf'); command.add_argument('--database',required=True)
    args = parser.parse_args(); db = None; client = None; started = time.monotonic()
    try:
        if args.command == 'capture':
            import os
            require(not args.output.exists() and not args.output.is_symlink(), 'Output exists.')
            token = os.environ.get('STARTGG_TOKEN','').strip(); require(bool(token),'Token missing.')
            client = Client(token)
            data,report = capture_batch(client,read_json(args.inventory),season_timestamp(args.start),season_timestamp(args.end),limit=args.limit,catalog=read_json(args.catalog) if args.catalog else None)
            if data is not None: write_private(args.output,data)
        else:
            db = connect(args.defaults_file,args.database)
            if args.command == 'inventory':
                data = inventory(db,args.year); write_private(args.output,data)
                report = dict(status='inventory_read_only',markedEvents=len(data['markedEventIds']),protectedEvents=len(data['protectedEventIds']))
            else: report = load_batch(db,read_json(args.package),apply=args.apply)
        report['operationSeconds'] = round(time.monotonic()-started,3)
        print(json.dumps(report)); return 0
    except Exception:
        # Never log provider bodies, people, connection strings or driver errors.
        print(json.dumps(dict(ok=False,reason='small_backfill_stopped',phase=args.command,
            apiRequests=client.calls if client else 0,operationSeconds=round(time.monotonic()-started,3)))); return 1
    finally:
        if db is not None: db.close()


if __name__ == '__main__': sys.exit(main())
