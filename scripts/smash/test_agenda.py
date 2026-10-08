"""No API/FTP/SQL in tests. Real capture is tested through a read-only Actions run."""
import copy
from datetime import datetime, timedelta, timezone
import ftplib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import agenda
from collect import APIError

NOW=datetime(2026,10,8,22,0,tzinfo=timezone.utc)


def event(tid='1',number='1',**overrides):
    value=dict(id=tid+'00'+number,name='Ultimate',slug=f'tournament/t-{tid}/event/e-{number}',
               startAt=int((NOW+timedelta(days=2)).timestamp()),type=1,isOnline=False,
               numEntrants=4,videogame=dict(id=1386),teamRosterSize=None)
    value.update(overrides);return value


def tournament(tid='1',**overrides):
    value=dict(id=tid,name='Torneo',slug='tournament/t-'+tid,url='https://www.start.gg/tournament/t-'+tid,
               countryCode='GT',startAt=int((NOW+timedelta(days=2)).timestamp()),
               endAt=int((NOW+timedelta(days=2,hours=6)).timestamp()),timezone='America/Guatemala',
               city='Xela',addrState='Quetzaltenango',venueName='Venue',venueAddress=None,lat=14.8,lng=-91.5,
               isOnline=False,isRegistrationOpen=True,registrationClosesAt=None,eventRegistrationClosesAt=None,
               numAttendees=4,events=[event(tid)])
    value.update(overrides);return value


class FakeClient:
    def __init__(self,rows=None,mutate=None):self.rows=rows if rows is not None else [tournament()];self.calls=0;self.queries=[];self.mutate=mutate
    def query(self,query,variables):
        self.calls+=1;self.queries.append((query,copy.deepcopy(variables)))
        start=(variables['page']-1)*agenda.PER_PAGE
        con=dict(pageInfo=dict(total=len(self.rows),totalPages=(len(self.rows)+agenda.PER_PAGE-1)//agenda.PER_PAGE),
                 nodes=copy.deepcopy(self.rows[start:start+agenda.PER_PAGE]))
        if self.mutate:self.mutate(con,self.calls)
        return dict(tournaments=con)


def data(rows=None):return agenda.capture(FakeClient(rows),now=NOW)


class FakeFTP:
    def __init__(self,prior=None,fail=None):
        self.files={} if prior is None else {'agenda.json':agenda.encode(prior)};self.fail=fail;self.commands=[]
    def cwd(self,name):self.commands.append(('cwd',name))
    def mkd(self,name):self.commands.append(('mkd',name))
    def retrbinary(self,command,receive):
        self.commands.append(('retr',command))
        if self.fail=='read':raise ftplib.error_perm('550 Permission denied')
        name=command.removeprefix('RETR ')
        if name not in self.files:raise ftplib.error_perm('550 File not found')
        for at in range(0,len(self.files[name]),99):receive(self.files[name][at:at+99])
    def storbinary(self,command,stream):
        self.commands.append(('stor',command));name=command.removeprefix('STOR ');body=stream.read()
        self.files[name]=body
        if self.fail=='upload':
            self.files[name]=body[:20];raise ftplib.error_temp('451 Simulated partial upload')
    def rename(self,source,target):
        self.commands.append(('rename',source,target))
        if self.fail=='rename':raise ftplib.error_perm('550 Rename refused')
        self.files[target]=self.files.pop(source)
        if self.fail=='ack':raise EOFError('Simulated lost rename acknowledgement')
    def delete(self,name):
        self.commands.append(('delete',name));self.files.pop(name,None)


class CaptureTests(unittest.TestCase):
    def test_capture_paginates_orders_and_keeps_small_online_doubles_and_unknowns(self):
        rows=[tournament(str(n),startAt=int((NOW+timedelta(days=12-n)).timestamp()),endAt=None) for n in range(1,7)]
        rows[0]['events']=[event('1',type=2,isOnline=True,teamRosterSize=dict(minPlayers=2,maxPlayers=2))]
        rows[1]['events']=[event('2',type=None,isOnline=None,numEntrants=None)]
        client=FakeClient(rows);out=agenda.capture(client,now=NOW)
        self.assertEqual((out['requests'],out['coverage']['pagesFetched'],len(out['tournaments'])),(2,2,6))
        self.assertEqual([t['id'] for t in out['tournaments']],['6','5','4','3','2','1'])
        self.assertEqual(out['tournaments'][-1]['events'][0]['competitionType'],'doubles')
        self.assertFalse(out['tournaments'][-1]['isOfflineSingles']);self.assertIsNone(out['tournaments'][-2]['isOfflineSingles'])
        self.assertEqual(client.queries[0][1]['after'],int(NOW.timestamp()))
        self.assertEqual([v['page'] for _,v in client.queries],[1,2])
        for forbidden in ('owner','participants','entrants(','user{','contact'):
            self.assertNotIn(forbidden,agenda.QUERY)
        self.assertIn('publiclySearchable:true',agenda.QUERY)
        self.assertIn('published:true',agenda.QUERY)

    def test_nulls_stay_null_and_real_zero_counts_stay_zero(self):
        row=tournament(timezone=None,city=None,addrState=None,venueName=None,lat=None,lng=None,
                       isOnline=None,isRegistrationOpen=None,numAttendees=None,endAt=None)
        row['events']=[event(type=None,isOnline=None,numEntrants=None)]
        out=data([row])['tournaments'][0]
        for key in ('timezone','city','department','venueName','latitude','longitude','isOnline','numAttendees','endAt','isRegistrationOpen','isOfflineSingles'):
            self.assertIsNone(out[key])
        self.assertTrue(out['startAt'].endswith('+00:00'))
        row['numAttendees']=0;row['events'][0]['numEntrants']=0
        out=data([row])['tournaments'][0];self.assertEqual((out['numAttendees'],out['events'][0]['numEntrants']),(0,0))
        row['lat']=row['lng']=0;row['registrationClosesAt']=0
        out=data([row])['tournaments'][0];self.assertIsNone(out['latitude']);self.assertIsNone(out['registrationClosesAt'])

    def test_mixed_format_and_candidates_use_ultimate_events_not_outer_online_flag(self):
        row=tournament(isOnline=True,events=[event(),event(number='2',type=2,isOnline=True,teamRosterSize=dict(minPlayers=2,maxPlayers=2))])
        out=data([row])['tournaments'][0]
        self.assertEqual(out['attendanceType'],'mixed');self.assertTrue(out['isOfflineSingles'])
        self.assertEqual([e['isOfflineSingles'] for e in out['events']],[True,False])
        # A different-game online event may set the tournament flag while all Ultimate is offline.
        row['events']=[event()];out=data([row])['tournaments'][0]
        self.assertTrue(out['isOnline']);self.assertEqual(out['attendanceType'],'offline')

    def test_no_future_claim_for_an_event_without_a_tournament_start(self):
        with self.assertRaises(ValueError):data([tournament(startAt=None)])
        row=tournament(startAt=int(NOW.timestamp()))
        self.assertEqual(data([row])['tournaments'],[])
        values=iter([NOW,NOW+timedelta(days=3)])
        self.assertEqual(agenda.capture(FakeClient(),clock=lambda:next(values))['tournaments'],[])

    def test_complete_empty_source_is_valid_but_missing_or_inconsistent_source_is_not(self):
        self.assertEqual(data([])['coverage']['rawTournaments'],0)
        variants=[lambda c,n:c.update(nodes=None),lambda c,n:c.update(pageInfo=None),
                  lambda c,n:c['pageInfo'].update(total=2),lambda c,n:c['pageInfo'].update(totalPages=0),
                  lambda c,n:c['pageInfo'].update(total=500,totalPages=100),lambda c,n:c.update(nodes=[])]
        for mutate in variants:
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):agenda.capture(FakeClient(mutate=mutate),now=NOW)
        class Missing:
            calls=0
            def query(self,*args):self.calls+=1;return dict(tournaments=None)
        with self.assertRaises(ValueError):agenda.capture(Missing(),now=NOW)

    def test_duplicate_or_changing_pages_never_produce_partial_success(self):
        rows=[tournament(str(i)) for i in range(1,7)]
        def change(con,n):
            if n==2:con['pageInfo']['total']=7
        with self.assertRaises(ValueError):agenda.capture(FakeClient(rows,change),now=NOW)
        rows[-1]=rows[0]
        with self.assertRaises(ValueError):data(rows)
        row=tournament(events=[event()]*agenda.EVENT_LIMIT)
        with self.assertRaises(ValueError):data([row])

    def test_wrong_country_game_and_malformed_dates_do_not_turn_into_an_empty_agenda(self):
        for row in (tournament(countryCode='MX'),tournament(endAt=int((NOW+timedelta(days=1)).timestamp())),
                    tournament(timezone='Invalid/Zone'),tournament(events=[event(videogame=dict(id=1))])):
            with self.subTest(row=row),self.assertRaises(ValueError):data([row])

    def test_failed_capture_preserves_the_previous_local_file_and_does_not_call_ftp(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'agenda.json';path.write_bytes(b'previous-public-agenda')
            client=FakeClient();client.query=lambda *args:(_ for _ in ()).throw(APIError('Simulated API rejection'))
            with patch.dict(os.environ,{'STARTGG_TOKEN':'synthetic-test-only'}),patch.object(agenda,'Client',return_value=client), \
                    patch.object(agenda.ftplib,'FTP') as ftp,patch('sys.argv',['agenda.py','capture','--output',str(path)]), \
                    self.assertRaises(SystemExit):agenda.main()
            self.assertEqual(path.read_bytes(),b'previous-public-agenda');ftp.assert_not_called()


class ValidationTests(unittest.TestCase):
    def test_strict_version_privacy_identifiers_order_coordinate_count_and_size_guards(self):
        base=data([tournament('2'),tournament('1')])
        def bad(change):
            value=copy.deepcopy(base);change(value)
            with self.assertRaises(ValueError):agenda.validate(value,now=NOW)
        for change in (lambda r:r.update(schemaVersion=2),lambda r:r.update(schemaVersion=True),
                       lambda r:r.update(ownerId='private'),lambda r:r['tournaments'][0].update(contacts=[]),
                       lambda r:r['tournaments'][0]['events'][0].update(participants=[]),
                       lambda r:r['tournaments'].reverse(),lambda r:r['tournaments'][0].update(id='0'),
                       lambda r:r['tournaments'][0].update(latitude=91),lambda r:r['tournaments'][0].update(longitude=float('nan')),
                       lambda r:r['tournaments'][0].update(numAttendees=-1),lambda r:r['tournaments'][0].update(isRegistrationOpen=1),
                       lambda r:r['tournaments'][0].update(startAt='2026-10-10T22:00:00'),
                       lambda r:r['tournaments'][0].update(isOfflineSingles=False),
                       lambda r:r['tournaments'][0].update(attendanceType='online'),
                       lambda r:r.update(generatedAt=(NOW+timedelta(hours=1)).isoformat())):bad(change)
        with patch.object(agenda,'MAX_BYTES',10),self.assertRaises(ValueError):agenda.validate(base,now=NOW)
        with self.assertRaises(ValueError):agenda.validate(base,now=NOW+timedelta(days=3),fresh=True)
        with self.assertRaises(ValueError):agenda.validate(base,now=NOW+timedelta(days=2))

    def test_url_scheme_host_credentials_path_and_event_parent_are_enforced(self):
        for url in ('https://evil.test/tournament/t-1','http://www.start.gg/tournament/t-1',
                    'https://www.start.gg.evil.test/tournament/t-1','https://a:b@start.gg/tournament/t-1',
                    'https://www.start.gg/tournament/t-1?token=secret','https://www.start.gg:444/tournament/t-1',
                    'https://www.start.gg/tournament/wrong'):
            with self.subTest(url=url),self.assertRaises(ValueError):data([tournament(url=url)])
        value=data();e=value['tournaments'][0]['events'][0]
        e['slug']='tournament/wrong/event/e-1';e['url']='https://www.start.gg/'+e['slug']
        with self.assertRaises(ValueError):agenda.validate(value,now=NOW)

    def test_seed_is_a_real_snapshot_valid_at_its_capture_and_not_a_permanent_live_listing(self):
        path=agenda.DEFAULT_OUTPUT
        value=agenda.load(path);agenda.validate(value,now=agenda.aware(value['generatedAt']))
        self.assertLessEqual(path.stat().st_size,agenda.MAX_BYTES)

    def test_local_save_is_atomic_and_removes_only_its_temporary_file_on_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'agenda.json';path.write_bytes(b'old')
            with patch.object(Path,'replace',side_effect=OSError('synthetic write failure')),self.assertRaises(OSError):agenda.save(path,data())
            self.assertEqual(path.read_bytes(),b'old');self.assertEqual(list(Path(tmp).iterdir()),[path])
            agenda.save(path,data());self.assertEqual(agenda.load(path)['schemaVersion'],1)


class PublicationTests(unittest.TestCase):
    def test_only_agenda_is_uploaded_and_rename_is_after_full_upload(self):
        old=data();new=data([tournament('2')]);ftp=FakeFTP(old)
        agenda.publish(ftp,new,clock=lambda:NOW)
        self.assertEqual(json.loads(ftp.files['agenda.json']),new)
        self.assertEqual(set(ftp.files),{'agenda.json'})
        commands=[c[0] for c in ftp.commands];self.assertLess(commands.index('stor'),commands.index('rename'))
        self.assertEqual(ftp.commands[0],('cwd','data'))
        names=[c[1] for c in ftp.commands if c[0]=='stor']
        self.assertEqual(len(names),1);self.assertRegex(names[0],r'^STOR agenda\.json\.[0-9a-f]{32}\.tmp$')
        self.assertNotIn('public.json',str(ftp.commands))

    def test_partial_upload_and_failed_rename_keep_old_agenda_and_clean_only_temp(self):
        old=data();new=data([tournament('2')])
        for fail in ('upload','rename'):
            with self.subTest(fail=fail):
                ftp=FakeFTP(old,fail)
                with self.assertRaises(ftplib.Error):agenda.publish(ftp,new,clock=lambda:NOW)
                self.assertEqual(ftp.files,{'agenda.json':agenda.encode(old)})
                self.assertTrue(any(c[0]=='delete' and c[1]!='agenda.json' for c in ftp.commands))

    def test_lost_rename_acknowledgement_leaves_a_complete_file_not_a_partial_or_deletion(self):
        old=data();new=data([tournament('2')]);ftp=FakeFTP(old,'ack')
        with self.assertRaises(EOFError):agenda.publish(ftp,new,clock=lambda:NOW)
        self.assertEqual(ftp.files,{'agenda.json':agenda.encode(new)})

    def test_stale_invalid_and_started_during_upload_never_replace_old_file(self):
        old=data();ftp=FakeFTP(old);value=copy.deepcopy(old);value['tournaments'][0]['latitude']=91
        with self.assertRaises(ValueError):agenda.publish(ftp,value,clock=lambda:NOW)
        self.assertEqual(ftp.commands,[])
        times=iter([NOW,NOW+timedelta(days=3)])
        with self.assertRaises(ValueError):agenda.publish(ftp,old,clock=lambda:next(times))
        self.assertEqual(ftp.files,{'agenda.json':agenda.encode(old)})
        self.assertFalse(any(c[0]=='rename' for c in ftp.commands))

    def test_valid_empty_agenda_cannot_erase_future_announcements_or_hide_read_denial(self):
        empty=data([]);old=data()
        for fail in (None,'read'):
            with self.subTest(fail=fail):
                ftp=FakeFTP(old,fail)
                with self.assertRaises((ValueError,ftplib.Error)):agenda.publish(ftp,empty,clock=lambda:NOW)
                self.assertEqual(ftp.files,{'agenda.json':agenda.encode(old)})
                self.assertFalse(any(c[0]=='stor' for c in ftp.commands))
        for prior in (None,empty):
            ftp=FakeFTP(prior);agenda.publish(ftp,empty,clock=lambda:NOW)
            self.assertEqual(json.loads(ftp.files['agenda.json'])['tournaments'],[])
        ftp=FakeFTP(old);current=NOW+timedelta(days=2,hours=1);empty['generatedAt']=current.isoformat()
        agenda.publish(ftp,empty,clock=lambda:current)
        self.assertEqual(json.loads(ftp.files['agenda.json'])['tournaments'],[])

    def test_remote_traversal_is_rejected_before_ftp_and_publish_defaults_to_plan(self):
        for remote in ('..','site/../../other','/absolute','a b','.'):
            ftp=FakeFTP()
            if remote=='.':continue
            with self.assertRaises(ValueError):agenda.publish(ftp,data(),remote=remote,clock=lambda:NOW)
            self.assertEqual(ftp.commands,[])
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'agenda.json';agenda.save(path,data())
            with patch.object(agenda,'utc_now',return_value=NOW),patch.object(agenda.ftplib,'FTP') as ftp, \
                    patch('sys.argv',['agenda.py','publish',str(path)]):agenda.main()
            ftp.assert_not_called()

    def test_workflow_serializes_ftp_never_dispatches_other_work_and_cannot_publish_a_branch(self):
        root=Path(__file__).resolve().parents[2]
        workflow=(root/'.github/workflows/smash-agenda.yml').read_text()
        for expected in ('group: smash-gt-publication','cancel-in-progress: false',"cron: '17 13 * * *'",'SMASH_AGENDA_ENABLED',
                         "github.ref == 'refs/heads/main'",'inputs.publish == true','default: false','agenda.py capture',
                         'agenda.py validate','agenda.py publish ranking-smash-ultimate/data/agenda.json --apply'):
            self.assertIn(expected,workflow)
        for forbidden in ('deploy.py','STARTGG_TOKEN: ${{ secrets.STARTGG_TOKEN }}\n          FTP_',
                          'publish_sql','discover.py','ranking-sync','recurrente','gh workflow run'):
            self.assertNotIn(forbidden,workflow)
        from deploy import FILES
        self.assertNotIn('data/agenda.json',FILES) # assets-only must never restore a stale Git seed


if __name__=='__main__':unittest.main(verbosity=2)
