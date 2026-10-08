"""Offline package and CLI-only initial game context load. Dry run is SQL READ ONLY.

An original ranking package is required as proof. Only games/game_selections may be written;
no endpoint, provider request, migration, cut rewrite or normal-import shortcut is introduced.
"""
import argparse
import copy
import gzip
import json
from pathlib import Path
import re
import resource
import sys
import time
from ranking_package import canonical, digest, identifier, instant, require, validate_package
from import_ranking import COLUMNS, LOCK, context_rows, insert_rows, sql, verify_parity, verify_schema

MAX_BYTES = 32 * 1024 * 1024


class ContextStopped(Exception):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def ensure(ok, reason):
    if not ok:
        raise ContextStopped(reason)


def build_context(original, captured, cut_id):
    old, new = validate_package(original), validate_package(captured)
    require(new['packageVersion'] == 2, 'Games require a captured v2 package.')
    require(old['public'] == new['public'] and old['capturedAt'] == new['capturedAt'], 'Cut changed.')
    require(all(old['entities'][k] == new['entities'][k] for k in old['entities'] if k not in ('games','game_selections')), 'Source identities changed.')
    p = old['public']
    content = dict(contextVersion=1, kind='initial_game_context',
        anchor=dict(cutId=identifier(cut_id), sourceHash=original['sha256'], generatedAt=p['generatedAt'],
                    seasonYear=p['seasonYear'], methodVersion=p['methodVersion'], characterCapturedAt=p['characterCapturedAt']),
        gameContextSetIds=new['gameContextSetIds'],
        entities={k:copy.deepcopy(new['entities'][k]) for k in ('games','game_selections')})
    return dict(content=content, sha256=digest(content))


def validate_context(package, original):
    base = validate_package(original)
    require(set(package) == {'content','sha256'} and package['sha256'] == digest(package['content']), 'Context hash invalid.')
    c = package['content']; p = base['public']
    require(set(c) == {'contextVersion','kind','anchor','gameContextSetIds','entities'} and type(c['contextVersion']) is int
            and c['contextVersion'] == 1 and c['kind'] == 'initial_game_context', 'Context contract invalid.')
    require(c['anchor'] == dict(cutId=identifier(c['anchor']['cutId']),sourceHash=original['sha256'],generatedAt=p['generatedAt'],
        seasonYear=p['seasonYear'],methodVersion=p['methodVersion'],characterCapturedAt=p['characterCapturedAt']), 'Anchor invalid.')
    require(set(c['entities']) == {'games','game_selections'}, 'Only game context is allowed.')
    proof = copy.deepcopy(base); proof['packageVersion'] = 2
    proof['gameContextSetIds'] = c['gameContextSetIds']; proof['entities'].update(c['entities'])
    validate_package(dict(content=proof,sha256=digest(proof)))  # Same relations, catalog and mains rules as the weekly package.
    return c


def normalize(rows):
    return {tuple(instant(v.isoformat()+'+00:00') if hasattr(v,'isoformat') else v for v in row) for row in rows}


def read_games(db):
    return {k:sql(db,'SELECT '+','.join(COLUMNS[k].split())+' FROM '+k) for k in ('games','game_selections')}


def inspect_context(db, original, c):
    p=original['content']['public']; a=c['anchor']
    cuts=sql(db,'SELECT id,generated_at,season_year,method_version,source_hash,status FROM cuts')
    ensure(len(cuts)==1 and cuts[0][0]==a['cutId'], 'later_or_other_cut')
    row=cuts[0]
    ensure((instant(row[1].isoformat()+'+00:00'),row[2],row[3],row[4],row[5]) ==
           (instant(a['generatedAt']),a['seasonYear'],a['methodVersion'],a['sourceHash'],'published'), 'cut_anchor_conflict')
    verify_parity(db,original['content'],a['cutId'])
    covered=c['gameContextSetIds']; tables=original['content']['entities']
    # Compare all context parents against the original proof. A live correction is a conflict.
    for table,columns,ids,id_column in (
        ('sets',COLUMNS['sets'],covered,'id'),
        ('set_slots',COLUMNS['set_slots'],covered,'set_id')):
        wanted_ids=set(ids)
        expected=[tuple(r.get(col) for col in columns.split()) for r in tables[table] if r[id_column] in wanted_ids]
        found=context_rows(db,table,columns,ids,id_column=id_column)
        ensure(normalize(found)==set(expected) and len(found)==len(expected), 'source_relations_changed')
    covered_set=set(covered)
    entrants=sorted({r['entrant_id'] for r in tables['set_slots'] if r['set_id'] in covered_set and r['entrant_id'] is not None})
    found=context_rows(db,'entrant_players','entrant_id player_id',entrants,id_column='entrant_id')
    entrant_ids=set(entrants)
    wanted={(r['entrant_id'],r['player_id']) for r in tables['entrant_players'] if r['entrant_id'] in entrant_ids}
    ensure(set(found)==wanted and len(found)==len(wanted), 'source_relations_changed')
    known={r[0] for r in sql(db,'SELECT id FROM characters')}
    ensure({r['character_id'] for r in c['entities']['game_selections']} <= known, 'catalog_missing')
    current=read_games(db)
    matches=all(normalize(current[k]) == {tuple(r[col] for col in COLUMNS[k].split()) for r in c['entities'][k]}
                and len(current[k])==len(c['entities'][k]) for k in current)
    empty=all(not current[k] for k in current)
    ensure(matches or empty, 'existing_game_context_conflict')
    return current,matches


def import_context(db, original, package, *, apply=False):
    c=validate_context(package,original)
    ensure(not db.get_transaction_status() if hasattr(db,'get_transaction_status') else not (db.server_status & 1), 'existing_transaction')
    ensure(sql(db,'SELECT GET_LOCK(%s,0)',(LOCK,))[0][0]==1, 'importer_busy')
    try:
        verify_schema(db)
        db.rollback()
        # Serializable reads lock the source/gaps during apply; dry run is enforced READ ONLY.
        sql(db,'SET TRANSACTION ISOLATION LEVEL '+('SERIALIZABLE' if apply else 'REPEATABLE READ'))
        sql(db,'SET TRANSACTION '+('READ WRITE' if apply else 'READ ONLY'))
        db.begin()
        current,matches=inspect_context(db,original,c)
        report=dict(cutId=c['anchor']['cutId'],sourceHash=c['anchor']['sourceHash'],contextHash=package['sha256'],
            contextSets=len(c['gameContextSetIds']),existing={k:len(v) for k,v in current.items()},
            expected={k:len(v) for k,v in c['entities'].items()},readOnly=not apply)
        if matches:
            db.rollback(); return dict(report,status='already_imported')
        if not apply:
            db.rollback(); return dict(report,status='validated_no_writes')
        for table in ('games','game_selections'):
            insert_rows(db,table,COLUMNS[table],c['entities'][table])
        _,matches=inspect_context(db,original,c)
        ensure(matches,'game_parity_failed')
        db.commit()
        return dict(report,status='context_imported')
    except Exception:
        db.rollback()
        raise
    finally:
        sql(db,'SELECT RELEASE_LOCK(%s)',(LOCK,))


def read_package(path):
    require(not path.is_symlink() and path.stat().st_size <= MAX_BYTES, 'Package too large or linked.')
    return json.loads(path.read_text())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    build=sub.add_parser('build',help='Build offline from the original package and captured v2 package')
    build.add_argument('original',type=Path); build.add_argument('captured',type=Path); build.add_argument('output',type=Path)
    build.add_argument('--cut-id',type=int,required=True)
    load=sub.add_parser('load',help='Read-only simulation unless --apply is explicitly given')
    load.add_argument('context',type=Path); load.add_argument('--original',type=Path,required=True)
    load.add_argument('--defaults-file',type=Path,default=Path.home()/'.my.cnf')
    load.add_argument('--database',required=True); load.add_argument('--apply',action='store_true')
    args=parser.parse_args(); db=None; start=time.monotonic()
    try:
        original=read_package(args.original)
        if args.command=='build':
            result=build_context(original,read_package(args.captured),args.cut_id); validate_context(result,original)
            body=canonical(result).encode(); require(len(body)<=MAX_BYTES,'Context too large.')
            compressed=gzip.compress(body,mtime=0)
            require(len(compressed)<=4*1024*1024,'Compressed context too large.')
            require(not args.output.is_symlink() and not args.output.exists(),'Output already exists.')
            with args.output.open('xb') as out:
                args.output.chmod(0o600); out.write(body)
            report=dict(status='context_built',contextHash=result['sha256'],canonicalBytes=len(body),gzipBytes=len(compressed),
                expected={k:len(v) for k,v in result['content']['entities'].items()})
        else:
            require(re.fullmatch('[A-Za-z0-9_]+',args.database) is not None,'Invalid database.')
            require(args.defaults_file.is_file() and args.defaults_file.stat().st_mode & 0o077 == 0,'Private defaults required.')
            package=read_package(args.context); validate_context(package,original)
            import pymysql
            db=pymysql.connect(read_default_file=str(args.defaults_file),database=args.database,charset='utf8mb4',autocommit=False,
                connect_timeout=10,read_timeout=120,write_timeout=120)
            report=import_context(db,original,package,apply=args.apply)
        report['seconds']=round(time.monotonic()-start,3)
        rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        report['processPeakRssBytes']=rss if sys.platform=='darwin' else rss*1024
        print(json.dumps(report,ensure_ascii=False))
    except ContextStopped as e:
        print(json.dumps(dict(ok=False,reason=e.reason))); return 1
    except Exception:
        # Never expose connection strings, credentials, queries or raw driver errors.
        print(json.dumps(dict(ok=False,reason='context_rejected'))); return 1
    finally:
        if db is not None: db.close()
    return 0


if __name__=='__main__': sys.exit(main())
