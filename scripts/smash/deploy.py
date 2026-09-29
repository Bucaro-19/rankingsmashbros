"""Publica solo los archivos de Smash GT; sustituye cada archivo al terminar su subida."""
import ftplib
import json
import os
import uuid
from pathlib import Path

FILES = ("feedback-data/.htaccess", "style.css", "arena.css", "metodologia.css", "encuesta.css",
         "app.js", "metodologia.js", ".htaccess", "encuesta.php", "index.html", "metodologia.html", "data/public.json")


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


def deploy(ftp, source):
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
    ftp.cwd("..")
    for name in FILES:
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
    source = Path(__file__).resolve().parents[2] / "ranking-smash-ultimate"
    data = json.loads((source / "data/public.json").read_text())
    try:
        validate_public_data(data)
    except ValueError as error:
        raise SystemExit(str(error)) from None
    for name in FILES:
        if not (source / name).is_file():
            raise SystemExit("Faltan archivos de publicación.")
    required = ("FTP_SERVER", "FTP_USERNAME", "FTP_PASSWORD")
    if not all(os.environ.get(name) for name in required):
        raise SystemExit("Faltan secretos de publicación.")
    phase = "conexión"
    try:
        # Match the FTP transport already used by the portfolio's working deploy.
        with ftplib.FTP(timeout=45) as ftp:
            ftp.connect(os.environ["FTP_SERVER"], 21)
            phase = "autenticación"
            ftp.login(os.environ["FTP_USERNAME"], os.environ["FTP_PASSWORD"])
            phase = "subida"
            deploy(ftp, source)
            ftp.quit()
    except (ftplib.Error, OSError, EOFError) as error:
        raise SystemExit(f"Publicación incompleta durante {phase}: {type(error).__name__}: {error}. No se eliminó el contenido anterior.") from None
    print("Smash GT publicado en su subcarpeta; datos reemplazados después de completar la subida.")


if __name__ == "__main__":
    main()
