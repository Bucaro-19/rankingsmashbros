"""Publica solo los archivos de Smash GT; sustituye cada archivo al terminar su subida."""
import argparse
import ftplib
import io
import json
import os
import re
import uuid
from pathlib import Path

FILES = ("feedback-data/.htaccess", "style.css", "arena.css", "metodologia.css", "encuesta.css", "opiniones.css", "analisis-torneos.css",
         "app.js", "metodologia.js", "analisis-torneos.js", ".htaccess", "encuesta.php", "opiniones.php", "index.html", "metodologia.html",
         "analisis-torneos.html", "data/analisis-torneos.json", "data/public.json")
HASH_PATTERN = re.compile(r"\$2y\$(?:10|11|12|13|14)\$[./0-9A-Za-z]{53}")


def validate_public_data(data):
    counts = data.get("counts") or {}
    players = data.get("players")
    events = data.get("events")
    if (data.get("schemaVersion") != 2 or data.get("status") != "international_pilot"
            or data.get("rankingComputed") is not True or not isinstance(players, list)
            or len(players) != 100 or counts.get("players") != 100
            or not isinstance(counts.get("events"), int) or counts["events"] < 1
            or not isinstance(counts.get("sets"), int) or counts["sets"] < 1
            or not isinstance(events, list) or len(events) != counts["events"]
            or not all(isinstance(event, dict) and isinstance(event.get("validSets"), int)
                       and event["validSets"] > 0 and isinstance(event.get("name"), str)
                       and isinstance(event.get("activePlayers"), int) for event in events)
            or sum(event["validSets"] for event in events) != counts["sets"]):
        raise ValueError("Se requiere un top 100 piloto completo con eventos internacionales antes de publicar.")


def validate_study_data(data):
    if (data.get("schemaVersion") != 1 or data.get("status") != "simulacion_sin_cambio_de_regla"
            or not isinstance(data.get("baselineVerifiedAsOf"), str)
            or not isinstance(data.get("smallEvents"), list) or not isinstance(data.get("scenarios"), dict)
            or not all(key in data["scenarios"] for key in ("pointsException", "min24", "min16"))):
        raise ValueError("Se requiere un estudio completo de torneos pequeños antes de publicar.")


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
