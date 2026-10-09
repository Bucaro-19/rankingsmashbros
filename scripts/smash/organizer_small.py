"""Optional private small-event context. Never mutate the national snapshot or query games.

Hard caps are a safety ceiling, not an approved production coverage policy. Weekly capture
stays disabled until the owner chooses the policy after reading the measured cost.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time

from collect import APIError, Client
from discover import TOURNAMENTS, fetch_event, season_timestamp, small_organizer_candidates

MAX_EVENTS = 10
MAX_ATTEMPTS = 30
MAX_SECONDS = 120


class BudgetClient:
    def __init__(self, client, clock=time.monotonic):
        self.client=client; self.initial=client.calls; self.clock=clock; self.started=clock()
    @property
    def calls(self):
        return self.client.calls
    def query(self, query, variables):
        # Client may retry up to three times. Reserve all three before starting a request.
        if self.client.calls-self.initial+3 > MAX_ATTEMPTS or self.clock()-self.started >= MAX_SECONDS:
            raise APIError('Límite del complemento de organizador; corte nacional intacto.')
        return self.client.query(query,variables)


def capture(client, national, *, limit=MAX_EVENTS, clock=time.monotonic):
    if type(limit) is not int or not 1 <= limit <= MAX_EVENTS:
        raise ValueError('Límite fuera del techo de captura pequeña.')
    candidates=national.get('organizerCandidates')
    if not isinstance(candidates,list): raise ValueError('Falta el catálogo separado de candidatos pequeños.')
    # Recheck the candidate criteria instead of trusting a resumed file's labels.
    tournaments=[dict(e['tournament'], isOnline=False, events=[e]) for e in candidates]
    selected=small_organizer_candidates(tournaments,national['season']['startInclusive'],national['season']['endExclusive'])
    if len(selected)!=len(candidates) or len({str(e['id']) for e in selected})!=len(selected):
        raise ValueError('Catálogo de candidatos inválido.')
    started=clock(); initial=client.calls; bounded=BudgetClient(client,clock)
    events=[];players={};sets={}
    for event in selected[:limit]:
        record,people,matches=fetch_event(bounded,event)
        if any(sid in sets for sid in matches): raise ValueError('Set duplicado en captura pequeña.')
        events.append(record);players.update(people);sets.update(matches)
    if clock()-started > MAX_SECONDS: raise APIError('Tiempo máximo del complemento excedido.')
    return dict(schemaVersion=1,kind='organizer_small_context',complete=True,
        nationalGeneratedAt=national['generatedAt'],season=national['season'],
        capturedAt=datetime.now(timezone.utc).isoformat(),candidateCount=len(selected),
        omittedEventIds=[str(e['id']) for e in selected[limit:]],events=events,players=players,sets=sets,
        requests=client.calls-initial,elapsedMilliseconds=round((clock()-started)*1000))


def probe_catalog(client,start,end):
    tournaments=[]
    for page in range(1,101):
        conn=client.query(TOURNAMENTS,dict(page=page,after=start,before=end))['tournaments']
        info=conn['pageInfo'];tournaments.extend(conn['nodes'])
        if page>=info['totalPages']: break
    if len(tournaments)!=info['total']: raise APIError('Catálogo de medición incompleto.')
    return dict(generatedAt=datetime.now(timezone.utc).isoformat(),season=dict(startInclusive=start,endExclusive=end),
                organizerCandidates=small_organizer_candidates(tournaments,start,end))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('national',type=Path,nargs='?')
    parser.add_argument('--output',type=Path,default=Path(__file__).parent/'data/organizer-small.json')
    parser.add_argument('--probe',action='store_true',help='Solo medir catálogo y muestra, sin publicar ni SQL')
    parser.add_argument('--start',default='2026-01-01'); parser.add_argument('--end')
    parser.add_argument('--limit',type=int,default=MAX_EVENTS)
    args=parser.parse_args()
    if args.national is not None and args.output.resolve()==args.national.resolve():
        parser.exit(1,'La salida de contexto no puede sustituir la captura nacional.\n')
    # Delete only our own old output: a failed optional capture must never reuse old context.
    args.output.unlink(missing_ok=True)
    client=Client(os.environ.get('STARTGG_TOKEN','').strip())
    if not client.token: parser.exit(1,'Falta token privado de start.gg.\n')
    started=time.monotonic()
    try:
        if args.probe:
            if not args.end: raise ValueError('Falta fecha final de medición.')
            national=probe_catalog(client,season_timestamp(args.start),season_timestamp(args.end))
        else:
            if args.national is None: raise ValueError('Falta captura nacional.')
            national=json.loads(args.national.read_text())
        catalog_calls=client.calls
        data=capture(client,national,limit=args.limit)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(data,ensure_ascii=False));args.output.chmod(0o600)
        print(json.dumps(dict(candidateEvents=data['candidateCount'],capturedEvents=len(data['events']),
            omittedEvents=len(data['omittedEventIds']),catalogRequests=catalog_calls,contextRequests=data['requests'],
            totalRequests=client.calls,sets=len(data['sets']),seconds=round(time.monotonic()-started,3),
            usualFullEstimateRequests=data['candidateCount']*3)))
    except (APIError,ValueError,KeyError,TypeError,OSError):
        parser.exit(1,'Captura pequeña omitida; no se modifica la captura nacional.\n')


if __name__=='__main__': main()
