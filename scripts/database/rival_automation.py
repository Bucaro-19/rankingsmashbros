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
from rival_history import connection,new_state,capture_batch,MAX_PLAYERS
from rival_context import package
from publish_sql import request,encode_transport,SyncStopped

UNTIL=datetime(2026,10,26,6,tzinfo=timezone.utc) # End of 25/oct, Guatemala/El Salvador.
MAX_BATCHES=2
SAFE_REASONS=frozenset(('analysis_migration_required','analysis_schema_invalid','analysis_entity_authorization_required',
    'analysis_authorization_expired','analysis_event_not_authorized','analysis_checkpoint_conflict',
    'analysis_failed_job_requires_review','analysis_queue_limit','analysis_batch_limit'))
EVENT_ROSTER='''query($id:ID!,$page:Int!){event(id:$id){id name slug type numEntrants startAt isOnline videogame{id name}
 tournament{id name slug countryCode startAt endAt timezone}
 entrants(query:{page:$page,perPage:50}){pageInfo{total totalPages}nodes{participants{player{id gamerTag user{slug location{country}}}}}}}'''


def active(now=None):return (now or datetime.now(timezone.utc))<UNTIL


def emit_summary(summary):
    # Only allowlisted aggregates; never raw provider/driver/header/body/roster data.
    print(json.dumps(summary,ensure_ascii=False))
    target=os.environ.get('GITHUB_STEP_SUMMARY')
    if target:
        lines=['## Contexto de análisis',f"Estado: `{summary['status']}`",'','| Inscritos | Conocidos | Agregados | Pendientes | Consultas | Segundos |','|---:|---:|---:|---:|---:|---:|',
               '| '+' | '.join('desconocido' if summary[k] is None else str(summary[k]) for k in ('registered','known','added','pending','queries','seconds'))+' |']
        with open(target,'a') as out:out.write('\n'.join(lines)+'\n')


def event_roster(client,event_id):
    """One request if hidden. No alternate participant route or schema/metadata probe."""
    b=BudgetClient(client);players={};count=0;event=None
    for page in range(1,MAX_PLAYERS//50+1):
        node=b.query(EVENT_ROSTER,dict(id=event_id,page=page)).get('event')
        if not isinstance(node,dict) or str(node.get('id'))!=str(event_id):raise APIError('event_unavailable')
        if node.get('type')!=1 or str((node.get('videogame') or {}).get('id'))!='1386':raise APIError('event_not_ultimate_singles')
        event={k:v for k,v in node.items() if k not in ('entrants','tournament')};t=node['tournament']
        if event_id==1687524 and (str(t['id'])!='942547' or t['countryCode']!='SV' or t['slug']!='tournament/legends7'):raise APIError('event_identity_changed')
        conn=node['entrants'];info=connection(conn)
        if page==1 and not conn['nodes'] and info['total']==0:return None
        for entrant in conn['nodes']:
            people=entrant.get('participants') or []
            if len(people)!=1 or not people[0].get('player'):raise APIError('registration_identity_unavailable')
            p=people[0]['player'];pid=str(p['id'])
            if not re.fullmatch('[1-9][0-9]*',pid) or pid in players:raise APIError('registration_identity_ambiguous')
            players[pid]=p;count+=1
        if page>=info['totalPages']:break
    if count!=info['total'] or count>MAX_PLAYERS or not count:raise APIError('registration_list_incomplete')
    return dict(schemaVersion=1,kind='analysis_roster',capturedAt=datetime.now(timezone.utc).isoformat(),
                event=event,tournament=t,players=players,source='entrants',registrations=count)


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
    start=clock();summary=dict(status='disabled',eventId=event_id,registered=None,known=None,added=0,pending=None,queries=0,seconds=0)
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
        reason=str(error) if isinstance(error,SyncStopped) and str(error) in SAFE_REASONS else 'analysis_automation_stopped_check_source_schema_queue_and_authorization'
        print(json.dumps(dict(ok=False,reason=reason)));return 1
if __name__=='__main__':sys.exit(main())
