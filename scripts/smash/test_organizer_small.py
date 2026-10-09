import copy
from datetime import datetime,timezone
import hashlib
import json
import unittest
from unittest.mock import patch

from collect import APIError
from discover import discover, small_organizer_candidates
from test_discover import CatalogClient
from organizer_small import capture,BudgetClient,MAX_ATTEMPTS,MAX_EVENTS
from rank import compute
from publish_ranking import export
from test_rank import fixture as ranking_fixture


def candidate(eid=200,**changes):
    e=dict(id=eid,name='Small',type=1,state='COMPLETED',isOnline=False,numEntrants=8,startAt=1768000000,
           videogame=dict(id=1386),tournament=dict(id=20,name='Small',countryCode='GT'))
    e.update(changes);return e


def national():
    data=ranking_fixture();data['organizerCandidates']=[candidate()];return data


class Client:
    def __init__(self):self.calls=0
    def query(self,q,v):self.calls+=1;return {}


def fetch(client,event):
    for _ in range(3):client.query('mock',{})
    return dict(event,setsFetched=1),{'999':dict(id=999,gamerTag='Solo chico')},{str(900+int(event['id'])):dict(id=900+int(event['id']),event=event)}


class SmallCaptureTests(unittest.TestCase):
    def test_national_calculation_eligibility_and_public_hash_unchanged_after_capture(self):
        data=national();saved=copy.deepcopy(data)
        before=compute(data,player_overrides={'1':'test'})
        public=export(data,before)
        with patch('organizer_small.fetch_event',side_effect=fetch):context=capture(Client(),data)
        after=compute(data,player_overrides={'1':'test'})
        encode=lambda x:json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
        self.assertEqual(data,saved);self.assertEqual(encode(before),encode(after))
        self.assertEqual(hashlib.sha256(encode(public)).hexdigest(),hashlib.sha256(encode(export(data,after))).hexdigest())
        self.assertEqual(public['eligibilityRules']['localMinimumActive'],20)
        self.assertNotIn('999',data['players']);self.assertNotIn('1100',data['sets']);self.assertEqual(context['requests'],3)
        self.assertNotIn('200',after['eventIds'])

    def test_candidate_flag_adds_no_queries_and_changes_only_the_separate_list(self):
        with patch('discover.datetime') as clock:
            clock.now.return_value=datetime(2026,10,4,12,tzinfo=timezone.utc)
            base=discover(CatalogClient(),100,200)
            expanded=discover(CatalogClient(),100,200,organizer_candidates=True)
        self.assertEqual(len(expanded.pop('organizerCandidates')),1)
        self.assertEqual(base,expanded)
        with patch('discover.datetime') as clock, patch('discover.small_organizer_candidates',side_effect=KeyError('missing metadata')):
            clock.now.return_value=datetime(2026,10,4,12,tzinfo=timezone.utc)
            failed=discover(CatalogClient(),100,200,organizer_candidates=True)
        self.assertIsNone(failed.pop('organizerCandidates'));self.assertEqual(base,failed)

    def test_candidate_selection_excludes_online_teams_unfinished_unknown_large_and_outside(self):
        for changes in ({'isOnline':True},{'state':'ACTIVE'},{'type':2},{'numEntrants':20},{'numEntrants':None},{'startAt':1700000000},{'videogame':{'id':1}}):
            e=candidate(**changes);t=dict(e['tournament'],isOnline=False,events=[e])
            self.assertEqual(small_organizer_candidates([t],1767225600,1798783200),[])
        for tchange in ({'isOnline':True},{'countryCode':'MX'}):
            t=dict(candidate()['tournament'],isOnline=False,events=[candidate()]);t.update(tchange)
            self.assertEqual(small_organizer_candidates([t],1767225600,1798783200),[])

    def test_caps_coverage_and_failures_preserve_national(self):
        data=national();data['organizerCandidates']=[candidate(200+i,startAt=1768000000+i) for i in range(12)]
        original=copy.deepcopy(data)
        with patch('organizer_small.fetch_event',side_effect=fetch):result=capture(Client(),data,limit=2)
        self.assertEqual((result['candidateCount'],len(result['events']),len(result['omittedEventIds'])),(12,2,10))
        self.assertEqual(data,original)
        for bad in (0,MAX_EVENTS+1,True):
            with self.assertRaises(ValueError):capture(Client(),data,limit=bad)
        client=Client();bounded=BudgetClient(client);client.calls=MAX_ATTEMPTS-2
        with self.assertRaises(APIError):bounded.query('',{})
        self.assertEqual(client.calls,MAX_ATTEMPTS-2)
        with patch('organizer_small.fetch_event',side_effect=APIError('test')):
            with self.assertRaises(APIError):capture(Client(),data)
        self.assertEqual(data,original)
        times=iter([0,0,121]);bounded=BudgetClient(Client(),clock=lambda:next(times))
        # First two timestamps are the start and the attempted call; a later attempt must stop.
        bounded.query('',{})
        with self.assertRaises(APIError):bounded.query('',{})

    def test_weekly_extension_disabled_by_default_and_fails_open(self):
        from pathlib import Path
        workflow=(Path(__file__).resolve().parents[2]/'.github/workflows/smash-publish.yml').read_text()
        self.assertIn("vars.SMASH_ORGANIZER_SMALL_ENABLED == 'true'",workflow)
        self.assertIn('continue-on-error: true',workflow)
        self.assertIn('--organizer-context scripts/smash/data/organizer-small.json',workflow)
        self.assertNotIn('--include-small',workflow)

if __name__=='__main__':unittest.main(verbosity=2)
