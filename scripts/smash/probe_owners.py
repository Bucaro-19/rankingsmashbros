"""Temporary read-only event review. No SQL, FTP, files or participant lists."""
import json
import os
from collect import Client
from discover_abroad import USER_EVENTS

META="""query($id:ID!){event(id:$id){id name slug startAt numEntrants isOnline state type videogame{id name} tournament{id name slug countryCode isOnline startAt endAt}}}"""

def main():
    client=Client(os.environ['STARTGG_TOKEN'])
    for eid in (1737661,1687524):
        event=client.query(META,{'id':eid}).get('event')
        print(json.dumps({'event':event},ensure_ascii=False))
    person=client.query('query{player(id:184005){user{id}}}',{})
    uid=person['player']['user']['id']
    user=client.query(USER_EVENTS,{'id':uid,'page':1}).get('user') or {}
    events=(user.get('events') or {}).get('nodes') or []
    recent=[{'id':e['id'],'name':e['tournament']['name'],'slug':e['slug'],'state':e['state'],'isOnline':e['isOnline'],'type':e['type'],'numEntrants':e['numEntrants'],'startAt':e['startAt'],'country':e['tournament'].get('countryCode')} for e in events if e.get('startAt',0)>=1791670000]
    print(json.dumps({'recentEvents':recent,'queries':client.calls},ensure_ascii=False))

if __name__=='__main__':main()
