"""Review three normal captures before considering a shorter schedule. Read only.

Reads local invented reports or bounded GitHub Actions logs. Never calls start.gg,
MySQL, the receiver, gh workflow run, or gh variable set. Does not activate anything.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

from rival_automation import COUNTERS, TIMINGS, UNTIL

REPO='Bucaro-19/rankingsmashbros'
WORKFLOW='.github/workflows/smash-rival-context.yml'
ROLLOUT='2026-11-03T03:08:11Z'  # PR #130 merge; earlier reports cannot measure this phase.
REQUIRED_RUNS=3
MAX_RUNS=12
MAX_BYTES=8*1024*1024
RUNS_ENDPOINT=f'repos/{REPO}/actions/workflows/smash-rival-context.yml/runs?branch=main&event=schedule&per_page={MAX_RUNS}'


def at(value):
    if not isinstance(value,str):raise ValueError('invalid_date')
    result=datetime.fromisoformat(value.replace('Z','+00:00'))
    if result.tzinfo is None:raise ValueError('invalid_date')
    return result


def number(value,*,integer=False):
    import math
    if type(value) not in ((int,) if integer else (int,float)) or not math.isfinite(value) or value<0:
        raise ValueError('invalid_metric')
    return value


def summary_from_log(raw):
    """Discard everything except the one aggregate summary for the authorized event."""
    matches=[]
    for line in raw.splitlines():
        start=line.find('{')
        if start<0:continue
        try:value=json.loads(line[start:])
        except ValueError:continue
        if isinstance(value,dict) and value.get('eventId')==1687524 and isinstance(value.get('metrics'),dict):
            matches.append(value)
    if len(matches)>1:raise ValueError('ambiguous_summary')
    return matches[0] if matches else None


def checked_summary(value):
    if not isinstance(value,dict) or value.get('eventId')!=1687524:raise ValueError('invalid_summary')
    metrics=value.get('metrics')
    if not isinstance(metrics,dict) or type(metrics.get('version')) is not int or metrics['version']!=1:
        raise ValueError('invalid_metrics_version')
    counters={key:number(metrics.get(key),integer=True) for key in COUNTERS}
    timings={key:None if metrics.get(key) is None else number(metrics[key]) for key in TIMINGS}
    if value.get('status') not in ('imported','already_imported'):raise ValueError('capture_not_successful')
    out={key:number(value.get(key),integer=True) for key in ('registered','known','added','pending','queries')}
    out['seconds']=number(value.get('seconds'))
    if not (out['pending']<=out['registered']<=1000 and out['known']<=out['registered'] and out['added']<=out['registered']):
        raise ValueError('invalid_counts')
    m=counters
    if not (m['historiesCompleted']<=m['playersAdvanced']<=m['pagesConfirmed']<=m['captureAttempts']<=60
            and m['batchesConfirmed']<=min(2,m['pagesConfirmed']) and m['pagesWithoutSeasonSets']<=m['pagesConfirmed']
            and m['competitiveSetsInConfirmedBatches']<=m['seasonSetsInConfirmedBatches']<=m['sourceSetsSeen']
            and m['sourceSetsSeen']<=m['pagesConfirmed']*5 and m['gamesInConfirmedBatches']<=m['batchesConfirmed']*1500):
        raise ValueError('inconsistent_metrics')
    if bool(m['batchesConfirmed'])!=bool(m['pagesConfirmed']):raise ValueError('inconsistent_metrics')
    if value['status']=='already_imported' and out['pending']:raise ValueError('inconsistent_metrics')
    measured=[timings[key] for key in TIMINGS if key!='importWaitSeconds' and timings[key] is not None]
    if sum(measured)>out['seconds']+0.02:raise ValueError('inconsistent_timings')
    if all(timings[key] is not None for key in ('importWaitSeconds','deliveryAndWaitSeconds','priorJobWaitSeconds')):
        if timings['importWaitSeconds']>timings['deliveryAndWaitSeconds']+timings['priorJobWaitSeconds']+0.02:
            raise ValueError('inconsistent_timings')
    out['metrics']=dict(version=1,**counters,**timings)
    return out


def evaluate(runs,*,now=None):
    if not isinstance(runs,list) or len(runs)>MAX_RUNS:raise ValueError('run_limit')
    selected=[];seen=set()
    for run in runs:
        if not isinstance(run,dict):raise ValueError('invalid_run')
        rid=run.get('id')
        if type(rid) is not int or rid<1 or rid in seen:raise ValueError('duplicate_or_invalid_run')
        seen.add(rid)
        if (run.get('head_branch')!='main' or run.get('event')!='schedule' or run.get('path')!=WORKFLOW
                or at(run.get('created_at'))<at(ROLLOUT)):continue
        selected.append(run)
    selected.sort(key=lambda run:(at(run['created_at']),run['id']),reverse=True)
    selected=selected[:REQUIRED_RUNS]  # Never cherry-pick three older successes around a recent failure.
    result=dict(status='insufficient_observations',requiredRuns=REQUIRED_RUNS,observedRuns=0,
                scheduleChangeAllowed=False,queueCheckRequired=True,runs=[],totals=None,
                notes=['No modifica horarios, variables, checkpoint ni datos.',
                       'La revisión de cola/429 compartidos y la orden del dueño siguen siendo necesarias.'])
    problems=[];summaries=[]
    for run in selected:
        row=dict(runId=run['id'])
        if run.get('status')!='completed':row['status']='capture_in_progress'
        elif run.get('conclusion')!='success':row['status']='failed_capture'
        else:
            try:s=checked_summary(run.get('summary'))
            except (ValueError,TypeError,KeyError,OverflowError):row['status']='metrics_unavailable_or_invalid'
            else:
                row.update(status='observed',**s);summaries.append(s)
        if row['status']!='observed':problems.append(row['status'])
        result['runs'].append(row)
    result['observedRuns']=len(summaries)
    if not (now or datetime.now(timezone.utc))<UNTIL:result['status']='authorization_expired';return result
    if problems:result['status']='review_required';return result
    if len(summaries)<REQUIRED_RUNS:return result
    result['totals']={key:sum(s['metrics'][key] for s in summaries) for key in COUNTERS}
    # Anonymous per-run counts cannot establish distinct people across runs.
    result['totals']['playersAdvanced']=None
    result['notes'].append('Los totales suman contadores por ejecución; no son sets/games únicos entre ejecuciones. Jugadores distintos entre ejecuciones: desconocido.')
    result['totals'].update({key:None if any(s['metrics'][key] is None for s in summaries)
                            else round(sum(s['metrics'][key] for s in summaries),3) for key in TIMINGS})
    latest=summaries[0]
    if latest['pending']==0:result['status']='nothing_pending';return result
    # Retries can be a 429, 5xx or transport error. Never infer which from a counter.
    retries=any(s['metrics']['captureAttempts']!=s['metrics']['pagesConfirmed']
                or s['queries']!=s['metrics']['captureAttempts']+(s['registered']+49)//50 for s in summaries)
    prior_wait=any(s['metrics']['priorJobWaitSeconds'] is None or s['metrics']['priorJobWaitSeconds']>0 for s in summaries)
    unknown_time=any(any(s['metrics'][key] is None for key in TIMINGS) for s in summaries)
    growing=any(newer['pending']>older['pending'] for newer,older in zip(summaries,summaries[1:]))
    if retries or prior_wait or unknown_time or growing or any(s['seconds']>=7200 for s in summaries):
        result['status']='review_required'
        result['signals']=dict(retriesOrUnexplainedRequests=retries,priorJobWait=prior_wait,
                               missingTiming=unknown_time,pendingIncreased=growing)
    elif not result['totals']['competitiveSetsInConfirmedBatches']:
        result['status']='review_capture_strategy'
    else:result['status']='ready_for_owner_review'
    return result


def gh(args):
    allowed=(args==['api',RUNS_ENDPOINT] or (len(args)==6 and args[:2]==['run','view']
             and isinstance(args[2],str) and args[2].isdigit() and 0<int(args[2])<10**18
             and args[3:]==['--repo',REPO,'--log']))
    if not allowed:raise ValueError('github_operation_not_readonly')
    try:run=subprocess.run(['gh',*args],capture_output=True,text=True,timeout=45)
    except (OSError,subprocess.TimeoutExpired):raise ValueError('github_read_unavailable') from None
    if run.returncode or len(run.stdout.encode())>MAX_BYTES:raise ValueError('github_read_unavailable')
    return run.stdout


def collect_actions():
    data=json.loads(gh(['api',RUNS_ENDPOINT]))
    if not isinstance(data,dict):raise ValueError('invalid_github_runs')
    runs=data.get('workflow_runs')
    if not isinstance(runs,list) or len(runs)>MAX_RUNS:raise ValueError('invalid_github_runs')
    eligible=[]
    for run in runs:
        if not isinstance(run,dict):raise ValueError('invalid_github_run')
        if (run.get('head_branch')=='main' and run.get('event')=='schedule' and run.get('path')==WORKFLOW
                and at(run.get('created_at'))>=at(ROLLOUT)):
            eligible.append({key:run.get(key) for key in ('id','head_branch','event','path','created_at','status','conclusion')})
    eligible.sort(key=lambda run:(at(run['created_at']),run['id']),reverse=True)
    eligible=eligible[:REQUIRED_RUNS]
    for run in eligible:
        if type(run['id']) is not int or run['id']<1:raise ValueError('invalid_github_run')
        if run['status']=='completed' and run['conclusion']=='success':
            run['summary']=summary_from_log(gh(['run','view',str(run['id']),'--repo',REPO,'--log']))
    return eligible


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    inputs=parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--from-actions',action='store_true',help='Solo leer hasta 12 metadatos y tres logs programados de main.')
    inputs.add_argument('--input',type=Path,help='JSON local con array runs, para revisión o pruebas sin red.')
    args=parser.parse_args()
    try:
        if args.from_actions:runs=collect_actions()
        else:
            if args.input.is_symlink() or args.input.stat().st_size>MAX_BYTES:raise ValueError('invalid_input')
            runs=json.loads(args.input.read_text())['runs']
        print(json.dumps(evaluate(runs),ensure_ascii=False));return 0
    except (ValueError,TypeError,KeyError,OSError,OverflowError):
        print(json.dumps(dict(status='review_unavailable',scheduleChangeAllowed=False)));return 1


if __name__=='__main__':raise SystemExit(main())
