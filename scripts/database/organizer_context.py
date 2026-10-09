"""Small-event transport extension; national packages/hashes and cut ledgers stay intact."""
import copy
from datetime import datetime
import gzip

# Imported lazily by ranking_package to keep legacy V1-V3 code and canonical output unchanged.
TABLES=('players','tournaments','events','entrants','entrant_players','sets','set_slots')
MARKER_COLUMNS='event_id cut_id captured_at active_players valid_sets context_hash'


def validate_context(context, base):
    from ranking_package import require, identifier, instant, digest, validate_package
    require(isinstance(context,dict) and set(context)=={'schemaVersion','capturedAt','entities','eligibility'}, 'Complemento inválido.')
    require(type(context['schemaVersion']) is int and context['schemaVersion']==1, 'Versión de complemento inválida.')
    require(context['capturedAt']==base['content']['capturedAt'], 'Complemento de otro corte.')
    tables=context['entities']; require(isinstance(tables,dict) and set(tables)==set(TABLES), 'Tablas de complemento inválidas.')
    core=base['content']; old=core['entities']
    event_ids={identifier(e['id']) for e in tables['events']}
    require(isinstance(context['eligibility'],list) and len(context['eligibility'])==len(event_ids)
            and {r['event_id'] for r in context['eligibility']}==event_ids
            and all(set(r)=={'event_id','is_online','state','entrant_size'} and r['is_online'] is False and r['state']=='COMPLETED' and type(r['entrant_size']) is int and r['entrant_size']==1 for r in context['eligibility']), 'Formato o estado pequeño inválido.')
    require(len(event_ids)==len(tables['events']) and 0<len(event_ids)<=10, 'Eventos pequeños duplicados o fuera de límite.')
    require(not event_ids.intersection(identifier(e['id']) for e in old['events']), 'Complemento no puede capturar un evento nacional.')
    for name in ('entrants','sets'):
        require(not {identifier(r['id']) for r in tables[name]}.intersection(identifier(r['id']) for r in old[name]), 'Identidad pequeña colisiona con el corte.')
    merged=copy.deepcopy(core)
    for name in TABLES:
        rows={r['id'] if 'id' in r else tuple(r[k] for k in ('entrant_id','player_id') if k in r):r for r in old[name]} if name not in ('set_slots',) else {(r['set_id'],r['slot_index']):r for r in old[name]}
        seen=set()
        for r in tables[name]:
            key=r['id'] if 'id' in r else (r['set_id'],r['slot_index']) if name=='set_slots' else (r['entrant_id'],r['player_id'])
            require(key not in seen, 'Fila pequeña duplicada.');seen.add(key)
            if key in rows:
                require(name in ('players','tournaments') and rows[key]==r, 'Identidad compartida contradictoria.')
            rows[key]=r
        merged['entities'][name]=list(rows.values())
    validate_package(dict(content=merged,sha256=digest(merged)))
    tournaments={r['id']:r for r in tables['tournaments']}
    slots={r['set_id']:[] for r in tables['set_slots']}
    links={r['entrant_id']:r['player_id'] for r in tables['entrant_players']}
    require(len(links)==len(tables['entrant_players']), 'Entrant pequeño con varios jugadores.')
    for r in tables['set_slots']: slots[r['set_id']].append(r['entrant_id'])
    for event in tables['events']:
        require(tournaments.get(event['tournament_id'],{}).get('country_code')=='GT' and event['videogame_id']==1386
                and event['entrant_size']==1 and type(event['registered_entrants']) is int and 1<=event['registered_entrants']<20,
                'Solo singles pequeños de Guatemala.')
        require(event['starts_at'] is not None and event['starts_at']<=instant(core['capturedAt']), 'Evento futuro en complemento.')
        active=set();valid=0
        for match in tables['sets']:
            if match['event_id']!=event['id']:continue
            require(match['status']=='completed' and match['source_state']==3, 'Set pequeño sin terminar.')
            if match['outcome_type']=='competitive':
                pair=slots[match['id']]
                require(len(pair)==2 and None not in pair and len(set(pair))==2 and all(e in links for e in pair), 'Set válido sin dos jugadores.')
                active.update(links[e] for e in pair);valid+=1
        require(event['active_players']==len(active) and valid>=1 and len(active)>=2, 'Evento pequeño sin actividad verificable.')
    # Reject stray rows; the subset must be exactly the graph of the selected events/sets.
    require(all(r['event_id'] in event_ids for r in tables['entrants']+tables['sets']), 'Fila ajena al complemento.')
    require({r['id'] for r in tables['tournaments']}=={e['tournament_id'] for e in tables['events']}, 'Torneo sin evento pequeño.')
    require({r['id'] for r in tables['players']}==set(links.values()), 'Jugador ajeno al complemento.')
    require({r['set_id'] for r in tables['set_slots']}=={r['id'] for r in tables['sets']}, 'Slots ajenos al complemento.')
    require(all(r['synced_at']==instant(core['capturedAt']) for name in ('players','tournaments','events','entrants','sets') for r in tables[name]), 'Fechas de complemento incompatibles.')
    return context


def extend_package(base, raw, context):
    from ranking_package import build_package, require, identifier, digest, canonical
    require(isinstance(context,dict) and context.get('kind')=='organizer_small_context' and context.get('complete') is True and context.get('schemaVersion')==1,
            'Captura pequeña incompleta.')
    require(isinstance(context.get('events'),list) and all(isinstance(e,dict) and isinstance(e.get('tournament'),dict) for e in context['events'])
            and isinstance(context.get('players'),dict) and isinstance(context.get('sets'),dict), 'Grafo pequeño inválido.')
    require(context['nationalGeneratedAt']==raw.get('nationalGeneratedAt',raw['generatedAt']) and context.get('season')==raw.get('season'), 'Captura pequeña de otra temporada/captura nacional.')
    require(datetime.fromisoformat(context['capturedAt'])<=datetime.fromisoformat(raw['generatedAt']), 'Captura pequeña posterior al corte.')
    require(all(e.get('state')=='COMPLETED' and e.get('isOnline') is False and e.get('type')==1
                and e['tournament'].get('countryCode')=='GT' for e in context['events']), 'Formato pequeño no admisible.')
    merged=copy.deepcopy(raw)
    require(not {str(e['id']) for e in raw['events']}.intersection(str(e['id']) for e in context['events']), 'Evento pequeño ya capturado para el nacional.')
    merged['events']+=context['events']
    for name in ('players','sets'):
        if name=='sets': require(not set(merged[name]).intersection(context[name]), 'Set pequeño ya presente.')
        merged[name]={**context[name],**merged[name]} # national identities keep precedence
    expanded=build_package(merged,base['content']['public'])['content']['entities']
    event_ids={identifier(e['id']) for e in context['events']}
    selected={name:[r for r in expanded[name] if r['event_id'] in event_ids] for name in ('entrants','sets')}
    entrant_ids={r['id'] for r in selected['entrants']};set_ids={r['id'] for r in selected['sets']}
    selected['events']=[r for r in expanded['events'] if r['id'] in event_ids]
    selected['set_slots']=[r for r in expanded['set_slots'] if r['set_id'] in set_ids]
    selected['entrant_players']=[r for r in expanded['entrant_players'] if r['entrant_id'] in entrant_ids]
    pids={r['player_id'] for r in selected['entrant_players']};tids={r['tournament_id'] for r in selected['events']}
    selected['players']=[r for r in expanded['players'] if r['id'] in pids]
    selected['tournaments']=[r for r in expanded['tournaments'] if r['id'] in tids]
    small=dict(schemaVersion=1,capturedAt=raw['generatedAt'],entities=selected,
               eligibility=[dict(event_id=e['id'],is_online=False,state='COMPLETED',entrant_size=1) for e in selected['events']])
    validate_context(small,base)
    c=dict(base['content'],packageVersion=4,nationalPackageVersion=base['content']['packageVersion'],nationalSha256=base['sha256'],organizerContext=small)
    result=dict(content=c,sha256=digest(c))
    body=canonical(result).encode()
    require(len(body)<=32*1024*1024 and len(gzip.compress(body,mtime=0))<=4*1024*1024, 'Complemento supera el transporte; usar corte solo.')
    return result


def national_package(package):
    from ranking_package import require, digest
    c=package['content']
    if c.get('packageVersion')!=4:return package
    require(type(c.get('nationalPackageVersion')) is int and c['nationalPackageVersion'] in (1,2,3), 'Versión nacional inválida.')
    core={k:v for k,v in c.items() if k not in ('nationalPackageVersion','nationalSha256','organizerContext')}
    core['packageVersion']=c['nationalPackageVersion']
    require(digest(core)==c.get('nationalSha256'), 'Hash nacional del complemento inválido.')
    return dict(content=core,sha256=c['nationalSha256'])
