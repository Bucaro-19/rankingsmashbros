"""Integration tests against an isolated MySQL/MariaDB service (never production)."""
import os
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(os.environ.get('SMASH_SCHEMA_TEST_DB'), 'Requires disposable database service')
class SchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import pymysql
        from pymysql.constants import CLIENT
        database = os.environ['SMASH_SCHEMA_TEST_DB']
        host = os.environ.get('SMASH_SCHEMA_TEST_HOST', '127.0.0.1')
        if not database.startswith('smash_schema_test') or host not in ('127.0.0.1', 'localhost'):
            raise RuntimeError('Only a local disposable test database is allowed')
        cls.driver = pymysql
        cls.db = pymysql.connect(host=host, port=int(os.environ.get('SMASH_SCHEMA_TEST_PORT', '3306')),
            user='root', password=os.environ['SMASH_SCHEMA_TEST_PASSWORD'], database=database,
            charset='utf8mb4', autocommit=True, client_flag=CLIENT.MULTI_STATEMENTS)
        # Installation and catalog seed must be repeatable on an actual database engine.
        for _ in range(2):
            for filename in ('schema.sql', 'seed-characters.sql'):
                with cls.db.cursor() as cursor:
                    cursor.execute((ROOT / 'docs/smash' / filename).read_text())
                    while cursor.nextset():
                        pass
            # Versioned migrations are applied in order after the base schema and must be repeatable too.
            for migration in sorted((ROOT / 'docs/smash/migrations').glob('*.sql')):
                with cls.db.cursor() as cursor:
                    cursor.execute(migration.read_text())
                    while cursor.nextset():
                        pass

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def execute(self, sql, args=None):
        with self.db.cursor() as cursor:
            cursor.execute(sql, args)
            return cursor.fetchall()

    def rejects(self, sql, args=None):
        with self.assertRaises(self.driver.MySQLError):
            self.execute(sql, args)

    def setUp(self):
        self.db.begin()
        self.execute("INSERT INTO players(id,tag,country_code) VALUES (1,'Juan','GT'),(2,'Lucas','MX'),(3,'Otro','GT')")
        self.execute("INSERT INTO users(id,startgg_user_id,player_id) VALUES (1,11,1),(2,22,2),(3,33,NULL)")
        self.execute("INSERT INTO tournaments(id,name,country_code) VALUES (10,'Torneo de prueba','GT')")
        self.execute("INSERT INTO events(id,tournament_id,name) VALUES (100,10,'Singles'),(101,10,'Otro evento')")
        self.execute("INSERT INTO entrants(id,event_id,name) VALUES (1000,100,'Juan'),(1001,100,'Lucas'),(1002,100,'Otro'),(1010,101,'Otro evento')")
        self.execute("INSERT INTO entrant_players(entrant_id,player_id) VALUES (1000,1),(1001,2),(1002,3),(1010,3)")
        self.execute("INSERT INTO sets(id,event_id,status) VALUES (500,100,'pending')")
        self.execute("INSERT INTO sets(id,event_id,status,winner_entrant_id,outcome_type) VALUES (501,100,'completed',1000,'competitive')")
        self.execute("INSERT INTO set_slots(set_id,slot_index,event_id,entrant_id,score) VALUES (500,0,100,1000,NULL),(500,1,100,NULL,NULL),(501,0,100,1000,3),(501,1,100,1001,0)")

    def tearDown(self):
        self.db.rollback()

    def test_repeatable_installation_and_catalog(self):
        self.assertEqual(self.execute('SELECT COUNT(*) FROM characters')[0][0], 87)
        self.assertEqual(self.execute('SELECT version FROM schema_migrations ORDER BY version'), (('001_accounts_competition',), ('002_sessions_visits',)))
        self.assertEqual(self.execute("SELECT name FROM characters WHERE id=1897")[0][0], 'Sora')
        self.assertEqual(self.execute('SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE()')[0][0], 34)

    def test_pending_opponent_and_foreign_unranked_player(self):
        self.assertEqual(self.execute('SELECT winner_entrant_id FROM sets WHERE id=500')[0][0], None)
        self.assertEqual(self.execute('SELECT entrant_id FROM set_slots WHERE set_id=500 AND slot_index=1')[0][0], None)
        self.execute('UPDATE set_slots SET entrant_id=1001 WHERE set_id=500 AND slot_index=1')
        rows = self.execute('SELECT p.tag FROM set_slots s JOIN entrant_players ep ON ep.entrant_id=s.entrant_id JOIN players p ON p.id=ep.player_id WHERE s.set_id=500 AND s.slot_index=1')
        self.assertEqual(rows, (('Lucas',),))
        self.assertEqual(self.execute('SELECT COUNT(*) FROM rankings WHERE player_id=2')[0][0], 0)
        self.rejects('UPDATE sets SET winner_entrant_id=1000 WHERE id=500')

    def test_player_and_organizer_and_verified_tournament_membership(self):
        self.execute("INSERT INTO user_roles(user_id,role) VALUES (1,'player'),(1,'organizer')")
        self.execute("INSERT INTO tournament_staff(tournament_id,user_id,role) VALUES (10,1,'organizer')")
        self.assertEqual(self.execute('SELECT COUNT(*) FROM user_roles WHERE user_id=1')[0][0], 2)
        self.assertEqual(self.execute('SELECT verification_status FROM tournament_staff WHERE user_id=1')[0][0], 'pending')
        self.execute('INSERT INTO user_characters(user_id,position,character_id) VALUES (1,1,1319),(1,2,1766)')
        self.rejects('INSERT INTO user_characters(user_id,position,character_id) VALUES (1,4,1897)')

    def test_cross_event_and_cross_set_relations_are_rejected(self):
        self.rejects('UPDATE set_slots SET entrant_id=1010 WHERE set_id=500 AND slot_index=1')
        self.rejects('UPDATE set_slots SET event_id=101 WHERE set_id=500 AND slot_index=1')
        self.execute('INSERT INTO games(id,set_id,game_number,winner_entrant_id) VALUES (700,501,1,1000)')
        self.execute('INSERT INTO game_selections(game_id,set_id,entrant_id,character_id) VALUES (700,501,1000,1319)')
        self.rejects('INSERT INTO game_selections(game_id,set_id,entrant_id,character_id) VALUES (700,501,1002,1319)')
        self.rejects('INSERT INTO game_selections(game_id,set_id,entrant_id,character_id) VALUES (700,500,1000,1319)')

    def test_versions_reviews_and_publish_deduplication(self):
        insert = 'INSERT INTO result_submissions(id,set_id,user_id,revision,winner_entrant_id,score_slot0,score_slot1,based_on_source_hash) VALUES (%s,501,%s,%s,1000,%s,%s,%s)'
        self.execute(insert, (1,1,1,3,0,'a'*64))
        self.execute(insert, (2,2,1,3,0,'a'*64))
        self.execute(insert, (3,1,2,3,1,'a'*64))
        self.assertEqual(self.execute('SELECT COUNT(*) FROM result_submissions WHERE set_id=501')[0][0], 3)
        self.rejects(insert, (4,1,2,3,1,'a'*64))
        self.rejects(insert, (5,1,3,2,2,'a'*64))
        self.execute('INSERT INTO result_reviews(submission_id,reviewer_id,decision,source_hash_checked) VALUES (3,3,%s,%s)', ('approved','a'*64))
        self.execute('INSERT INTO result_publish_attempts(set_id,submission_id,reporter_id,idempotency_key,source_hash_checked) VALUES (501,3,3,%s,%s)', ('00000000-0000-0000-0000-000000000001','a'*64))
        self.rejects('INSERT INTO result_publish_attempts(set_id,submission_id,reporter_id,idempotency_key,source_hash_checked) VALUES (501,3,3,%s,%s)', ('00000000-0000-0000-0000-000000000002','a'*64))
        self.rejects('INSERT INTO result_publish_attempts(set_id,submission_id,reporter_id,idempotency_key,source_hash_checked) VALUES (500,1,3,%s,%s)', ('00000000-0000-0000-0000-000000000003','a'*64))

    def test_cut_results_survive_live_correction_and_scope_is_preserved(self):
        insert = 'INSERT INTO cuts(id,generated_at,season_year,season_label,method_version,schema_version,source_hash,public_snapshot) VALUES (%s,%s,2026,%s,%s,3,%s,%s)'
        self.execute(insert, (1,'2026-10-04 11:43:18.348499','2026','BT-PILOTO-3','a'*64,'{}'))
        self.execute(insert, (2,'2026-10-11 06:00:00','2026','BT-PILOTO-3','b'*64,'{}'))
        self.execute("INSERT INTO cut_events(cut_id,scope,event_id,tournament_name,event_name,event_date) VALUES (1,'combined',100,'Original','Singles','2026-10-04')")
        self.execute("INSERT INTO cut_set_results(cut_id,scope,set_id,event_id,winner_id,loser_id,winner_tag,loser_tag,winner_score,loser_score) VALUES (1,'combined',501,100,1,2,'Juan','Lucas',3,0)")
        self.execute('UPDATE sets SET winner_entrant_id=1001 WHERE id=501')
        self.execute('UPDATE set_slots SET score=0 WHERE set_id=501 AND slot_index=0')
        self.assertEqual(self.execute('SELECT winner_id,winner_score FROM cut_set_results WHERE cut_id=1')[0], (1,3))
        self.execute("INSERT INTO rankings(cut_id,scope,player_id,player_tag,rank_position,rating,wins,losses,events_count) VALUES (1,'combined',1,'Juan',1,2500,3,1,2)")
        self.execute("INSERT INTO rankings(cut_id,scope,player_id,player_tag,rank_position,rating,wins,losses,events_count,previous_rank,previous_cut_id,previous_cut_at) VALUES (2,'combined',1,'Juan',1,2501,4,1,2,1,1,'2026-10-04 11:43:18.348499')")
        self.rejects("INSERT INTO rankings(cut_id,scope,player_id,player_tag,rank_position,rating,wins,losses,events_count,previous_rank,previous_cut_id,previous_cut_at) VALUES (2,'guatemala',1,'Juan',1,2501,4,1,2,1,1,'2026-10-04 11:43:18.348499')")
        self.rejects(insert, (3,'2026-10-12 00:00:00','2026','BT-PILOTO-3','c'*64,'invalid json'))

    def test_persistent_sessions_and_visit_counters(self):
        insert = 'INSERT INTO user_sessions(user_id,token_hash,connection_version,created_at,last_used_at,expires_at) VALUES (%s,%s,%s,%s,%s,%s)'
        at = '2026-10-07 00:00:00'
        self.execute(insert, (1, 'a'*64, at, at, at, '2027-01-05 00:00:00'))
        self.rejects(insert, (2, 'a'*64, at, at, at, '2027-01-05 00:00:00'))
        self.rejects(insert, (999, 'b'*64, at, at, at, '2027-01-05 00:00:00'))
        self.execute('DELETE FROM users WHERE id=1')
        self.assertEqual(self.execute('SELECT COUNT(*) FROM user_sessions')[0][0], 0)
        count = 'INSERT INTO site_visit_days(day,page,views) VALUES (%s,%s,1) ON DUPLICATE KEY UPDATE views=views+1'
        for _ in range(3):
            self.execute(count, ('2026-10-07', 'inicio'))
        self.assertEqual(self.execute('SELECT views FROM site_visit_days')[0][0], 3)
        self.execute("INSERT INTO site_visitor_days(day,visitor_hash,views) VALUES ('2026-10-07',%s,1),('2026-10-08',%s,1)", ('c'*64, 'c'*64))
        self.rejects("INSERT INTO site_visitor_days(day,visitor_hash,views) VALUES ('2026-10-07',%s,1)", ('c'*64,))
        self.assertEqual(self.execute('SELECT COUNT(DISTINCT visitor_hash) FROM site_visitor_days')[0][0], 1)

    def test_notification_dedup_and_correct_recipient(self):
        self.execute('INSERT INTO notifications(id,user_id,type,deduplication_key,title,body) VALUES (1,1,%s,%s,%s,%s)', ('match_ready','a'*64,'Tu rival','Lucas'))
        self.rejects('INSERT INTO notifications(user_id,type,deduplication_key,title,body) VALUES (1,%s,%s,%s,%s)', ('match_ready','a'*64,'Tu rival','Lucas'))
        self.execute('INSERT INTO push_subscriptions(id,user_id,endpoint,endpoint_hash,p256dh,auth_secret) VALUES (1,1,%s,%s,%s,%s),(2,2,%s,%s,%s,%s)', ('https://example.invalid/1','a'*64,'test','test','https://example.invalid/2','b'*64,'test','test'))
        self.execute('INSERT INTO notification_deliveries(notification_id,subscription_id,user_id) VALUES (1,1,1)')
        self.rejects('INSERT INTO notification_deliveries(notification_id,subscription_id,user_id) VALUES (1,2,1)')

    def test_anonymous_survey_import_is_repeatable_and_validated(self):
        insert = 'INSERT INTO survey_responses(submitted_at,season_year,role,eligibility,minimum_activity,international,clarity,confidence,import_hash) VALUES (%s,2026,%s,%s,%s,%s,%s,5,%s)'
        args = ('2026-10-07 00:00:00','jugador','nacionalidad-local','2-eventos-4-sets','todos-validos',5,'a'*64)
        self.execute(insert, args)
        self.rejects(insert, args)
        self.rejects(insert, (*args[:5],6,'b'*64))
        self.rejects('INSERT INTO oauth_connections(user_id,scopes,access_token_encrypted) VALUES (1,%s,%s)', ('user.identity',b'not-a-real-token'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
