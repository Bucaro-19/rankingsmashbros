"""Initial context contracts and transactional tests in disposable SQL only."""
import copy
import os
from pathlib import Path
import unittest
from game_context import ContextStopped, build_context, import_context, validate_context
from import_ranking import import_package, sql
from ranking_package import build_package, digest
import test_import_ranking as ranking_tests
fixture = ranking_tests.fixture
legacy_package = ranking_tests.legacy_package


class ContextContracts(unittest.TestCase):
    def setUp(self):
        self.captured=build_package(*fixture()); self.original=legacy_package(self.captured)
        self.package=build_context(self.original,self.captured,1)

    def test_context_contains_only_games_and_immutable_anchor(self):
        c=validate_context(self.package,self.original)
        self.assertEqual(set(c['entities']),{'games','game_selections'})
        self.assertEqual(c['anchor']['sourceHash'],self.original['sha256'])
        self.assertEqual(self.package,build_context(self.original,self.captured,1))

    def test_tampering_relationships_coverage_mains_and_anchor_rejected(self):
        for kind in ('hash','anchor','selection','winner','coverage','extra'):
            p=copy.deepcopy(self.package); c=p['content']
            if kind=='hash': p['sha256']='f'*64
            if kind=='anchor': c['anchor']['sourceHash']='f'*64
            if kind=='selection': c['entities']['game_selections'][0]['character_id']=1302
            if kind=='winner': c['entities']['games'][0]['winner_entrant_id']=999
            if kind=='coverage': c['gameContextSetIds']=[]
            if kind=='extra': c['entities']['cuts']=[]
            if kind!='hash':p['sha256']=digest(c)
            with self.subTest(kind=kind),self.assertRaises(ValueError):validate_context(p,self.original)


@unittest.skipUnless(os.environ.get('SMASH_SCHEMA_TEST_DB'),'Requires disposable SQL')
class ContextSql(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ranking_tests.ImportTests.setUpClass(); cls.db=ranking_tests.ImportTests.db
    @classmethod
    def tearDownClass(cls):cls.db.close()
    def setUp(self):
        self.captured=build_package(*fixture());self.original=legacy_package(self.captured)
        self.cut=import_package(self.db,self.original,apply=True)['cutId']
        self.package=build_context(self.original,self.captured,self.cut)
    def tearDown(self):
        self.db.rollback();sql(self.db,'DROP TRIGGER IF EXISTS reject_context_test')
        sql(self.db,'UPDATE rankings SET previous_cut_id=NULL')
        for t in ('game_selections','games','player_characters','rankings','cut_set_results','cut_events','cuts','set_slots','sets','entrant_players','entrants','events','tournaments','players'):
            sql(self.db,'DELETE FROM '+t)
        self.db.commit()
    def immutable(self):
        return {t:sql(self.db,'SELECT * FROM '+t+' ORDER BY 1') for t in ('cuts','rankings','player_characters','cut_events','cut_set_results','players','tournaments','events','entrants','entrant_players','sets','set_slots')}
    def test_simulation_apply_repeat_only_game_tables_change(self):
        before=self.immutable()
        r=import_context(self.db,self.original,self.package);self.assertEqual(r['status'],'validated_no_writes');self.assertTrue(r['readOnly'])
        self.assertEqual(sql(self.db,'SELECT COUNT(*) FROM games')[0][0],0)
        self.assertEqual(import_context(self.db,self.original,self.package,apply=True)['status'],'context_imported')
        self.assertEqual(import_context(self.db,self.original,self.package,apply=True)['status'],'already_imported')
        self.assertEqual(before,self.immutable())
        self.assertEqual(sql(self.db,'SELECT COUNT(*) FROM games')[0][0],1)
        self.assertEqual(sql(self.db,'SELECT COUNT(*) FROM game_selections')[0][0],2)
    def test_partial_and_later_context_are_rejected_without_overwrite(self):
        sql(self.db,"INSERT INTO games(id,set_id,game_number,winner_entrant_id,synced_at) VALUES (9001,500,2,1001,'2026-10-11 00:00:00')");self.db.commit()
        with self.assertRaises(ContextStopped) as e:import_context(self.db,self.original,self.package,apply=True)
        self.assertEqual(e.exception.reason,'existing_game_context_conflict');self.assertEqual(sql(self.db,'SELECT id FROM games'),((9001,),))
    def test_later_cut_even_with_empty_games_blocks_old_context(self):
        later=legacy_package(build_package(*fixture('2026-10-11T06:00:00+00:00')));import_package(self.db,later,apply=True)
        with self.assertRaises(ContextStopped) as e:import_context(self.db,self.original,self.package)
        self.assertEqual(e.exception.reason,'later_or_other_cut');self.assertEqual(sql(self.db,'SELECT COUNT(*) FROM games')[0][0],0)
    def test_changed_source_or_catalog_is_rejected(self):
        sql(self.db,"UPDATE sets SET source_hash=REPEAT('f',64) WHERE id=500");self.db.commit()
        with self.assertRaises(ContextStopped) as e:import_context(self.db,self.original,self.package,apply=True)
        self.assertEqual(e.exception.reason,'source_relations_changed');self.assertEqual(sql(self.db,'SELECT COUNT(*) FROM games')[0][0],0)
    def test_cut_hash_or_snapshot_conflict_is_rejected(self):
        sql(self.db,"UPDATE cuts SET source_hash=REPEAT('f',64)");self.db.commit()
        with self.assertRaises(ContextStopped) as e:import_context(self.db,self.original,self.package)
        self.assertEqual(e.exception.reason,'cut_anchor_conflict')
    def test_failure_after_games_rolls_back_and_keeps_cut(self):
        before=self.immutable()
        sql(self.db,"CREATE TRIGGER reject_context_test BEFORE INSERT ON game_selections FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='test-only'")
        with self.assertRaises(Exception):import_context(self.db,self.original,self.package,apply=True)
        self.assertEqual(sql(self.db,'SELECT COUNT(*) FROM games')[0][0],0);self.assertEqual(before,self.immutable())
    def test_foreign_transaction_is_not_rolled_back(self):
        self.db.begin();sql(self.db,"UPDATE sets SET source_hash=REPEAT('f',64) WHERE id=500")
        with self.assertRaises(ContextStopped) as e:import_context(self.db,self.original,self.package)
        self.assertEqual(e.exception.reason,'existing_transaction')
        self.assertEqual(sql(self.db,'SELECT source_hash FROM sets WHERE id=500')[0][0],'f'*64)


if __name__=='__main__':unittest.main(verbosity=2)
