"""One read-only source request; logs only allowlisted types/presence, never values."""
import json
import os
import urllib.request
import urllib.error
from rival_automation import EVENT_ROSTER
from collect import ENDPOINT


def field(parent,key):
    present=isinstance(parent,dict) and key in parent
    value=parent.get(key) if present else None
    kind=('missing' if not present else 'null' if value is None else
          'boolean' if type(value) is bool else 'integer' if type(value) is int else
          'number' if type(value) is float else 'string' if isinstance(value,str) else
          'object' if isinstance(value,dict) else 'array' if isinstance(value,list) else 'other')
    return dict(present=present,type=kind)


def shape(payload):
    data=payload.get('data') if isinstance(payload,dict) else None
    event=data.get('event') if isinstance(data,dict) else None
    tournament=event.get('tournament') if isinstance(event,dict) else None
    entrants=event.get('entrants') if isinstance(event,dict) else None
    info=entrants.get('pageInfo') if isinstance(entrants,dict) else None
    nodes=entrants.get('nodes') if isinstance(entrants,dict) else None
    errors=payload.get('errors') if isinstance(payload,dict) else None
    return dict(data=field(payload,'data'),event=field(data,'event'),tournament=field(event,'tournament'),
        eventFields={key:field(event,key) for key in ('id','type','videogame')},
        tournamentFields={key:field(tournament,key) for key in ('id','countryCode','slug')},
        entrants=field(event,'entrants'),pageInfo=field(entrants,'pageInfo'),
        total=field(info,'total'),totalPages=field(info,'totalPages'),nodes=field(entrants,'nodes'),
        nodesEmpty=isinstance(nodes,list) and not nodes,
        errors=field(payload,'errors'),hasGraphQLErrors=bool(errors))


def main():
    queries=0
    try:
        token=os.environ.get('STARTGG_TOKEN','')
        if not token:raise ValueError('configuration')
        request=urllib.request.Request(ENDPOINT,data=json.dumps(dict(query=EVENT_ROSTER,variables=dict(id=1687524,page=1))).encode(),
            headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'},method='POST')
        queries=1
        with urllib.request.urlopen(request,timeout=30) as response:
            raw=response.read(2*1024*1024+1)
            if len(raw)>2*1024*1024:raise ValueError('size')
            payload=json.loads(raw)
            print(json.dumps(dict(queries=queries,httpStatus=response.status,shape=shape(payload))))
        return 0
    except Exception:
        print(json.dumps(dict(queries=queries,status='probe_failed',reason='source_probe_unavailable')));return 1


if __name__=='__main__':raise SystemExit(main())
