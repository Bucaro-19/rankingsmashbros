"""Prueba de cobertura; no calcula ni imita puntuaciones de UltRank."""
import argparse
import getpass
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ENDPOINT = "https://api.start.gg/gql/alpha"
IDENTITY = "id gamerTag user { id slug location { country } }"
PROFILE = "query Profile($slug:String!){user(slug:$slug){player{" + IDENTITY + "}}}"
SETS = """query History($id:ID!, $page:Int!){
 player(id:$id){sets(page:$page,perPage:20,filters:{entrantSize:[1]}){
  pageInfo { totalPages }
  nodes { id state winnerId completedAt updatedAt displayScore
   event { id name slug startAt isOnline videogame { id name }
    tournament { id name countryCode } }
   slots { entrant { id participants { player { IDENTITY } } } }
  }
 }}
}""".replace("IDENTITY", IDENTITY)


class APIError(Exception):
    pass


class Client:
    def __init__(self, token):
        self.token = token
        self.calls = 0
        self.last_call = 0

    def query(self, query, variables):
        for attempt in range(3):
            # One process stays below 80 requests/minute; do not run collectors concurrently.
            time.sleep(max(0, 1 - (time.monotonic() - self.last_call)))
            self.last_call = time.monotonic()
            self.calls += 1
            req = urllib.request.Request(
                ENDPOINT, data=json.dumps({"query": query, "variables": variables}).encode(),
                headers={"Authorization": "Bearer " + self.token,
                         "Content-Type": "application/json"}, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=30) as response:
                    payload = json.load(response)
            except urllib.error.HTTPError as error:
                if error.code == 429 or error.code >= 500:
                    if attempt < 2:
                        time.sleep(5 * (attempt + 1))
                        continue
                raise APIError(f"start.gg respondió HTTP {error.code}; no se guardó una captura parcial.") from None
            except (urllib.error.URLError, TimeoutError, ValueError):
                raise APIError("No se pudo leer una respuesta válida de start.gg.") from None
            if payload.get("errors") or payload.get("success") is False:
                # Do not print raw responses or request credentials.
                raise APIError("start.gg rechazó la consulta. Revisar token, permisos y esquema vigente.")
            if not isinstance(payload.get("data"), dict):
                raise APIError("Respuesta sin datos; se conserva la captura anterior.")
            return payload["data"]
        raise APIError("No fue posible completar la consulta.")


def profile_slug(value):
    value = value.strip()
    if "://" in value:
        parsed = urlparse(value)
        if parsed.hostname not in {"start.gg", "www.start.gg"}:
            raise ValueError("El perfil debe pertenecer a start.gg.")
        value = parsed.path.strip("/")
    if not re.fullmatch(r"user/[A-Za-z0-9_-]+", value):
        raise ValueError("Usa el enlace del perfil con la forma https://www.start.gg/user/abc123.")
    return value


def country_candidate(player):
    country = ((player.get("user") or {}).get("location") or {}).get("country")
    if not country or not country.strip():
        return "unknown"
    return "GT_candidate" if country.strip().casefold() in {"gt", "guatemala"} else "other_country"


def participants(match):
    for slot in match.get("slots") or []:
        entrant = slot.get("entrant") or {}
        for participant in entrant.get("participants") or []:
            if participant.get("player"):
                yield participant["player"]


def season_timestamp(value):
    return int(datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


def collect(client, slugs, start, end, max_pages=10, max_opponents=20):
    players, matches, coverage = {}, {}, {}
    roots = []
    for slug in slugs:
        user = client.query(PROFILE, {"slug": profile_slug(slug)}).get("user")
        player = (user or {}).get("player")
        if not player or player.get("id") is None:
            raise APIError("Perfil no encontrado o sin jugador vinculado.")
        pid = str(player["id"])
        players[pid] = player
        if pid not in roots:
            roots.append(pid)

    def fetch_player(pid):
        total_pages = None
        for page in range(1, max_pages + 1):
            player = client.query(SETS, {"id": pid, "page": page}).get("player")
            connection = (player or {}).get("sets")
            if connection is None:
                raise APIError("Historial no disponible; no se interpreta como cero resultados.")
            total_pages = (connection.get("pageInfo") or {}).get("totalPages")
            if total_pages is None:
                raise APIError("Paginación incompleta; no se puede comprobar la cobertura.")
            for match in connection.get("nodes") or []:
                event = match.get("event") or {}
                # Season uses event start in UTC; no country restriction.
                started = event.get("startAt")
                if (event.get("videogame") or {}).get("name") != "Super Smash Bros. Ultimate":
                    continue
                if started is None or not start <= started < end:
                    continue
                if match.get("id") is None:
                    continue
                matches[str(match["id"])] = match
                for other in participants(match):
                    if other.get("id") is not None:
                        players[str(other["id"])] = other
            if page >= total_pages:
                break
        coverage[pid] = {"pagesFetched": page, "totalPages": total_pages,
                         "historyComplete": page >= total_pages}

    for pid in roots:
        fetch_player(pid)
    direct = sorted(set(players) - set(roots))
    for pid in direct[:max_opponents]:
        fetch_player(pid)
    for player in players.values():
        player["countryStatus"] = country_candidate(player)
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "kind": "coverage_probe", "rankingComputed": False,
        "season": {"startInclusive": start, "endExclusive": end, "basis": "event.startAt UTC"},
        "rootPlayerIds": roots, "players": players, "sets": matches,
        "coverage": coverage, "requests": client.calls,
        "directOpponents": len(direct), "directOpponentsFetched": min(len(direct), max_opponents),
        "unfetchedDirectOpponents": direct[max_opponents:],
        "contextPlayerIdsWithoutHistory": sorted(set(players) - set(coverage)),
        "methodologyStatus": "Exact UltRank implementation and eligibility rules not validated",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profiles", nargs="+", help="Enlaces públicos o user/slug")
    parser.add_argument("--start", required=True, help="Inicio inclusivo YYYY-MM-DD UTC")
    parser.add_argument("--end", required=True, help="Fin exclusivo YYYY-MM-DD UTC")
    parser.add_argument("--max-pages", type=int, default=10)
    parser.add_argument("--max-opponents", type=int, default=20)
    args = parser.parse_args()
    try:
        start, end = season_timestamp(args.start), season_timestamp(args.end)
        if start >= end or args.max_pages < 1 or args.max_opponents < 0:
            raise ValueError("Fechas o límites inválidos.")
        slugs = [profile_slug(value) for value in args.profiles]
        token = os.environ.get("STARTGG_TOKEN") or getpass.getpass("Token start.gg (entrada oculta): ")
        if not token.strip():
            raise ValueError("Se requiere un token de start.gg.")
        snapshot = collect(Client(token.strip()), slugs, start, end, args.max_pages, args.max_opponents)
        target = Path(__file__).parent / "data" / "coverage.json"
        target.parent.mkdir(exist_ok=True)
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False))
        temporary.replace(target)
        print(f"Captura guardada: {target}")
        print(f"{len(snapshot['sets'])} sets únicos; {len(snapshot['players'])} jugadores; {snapshot['requests']} consultas.")
        incomplete = sum(not c["historyComplete"] for c in snapshot["coverage"].values())
        print(f"Historiales recortados: {incomplete}; rivales directos sin consultar: {len(snapshot['unfetchedDirectOpponents'])}.")
        print("Prueba de cobertura. No contiene posiciones ni puntuaciones de ranking.")
    except (ValueError, APIError) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
