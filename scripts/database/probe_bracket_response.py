"""Read-only bracket diagnosis. Only static categories, types, counts and timings."""
import json,os,re,sys,time,urllib.error,urllib.request,traceback
from pathlib import Path
from unittest import mock
import my_tournament_sync as sync

def main():
    original_open=urllib.request.urlopen;original_load=json.load;c=sync.Client(os.environ['STARTGG_TOKEN']);started=time.monotonic()
    def read(*args,**kw):
        payload=original_load(*args,**kw)
        if isinstance(payload,dict) and payload.get('errors'):
            categories=[]
            for e in payload['errors']:
                message=e.get('message','') if isinstance(e,dict) else '';category='graphql_other'
                if 'complexity' in message.lower():category='complexity'
                elif 'Syntax Error' in message:category='syntax'
                elif any(w in message for w in ('Cannot query field','Unknown argument','is not defined')):category='schema'
                categories.append(category)
            print(json.dumps(dict(query=c.calls,graphqlErrors=categories,dataType=type(payload.get('data')).__name__)))
        return payload
    def open_safe(*args,**kw):
        began=time.monotonic()
        try:return original_open(*args,**kw)
        except urllib.error.HTTPError as e:
            print(json.dumps(dict(query=c.calls,httpStatus=e.code,seconds=round(time.monotonic()-began,3))));raise
        except (urllib.error.URLError,TimeoutError):
            print(json.dumps(dict(query=c.calls,transport='timeout_or_unavailable',seconds=round(time.monotonic()-began,3))));raise
    try:
        with mock.patch('urllib.request.urlopen',side_effect=open_safe),mock.patch('json.load',side_effect=read):p=sync.capture(c,1687524)
        print(json.dumps(dict(status='validated_no_writes',queries=c.calls,groups=len(p['groups']),entrants=len(p['entrants']),sets=sum(len(g['sets']) for g in p['groups']),seconds=round(time.monotonic()-started,3))))
    except Exception as e:
        print(json.dumps(dict(status='probe_failed_no_writes',queries=c.calls,seconds=round(time.monotonic()-started,3),trace=[dict(file=Path(x.filename).name,function=x.name,line=x.lineno) for x in traceback.extract_tb(e.__traceback__)])));return 1
    return 0
if __name__=='__main__':raise SystemExit(main())
