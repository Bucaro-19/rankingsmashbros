"""Publica solo los archivos de Smash GT; sustituye cada archivo al terminar su subida."""
import argparse
import ftplib
import io
import json
import os
import re
import uuid
from pathlib import Path
from collections import Counter, defaultdict

FILES = ("feedback-data/.htaccess", "style.css", "arena.css", "metodologia.css", "encuesta.css", "opiniones.css", "analisis-torneos.css",
         "app.js", "metodologia.js", "analisis-torneos.js", ".htaccess", "encuesta.php", "opiniones.php", "index.html", "metodologia.html",
         "analisis-torneos.html", "data/analisis-torneos.json", "analisis-top20.html", "analisis-top20.css",
         "analisis-top20.js", "data/analisis-top20.json", "data/public.json")
HASH_PATTERN = re.compile(r"\$2y\$(?:10|11|12|13|14)\$[./0-9A-Za-z]{53}")


def validate_public_data(data, *, local=False):
    counts = data.get("counts") or {}
    players = data.get("players")
    events = data.get("events")
    if (data.get("schemaVersion") != 2 or data.get("status") != ("local_pilot" if local else "international_pilot")
            or data.get("rankingComputed") is not True or not isinstance(players, list)
            or not players or counts.get("players") != len(players)
            or any(not isinstance(player, dict) or not isinstance(player.get("id"), str)
                   or player.get("rank") != index for index, player in enumerate(players, 1))
            or len({player["id"] for player in players}) != len(players)
            or (data.get("rankingCoverage") == "all_eligible" and
                (counts.get("eligiblePlayers") != len(players) or counts.get("top100") != min(100, len(players))))
            or not isinstance(counts.get("events"), int) or counts["events"] < 1
            or not isinstance(counts.get("sets"), int) or counts["sets"] < 1
            or not isinstance(events, list) or len(events) != counts["events"]
            or not all(isinstance(event, dict) and isinstance(event.get("validSets"), int)
                       and event["validSets"] > 0 and isinstance(event.get("name"), str)
                       and isinstance(event.get("activePlayers"), int) for event in events)
            or sum(event["validSets"] for event in events) != counts["sets"]):
        raise ValueError("Se requiere una clasificación coherente y completa con eventos internacionales antes de publicar.")


    validate_activity(data)
    if local and (data.get('rankingScope') != 'guatemala' or 'localRanking' in data
                  or any(e.get('country') != 'GT' for e in events)
                  or any(m.get('country') != 'GT' for m in data.get('results', []))):
        raise ValueError('La vista local solo puede contener eventos y sets de Guatemala.')
    if 'localRanking' in data:
        view = data['localRanking']
        if not isinstance(view, dict):
            raise ValueError('Vista local inválida.')
        validate_public_data(view, local=True)
        if (data.get('rankingScope') != 'combined'
                or any(view.get(k) != data.get(k) for k in ('generatedAt', 'seasonYear', 'seasonLabel', 'methodVersion', 'eligibilityRules'))
                or {e['id'] for e in view['events']} != {e['id'] for e in events if e.get('country') == 'GT'}):
            raise ValueError('Las dos vistas deben usar el mismo corte, reglas y eventos locales.')


def validate_activity(data):
    """Optional for legacy cuts; new ledgers must reconcile with published sets."""
    if not any('activity' in p for p in data['players']):
        return
    def require(condition):
        if not condition:
            raise ValueError("Actividad incoherente")

    try:
        events = {e['id']: e for e in data['events']}
        records = defaultdict(lambda: defaultdict(Counter))
        seen = set()
        for match in data['results']:
            require(match['id'] not in seen)
            seen.add(match['id'])
            require(match['eventId'] in events and len(match['playerIds']) == 2)
            require(len(set(match['playerIds'])) == 2)
            for pid, outcome in zip(match['playerIds'], ('wins', 'losses')):
                records[pid][match['eventId']][outcome] += 1
        for player in data['players']:
            activity = player['activity']
            ledger = activity['events']
            require(len(ledger) == player['events'] == len({e['id'] for e in ledger}))
            require({e['id'] for e in ledger} == set(records[player['id']]))
            for event in ledger:
                require(event['id'] in events)
                for outcome in ('wins', 'losses'):
                    require(type(event[outcome]) is int and event[outcome] >= 0)
                    require(event[outcome] == records[player['id']][event['id']][outcome])
            require(sum(e['wins'] for e in ledger) == player['wins'])
            require(sum(e['losses'] for e in ledger) == player['losses'])
            require(player['sets'] == player['wins'] + player['losses'])
            require(activity['months'] == sorted({events[e['id']]['date'][:7] for e in ledger}))
    except (KeyError, TypeError, ValueError):
        raise ValueError('La actividad debe coincidir con los torneos, sets y totales del jugador.') from None

def validate_study_data(data):
    if (data.get("schemaVersion") != 1 or data.get("status") != "simulacion_sin_cambio_de_regla"
            or not isinstance(data.get("baselineVerifiedAsOf"), str)
            or not isinstance(data.get("smallEvents"), list) or not isinstance(data.get("scenarios"), dict)
            or not all(key in data["scenarios"] for key in ("pointsException", "min24", "min16"))):
        raise ValueError("Se requiere un estudio completo de torneos pequeños antes de publicar.")


def validate_top20_study(data):
    def require(condition):
        if not condition:
            raise ValueError('Estudio inconsistente')

    try:
        count = data['counts']['players']
        require(data['schemaVersion'] == 1 and data['status'] == 'study_not_adopted')
        require(isinstance(data['cut'], str) and isinstance(count, int) and count >= 20)
        require(data['sensitivityEventCount'] == data['counts']['events'])
        base = data['scenarios']['none']['players']
        ids = {p['id'] for p in base}
        require(len(ids) == count)
        require([p['rank'] for p in data['profiles']] == list(range(1, 21)))
        require([p['id'] for p in data['profiles']] == [p['id'] for p in base[:20]])
        for name in ('none', 'events', 'months'):
            rows = data['scenarios'][name]['players']
            require(len(rows) == count and {p['id'] for p in rows} == ids)
            require([p['rank'] for p in rows] == list(range(1, count + 1)))
            require(all(0 <= p['bonus'] <= 30 and p['points'] == p['basePoints'] + p['bonus'] for p in rows))
        require(all(p['bonus'] == 0 and p['baseRank'] == p['rank'] for p in base))
        for p in data['profiles']:
            require(len(p['sensitivity']['scenarios']) == data['sensitivityEventCount'])
            require(sum(e['wins'] for e in p['eventLedger']) == p['wins'])
            require(sum(e['losses'] for e in p['eventLedger']) == p['losses'])
    except (KeyError, TypeError, ValueError):
        raise ValueError('El estudio del top 20 está incompleto o mezcla escenarios incompatibles.') from None


def deploy(ftp, source, *, assets_only=False, admin_hash=None):
    # FTP credentials must have the same root as the existing portfolio workflow.
    # No deletion or recursive synchronization of the site's root.
    try:
        ftp.cwd("ranking-smash-ultimate")
    except ftplib.error_perm as error:
        if not str(error).startswith("550"):
            raise
        ftp.mkd("ranking-smash-ultimate")
        ftp.cwd("ranking-smash-ultimate")
    try:
        ftp.cwd("data")
    except ftplib.error_perm as error:
        if not str(error).startswith("550"):
            raise
        ftp.mkd("data")
        ftp.cwd("data")
    ftp.cwd("..")
    try:
        ftp.cwd("feedback-data")
    except ftplib.error_perm as error:
        if not str(error).startswith("550"):
            raise
        ftp.mkd("feedback-data")
        ftp.cwd("feedback-data")
    if admin_hash:
        temporary = "admin-auth.php." + uuid.uuid4().hex + ".tmp"
        try:
            config = ("<?php\nreturn '" + admin_hash + "';\n").encode()
            ftp.storbinary("STOR " + temporary, io.BytesIO(config))
            ftp.rename(temporary, "admin-auth.php")
        except Exception:
            try:
                ftp.delete(temporary)
            except ftplib.all_errors:
                pass
            raise
    ftp.cwd("..")
    for name in FILES[:-1] if assets_only else FILES:
        temporary = name + "." + uuid.uuid4().hex + ".tmp"
        try:
            with (source / name).open("rb") as file:
                ftp.storbinary("STOR " + temporary, file)
            ftp.rename(temporary, name)
        except Exception:
            try:
                ftp.delete(temporary)
            except ftplib.all_errors:
                pass
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets-only", action="store_true", help="Publicar la página sin sustituir el corte de datos")
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[2] / "ranking-smash-ultimate"
    try:
        validate_study_data(json.loads((source / "data/analisis-torneos.json").read_text()))
        validate_top20_study(json.loads((source / "data/analisis-top20.json").read_text()))
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise SystemExit(str(error)) from None
    if not args.assets_only:
        data = json.loads((source / "data/public.json").read_text())
        try:
            validate_public_data(data)
        except ValueError as error:
            raise SystemExit(str(error)) from None
    for name in FILES[:-1] if args.assets_only else FILES:
        if not (source / name).is_file():
            raise SystemExit("Faltan archivos de publicación.")
    required = ("FTP_SERVER", "FTP_USERNAME", "FTP_PASSWORD")
    if not all(os.environ.get(name) for name in required):
        raise SystemExit("Faltan secretos de publicación.")
    admin_hash = os.environ.get("SMASH_FEEDBACK_ADMIN_HASH", "")
    if not HASH_PATTERN.fullmatch(admin_hash):
        raise SystemExit("Falta el hash de acceso al panel de opiniones o tiene un formato inválido.")
    phase = "conexión"
    try:
        # Match the FTP transport already used by the portfolio's working deploy.
        with ftplib.FTP(timeout=45) as ftp:
            ftp.connect(os.environ["FTP_SERVER"], 21)
            phase = "autenticación"
            ftp.login(os.environ["FTP_USERNAME"], os.environ["FTP_PASSWORD"])
            phase = "subida"
            deploy(ftp, source, assets_only=args.assets_only, admin_hash=admin_hash)
            ftp.quit()
    except (ftplib.Error, OSError, EOFError) as error:
        raise SystemExit(f"Publicación incompleta durante {phase}: {type(error).__name__}: {error}. No se eliminó el contenido anterior.") from None
    print("Smash GT publicado en su subcarpeta; " + ("corte de datos conservado." if args.assets_only else "datos reemplazados después de completar la subida."))


if __name__ == "__main__":
    main()
