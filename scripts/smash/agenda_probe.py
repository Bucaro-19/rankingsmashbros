"""Temporary read-only schema probe, no people, FTP, SQL, or publication."""
import json
import os
from pathlib import Path
from collect import Client
import io
import urllib.request

# Only this schema probe exposes schema error text, with the token redacted.
original_open=urllib.request.urlopen
def diagnostic_open(*args,**kwargs):
    with original_open(*args,**kwargs) as response: body=response.read()
    payload=json.loads(body)
    if payload.get("errors"):
        print(json.dumps({"schemaErrors":[str(e.get("message", "unknown"))[:1000].replace(os.environ["STARTGG_TOKEN"],"[redacted]") for e in payload["errors"]]}))
    return io.BytesIO(body)
urllib.request.urlopen=diagnostic_open

TYPE = 'kind name ofType { kind name ofType { kind name ofType { kind name } } }'
client=Client(os.environ['STARTGG_TOKEN'])
query='query AgendaSchema {'
for name in ('Tournament','Event','Query','TournamentQuery','EventFilter'):
 query+=name+':__type(name:"'+name+'"){name kind fields{name description type{'+TYPE+'} args{name type{'+TYPE+'}}} inputFields{name type{'+TYPE+'}} enumValues{name description}} '
query+='}'
data=client.query(query,{})
out=Path('scripts/smash/data/agenda-schema.json');out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(data,indent=2))
print(json.dumps({'requests':client.calls,'typesFound':[k for k,v in data.items() if v is not None]}))
