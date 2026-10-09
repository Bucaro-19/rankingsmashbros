"""Optional SQL context under a savepoint. Never changes national ledgers or cut hashes."""
from organizer_context import TABLES, MARKER_COLUMNS
from ranking_package import digest, require, instant


def organizer_plan(db, context):
    from import_ranking import sql
    if not sql(db,"SELECT version FROM schema_migrations WHERE version='006_organizer_event_context'"):
        return dict(status='migration_missing',events=len(context['entities']['events']))
    try:
        require(sql(db,"SELECT ENGINE FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name='organizer_event_context'")==(('InnoDB',),), 'Marcador no transaccional.')
        require(set(MARKER_COLUMNS.split())<={r[0] for r in sql(db,'SHOW COLUMNS FROM organizer_event_context')}, 'Marcador incompleto.')
    except Exception:
        return dict(status='schema_unavailable',events=len(context['entities']['events']))
    return dict(status='ready',events=len(context['entities']['events']))


def import_organizer_context(db, context, cut_id, plan, *, marker_subset=False):
    from import_ranking import sql, insert_rows, COLUMNS
    if plan['status']!='ready':return plan
    sql(db,'SAVEPOINT organizer_context')
    try:
        t=context['entities'];event_ids=[r['id'] for r in t['events']]
        for eid in event_ids:
            require(not sql(db,'SELECT 1 FROM cut_events WHERE event_id=%s LIMIT 1',(eid,)), 'Evento pequeño ya usado por un corte nacional.')
            existing=sql(db,'SELECT tournament_id FROM events WHERE id=%s',(eid,))
            require(not existing or existing[0][0]==next(r['tournament_id'] for r in t['events'] if r['id']==eid), 'Evento movido de torneo.')
            for name in ('entrants','sets'):
                parents=dict(sql(db,'SELECT id,event_id FROM '+name))
                require(all(r['id'] not in parents or parents[r['id']]==r['event_id'] for r in t[name]), 'Identidad externa de otro evento.')
            require(not sql(db,'SELECT 1 FROM games g JOIN sets s ON s.id=g.set_id WHERE s.event_id=%s LIMIT 1',(eid,)), 'Games existentes: no borrar contexto ajeno.')
            # Only our known small events can be refreshed; never delete unmarked live data.
            require(not sql(db,'SELECT 1 FROM sets WHERE event_id=%s LIMIT 1',(eid,)) or sql(db,'SELECT 1 FROM organizer_event_context WHERE event_id=%s',(eid,)), 'Contexto existente sin marca de organizador.')
        # Preserve global identities (same policy as normal import), refresh only small-event graph.
        expected_global={}
        for name in ('players','tournaments'):
            cols=COLUMNS[name].split();expected_global[name]=[]
            for row in t[name]:
                present=sql(db,'SELECT '+','.join(cols)+' FROM '+name+' WHERE id=%s FOR UPDATE',(row['id'],))
                expected_global[name].append(present[0] if present else tuple(row.get(c) for c in cols))
            insert_rows(db,name,COLUMNS[name],t[name],keep_existing=True)
        for eid in event_ids:
            sql(db,'DELETE FROM set_slots WHERE event_id=%s',(eid,))
            sql(db,'DELETE FROM sets WHERE event_id=%s',(eid,))
            sql(db,'DELETE ep FROM entrant_players ep JOIN entrants e ON e.id=ep.entrant_id WHERE e.event_id=%s',(eid,))
            sql(db,'DELETE FROM entrants WHERE event_id=%s',(eid,))
        for r in t['events']:
            cols=COLUMNS['events'].split()
            if sql(db,'SELECT 1 FROM events WHERE id=%s',(r['id'],)):
                sql(db,'UPDATE events SET '+','.join(c+'=%s' for c in cols[1:])+' WHERE id=%s',tuple(r.get(c) for c in cols[1:])+(r['id'],))
            else: insert_rows(db,'events',COLUMNS['events'],[r])
        for name in ('entrants','entrant_players','sets','set_slots'):
            insert_rows(db,name,COLUMNS[name],t[name])
        markers=[]
        for event in t['events']:
            valid=sum(s['event_id']==event['id'] and s['outcome_type']=='competitive' for s in t['sets'])
            markers.append(dict(event_id=event['id'],cut_id=cut_id,captured_at=instant(context['capturedAt']),active_players=event['active_players'],valid_sets=valid,context_hash=digest(context)))
            sql(db,'DELETE FROM organizer_event_context WHERE event_id=%s',(event['id'],))
        insert_rows(db,'organizer_event_context',MARKER_COLUMNS,markers)
        # Table-by-table parity: shared player/tournament identities are deliberately first observed;
        # verify existence for these, and every column exactly for the refreshed event graph.
        for name in TABLES:
            if name in ('players','tournaments'):
                actual=[sql(db,'SELECT '+COLUMNS[name].replace(' ', ',')+' FROM '+name+' WHERE id=%s',(r['id'],))[0] for r in t[name]]
                normalize=lambda row:tuple(instant(v.isoformat()+'+00:00') if hasattr(v,'isoformat') else v for v in row)
                require(sorted(map(normalize,actual),key=repr)==sorted(map(normalize,expected_global[name]),key=repr), 'Identidad pequeña alterada.')
                continue
            cols=COLUMNS[name].split()
            if name=='events': rows=tuple(row for eid in event_ids for row in sql(db,'SELECT '+','.join(cols)+' FROM events WHERE id=%s',(eid,)))
            elif name in ('entrants','sets'): rows=tuple(row for eid in event_ids for row in sql(db,'SELECT '+','.join(cols)+' FROM '+name+' WHERE event_id=%s',(eid,)))
            else:
                parent='entrants' if name=='entrant_players' else 'sets';key='entrant_id' if name=='entrant_players' else 'set_id'
                rows=tuple(row for eid in event_ids for row in sql(db,'SELECT '+','.join('r.'+c for c in cols)+' FROM '+name+' r JOIN '+parent+' p ON p.id=r.'+key+' WHERE p.event_id=%s',(eid,)))
            normalized=lambda row:tuple(instant(v.isoformat()+'+00:00') if hasattr(v,'isoformat') else v for v in row)
            require({normalized(r) for r in rows}=={tuple(r.get(c) for c in cols) for r in t[name]} and len(rows)==len(t[name]), 'Paridad de contexto pequeño falló.')
        if marker_subset:
            found=tuple(row for eid in event_ids for row in sql(db,'SELECT '+MARKER_COLUMNS.replace(' ', ',')+' FROM organizer_event_context WHERE event_id=%s',(eid,)))
        else:
            found=sql(db,'SELECT '+MARKER_COLUMNS.replace(' ', ',')+' FROM organizer_event_context WHERE cut_id=%s',(cut_id,))
        require({tuple(instant(v.isoformat()+'+00:00') if hasattr(v,'isoformat') else v for v in r) for r in found}=={tuple(r[c] for c in MARKER_COLUMNS.split()) for r in markers}, 'Paridad de marcadores falló.')
        sql(db,'RELEASE SAVEPOINT organizer_context')
        return dict(plan,status='imported')
    except Exception:
        sql(db,'ROLLBACK TO SAVEPOINT organizer_context');sql(db,'RELEASE SAVEPOINT organizer_context')
        return dict(plan,status='skipped_context_error')
