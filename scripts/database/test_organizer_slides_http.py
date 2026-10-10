"""Private slide DTO: invented data, disposable SQL and simulated sessions only."""
import unittest
import test_organizador_http as org


class OrganizerSlideHttpTests(org.OrganizerHttpTests):
    def test_slide_free_expired_and_foreign_accounts_receive_no_payload(self):
        self.assertNotIn('data', self.call('/organizador-api.php')[1])
        owner = self.login('org')
        free = self.call('/organizador-api.php')[1]
        self.assertEqual(free['state'], 'premium')
        self.assertNotIn('slides', str(free)); self.assertNotIn('players', free)
        self.premium(owner, '2020-01-01 00:00:00')
        expired = self.call('/organizador-api.php')[1]
        self.assertEqual(expired['state'], 'expired'); self.assertNotIn('slides', str(expired))
        self.login('other', '&admin=1')
        self.assertEqual(self.call('/organizador-api.php?organizador='+owner), (403, {'ok': False, 'reason': 'forbidden'}))

    def test_slide_empty_games_and_missing_placements_are_honest(self):
        owner = self.login('org'); self.premium(owner)
        data = self.call('/organizador-api.php')[1]['data']
        slides = data['slides']
        self.assertEqual(set(slides), {'schemaVersion', 'organizer', 'players'})
        self.assertEqual(len(slides['players']), len(data['top']))
        self.assertEqual([(p['rank'], p['tag'], p['setsWon'], p['setsLost']) for p in slides['players']], [(p['rank'], p['alias'], p['setsWon'], p['setsLost']) for p in data['top']])
        self.assertTrue(all(p['mains'] == [] and p['results'] == [] for p in slides['players']))
        kenji = next(p for p in slides['players'] if p['tag'] == 'Kenji')
        self.assertEqual(kenji['vsTop5'], {'won': 4, 'lost': 0})
        self.assertNotIn('id', str(slides)); self.assertNotIn('email', str(slides)); self.assertNotIn('provider', str(slides))
        self.assertTrue(all('id' not in row for row in data['top'] + data['rest']))

    def populate(self):
        B = org.ORGANIZER_FIXTURE_BASE if hasattr(org, 'ORGANIZER_FIXTURE_BASE') else 8999500000
        with self.db.cursor() as q:
            q.execute('UPDATE entrants SET final_placement=1,synced_at=%s WHERE id=%s', ('2026-10-01', B+1101))
            q.execute('UPDATE entrants SET final_placement=2,synced_at=%s WHERE id=%s', ('2026-10-01', B+1102))
            q.execute('UPDATE entrants SET final_placement=3,synced_at=%s WHERE id=%s', ('2026-10-01', B+1103))
            # Later placement, outside this cut's capture, cannot decorate an older top.
            q.execute('UPDATE entrants SET final_placement=1,synced_at=%s WHERE id=%s', ('2099-10-01', B+1201))
            for n, picks in [(1, [(1302, 1), (1296, 1)]), (2, [(1302, 1), (1302, 1)]), (3, [(1302, 1)])]:
                sid = B+5000+n
                q.execute('SELECT winner_entrant_id FROM sets WHERE id=%s', (sid,)); en = q.fetchone()[0]
                for number, (cid, _) in enumerate(picks, 1):
                    gid = B+6000+n*10+number
                    q.execute('INSERT INTO games (id,set_id,game_number,winner_entrant_id,synced_at) VALUES (%s,%s,%s,%s,%s)', (gid,sid,number,en,'2026-10-01'))
                    q.execute('INSERT INTO game_selections (game_id,set_id,entrant_id,character_id) VALUES (%s,%s,%s,%s)', (gid,sid,en,cid))
            # A small tournament and another owner's tournament must never contribute.
            for n in (8,9):
                sid = B+5000+n
                q.execute('SELECT winner_entrant_id FROM sets WHERE id=%s', (sid,)); en=q.fetchone()[0]
                q.execute('INSERT INTO games (id,set_id,game_number,winner_entrant_id,synced_at) VALUES (%s,%s,1,%s,%s)', (B+6500+n,sid,en,'2026-10-01'))
                q.execute('INSERT INTO game_selections (game_id,set_id,entrant_id,character_id) VALUES (%s,%s,%s,1299)', (B+6500+n,sid,en))
        return B

    def test_slide_characters_placements_wins_and_unchanged_points(self):
        self.login('org', '&admin=1'); before=self.call('/organizador-api.php')[1]['data']
        self.populate(); after=self.call('/organizador-api.php')[1]['data']
        self.assertEqual([(r['rank'],r['points'],r['setsWon'],r['setsLost']) for r in before['top']], [(r['rank'],r['points'],r['setsWon'],r['setsLost']) for r in after['top']])
        p=next(p for p in after['slides']['players'] if p['tag']=='Kenji')
        self.assertEqual([(m['characterId'],m['games']) for m in p['mains']], [('1302',3),('1296',1)])
        self.assertEqual(len(p['results']),1); self.assertEqual(p['results'][0]['placement'],1)
        self.assertEqual([w['tag'] for w in p['results'][0]['wins']], ['Vlad','Momo'])
        self.assertTrue(all('Ajeno' not in str(p) and 'Torneo 4' not in str(p) for p in after['slides']['players']))
        momo=next(p for p in after['slides']['players'] if p['tag']=='Momo')
        self.assertEqual(momo['results'][0]['wins'], [])  # beating an unranked opponent is not a highlighted top win

    def test_slide_ambiguous_duplicate_mapping_and_corrected_context_omitted(self):
        self.login('org', '&admin=1'); B=self.populate()
        with self.db.cursor() as q:
            q.execute('INSERT INTO game_selections (game_id,set_id,entrant_id,character_id) VALUES (%s,%s,%s,1295)', (B+6011,B+5001,B+1101))
            q.execute('UPDATE sets SET source_hash=%s WHERE id=%s', ('a'*64,B+5002))
        p=self.call('/organizador-api.php')[1]['data']['slides']['players'][0]
        self.assertEqual([(m['characterId'],m['games']) for m in p['mains']], [('1296',1)])
        with self.db.cursor() as q: q.execute('INSERT INTO entrant_players (entrant_id,player_id) VALUES (%s,%s)', (B+1102,B+3))
        p=self.call('/organizador-api.php')[1]['data']['slides']['players'][0]
        self.assertEqual(p['mains'], [])

    def test_slide_coorganizer_own_premium_and_public_projection_stays_clean(self):
        owner=self.login('org'); self.premium(owner)
        data=self.call('/organizador-api.php')[1]
        invite=self.call('/organizador-api.php', {'action':'invite'}, data['csrf'])[1]['inviteUrl'].split('invita=')[1].split('#')[0]
        co=self.login('co'); csrf=self.call('/organizador-api.php')[1]['csrf']
        self.call('/organizador-api.php', {'action':'join','token':invite}, csrf)
        free=self.call('/organizador-api.php?organizador='+owner)[1]
        self.assertEqual(free['state'],'premium'); self.assertNotIn('slides',str(free))
        self.premium(co)
        paid=self.call('/organizador-api.php?organizador='+owner)[1]
        self.assertEqual(paid['state'],'data'); self.assertEqual(paid['data']['slides']['organizer']['coorganizers'], ['Coorganizador'])
        self.login('org'); data=self.call('/organizador-api.php')[1]
        self.call('/organizador-api.php', {'action':'settings','publicEnabled':True}, data['csrf'])
        public=self.call('/top.php?slug='+data['data']['organizer']['slug'], raw=True)[2]
        self.assertNotIn('slides',public); self.assertNotIn('vsTop5',public)
        directory=self.call('/tops-api.php')[1]
        self.assertNotIn('slides',str(directory)); self.assertNotIn('mains',str(directory))


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(OrganizerSlideHttpTests(name) for name in loader.getTestCaseNames(OrganizerSlideHttpTests) if name.startswith('test_slide_'))

if __name__ == '__main__': unittest.main()
