"""Import a validated private package. Dry run by default; no public HTTP endpoint."""
import argparse
from pathlib import Path
import json
import re

from ranking_package import canonical, identifier, instant, require, validate_package

# SQL identifiers are fixed in source, never supplied by the package or request.
COLUMNS = {
 'players': 'id tag known_as country_code country_basis profile_url synced_at',
 'tournaments': 'id name slug country_code url synced_at',
 'events': 'id tournament_id name videogame_id entrant_size starts_at registered_entrants active_players url synced_at',
 'entrants': 'id event_id name competitive_sets final_placement synced_at',
 'entrant_players': 'entrant_id player_id registered_tag',
 'sets': 'id event_id source_state status outcome_type winner_entrant_id display_score completed_at source_updated_at synced_at source_hash',
 'set_slots': 'set_id slot_index event_id entrant_id score is_dq',
 'games': 'id set_id game_number winner_entrant_id stage_id synced_at',
 'game_selections': 'game_id set_id entrant_id character_id',
}
LOCK = 'smash-ranking-import-v1'


def sql(db, statement, args=()):
    with db.cursor() as cursor:
        cursor.execute(statement, args)
        return cursor.fetchall()


def insert_rows(db, table, columns, rows, *, keep_existing=False):
    cols = columns.split()
    statement = 'INSERT INTO `' + table + '` (' + ','.join('`'+c+'`' for c in cols) + ') VALUES (' + ','.join(['%s']*len(cols)) + ')'
    if keep_existing:
        statement += ' ON DUPLICATE KEY UPDATE `' + cols[0] + '`=`' + cols[0] + '`'
    values = [tuple(r.get(c) for c in cols) for r in rows]
    with db.cursor() as cursor:
        for offset in range(0, len(values), 500):
            cursor.executemany(statement, values[offset:offset+500])


def verify_schema(db):
    require(sql(db, "SELECT version FROM schema_migrations WHERE version=%s", ('001_accounts_competition',)) == (('001_accounts_competition',),), 'Esquema requerido no instalado.')
    rows = dict(sql(db, "SELECT TABLE_NAME,ENGINE FROM information_schema.tables WHERE table_schema=DATABASE()"))
    for name in list(COLUMNS) + ['cuts','cut_events','cut_set_results','rankings','player_characters','characters']:
        require(rows.get(name) == 'InnoDB', 'Tabla requerida ausente o sin transacciones.')
    sql(db, "SET time_zone='+00:00'")
    sql(db, "SET SESSION sql_mode=CONCAT(@@sql_mode,',STRICT_TRANS_TABLES')")


def scope_rows(content):
    p = content['public']
    return [('combined', p), ('guatemala', p['localRanking'])]


def ranking_rows(db, content, cut_id):
    rows, mains = [], []
    p = content['public']
    for scope, view in scope_rows(content):
        for player in view['players']:
            previous = None
            at = instant(view['previousCutAt']) if player.get('previousRank') is not None else None
            if at:
                found = sql(db, 'SELECT c.id,r.rank_position FROM cuts c JOIN rankings r ON r.cut_id=c.id '
                    "WHERE c.generated_at=%s AND c.season_year=%s AND c.method_version=%s AND c.status='published' AND r.scope=%s AND r.player_id=%s",
                    (at,p['seasonYear'],p['methodVersion'],scope,identifier(player['id'])))
                if found:
                    require(len(found)==1 and found[0][1] == player['previousRank'], 'Puesto anterior distinto del corte importado.')
                    previous = found[0][0]
            coverage = player['mainCoverage']
            rows.append(dict(cut_id=cut_id, scope=scope, player_id=identifier(player['id']), player_tag=player['tag'],
                rank_position=player['rank'], previous_rank=player.get('previousRank'), previous_cut_at=at, previous_cut_id=previous,
                rating=player['rating'], wins=player['wins'], losses=player['losses'], events_count=player['events'],
                sets_queried=coverage['setsQueried'], sets_with_selections=coverage['setsWithSelections'],
                games_with_selections=coverage['gamesWithSelections'], ambiguous_games=coverage['ambiguousGames']))
            for main in player['mains']:
                mains.append(dict(cut_id=cut_id, scope=scope, player_id=identifier(player['id']),
                    character_id=identifier(main['characterId']), games=main['games']))
    return rows, mains


def verify_parity(db, content, cut_id):
    p = content['public']
    stored = sql(db, 'SELECT public_snapshot FROM cuts WHERE id=%s', (cut_id,))[0][0]
    require(json.loads(stored) == p, 'Snapshot almacenado diferente del público.')
    for scope, view in scope_rows(content):
        found = sql(db, 'SELECT player_id,player_tag,rank_position,rating,wins,losses,events_count,previous_rank,previous_cut_at,'
            'sets_queried,sets_with_selections,games_with_selections,ambiguous_games FROM rankings WHERE cut_id=%s AND scope=%s ORDER BY rank_position', (cut_id,scope))
        wanted = []
        for r in view['players']:
            at = instant(view['previousCutAt']) if r.get('previousRank') is not None else None
            c = r['mainCoverage']
            wanted.append((identifier(r['id']),r['tag'],r['rank'],r['rating'],r['wins'],r['losses'],r['events'],r.get('previousRank'),
                at,c['setsQueried'],c['setsWithSelections'],c['gamesWithSelections'],c['ambiguousGames']))
        normalized = [tuple(instant(v.isoformat()+'+00:00') if i==8 and v is not None else v for i,v in enumerate(row)) for row in found]
        require(normalized == wanted, 'Ranking SQL distinto del público.')
        found = sql(db, 'SELECT player_id,character_id,games FROM player_characters WHERE cut_id=%s AND scope=%s', (cut_id,scope))
        wanted_mains = {(identifier(r['id']),identifier(m['characterId']),m['games']) for r in view['players'] for m in r['mains']}
        require(set(found) == wanted_mains and len(found)==len(wanted_mains), 'Mains SQL distintos del público.')
        found = sql(db, 'SELECT event_id,tournament_name,event_name,event_date,country_code,active_players,url FROM cut_events WHERE cut_id=%s AND scope=%s', (cut_id,scope))
        wanted_events = {(identifier(e['id']),e['name'],e['eventName'],e['date'],e['country'],e['activePlayers'],e['url']) for e in view['events']}
        require({row[:3]+(row[3].isoformat(),)+row[4:] for row in found} == wanted_events and len(found)==len(wanted_events), 'Eventos SQL distintos del público.')
        found = sql(db, 'SELECT set_id,event_id,winner_id,loser_id,winner_tag,loser_tag,display_score,winner_score,loser_score FROM cut_set_results WHERE cut_id=%s AND scope=%s', (cut_id,scope))
        wanted_results = {(identifier(r['id']),identifier(r['eventId']),identifier(r['playerIds'][0]),identifier(r['playerIds'][1]),r['playerTags'][0],r['playerTags'][1],r['score'],None,None) for r in view['results']}
        require(set(found)==wanted_results and len(found)==len(wanted_results), 'Resultados SQL distintos del público.')


def context_rows(db, table, columns, set_ids, *, id_column="set_id"):
    rows = []
    for offset in range(0, len(set_ids), 500):
        batch = set_ids[offset:offset+500]
        rows.extend(sql(db, 'SELECT ' + ','.join('`'+c+'`' for c in columns.split()) +
            ' FROM `' + table + '` WHERE `' + id_column + '` IN (' + ','.join(['%s']*len(batch)) + ')', batch))
    return rows


def replace_game_context(db, content):
    if content['packageVersion'] == 1:
        return
    tables = content['entities']; covered = content['gameContextSetIds']
    # Reject a known game ID assigned to another set, even if both sets are replaced.
    owners = dict(context_rows(db,'games','id set_id',[r['id'] for r in tables['games']],id_column='id'))
    require(all(r['id'] not in owners or owners[r['id']] == r['set_id'] for r in tables['games']), 'Game movido a otro set.')
    expected_slots = defaultdict_set((r['set_id'],r['entrant_id']) for r in tables['set_slots'])
    actual_slots = defaultdict_set(context_rows(db,'set_slots','set_id entrant_id',covered))
    competitive = {s['id'] for s in tables['sets'] if s['outcome_type'] == 'competitive'}
    require(all(actual_slots.get(sid) == expected_slots[sid] for sid in covered if sid in competitive),
            'Los slots guardados cambiaron; requiere conciliación manual.')
    for offset in range(0,len(covered),500):
        batch = covered[offset:offset+500]; placeholders = ','.join(['%s']*len(batch))
        sql(db, 'DELETE FROM game_selections WHERE set_id IN ('+placeholders+')', batch)
        sql(db, 'DELETE FROM games WHERE set_id IN ('+placeholders+')', batch)
    for table in ('games','game_selections'):
        insert_rows(db,table,COLUMNS[table],tables[table])
        found = context_rows(db,table,COLUMNS[table],covered)
        normalized = {tuple(instant(v.isoformat()+'+00:00') if hasattr(v,'isoformat') else v for v in r) for r in found}
        wanted = {tuple(r[col] for col in COLUMNS[table].split()) for r in tables[table]}
        require(normalized == wanted and len(found) == len(wanted), 'Paridad de games/selecciones falló.')


def import_package(db, package, *, apply=False):
    content = validate_package(package)
    p = content['public']; identity = (instant(p['generatedAt']),p['seasonYear'],p['methodVersion'])
    require(sql(db, 'SELECT GET_LOCK(%s,0)', (LOCK,))[0][0] == 1, 'Otro importador está ejecutándose.')
    try:
        verify_schema(db)
        existing = sql(db, 'SELECT id,source_hash,status FROM cuts WHERE generated_at=%s AND season_year=%s AND method_version=%s', identity)
        plan = dict(sha256=package['sha256'], generatedAt=p['generatedAt'],
            entities={k:len(v) for k,v in content['entities'].items()},
            views={s:dict(players=len(v['players']),events=len(v['events']),results=len(v['results'])) for s,v in scope_rows(content)})
        if existing:
            cut_id, old_hash, status = existing[0]
            require(old_hash==package['sha256'] and status=='published', 'Conflicto: identidad del corte ya existe con otro paquete o estado.')
            verify_parity(db,content,cut_id)
            db.rollback()
            return dict(plan,status='already_imported',cutId=cut_id)
        cuts = sql(db, 'SELECT generated_at,status FROM cuts')
        require(all(row[1] == 'published' for row in cuts), 'Existe un corte incompleto.')
        require(not cuts or identity[0] > max(instant(row[0].isoformat()+'+00:00') for row in cuts), 'Corte anterior al último guardado.')
        character_ids = {identifier(m['characterId']) for _,v in scope_rows(content) for r in v['players'] for m in r['mains']}
        character_ids.update(r['character_id'] for r in content['entities'].get('game_selections', []))
        known = {r[0] for r in sql(db,'SELECT id FROM characters')}
        require(character_ids <= known, 'Personaje no instalado; actualizar catálogo antes de importar.')
        if not apply:
            db.rollback()
            return dict(plan,status='validated_no_writes')
        db.rollback(); db.begin()
        with db.cursor() as cursor:
            cursor.execute('INSERT INTO cuts(generated_at,season_year,method_version,season_label,schema_version,character_captured_at,public_snapshot,source_hash) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)',
                identity+(p['seasonLabel'],p['schemaVersion'],instant(p['characterCapturedAt']),canonical(p),package['sha256']))
            cut_id = cursor.lastrowid
        # Preserve first-observed identities/live rows; immutable cut copies carry every later result.
        for table in ('players','tournaments','events','entrants','entrant_players','sets','set_slots'):
            if table in ('events','entrants','sets'):
                parent = 'tournament_id' if table=='events' else 'event_id'
                known_parent = dict(sql(db,'SELECT id,`'+parent+'` FROM `'+table+'`'))
                require(all(r['id'] not in known_parent or known_parent[r['id']]==r[parent] for r in content['entities'][table]), 'Identidad externa asociada a otro evento/torneo.')
            if table=='entrant_players':
                present = defaultdict_set(sql(db,'SELECT entrant_id,player_id FROM entrant_players'))
                require(all(not present.get(r['entrant_id']) or present[r['entrant_id']]=={r['player_id']} for r in content['entities'][table]), 'Entrant vinculado a otro jugador.')
            insert_rows(db, table, COLUMNS[table], content['entities'][table], keep_existing=True)
        replace_game_context(db,content)
        events, results = [], []
        set_hashes = {s['id']:s['source_hash'] for s in content['entities']['sets']}
        for scope,view in scope_rows(content):
            for e in view['events']:
                events.append(dict(cut_id=cut_id,scope=scope,event_id=identifier(e['id']),tournament_name=e['name'],event_name=e['eventName'],
                    event_date=e['date'],country_code=e['country'],active_players=e['activePlayers'],url=e['url']))
            for r in view['results']:
                results.append(dict(cut_id=cut_id,scope=scope,set_id=identifier(r['id']),event_id=identifier(r['eventId']),winner_id=identifier(r['playerIds'][0]),
                    loser_id=identifier(r['playerIds'][1]),winner_tag=r['playerTags'][0],loser_tag=r['playerTags'][1],display_score=r['score'],source_hash=set_hashes[identifier(r['id'])]))
        insert_rows(db,'cut_events','cut_id scope event_id tournament_name event_name event_date country_code active_players url',events)
        insert_rows(db,'cut_set_results','cut_id scope set_id event_id winner_id loser_id winner_tag loser_tag display_score source_hash',results)
        ranking,mains = ranking_rows(db,content,cut_id)
        insert_rows(db,'rankings','cut_id scope player_id player_tag rank_position previous_rank previous_cut_at previous_cut_id rating wins losses events_count sets_queried sets_with_selections games_with_selections ambiguous_games',ranking)
        insert_rows(db,'player_characters','cut_id scope player_id character_id games',mains)
        verify_parity(db,content,cut_id)
        sql(db,"UPDATE cuts SET status='published' WHERE id=%s",(cut_id,))
        db.commit()
        return dict(plan,status='imported',cutId=cut_id)
    except Exception:
        db.rollback()
        raise
    finally:
        sql(db, 'SELECT RELEASE_LOCK(%s)', (LOCK,))


def defaultdict_set(rows):
    found = {}
    for key,value in rows:
        found.setdefault(key,set()).add(value)
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package',type=Path)
    parser.add_argument('--defaults-file',type=Path,default=Path.home()/'.my.cnf')
    parser.add_argument('--database',required=True)
    parser.add_argument('--apply',action='store_true',help='Confirmar escritura del paquete validado en una transacción')
    args = parser.parse_args()
    db = None
    try:
        require(re.fullmatch('[A-Za-z0-9_]+',args.database) is not None,'Base inválida.')
        require(args.package.stat().st_size <= 32*1024*1024,'Paquete excede 32 MiB.')
        require(args.defaults_file.is_file() and args.defaults_file.stat().st_mode & 0o077 == 0,'Archivo de conexión debe ser privado (600).')
        package = json.loads(args.package.read_text())
        validate_package(package)
        import pymysql
        db = pymysql.connect(read_default_file=str(args.defaults_file),database=args.database,
            charset='utf8mb4',autocommit=False,connect_timeout=10,read_timeout=120,write_timeout=120)
        print(json.dumps(import_package(db,package,apply=args.apply),ensure_ascii=False))
    except Exception:
        # Drivers can include host/password/query values in errors. Never print them.
        parser.exit(1,'Importación rechazada; no se publicó un corte parcial. Revisar conexión, esquema, hash e integridad del paquete.\n')
    finally:
        if db is not None:
            db.close()


if __name__ == '__main__':
    main()
