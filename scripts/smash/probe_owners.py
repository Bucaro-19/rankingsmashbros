"""One-off check: does the weekly capture's optional owner query work against start.gg?

Read-only. Runs exactly the query the capture uses and prints aggregate counts only: no user,
tournament or player identifiers, so the public Actions log exposes nothing about any person.
"""
import json
import os
import sys
import time
from collections import Counter

from collect import Client
from discover import season_timestamp, tournament_owners


def main():
    token = os.environ.get("STARTGG_TOKEN")
    if not token:
        sys.exit("STARTGG_TOKEN is required")
    client = Client(token)
    year = time.gmtime().tm_year
    owners = tournament_owners(client, season_timestamp(f"{year}-01-01"), season_timestamp(f"{year + 1}-01-01"))
    if owners is None:
        print(json.dumps({"ownerQuery": "failed", "requests": client.calls}))
        sys.exit(1)
    counts = Counter(row["ownerId"] for row in owners.values() if row["ownerId"])
    print(json.dumps({"ownerQuery": "ok", "requests": client.calls, "tournaments": len(owners),
                      "withOwner": sum(counts.values()), "withCity": sum(bool(row["city"]) for row in owners.values()),
                      "distinctOwners": len(counts), "tournamentsOfTopOwners": [n for _, n in counts.most_common(5)]}))


if __name__ == "__main__":
    main()
