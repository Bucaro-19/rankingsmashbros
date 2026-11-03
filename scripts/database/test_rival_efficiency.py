"""Invented reports only. No network, SQL, credentials or captures."""
import contextlib
import copy
from datetime import datetime,timezone
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import rival_efficiency as review
from rival_automation import new_metrics

NOW=datetime(2026,11,4,tzinfo=timezone.utc)


def sample(rid=1):
    metrics=new_metrics()
    metrics.update(batchesConfirmed=2,playersAdvanced=28,historiesCompleted=0,pagesConfirmed=56,
        sourceSetsSeen=280,pagesWithoutSeasonSets=20,seasonSetsInConfirmedBatches=100,
        competitiveSetsInConfirmedBatches=80,gamesInConfirmedBatches=200,captureAttempts=56,
        rosterSeconds=7,inventorySeconds=3,captureSeconds=56,packageSeconds=1,
        deliveryAndWaitSeconds=400,priorJobWaitSeconds=0,importWaitSeconds=390)
    summary=dict(status='imported',eventId=1687524,registered=343,known=343,added=0,pending=165,
                 queries=63,seconds=470,metrics=metrics)
    return dict(id=rid,head_branch='main',event='schedule',path=review.WORKFLOW,
                created_at=f'2026-11-03T{rid+4:02d}:00:00Z',status='completed',conclusion='success',summary=summary)


class Review(unittest.TestCase):
    def evaluate(self,runs):return review.evaluate(runs,now=NOW)

    def test_zero_two_and_three_normal_observations_do_not_change_the_schedule(self):
        for n in (0,2,3):
            result=self.evaluate([sample(i) for i in range(1,n+1)])
            self.assertEqual(result['status'],'ready_for_owner_review' if n==3 else 'insufficient_observations')
            self.assertEqual(result['observedRuns'],n);self.assertFalse(result['scheduleChangeAllowed'])
            self.assertTrue(result['queueCheckRequired'])
        result=self.evaluate([sample(i) for i in range(1,4)])
        self.assertEqual(result['totals']['pagesConfirmed'],168)
        self.assertIsNone(result['totals']['playersAdvanced'])
        self.assertEqual(result['totals']['importWaitSeconds'],1170)

    def test_old_branch_manual_and_wrong_workflow_cannot_fill_the_three_samples(self):
        rows=[sample(i) for i in range(1,5)]
        rows[0]['created_at']='2026-11-02T22:52:29Z'
        rows[1]['head_branch']='feat/anything';rows[2]['event']='workflow_dispatch'
        rows[3]['path']='.github/workflows/smash-publish.yml'
        self.assertEqual(self.evaluate(rows)['observedRuns'],0)
        with self.assertRaises(ValueError):self.evaluate([sample(1),sample(1),sample(1)])
        with self.assertRaises(ValueError):self.evaluate([sample(i) for i in range(1,14)])

    def test_latest_failure_or_active_capture_cannot_be_skipped_for_older_successes(self):
        for state,conclusion in (('completed','failure'),('completed','cancelled'),('in_progress',None)):
            rows=[sample(i) for i in range(1,5)];rows[-1].update(status=state,conclusion=conclusion)
            result=self.evaluate(rows)
            self.assertEqual(result['status'],'review_required')
            self.assertEqual([r['runId'] for r in result['runs']],[4,3,2])
            self.assertEqual(result['observedRuns'],2)

    def test_missing_old_version_malformed_and_nonfinite_metrics_need_review(self):
        for change in ('absent','version','bool','nan','contradiction','timing','source_hidden'):
            rows=[sample(i) for i in range(1,4)];s=rows[-1]['summary'];m=s['metrics']
            if change=='absent':s.pop('metrics')
            elif change=='version':m['version']=2
            elif change=='bool':m['pagesConfirmed']=True
            elif change=='nan':m['captureSeconds']=float('nan')
            elif change=='contradiction':m['pagesConfirmed']=100
            elif change=='timing':m['importWaitSeconds']=1000
            else:s['status']='registrations_unavailable'
            with self.subTest(change=change):self.assertEqual(self.evaluate(rows)['status'],'review_required')

    def test_retries_roster_retries_pending_growth_and_previous_job_wait_need_review(self):
        for change in ('capture_retry','roster_retry','backlog','queue','unknown_time'):
            rows=[sample(i) for i in range(1,4)];s=rows[-1]['summary'];m=s['metrics']
            if change=='capture_retry':m['captureAttempts']+=1;s['queries']+=1
            elif change=='roster_retry':s['queries']+=1
            elif change=='backlog':s['pending']+=1
            elif change=='queue':m['priorJobWaitSeconds']=1
            else:m['importWaitSeconds']=None
            with self.subTest(change=change):self.assertEqual(self.evaluate(rows)['status'],'review_required')

    def test_no_pending_or_no_useful_sets_is_not_a_reason_to_increase_frequency(self):
        rows=[sample(i) for i in range(1,4)];rows[-1]['summary']['pending']=0
        self.assertEqual(self.evaluate(rows)['status'],'nothing_pending')
        rows=[sample(i) for i in range(1,4)]
        for r in rows:r['summary']['metrics']['competitiveSetsInConfirmedBatches']=0
        self.assertEqual(self.evaluate(rows)['status'],'review_capture_strategy')
        result=review.evaluate(rows,now=review.UNTIL)
        self.assertEqual(result['status'],'authorization_expired');self.assertFalse(result['scheduleChangeAllowed'])

    def test_parser_and_report_never_echo_private_or_unknown_fields(self):
        run=sample();run['summary'].update(token='NEVER ECHO',checkpoint={'tag':'NEVER ECHO'})
        run['summary']['metrics']['raw']='NEVER ECHO'
        log='PRIVATE BODY NEVER ECHO\nstep\t2026-11-03T08:00:00Z '+json.dumps(run['summary'])
        self.assertEqual(review.summary_from_log(log),run['summary'])
        result=self.evaluate([dict(sample(i),summary=copy.deepcopy(run['summary'])) for i in range(1,4)])
        output=json.dumps(result)
        self.assertNotIn('NEVER ECHO',output);self.assertNotIn('"token":',output);self.assertNotIn('"checkpoint":',output)
        self.assertIsNone(review.summary_from_log('No JSON or metrics'))
        with self.assertRaises(ValueError):review.summary_from_log(log+'\n'+log)

    def test_actions_collection_reads_one_metadata_page_and_at_most_three_logs(self):
        rows=[sample(i) for i in range(1,8)]
        def fake(args):
            if args[0]=='api':return json.dumps(dict(workflow_runs=rows))
            self.assertEqual(args[:2],['run','view']);self.assertEqual(args[-1],'--log')
            return 'safe step '+json.dumps(sample(int(args[2]))['summary'])
        with mock.patch.object(review,'gh',side_effect=fake) as gh:
            got=review.collect_actions()
        self.assertEqual([r['id'] for r in got],[7,6,5]);self.assertEqual(gh.call_count,4)
        old=sample();old['created_at']='2026-11-02T22:00:00Z'
        with mock.patch.object(review,'gh',return_value=json.dumps(dict(workflow_runs=[old]))) as gh:
            self.assertEqual(review.collect_actions(),[])
        self.assertEqual(gh.call_count,1)

    def test_cli_failures_are_generic_and_cannot_run_mutating_commands(self):
        for error in (OSError('SECRET'),subprocess.TimeoutExpired('SECRET',45)):
            with mock.patch.object(review.subprocess,'run',side_effect=error),mock.patch('sys.argv',['review','--from-actions']),contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(review.main(),1)
            self.assertEqual(json.loads(out.getvalue()),dict(status='review_unavailable',scheduleChangeAllowed=False))
            self.assertNotIn('SECRET',out.getvalue())
        with mock.patch.object(review.subprocess,'run',return_value=mock.Mock(returncode=0,stdout='{}')) as command:
            review.gh(['api',review.RUNS_ENDPOINT])
        self.assertEqual(command.call_args.args[0],['gh','api',review.RUNS_ENDPOINT])
        for args in (['workflow','run','smash-rival-context.yml'],['variable','set','SMASH_RIVAL_SYNC_ENABLED'],['api','repos/another/private-repo']):
            with mock.patch.object(review.subprocess,'run') as command,self.assertRaises(ValueError):review.gh(args)
            command.assert_not_called()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'reports.json';path.write_text(json.dumps(dict(runs=[])))
            with mock.patch('sys.argv',['review','--input',str(path)]),contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(review.main(),0)
            self.assertEqual(json.loads(out.getvalue())['status'],'insufficient_observations')


if __name__=='__main__':unittest.main(verbosity=2)
