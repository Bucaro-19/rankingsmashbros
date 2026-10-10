"""Anonymous directory on disposable MySQL/MariaDB. Never uses the production config."""
import json
import unittest
import urllib.request
import test_organizador_http as fixture


@unittest.skipUnless(fixture.DATABASE, 'Requires local disposable database')
class TopsHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.OrganizerHttpTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        fixture.OrganizerHttpTests.tearDownClass.__func__(cls)

    browser = fixture.OrganizerHttpTests.browser
    call = fixture.OrganizerHttpTests.call
    premium = fixture.OrganizerHttpTests.premium
    login = fixture.OrganizerHttpTests.login

    def setUp(self):
        fixture.OrganizerHttpTests.setUp(self)
        with self.db.cursor() as q:
            q.execute('SELECT id FROM users WHERE startgg_user_id BETWEEN 8999500001 AND 8999500004 ORDER BY startgg_user_id')
            self.org, self.co, self.other, self.empty = [str(row[0]) for row in q.fetchall()]
            q.execute("INSERT INTO organizer_profiles(user_id,slug,public_enabled,top_size,created_at,updated_at) VALUES (%s,%s,1,5,'2026-10-09','2026-10-09'),(%s,%s,0,10,'2026-10-09','2026-10-09'),(%s,%s,1,15,'2026-10-09','2026-10-09')",
                      (self.org, 'arena-xela', self.other, 'privado', self.empty, 'sin-torneos'))
            q.execute("INSERT INTO organizer_members(organizer_user_id,member_user_id,created_at) VALUES (%s,%s,'2026-10-09')", (self.org, self.co))
        for user in (self.org, self.other, self.empty): self.premium(user)

    def sql(self, query, args=None):
        with self.db.cursor() as q:
            q.execute(query, args)
            return q.fetchall()

    def test_only_open_top_with_counted_tournaments_and_public_projection(self):
        tables = ('users','organizer_profiles','organizer_members','premium_subscriptions','cuts','cut_events','cut_set_results','rankings')
        before = {table: self.sql('SELECT COUNT(*) FROM '+table) for table in tables}
        status, data = self.call('/tops-api.php')
        self.assertEqual(status, 200)
        self.assertEqual(set(data), {'ok','schemaVersion','items','nextCursor'})
        self.assertEqual(len(data['items']), 1)
        item = data['items'][0]
        self.assertEqual(item, dict(name='Árena Xelá', coorganizers=['Coorganizador'], topSize=5,
            tournaments=2, cutDate='2098-10-04', top=[dict(rank=1,alias='Kenji'),dict(rank=2,alias='Vlad'),dict(rank=3,alias='Momo')],url='/top/arena-xela'))
        self.assertIsNone(data['nextCursor'])
        text=json.dumps(data)
        for secret in ('user_id','player_id','startgg','email','payment','premium','checkout','subscription','memberId','detail','points','privado','sin-torneos'):
            self.assertNotIn(secret, text)
        # The projection matches the real existing /top view, not a second fit.
        self.assertIn('Kenji', self.call('/top.php?o=arena-xela', raw=True)[2])
        self.assertEqual(before, {table: self.sql('SELECT COUNT(*) FROM '+table) for table in tables})

    def test_closed_empty_expired_and_under_twenty_never_appear(self):
        self.sql('UPDATE organizer_profiles SET public_enabled=0 WHERE user_id=%s', (self.org,))
        self.assertEqual(self.call('/tops-api.php')[1]['items'], [])
        self.sql('UPDATE organizer_profiles SET public_enabled=1 WHERE user_id=%s', (self.org,))
        self.sql("UPDATE premium_subscriptions SET current_period_end='2025-01-01' WHERE user_id=%s", (self.org,))
        self.assertEqual(self.call('/tops-api.php')[1]['items'], [])
        self.sql("UPDATE premium_subscriptions SET current_period_end='2099-01-01' WHERE user_id=%s", (self.org,))
        self.sql('UPDATE cut_events ce JOIN events e ON e.id=ce.event_id SET ce.active_players=19 WHERE e.tournament_id IN (8999500001,8999500002)')
        self.assertEqual(self.call('/tops-api.php')[1]['items'], [])

    def test_cache_revalidation_head_and_no_session_or_cookie_variation(self):
        status, headers, body = self.call('/tops-api.php', raw=True)
        self.assertEqual(status,200); self.assertEqual(headers['Cache-Control'],'public, max-age=30, must-revalidate')
        self.assertIsNone(headers.get('Set-Cookie'))
        req=urllib.request.Request(self.base+'/tops-api.php', headers={'If-None-Match':headers['ETag']})
        try: response=urllib.request.urlopen(req)
        except fixture.urllib.error.HTTPError as error: response=error
        with response:
            self.assertEqual(response.status,304); self.assertEqual(response.read(),b'')
        with urllib.request.urlopen(urllib.request.Request(self.base+'/tops-api.php',method='HEAD')) as response:
            self.assertEqual(response.status,200); self.assertEqual(response.headers['ETag'],headers['ETag']); self.assertEqual(response.read(),b'')
        self.login('org')
        self.assertEqual(self.call('/tops-api.php', raw=True)[2],body)
        # Disabling sharing invalidates the ETag immediately at the server.
        self.sql('UPDATE organizer_profiles SET public_enabled=0 WHERE user_id=%s',(self.org,))
        with urllib.request.urlopen(req) as response:
            self.assertEqual(response.status,200); self.assertEqual(json.load(response)['items'],[])

    def test_bound_and_pagination_cursor_are_public_and_validated(self):
        self.sql('UPDATE organizer_profiles SET public_enabled=1 WHERE user_id=%s',(self.other,))
        one=self.call('/tops-api.php?limit=1')[1]
        self.assertEqual(len(one['items']),1); self.assertEqual(one['nextCursor'],'arena-xela')
        two=self.call('/tops-api.php?limit=1&after='+one['nextCursor'])[1]
        self.assertEqual(two['items'][0]['url'],'/top/privado'); self.assertIsNone(two['nextCursor'])
        for query in ('limit=0','limit=13','limit=999999','limit[]=1','after[]=arena','after=%27OR%201%3D1','limit=-1'):
            status,data=self.call('/tops-api.php?'+query)
            self.assertEqual((status,data),(400,dict(ok=False,reason='invalid_query')))
        status,headers,_=self.call('/tops-api.php',{},raw=True)
        self.assertEqual(status,405);self.assertEqual(headers['Allow'],'GET, HEAD');self.assertEqual(headers['Cache-Control'],'no-store')

    def test_canceled_paid_period_past_due_latest_period_and_admin_parity(self):
        for state in ('canceled','past_due'):
            self.sql('UPDATE premium_subscriptions SET status=%s WHERE user_id=%s',(state,self.org))
            self.assertEqual(len(self.call('/tops-api.php')[1]['items']),1)
        # An older running subscription must not override the latest nonpending end.
        self.sql("INSERT INTO premium_subscriptions(user_id,plan,live_mode,provider_checkout_id,status,current_period_end,created_at,updated_at) VALUES(%s,'monthly',0,'future-ended-fixture','ended','2099-02-01','2026-10-09','2026-10-09')",(self.org,))
        self.assertEqual(self.call('/tops-api.php')[1]['items'],[])
        self.sql("INSERT INTO user_roles(user_id,role) VALUES(%s,'admin')",(self.org,))
        self.assertEqual(len(self.call('/tops-api.php')[1]['items']),1)

    def test_read_failure_is_not_a_fake_empty_directory(self):
        self.sql('RENAME TABLE organizer_profiles TO organizer_profiles_tops_fixture')
        try:
            status,headers,text=self.call('/tops-api.php',raw=True)
            self.assertEqual(status,503);self.assertEqual(json.loads(text),dict(ok=False,reason='tops_unavailable'))
            self.assertEqual(headers['Cache-Control'],'no-store');self.assertNotIn('PDO',text);self.assertIsNone(headers.get('Set-Cookie'))
        finally:self.sql('RENAME TABLE organizer_profiles_tops_fixture TO organizer_profiles')

    def test_claims_use_only_admitted_tournaments_and_active_accounts(self):
        self.sql("INSERT INTO organizer_claims(organizer_user_id,tournament_slug,tournament_id,status,created_at) VALUES(%s,'tournament/torneo-4',8999500004,'approved','2026-10-09'),(%s,'tournament/torneo-1',8999500001,'sent','2026-10-09')",(self.empty,self.empty))
        self.assertEqual(len(self.call('/tops-api.php')[1]['items']),1)
        self.sql("UPDATE organizer_claims SET status='approved' WHERE organizer_user_id=%s AND tournament_id=8999500001",(self.empty,))
        self.assertEqual(len(self.call('/tops-api.php')[1]['items']),2)
        self.sql("UPDATE users SET status='disabled' WHERE id=%s",(self.empty,))
        self.assertEqual(len(self.call('/tops-api.php')[1]['items']),1)
        self.sql('UPDATE premium_subscriptions SET live_mode=1 WHERE user_id=%s',(self.org,))
        self.assertEqual(self.call('/tops-api.php')[1]['items'],[])

    def test_default_hard_limit_and_complete_pagination_of_fifteen_open_tops(self):
        for number in range(14):
            self.sql('INSERT INTO users(startgg_user_id,display_name) VALUES(%s,%s)',(8999500100+number,'Organizador inventado '+str(number)))
            user=str(self.sql('SELECT id FROM users WHERE startgg_user_id=%s',(8999500100+number,))[0][0])
            self.sql("INSERT INTO organizer_profiles(user_id,slug,public_enabled,top_size,created_at,updated_at) VALUES(%s,%s,1,15,'2026-10-09','2026-10-09')",(user,'muestra-'+str(number).zfill(2)))
            self.sql("INSERT INTO organizer_claims(organizer_user_id,tournament_slug,tournament_id,status,created_at) VALUES(%s,'tournament/torneo-1',8999500001,'approved','2026-10-09')",(user,))
            self.premium(user)
        first=self.call('/tops-api.php')[1]
        self.assertEqual(len(first['items']),12)
        self.assertEqual(first['nextCursor'],first['items'][-1]['url'][5:])
        last=self.call('/tops-api.php?after='+first['nextCursor'])[1]
        self.assertEqual(len(last['items']),3); self.assertIsNone(last['nextCursor'])
        self.assertEqual(len({item['url'] for item in first['items']+last['items']}),15)

if __name__=='__main__': unittest.main()
