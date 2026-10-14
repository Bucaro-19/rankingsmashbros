"""One-off analysis context: roster → bounded capture → validated SQL plan (default).

Does not call the ranking importer, write cuts/ledgers/rankings or change eligibility.
Existing identities/results/games are never replaced, including national context.
"""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import gzip
import json
import os
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'smash'))
from collect import Client, APIError
from rival_history import roster, new_state, capture_batch, save, MAX_BYTES
from ranking_package import (normalize_capture_entities, validate_entity_relations, canonical,
                             digest, identifier, instant, integer, require, character_ids)
from import_ranking import COLUMNS, LOCK, sql, insert_rows, verify_schema
from weekly_ranking_load import connect
from small_events_backfill import begin


def package(data):
    require(data['kind']=='analysis_history' and data['schemaVersion']==1,'History kind.')
    players=dict(data['roster']['players']);events={};matches={}
    for sid,m in data['sets'].items():
        e=dict(m['event']);e['setsFetched']=0
        eid=str(e['id']);events[eid]=e
        for slot in m['slots']:
            for p in (slot.get('entrant') or {}).get('participants') or []:
                if p.get('player'): players[str(p['player']['id'])]=p['player']
        matches[sid]=dict(m,tournament=e['tournament'])
    for eid,e in events.items():
        e['setsFetched']=sum(str(m['event']['id'])==eid for m in matches.values())
        # The shared normalizer expects an integer. Restore missing source counts below;
        # the number of opponents in a player's history is NOT event attendance/activity.
        e['numEntrants']=e.get('numEntrants') if e.get('numEntrants') is not None else 0
    raw=dict(generatedAt=data['capturedAt'],players=players,events=list(events.values()),sets=matches)
    indexed,ep,slots,_,_,_=normalize_capture_entities(raw)
    tables={k:[v[x] for x in sorted(v)] for k,v in indexed.items()}
    tables['entrant_players']=[ep[x] for x in sorted(ep)];tables['set_slots']=[slots[x] for x in sorted(slots)]
    for e in tables['events']:
        src=next(m['event'] for m in matches.values() if identifier(m['event']['id'])==e['id'])
        e['registered_entrants']=src.get('numEntrants');e['active_players']=None
    games={};selections=[];scores=[];known=character_ids()
    for s in tables['sets']:
        if s['outcome_type']!='competitive': continue
        m=matches[str(s['id'])];ens={identifier(x['entrant']['id']) for x in m['slots']}
        for g in m.get('games') or []:
            number=g.get('orderNum');gid=g.get('id');win=g.get('winnerId')
            if type(number) is not int or number<1 or gid is None or win is None or identifier(win) not in ens:continue
            gid=identifier(gid);require(gid not in games,'Repeated game.')
            games[gid]=dict(id=gid,set_id=s['id'],game_number=number,winner_entrant_id=identifier(win),stage_id=(g.get('stage') or {}).get('id'),synced_at=instant(data['capturedAt']))
            picks=defaultdict(set)
            for pick in g.get('selections') or []:
                en=(pick.get('entrant') or {}).get('id');char=(pick.get('character') or {}).get('id')
                if en is not None and char is not None and identifier(en) in ens:picks[identifier(en)].add(identifier(char))
            for en,chars in picks.items():
                if len(chars)==1 and next(iter(chars)) in known:selections.append(dict(game_id=gid,set_id=s['id'],entrant_id=en,character_id=next(iter(chars))))
            scores.append(dict(game_id=gid,entrant1_score=g.get('entrant1Score'),entrant2_score=g.get('entrant2Score')))
    tables['games']=[games[x] for x in sorted(games)];tables['game_selections']=selections
    content=dict(contextVersion=1,kind='rival_analysis_only',seasonYear=data['seasonYear'],capturedAt=data['capturedAt'],
        sourceEventId=identifier(data['roster']['event']['id']),rootPlayerIds=sorted(map(identifier,data['roster']['players'])),
        entities=tables,gameScores=scores,audit=data['audit'],coverage=data['coverage'])
    result=dict(content=content,sha256=digest(content));validate(result);return result


def validate(p):
    require(set(p)=={'content','sha256'} and p['sha256']==digest(p['content']),'Hash.')
    c=p['content'];require(set(c)=={'contextVersion','kind','seasonYear','capturedAt','sourceEventId','rootPlayerIds','entities','gameScores','audit','coverage'},'Content fields.')
    require(c['kind']=='rival_analysis_only' and type(c['contextVersion']) is int and c['contextVersion']==1,'Context kind.')
    integer(c['seasonYear'],minimum=2000,maximum=2100);instant(c['capturedAt']);identifier(c['sourceEventId'])
    t=c['entities'];require(set(t)==set(COLUMNS),'Entity tables.')
    ids,slots,links=validate_entity_relations(t)
    require(len(t['sets'])<=5000,'Set ceiling.')
    from discover import season_timestamp
    low=datetime.fromtimestamp(season_timestamp(f"{c['seasonYear']}-01-01"),timezone.utc).replace(tzinfo=None).isoformat(sep=' ',timespec='microseconds')
    high=datetime.fromtimestamp(season_timestamp(f"{c['seasonYear']+1}-01-01"),timezone.utc).replace(tzinfo=None).isoformat(sep=' ',timespec='microseconds')
    for e in t['events']: require(e['videogame_id']==1386 and e['entrant_size']==1 and low<=e['starts_at']<high,'Event season/game/type.')
    require(0<len(c['rootPlayerIds'])<=1000 and len(set(c['rootPlayerIds']))==len(c['rootPlayerIds']) and set(c['rootPlayerIds'])<=ids['players'].keys(),'Root identities.')
    for table,rows in t.items():
        require(all(set(r)<=set(COLUMNS[table].split()) for r in rows),'Unknown columns.')
    gameids={identifier(g['id']):g for g in t['games']};require(len(gameids)==len(t['games']),'Duplicate games.')
    seen=set();validchars=character_ids()
    for g in t['games']:
        sid=identifier(g['set_id']);require(sid in ids['sets'] and ids['sets'][sid]['outcome_type']=='competitive','Game set.')
        number=integer(g['game_number'],minimum=1,maximum=65535);require((sid,number) not in seen,'Game number.');seen.add((sid,number))
        require(g['winner_entrant_id'] in [slots[(sid,i)]['entrant_id'] for i in range(2)],'Game winner.');require(g['synced_at']==instant(c['capturedAt']),'Game date.')
    seen=set()
    for r in t['game_selections']:
        gid=identifier(r['game_id']);en=identifier(r['entrant_id']);sid=identifier(r['set_id'])
        require(gid in gameids and gameids[gid]['set_id']==sid and en in [slots[(sid,i)]['entrant_id'] for i in range(2)] and identifier(r['character_id']) in validchars and (gid,en) not in seen,'Selection relation.');seen.add((gid,en))
    require(len(c['gameScores'])==len(gameids) and {r['game_id'] for r in c['gameScores']}==set(gameids),'Game scores coverage.')
    for r in c['gameScores']:
        require(set(r)=={'game_id','entrant1_score','entrant2_score'},'Score fields.')
        for key in ('entrant1_score','entrant2_score'):
            if r[key] is not None: integer(r[key],minimum=-2147483648,maximum=2147483647)
    require(len(canonical(p).encode())<=MAX_BYTES and len(gzip.compress(canonical(p).encode(),mtime=0))<=4*1024*1024,'Package size ceiling.')


def existing(db,table,ids,columns='id'):
    out=[]
    for start in range(0,len(ids),500):
        part=ids[start:start+500]
        if part:out.extend(sql(db,'SELECT '+columns+' FROM '+table+' WHERE '+('entrant_id' if table=='entrant_players' else 'id')+' IN ('+','.join(['%s']*len(part))+')',part))
    return out


def plan(db,c):
    t=c['entities'];found={table:dict(existing(db,table,[r['id'] for r in t[table]],'id,'+field)) for table,field in [('events','tournament_id'),('entrants','event_id'),('sets','event_id'),('games','set_id')]}
    for table,field in [('events','tournament_id'),('entrants','event_id'),('sets','event_id'),('games','set_id')]:
        require(all(r['id'] not in found[table] or found[table][r['id']]==r[field] for r in t[table]),'Existing foreign relation conflict.')
    wanted={r['entrant_id']:r['player_id'] for r in t['entrant_players']}
    require(all(wanted.get(en)==pid for en,pid in existing(db,'entrant_players',list(wanted),'entrant_id,player_id')),'Existing entrant identity conflict.')
    expected={(r['set_id'],r['slot_index']):(r['event_id'],r['entrant_id']) for r in t['set_slots']}
    old=list(found['sets'])
    for start in range(0,len(old),500):
        part=old[start:start+500]
        if part:
            for sid,index,eid,en in sql(db,'SELECT set_id,slot_index,event_id,entrant_id FROM set_slots WHERE set_id IN ('+','.join(['%s']*len(part))+')',part):
                require(expected.get((sid,index))==(eid,en),'Existing set participants differ.')
    selected={r['id'] for r in t['sets'] if r['id'] not in found['sets']}
    newgames={g['id'] for g in t['games'] if g['set_id'] in selected}
    require(not (newgames & found['games'].keys()),'Existing game cannot move.')
    rows={k:list(v) for k,v in t.items()}
    rows['sets']=[r for r in t['sets'] if r['id'] in selected]
    rows['set_slots']=[r for r in t['set_slots'] if r['set_id'] in selected]
    rows['games']=[r for r in t['games'] if r['id'] in newgames]
    rows['game_selections']=[r for r in t['game_selections'] if r['game_id'] in newgames]
    scores=[r for r in c['gameScores'] if r['game_id'] in newgames]
    return rows,scores,dict(roots=len(c['rootPlayerIds']),newRosterPlayers=len(c['rootPlayerIds'])-len(existing(db,'players',c['rootPlayerIds'])),newPlayers=len(t['players'])-len(existing(db,'players',[r['id'] for r in t['players']])),newSets=len(selected),existingSetsKept=len(t['sets'])-len(selected),newGames=len(newgames),newSelections=len(rows['game_selections']))


def load(db,p,*,apply=False):
    validate(p);c=p['content'];locked=False
    try:
        if apply:
            require(sql(db,'SELECT GET_LOCK(%s,0)',(LOCK,))==((1,),),'Importer busy.');locked=True
        begin(db,apply);verify_schema(db)
        ready=bool(sql(db,"SELECT version FROM schema_migrations WHERE version='007_analysis_context'"))
        if ready:
            engines=dict(sql(db,"SELECT table_name,engine FROM information_schema.tables WHERE table_schema=DATABASE()"))
            require(all(engines.get(k)=='InnoDB' for k in ('analysis_context_batches','analysis_context_players','analysis_game_scores')),'Transactional context tables required.')
        rows,scores,counts=plan(db,c)
        if not ready:
            require(not apply,'Migration 007 required; not applied by this tool.')
            return dict(status='migration_required_no_writes',**counts)
        if sql(db,'SELECT source_hash FROM analysis_context_batches WHERE source_hash=%s',(p['sha256'],)):
            return dict(status='already_imported',**counts)
        if not apply:return dict(status='validated_no_writes',**counts)
        for table in COLUMNS:insert_rows(db,table,COLUMNS[table],rows[table],keep_existing=True)
        insert_rows(db,'analysis_game_scores','game_id entrant1_score entrant2_score',scores,keep_existing=True)
        sql(db,'INSERT INTO analysis_context_batches(source_hash,source_event_id,season_year,captured_at) VALUES (%s,%s,%s,%s)',(p['sha256'],c['sourceEventId'],c['seasonYear'],instant(c['capturedAt'])))
        for pid in c['rootPlayerIds']:
            sql(db,'INSERT INTO analysis_context_players(player_id,season_year,source_hash) VALUES (%s,%s,%s) ON DUPLICATE KEY UPDATE source_hash=VALUES(source_hash)',(pid,c['seasonYear'],p['sha256']))
        require(len(sql(db,'SELECT player_id FROM analysis_context_players WHERE season_year=%s AND player_id IN ('+','.join(['%s']*len(c['rootPlayerIds']))+')',[c['seasonYear']]+c['rootPlayerIds']))==len(c['rootPlayerIds']),'Root parity.')
        for r in rows['sets']:require(sql(db,'SELECT event_id,winner_entrant_id,source_hash FROM sets WHERE id=%s',(r['id'],))==((r['event_id'],r['winner_entrant_id'],r['source_hash']),),'Set parity.')
        for r in rows['games']:require(sql(db,'SELECT set_id,game_number,winner_entrant_id FROM games WHERE id=%s',(r['id'],))==((r['set_id'],r['game_number'],r['winner_entrant_id']),),'Game parity.')
        for r in rows['game_selections']:require(sql(db,'SELECT character_id FROM game_selections WHERE game_id=%s AND entrant_id=%s',(r['game_id'],r['entrant_id']))==((r['character_id'],),),'Selection parity.')
        for r in scores:require(sql(db,'SELECT entrant1_score,entrant2_score FROM analysis_game_scores WHERE game_id=%s',(r['game_id'],))==((r['entrant1_score'],r['entrant2_score']),),'Score parity.')
        db.commit();return dict(status='imported',**counts)
    finally:
        db.rollback()
        if locked:sql(db,'SELECT RELEASE_LOCK(%s)',(LOCK,));db.rollback()


def read_private_json(path):
    path=Path(path)
    require(path.suffix=='.json' and not path.is_symlink() and path.is_file(),'Private JSON input required.')
    require(path.stat().st_size<=MAX_BYTES,'Input ceiling.')
    with path.open('rb') as source:
        body=source.read(MAX_BYTES+1)
    require(len(body)<=MAX_BYTES,'Input ceiling.')
    return json.loads(body)


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    r=sub.add_parser('roster');r.add_argument('--slug',required=True);r.add_argument('--output',type=Path,required=True)
    inv=sub.add_parser('inventory');inv.add_argument('roster',type=Path);inv.add_argument('--year',type=int,default=2026);inv.add_argument('--output',type=Path,required=True)
    cap=sub.add_parser('capture');cap.add_argument('state',type=Path);cap.add_argument('--output',type=Path,required=True)
    ld=sub.add_parser('load');ld.add_argument('package',type=Path);ld.add_argument('--apply',action='store_true')
    for s in (inv,ld):s.add_argument('--defaults-file',type=Path,default=Path.home()/'.my.cnf');s.add_argument('--database',default='ivcjgjlk_smash')
    a=p.parse_args();db=None
    try:
        if a.action in ('roster','capture'):
            token=os.environ.get('STARTGG_TOKEN','').strip();require(bool(token),'STARTGG_TOKEN required in private environment.')
            client=Client(token)
        if a.action=='roster':
            started=__import__('time').monotonic();v=roster(client,a.slug);save(a.output,v);result=dict(status='verified_roster',registered=v['registrations'],requests=client.calls,seconds=round(__import__('time').monotonic()-started,3))
        elif a.action=='inventory':
            v=read_private_json(a.roster);db=connect(a.defaults_file,a.database);begin(db)
            ids=[identifier(x) for x in v['players']];known=[x[0] for x in existing(db,'players',ids)];db.rollback()
            save(a.output,new_state(v,known,a.year));result=dict(status='inventory_no_writes',registered=len(ids),known=len(known),missing=len(ids)-len(known))
        elif a.action=='capture':
            data,state=capture_batch(client,read_private_json(a.state));pack=package(data);save(a.output,pack);save(a.state,state,replace=True);result=dict(status='captured_no_sql_writes',**data['audit'])
        else:db=connect(a.defaults_file,a.database);result=load(db,read_private_json(a.package),apply=a.apply)
        print(json.dumps(result))
    except Exception:
        p.exit(1,'Analysis context stopped. No ranking/publication change. Check source availability, budget, schema and private configuration; no raw provider/database error is printed.\n')
    finally:
        if db:db.close()
if __name__=='__main__':main()
