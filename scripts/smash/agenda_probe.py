"""Temporary read-only schema probe, no people, FTP, SQL, or publication."""
import json
import os
from pathlib import Path
from collect import Client

TYPE = 'kind name ofType { kind name ofType { kind name ofType { kind name } } }'
client=Client(os.environ['STARTGG_TOKEN'])
query='query AgendaSchema {'
for name in ('Tournament','Event','Query','TournamentQuery','TournamentFilter','TournamentQueryFilter','EventFilter','EventType'):
 query+=name+':__type(name:"'+name+'"){name kind fields{name type{'+TYPE+'} args{name type{'+TYPE+'}}} inputFields{name type{'+TYPE+'}} enumValues{name description}} '
query+='}'
data=client.query(query,{})
out=Path('scripts/smash/data/agenda-schema.json');out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(data,indent=2))
print(json.dumps({'requests':client.calls,'typesFound':[k for k,v in data.items() if v is not None]}))
