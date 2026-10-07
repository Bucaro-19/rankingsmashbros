"""Contract tests and real transactional tests in disposable database services only."""
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import unittest

from ranking_package import build_package, canonical, digest, validate_package
from import_ranking import import_package, sql, verify_parity

ROOT = Path(__file__).resolve().parents[2]


def fixture(at='2026-10-04T11:43:18.348499+00:00', mutate=None):
    players = {str(i):dict(id=i,gamerTag=f'Jugador Á{i}',user=dict(slug=f'user/test{i}',location=dict(country='Guatemala' if i==1 else 'Mexico'))) for i in (1,2)}
    events,sets = [],{}
    for offset in range(3):
        eid,tid = 100+offset,10+offset
        e = dict(id=eid,name='Singles',slug=f'tournament/test{tid}/event/singles',numEntrants=2,
            startAt=1767276000+offset*86400,videogame=dict(id=1386),
            tournament=dict(id=tid,name=f'Torneo {tid}',slug=f'tournament/test{tid}',countryCode='GT' if offset<2 else 'MX'),
            placements={'1':1,'2':2},setsFetched=2 if offset<2 else 1)
        events.append(e)
        for j in range(e['setsFetched']):
            sid=500+offset*2+j
            winner=1 if offset<2 and j==0 else 2
            sets[str(sid)]=dict(id=sid,state=3,winnerId=eid*10+winner,displayScore=f'Jugador Á{winner} 2 - Otro 0',
                completedAt=e['startAt']+3600,updatedAt=e['startAt']+3600,event=e,tournament=e['tournament'],
                slots=[dict(entrant=dict(id=eid*10+i,participants=[dict(player=players[str(i)])])) for i in (1,2)],
                games=[dict(id=9000,winnerId=eid*10+1,selections=[dict(entrant=dict(id=eid*10+i),character=dict(id=1319,name='Mario')) for i in (1,2)])] if sid == 500 else [])
    raw=dict(kind='national_discovery',catalogComplete=True,eventsComplete=True,internationalComplete=True,
        generatedAt=at,events=events,players=players,sets=sets,characterDataComplete=True,characterCapturedAt=at,
        characterPlayerIds=['1','2'],characterEventIds=[str(e['id']) for e in events])
    if mutate: mutate(raw)
    from characters import player_mains
    from rank import competitive_set
    def scope(local):
        selected=events[:2] if local else events
        included={e['id'] for e in selected}
        matches=[m for m in sets.values() if m['event']['id'] in included and competitive_set(m)]
        ledger=[dict(id=str(m['id']),eventId=str(m['event']['id']),playerIds=list(competitive_set(m)),
            playerTags=[players[pid]['gamerTag'] for pid in competitive_set(m)],score=m['displayScore'],country=m['tournament']['countryCode']) for m in matches]
        public_events=[dict(id=str(e['id']),name=e['tournament']['name'],eventName=e['name'],country=e['tournament']['countryCode'],
            date=datetime.fromtimestamp(e['startAt'],timezone.utc).date().isoformat(),validSets=sum(m['event']['id']==e['id'] for m in matches),activePlayers=2,
            url='https://www.start.gg/'+e['slug']) for e in selected]
        ranked=[]
        for rank,pid in enumerate((1,2) if local else (2,1),1):
            activity=[]
            for e in selected:
                played=[m for m in ledger if m['eventId']==str(e['id'])]
                wins=sum(m['playerIds'][0]==str(pid) for m in played)
                activity.append(dict(id=str(e['id']),wins=wins,losses=len(played)-wins))
            wins=sum(r['wins'] for r in activity); losses=sum(r['losses'] for r in activity)
            ranked.append(dict(id=str(pid),tag=players[str(pid)]['gamerTag'],rank=rank,rating=1700-rank*100,
                wins=wins,losses=losses,sets=wins+losses,events=len(activity),knownAs=None,previousRank=None,
                countryBasis='perfil start.gg',activity=dict(months=['2026-01'],events=activity),
                mains=[dict(characterId='1319',name='Mario',games=1)],
                mainCoverage=dict(setsQueried=wins+losses,setsWithSelections=1,gamesWithSelections=1,ambiguousGames=0)))
        mains = player_mains(raw, {str(e['id']) for e in selected}, {'1','2'})
        for p in ranked: p.update(mains[p['id']])
        return dict(schemaVersion=3,status='local_pilot' if local else 'international_pilot',rankingComputed=True,
            generatedAt=at,seasonYear=2026,seasonLabel='2026',methodVersion='BT-PILOTO-3',rankingScope='guatemala' if local else 'combined',
            rankingCoverage='all_eligible',characterCapturedAt=at,previousCutAt=None,players=ranked,results=ledger,events=public_events,
            counts=dict(players=2,eligiblePlayers=2,top100=2,events=len(selected),sets=len(matches)))
    public=scope(False);public['localRanking']=scope(True)
    return raw,public


def legacy_package(package):
    p = copy.deepcopy(package); c = p['content']; c['packageVersion'] = 1
    del c['gameContextSetIds']; del c['entities']['games']; del c['entities']['game_selections']
    p['sha256'] = digest(c)
    return p


def corrected_games(raw):
    m = raw['sets']['500']; m['winnerId'] = 1002; m['displayScore'] = 'Jugador Á2 2 - Otro 0'
    m['games'][0]['winnerId'] = 1002
    m['games'][0]['selections'][0]['character'] = dict(id=1302,name='Mario')
    game = copy.deepcopy(m['games'][0]); game['id'] = 9001; game['winnerId'] = 1001
    game['selections'].append(dict(entrant=dict(id=1001),character=dict(id=1319,name='Pikachu')))
    m['games'].append(game)  # ambiguous for entrant 1001, valid for foreign opponent 1002


class PackageTests(unittest.TestCase):
    def test_deterministic_relational_package_and_unicode(self):
        raw,public=fixture();package=build_package(raw,public)
        self.assertEqual(package,build_package(raw,public))
        self.assertEqual(validate_package(package)['public'],public)
        self.assertEqual([p['country_code'] for p in package['content']['entities']['players']],['GT','MX'])
        self.assertIn('Jugador Á1',canonical(package))
        self.assertEqual(package['content']['entities']['set_slots'][0]['score'],None)
        self.assertEqual(len(package['content']['entities']['sets']),5)

    def test_rejects_incomplete_mismatched_raw_and_public(self):
        for change in ('cut','count','winner','entrant'):
            raw,public=fixture()
            if change=='cut':raw['generatedAt']='2026-10-05T00:00:00+00:00'
            if change=='count':raw['events'][0]['setsFetched']=3
            if change=='winner':raw['sets']['500']['winnerId']=999999
            if change=='entrant':raw['sets']['500']['slots'][0]['entrant']['id']=-1
            with self.subTest(change=change),self.assertRaises(ValueError):build_package(raw,public)

    def test_rejects_tampering_even_when_relationship_hash_is_recomputed(self):
        package=build_package(*fixture())
        package['content']['entities']['entrants'][0]['event_id']=102
        with self.assertRaises(ValueError):validate_package(package)
        package['sha256']=digest(package['content'])
        with self.assertRaises(ValueError):validate_package(package)

    def test_previous_rank_requires_previous_timestamp(self):
        raw,public=fixture();public['players'][0]['previousRank']=1
        with self.assertRaises(ValueError):build_package(raw,public)

    def test_filtering_matches_mains_duplicates_ambiguity_and_real_random(self):
        def mutate(raw):
            corrected_games(raw); games = raw['sets']['500']['games']
            games[0]['selections'][0]['character'] = dict(id=1746,name='Random Character')
            games[0]['selections'].append(copy.deepcopy(games[0]['selections'][0]))
            games.extend([copy.deepcopy(games[0]),dict(id=9002,winnerId=None),dict(id=None,winnerId=1001)])
            games[0]['selections'].append(dict(entrant=dict(id=999),character=dict(id=999,name='Outside')))
        p = build_package(*fixture(mutate=mutate)); validate_package(p); t = p['content']['entities']
        self.assertEqual([g['id'] for g in t['games']], [9000,9001])
        self.assertEqual([(r['game_id'],r['entrant_id'],r['character_id']) for r in t['game_selections']],
                         [(9000,1001,1746),(9000,1002,1319),(9001,1002,1319)])
        self.assertEqual(p['content']['public']['players'][1]['mainCoverage']['ambiguousGames'],1)

    def test_missing_private_games_or_mismatched_mains_stops_before_publication(self):
        for kind in ('coverage','missing','time','mains'):
            raw, public = fixture()
            if kind == 'coverage': raw['characterDataComplete'] = False
            if kind == 'missing': del raw['sets']['500']['games']
            if kind == 'time': raw['characterCapturedAt'] = '2026-10-05T00:00:00Z'
            if kind == 'mains': raw['sets']['500']['games'][0]['selections'][0]['character']['id'] = 1302
            with self.subTest(kind=kind), self.assertRaises(ValueError): build_package(raw,public)

    def test_game_id_collision_and_unknown_character_stop(self):
        def collide(raw): raw['sets']['501']['games'] = copy.deepcopy(raw['sets']['500']['games'])
        with self.assertRaises(ValueError): build_package(*fixture(mutate=collide))
        def unknown(raw): raw['sets']['500']['games'][0]['selections'][0]['character']['id'] = 999999
        with self.assertRaises(ValueError): validate_package(build_package(*fixture(mutate=unknown)))

    def test_version_one_stays_readable_with_original_hash(self):
        p = legacy_package(build_package(*fixture())); before = canonical(p)
        validate_package(p); self.assertEqual(before, canonical(p))


@unittest.skipUnless(os.environ.get('SMASH_SCHEMA_TEST_DB'),'Requires disposable SQL service')
class ImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import pymysql
        from pymysql.constants import CLIENT
        database=os.environ['SMASH_SCHEMA_TEST_DB'];host=os.environ.get('SMASH_SCHEMA_TEST_HOST','127.0.0.1')
        if not database.startswith('smash_schema_test') or host not in ('127.0.0.1','localhost'):
            raise RuntimeError('Only a local disposable database is allowed')
        cls.db=pymysql.connect(host=host,port=int(os.environ.get('SMASH_SCHEMA_TEST_PORT',3306)),database=database,user='root',
            password=os.environ['SMASH_SCHEMA_TEST_PASSWORD'],charset='utf8mb4',autocommit=True,client_flag=CLIENT.MULTI_STATEMENTS)
        for name in ('schema.sql','seed-characters.sql'):
            with cls.db.cursor() as c:
                c.execute((ROOT/'docs/smash'/name).read_text())
                while c.nextset():pass
    @classmethod
    def tearDownClass(cls):cls.db.close()

    def setUp(self):
        self.package=build_package(*fixture())
        self.assertEqual(sql(self.db,'SELECT COUNT(*) FROM cuts')[0][0],0)

    def tearDown(self):
        self.db.rollback()
        sql(self.db,'DROP TRIGGER IF EXISTS reject_ranking_test')
        sql(self.db,'UPDATE rankings SET previous_cut_id=NULL')
        for table in ('player_characters','rankings','cut_set_results','cut_events','cuts','game_selections','games','set_slots','sets','entrant_players','entrants','events','tournaments','players'):
            sql(self.db,'DELETE FROM `'+table+'`')
        self.db.commit()

    def test_dry_run_then_import_repetition_and_both_scopes(self):
        self.assertEqual(import_package(self.db,self.package)['status'],'validated_no_writes')
        self.assertEqual(sql(self.db,'SELECT COUNT(*) FROM players')[0][0],0)
        report=import_package(self.db,self.package,apply=True)
        self.assertEqual(report['status'],'imported')
        verify_parity(self.db,self.package['content'],report['cutId'])
        self.assertEqual(sql(self.db,'SELECT scope,player_id FROM rankings WHERE rank_position=1 ORDER BY scope'),(('combined',2),('guatemala',1)))
        self.assertEqual(import_package(self.db,self.package,apply=True)['status'],'already_imported')
        self.assertEqual(sql(self.db,'SELECT COUNT(*) FROM cuts')[0][0],1)
        self.assertEqual(sql(self.db,'SELECT COUNT(*) FROM users')[0][0],0)

    def test_same_identity_with_changed_hash_rejected(self):
        import_package(self.db,self.package,apply=True)
        changed=copy.deepcopy(self.package);changed['content']['public']['players'][0]['rating']+=1
        changed['sha256']=digest(changed['content'])
        with self.assertRaises(ValueError):import_package(self.db,changed,apply=True)
        self.assertEqual(sql(self.db,'SELECT COUNT(*) FROM cuts')[0][0],1)

    def test_missing_previous_cut_preserved_then_links_existing_previous(self):
        first=copy.deepcopy(self.package)
        for _,v in [('combined',first['content']['public']),('guatemala',first['content']['public']['localRanking'])]:
            v['previousCutAt']='2026-09-27T06:00:00+00:00'
            for p in v['players']:p['previousRank']=p['rank']
        first['sha256']=digest(first['content'])
        initial=import_package(self.db,first,apply=True)
        self.assertEqual(sql(self.db,'SELECT COUNT(*) FROM rankings WHERE previous_cut_id IS NULL')[0][0],4)
        raw,public=fixture('2026-10-11T06:00:00+00:00')
        for v in (public,public['localRanking']):
            v['previousCutAt']=first['content']['public']['generatedAt']
            for p in v['players']:p['previousRank']=p['rank']
        import_package(self.db,build_package(raw,public),apply=True)
        self.assertEqual(sql(self.db,'SELECT COUNT(*) FROM rankings WHERE previous_cut_id=%s',(initial['cutId'],))[0][0],4)
        verify_parity(self.db,first['content'],initial['cutId'])

    def test_failure_mid_import_rolls_back_everything(self):
        sql(self.db,"CREATE TRIGGER reject_ranking_test BEFORE INSERT ON rankings FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='test-only-fault'")
        with self.assertRaises(Exception):import_package(self.db,self.package,apply=True)
        for table in ('cuts','players','sets','rankings','tournaments'):
            self.assertEqual(sql(self.db,'SELECT COUNT(*) FROM `'+table+'`')[0][0],0)

    def test_external_parent_collision_rolls_back_new_cut(self):
        sql(self.db,"INSERT INTO tournaments(id,name) VALUES (99,'Existing')")
        sql(self.db,"INSERT INTO events(id,tournament_id,name) VALUES (100,99,'Existing')")
        with self.assertRaises(ValueError):import_package(self.db,self.package,apply=True)
        self.assertEqual(sql(self.db,'SELECT COUNT(*) FROM cuts')[0][0],0)
        self.assertEqual(sql(self.db,'SELECT COUNT(*) FROM players')[0][0],0)
        self.assertEqual(sql(self.db,'SELECT tournament_id FROM events WHERE id=100')[0][0],99)

    def test_changed_live_result_does_not_rewrite_published_cut(self):
        report=import_package(self.db,self.package,apply=True)
        sql(self.db,'UPDATE sets SET winner_entrant_id=1002 WHERE id=500')
        sql(self.db,"UPDATE events SET name='Correction' WHERE id=100")
        self.db.commit()
        verify_parity(self.db,self.package['content'],report['cutId'])
        self.assertEqual(import_package(self.db,self.package,apply=True)['status'],'already_imported')


if __name__=='__main__':unittest.main(verbosity=2)
