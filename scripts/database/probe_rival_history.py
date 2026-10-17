"""Read-only diagnosis: aggregate/form/stack metadata only, no person values or raw errors."""
import copy,json,os,re,time,traceback,urllib.request
from pathlib import Path
from rival_automation import event_roster,Hosting,merge_state
from rival_context import package
from rival_history import HISTORY,connection,capture_batch
from collect import Client,ENDPOINT
from publish_sql import NoRedirect,encode_transport
from probe_rival_roster import field


def main():
    client=Client(os.environ['STARTGG_TOKEN'])
    roster=event_roster(client,1687524)
    if roster is None:print(json.dumps(dict(status='registrations_unavailable',queries=client.calls)));return
    inv=Hosting(os.environ['SMASH_SQL_SYNC_KEY']).inventory(roster)
    state=merge_state(roster,inv['checkpoint'],inv['knownIds'])
    pid=next((pid for pid,cov in state['coverage'].items() if not cov['complete']),None)
    if pid is None:print(json.dumps(dict(status='no_missing_roots',queries=client.calls)));return
    stage='capture'
    try:
        data,state=capture_batch(client,state)
        stage='package'
        import math
        before=inv['checkpoint']['coverage'] if inv['checkpoint'] else {}
        progressed={pid for pid,cov in state['coverage'].items() if cov!=before.get(pid,dict(nextPage=1,totalPages=None,complete=False))}
        data['audit']['seconds']=math.ceil(data['audit']['seconds'])
        data['roster']=copy.deepcopy(roster);data['roster']['players']={pid:roster['players'][pid] for pid in progressed}
        data['coverage']={pid:state['coverage'][pid] for pid in progressed}
        p=package(data);state['pages']={};stage='transport'
        envelope=dict(operation='analysis_import',eventId=1687524,baseRevision=inv['revision'],package=p,checkpoint=state)
        body=encode_transport(envelope)
        import subprocess
        php="require 'ranking-smash-ultimate/ranking-sync-lib.php';try{rc_validate_envelope(rc_envelope(stream_get_contents(STDIN)));echo json_encode(['stage'=>'php_validated_no_writes']);}catch(Throwable $e){echo json_encode(['stage'=>'php_validation','reason'=>$e instanceof SmashRankingError?$e->reason:'validation_failed','trace'=>array_map(static function($x){return ['file'=>basename($x['file']??''),'line'=>$x['line']??null,'function'=>$x['function']??''];},$e->getTrace())]);}"
        checked=subprocess.run(['php','-r',php],input=body,capture_output=True,check=True)
        print(checked.stdout.decode())
        print(json.dumps(dict(stage='validated_no_writes',queries=client.calls,sets=len(p['content']['entities']['sets']),games=len(p['content']['entities']['games']),bytes=len(body))))
        from publish_sql import request,SyncStopped
        safe=('package_invalid','payload_invalid','analysis_checkpoint_progress_invalid','analysis_checkpoint_regression','analysis_identity_conflict','analysis_unrelated_set','receiver_busy','inbox_unavailable','analysis_job_pending','receiver_unavailable','analysis_batch_limit','analysis_checkpoint_conflict')
        try:
            result=request(os.environ['SMASH_SQL_SYNC_KEY'],body,'application/vnd.smash.analysis+gzip',safe_reasons=safe)
            print(json.dumps(dict(stage='single_authorized_delivery',status=result.get('status') if result.get('status') in ('queued','running','succeeded','failed') else 'unexpected')))
        except SyncStopped as error:print(json.dumps(dict(stage='single_authorized_delivery',reason=str(error) if str(error) in safe else 'unclassified')))

    except Exception as error:
        trace=[dict(file=Path(x.filename).name,function=x.name,line=x.lineno) for x in traceback.extract_tb(error.__traceback__)]
        print(json.dumps(dict(stage=stage,queries=client.calls,errorType=type(error).__name__,trace=trace)))

if __name__=='__main__':
    try:main()
    except Exception:print(json.dumps(dict(status='probe_stopped_no_writes')));raise SystemExit(1)
