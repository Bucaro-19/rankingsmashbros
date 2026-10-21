"""Read-only diagnosis: inventory/capture/local validation, never deliver/import."""
import ast,copy,json,math,os,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import rival_automation as a
from ranking_package import canonical

safe=set()
for filename in ('scripts/database/ranking_package.py','scripts/database/rival_context.py'):
    for node in ast.walk(ast.parse(Path(filename).read_text())):
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='require' and len(node.args)>1 and isinstance(node.args[1],ast.Constant) and isinstance(node.args[1].value,str):safe.add(node.args[1].value)

stage='roster';client=a.Client(os.environ['STARTGG_TOKEN'])
try:
    roster=a.event_roster(client,1687524)
    if roster is None:print(json.dumps(dict(status='registrations_unavailable',queries=client.calls)));raise SystemExit(0)
    stage='inventory';host=a.Hosting(os.environ['SMASH_SQL_SYNC_KEY']);inv=host.inventory(roster)
    if inv.get('pendingJob'):
        print(json.dumps(dict(status='pending_job_no_capture',jobStatus=inv['pendingJob']['status'],queries=client.calls)));raise SystemExit(0)
    state=a.merge_state(roster,inv.get('checkpoint'),inv['knownIds']);prior=copy.deepcopy(state['coverage'])
    stage='capture';data,state=a.capture_batch(client,state);data['audit']['seconds']=math.ceil(data['audit']['seconds'])
    changed={pid for pid,v in state['coverage'].items() if v!=prior.get(pid)}
    data['roster']=copy.deepcopy(roster);data['roster']['players']={pid:roster['players'][pid] for pid in changed}
    data['coverage']={pid:state['coverage'][pid] for pid in changed}
    print(json.dumps(dict(stage='captured',queries=client.calls,roots=len(changed),sets=len(data['sets']))))
    stage='package';pack=a.package(data);state['pages']={}
    env=dict(operation='analysis_import',eventId=1687524,baseRevision=inv['revision'],package=pack,checkpoint=state)
    stage='transport';body=a.encode_transport(env)
    stage='php_local_validation'
    php="require 'ranking-smash-ultimate/ranking-sync-lib.php';try{$v=rc_envelope(stream_get_contents(STDIN));rc_validate_envelope($v);echo json_encode(['ok'=>true]);}catch(Throwable $e){echo json_encode(['ok'=>false,'class'=>get_class($e),'reason'=>$e instanceof SmashRankingError?$e->reason:'local_validation_failed']);exit(1);}"
    r=subprocess.run(['php','-r',php],input=body,capture_output=True,timeout=30)
    result=json.loads(r.stdout)
    print(json.dumps(dict(status='validated_no_delivery',queries=client.calls,php=result,compressedBytes=len(body))))
except Exception as error:
    out=dict(status='probe_failed_no_delivery',stage=stage,errorType=type(error).__name__,queries=client.calls)
    if isinstance(error,ValueError) and str(error) in safe:out['staticConstraint']=str(error)
    if isinstance(error,a.SyncStopped) and str(error) in a.SAFE_REASONS|{'transport_type_unsupported','receiver_unavailable','receiver_response_too_large','payload_too_large'}:out['safeReason']=str(error)
    print(json.dumps(out,ensure_ascii=False));raise SystemExit(1)
