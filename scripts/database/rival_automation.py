"""Bounded tournament-roster context through the existing signed hosting channel.

No SQL driver/credentials in Actions. No ranking publisher, FTP, artifacts or public files.
Only aggregates reach stdout/step summary. Private checkpoints live on BanaHosting.
"""
import copy
from datetime import datetime, timezone
import json
import hashlib
import math
import os
from pathlib import Path
import re
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'smash'))
from collect import APIError,Client
from organizer_small import BudgetClient
from rival_history import new_state,capture_batch,MAX_PLAYERS
from rival_context import package
from publish_sql import request,encode_transport,SyncStopped

UNTIL=datetime(2027,1,1,6,tzinfo=timezone.utc) # Owner renewal 27/oct: finish 2026 context by end of 31/Dec GT/SV.
MAX_BATCHES=2
SAFE_REASONS=frozenset(('analysis_migration_required','analysis_schema_invalid','analysis_entity_authorization_required',
    'analysis_authorization_expired','analysis_event_not_authorized','analysis_checkpoint_conflict','analysis_checkpoint_progress_invalid','analysis_checkpoint_regression','analysis_identity_conflict',
    'analysis_failed_job_requires_review','analysis_queue_limit','analysis_batch_limit',
    'analysis_source_shape_unexpected','analysis_source_query_failed','analysis_history_source_failed','analysis_unrelated_set'))
EVENT_ROSTER='''query($id:ID!,$page:Int!){
 event(id:$id){
  id name slug type numEntrants startAt isOnline videogame{id name}
  tournament{id name slug countryCode startAt endAt timezone}
  entrants(query:{page:$page,perPage:50}){
   pageInfo{total totalPages}
   nodes{participants{player{id gamerTag user{slug location{country}}}}}
  }
 }
}'''


def active(now=None):return (now or datetime.now(timezone.utc))<UNTIL


def emit_summary(summary):
    # Only allowlisted aggregates; never raw provider/driver/header/body/roster data.
    print(json.dumps(summary,ensure_ascii=False))
    target=os.environ.get('GITHUB_STEP_SUMMARY')
    if target:
        lines=['## Contexto de análisis',f"Estado: `{summary['status']}`",'','| Inscritos | Conocidos | Agregados | Pendientes | Consultas | Segundos |','|---:|---:|---:|---:|---:|---:|',
               '| '+' | '.join('desconocido' if summary[k] is None else str(summary[k]) for k in ('registered','known','added','pending','queries','seconds'))+' |',
               '', 'Sets sin vínculo con el inscrito omitidos en tandas confirmadas: '+str(summary.get('unlinkedSetsSkipped',0))]
        with open(target,'a') as out:out.write('\n'.join(lines)+'\n')


def source_require(condition):
    if not condition:raise SyncStopped('analysis_source_shape_unexpected')


def roster_page(conn):
    """Null/missing/empty roster data is unavailable, never a verified zero roster.

    Wrong types and contradictory nonempty pagination are still errors. Stop at
    the first unavailable page without alternate queries or a partial inventory.
    """
    if conn is None:return None
    source_require(isinstance(conn,dict))
    nodes=conn.get('nodes');info=conn.get('pageInfo')
    source_require(nodes is None or isinstance(nodes,list))
    source_require(info is None or isinstance(info,dict))
    total=info.get('total') if info is not None else None
    pages=info.get('totalPages') if info is not None else None
    for number in (total,pages):source_require(number is None or (type(number) is int and number>=0))
    if not nodes or total is None or pages is None:return None
    source_require(total>0 and pages>0 and total<=MAX_PLAYERS and pages<=MAX_PLAYERS//50)
    return nodes,total,pages


def event_roster(client,event_id):
    """One request if hidden. No alternate participant route or schema/metadata probe."""
    b=BudgetClient(client);players={};expected=None
    for page in range(1,MAX_PLAYERS//50+1):
        try:data=b.query(EVENT_ROSTER,dict(id=event_id,page=page))
        except APIError:raise SyncStopped('analysis_source_query_failed') from None
        except (AttributeError,KeyError,TypeError,ValueError):raise SyncStopped('analysis_source_shape_unexpected') from None
        source_require(isinstance(data,dict))
        node=data.get('event');source_require(isinstance(node,dict))
        vg=node.get('videogame');t=node.get('tournament')
        source_require(str(node.get('id'))==str(event_id) and type(node.get('type')) is int and node['type']==1)
        source_require(isinstance(vg,dict) and str(vg.get('id'))=='1386' and isinstance(t,dict))
        if event_id==1687524:
            source_require(str(t.get('id'))=='942547' and t.get('countryCode')=='SV' and t.get('slug')=='tournament/legends7')
        result=roster_page(node.get('entrants'))
        if result is None:return None
        nodes,total,pages=result
        source_require(expected is None or expected==(total,pages));expected=(total,pages)
        for entrant in nodes:
            source_require(isinstance(entrant,dict));people=entrant.get('participants')
            source_require(isinstance(people,list) and len(people)==1 and isinstance(people[0],dict))
            p=people[0].get('player');source_require(isinstance(p,dict))
            pid=str(p.get('id'));tag=p.get('gamerTag')
            source_require(re.fullmatch('[1-9][0-9]*',pid) is not None and pid not in players)
            source_require(isinstance(tag,str) and 0<len(tag)<=100)
            players[pid]=p
        if page>=pages:break
    source_require(expected is not None and len(players)==expected[0])
    event={k:v for k,v in node.items() if k not in ('entrants','tournament')}
    return dict(schemaVersion=1,kind='analysis_roster',capturedAt=datetime.now(timezone.utc).isoformat(),
                event=event,tournament=t,players=players,source='entrants',registrations=len(players))


def merge_state(roster,checkpoint,known):
    ids=set(roster['players']);known=set(map(str,known));old=copy.deepcopy(checkpoint) if checkpoint else new_state(roster,known,2026)
    prior=old['coverage'];old.update(roster=copy.deepcopy(roster),pages={})
    # SQL already has the national/history context for known registrants. Resume partial
    # roots even after their first batch inserted a player row; do not restart all known players.
    old['coverage']={pid:prior.get(pid,dict(nextPage=1,totalPages=None,complete=False)) for pid in sorted(ids,key=int) if pid in prior or pid not in known}
    old['knownPlayerIds']=sorted(ids & known,key=int)
    return old


class Hosting:
    def __init__(self,key,*,pause=time.sleep,clock=time.monotonic):self.key=key;self.pause=pause;self.clock=clock
    def call(self,value):return request(self.key,encode_transport(value),'application/vnd.smash.analysis+gzip',response_limit=2*1024*1024,safe_reasons=SAFE_REASONS)
    def inventory(self,roster):return self.call(dict(operation='analysis_inventory',roster=roster))
    def deliver(self,envelope):
        # Same body on a lost response. Receiver deduplicates its hash; no API capture retry.
        body=encode_transport(envelope)
        digest=hashlib.sha256(body).hexdigest();last=None
        for attempt in range(3):
            try:last=request(self.key,body,'application/vnd.smash.analysis+gzip',safe_reasons=SAFE_REASONS);break
            except SyncStopped as error:
                if str(error) in SAFE_REASONS:raise
                if attempt==2:raise
                self.pause(5*(attempt+1))
        return self.wait(envelope['eventId'],digest,last)
    def wait(self,event_id,digest,last):
        end=self.clock()+600
        while last['status'] in ('queued','running'):
            if self.clock()>=end:raise SyncStopped('analysis_import_pending')
            self.pause(min(15,max(0,end-self.clock())))
            last=request(self.key,json.dumps(dict(operation='analysis_status',eventId=event_id,sha256=digest)).encode(),'application/json',safe_reasons=SAFE_REASONS)
        if last['status']!='succeeded':raise SyncStopped(last.get('reason') if last.get('reason') in SAFE_REASONS else 'analysis_import_failed')
        return last


def run(client,hosting,event_id,*,now=None,clock=time.monotonic):
    start=clock();summary=dict(status='disabled',eventId=event_id,registered=None,known=None,added=0,pending=None,queries=0,seconds=0,unlinkedSetsSkipped=0)
    try:
        if not active(now):summary['status']='authorization_expired';return summary
        if event_id!=1687524:raise SyncStopped('analysis_event_not_authorized')
        roster=event_roster(client,event_id)
        summary['queries']=client.calls
        if roster is None:summary['status']='registrations_unavailable';return summary
        summary.update(registered=roster['registrations'],pending=roster['registrations'])
        for batch in range(MAX_BATCHES):
            if not active(now):raise SyncStopped('authorization_expired')
            inventory=hosting.inventory(roster) # Checks 007 before any history query or queue insert.
            if inventory.get('pendingJob'):
                pending=inventory['pendingJob'];hosting.wait(event_id,pending['sha256'],pending)
                inventory=hosting.inventory(roster)
            known=inventory['knownIds'];checkpoint=inventory.get('checkpoint')
            if summary['known'] is None:summary['known']=len(known)
            state=merge_state(roster,checkpoint,known)
            pending=sum(not c['complete'] for c in state['coverage'].values());summary['pending']=pending
            if not pending:summary['status']='already_imported' if not summary['added'] else 'imported';break
            before=copy.deepcopy(state['coverage'])
            data,state=capture_batch(client,state)
            if pending and not data['audit']['requests']:raise APIError('capture_made_no_progress')
            # Integer transport matches PHP/Python canonical hashes; accurate fractional time stays in the summary.
            data['audit']['seconds']=math.ceil(data['audit']['seconds'])
            progressed={pid for pid,cov in state['coverage'].items() if cov!=before.get(pid)}
            data['roster']=copy.deepcopy(roster);data['roster']['players']={pid:roster['players'][pid] for pid in progressed}
            data['coverage']={pid:state['coverage'][pid] for pid in progressed}
            pack=package(data);state['pages']={}
            envelope=dict(operation='analysis_import',eventId=event_id,baseRevision=inventory['revision'],package=pack,checkpoint=state)
            hosting.deliver(envelope)
            after=hosting.inventory(roster)
            summary['added']+=after['lastResult']['newRosterPlayers']
            summary['unlinkedSetsSkipped']+=data['audit'].get('unlinkedSetsSkipped',0)
            summary.update(pending=sum(not c['complete'] for c in state['coverage'].values()),status='imported')
            if not summary['pending']:break
        return summary
    except Exception:
        summary['status']='failed';raise
    finally:
        summary['queries']=client.calls;summary['seconds']=round(clock()-start,3)
        emit_summary(summary)


def main():
    started=False;event_id=None
    try:
        raw=os.environ.get('SMASH_RIVAL_EVENT_ID','1687524')
        if not re.fullmatch('[1-9][0-9]{0,17}',raw):raise ValueError('event_invalid')
        event_id=int(raw)
        if not active():started=True;run(Client(''),None,event_id);return 0
        key=os.environ.get('SMASH_SQL_SYNC_KEY','');token=os.environ.get('STARTGG_TOKEN','')
        if not re.fullmatch('[a-f0-9]{64}',key) or not token:raise ValueError('private_configuration_required')
        started=True;run(Client(token),Hosting(key),event_id);return 0
    except Exception as error:
        if not started:emit_summary(dict(status='configuration_invalid',eventId=event_id,registered=None,known=None,added=0,pending=None,queries=0,seconds=0))
        reason=('analysis_history_source_failed' if isinstance(error,APIError) else str(error) if isinstance(error,SyncStopped) and str(error) in SAFE_REASONS else 'analysis_automation_stopped_check_source_schema_queue_and_authorization')
        print(json.dumps(dict(ok=False,reason=reason)));return 1
if __name__=='__main__':sys.exit(main())
