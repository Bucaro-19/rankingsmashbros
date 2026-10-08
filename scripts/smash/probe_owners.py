"""One-off check: does start.gg tell us who created each tournament of the published cut?

Read-only against start.gg. Prints aggregate counts only: no user, tournament or player
identifiers, so the public Actions log exposes nothing about any person.
"""
import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

from collect import APIError, Client

PUBLIC = Path(__file__).resolve().parents[2] / "ranking-smash-ultimate/data/public.json"
ULTIMATE = 1386


def tournament_slugs(public):
    slugs = []
    for event in public["events"]:
        match = re.fullmatch(r"https://www\.start\.gg/tournament/([a-z0-9-]+)/event/[a-z0-9-]+", event.get("url") or "")
        if match and match.group(1) not in slugs:
            slugs.append(match.group(1))
    return slugs


def main():
    token = os.environ.get("STARTGG_TOKEN")
    if not token:
        sys.exit("STARTGG_TOKEN is required")
    client = Client(token)
    public = json.loads(PUBLIC.read_text())
    slugs = tournament_slugs(public)
    owners, missing, failed = {}, 0, 0
    for slug in slugs:
        try:
            data = client.query("query($slug:String){tournament(slug:$slug){id owner{id}}}", {"slug": slug})
        except APIError:
            failed += 1
            continue
        tournament = data.get("tournament")
        owner = (tournament or {}).get("owner") or {}
        if tournament and owner.get("id") is not None:
            owners[str(tournament["id"])] = str(owner["id"])
        else:
            missing += 1
        time.sleep(0.8)
    counts = Counter(owners.values())
    summary = {"tournamentsInCut": len(slugs), "withOwner": len(owners), "withoutOwner": missing, "failedQueries": failed,
               "distinctOwners": len(counts), "tournamentsOfTopOwners": [n for _, n in counts.most_common(5)]}
    if counts:
        top, expected = counts.most_common(1)[0]
        season = int(time.mktime(time.strptime(f"{public['seasonYear']}-01-01", "%Y-%m-%d")))
        try:
            data = client.query(
                "query($owner:ID,$after:Timestamp,$games:[ID]){tournaments(query:{perPage:100,filter:{ownerId:$owner,afterDate:$after,videogameIds:$games}}){nodes{id}}}",
                {"owner": top, "after": season, "games": [ULTIMATE]})
            found = {str(node["id"]) for node in (data.get("tournaments") or {}).get("nodes") or []}
            mine = {tid for tid, owner in owners.items() if owner == top}
            summary["ownerFilter"] = {"returned": len(found), "cutTournamentsOfThatOwner": expected, "cutTournamentsFound": len(mine & found)}
        except APIError:
            summary["ownerFilter"] = "query_failed"
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
